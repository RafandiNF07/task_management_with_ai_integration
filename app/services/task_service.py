import uuid
import os
import aiofiles
from datetime import datetime
from sqlmodel import select
from sqlalchemy import delete
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

import uuid

from app.models.domain import Task, SubTask, ActivityLog, TaskStatus, ProjectMember, RoleEnum
from app.core.database import engine, AsyncSessionLocal
from app.core.config import settings
from app.schemas.task_schema import TaskAIResponse

# ─── Lazy singleton agar tidak crash saat import tanpa .env (e.g. pytest) ───
_ai_service = None

def get_ai_service():
    global _ai_service
    if _ai_service is None:
        from app.services.ai_service import AIService
        _ai_service = AIService()
    return _ai_service


class TaskService:
    @staticmethod
    async def create_task_from_ai(
        db: AsyncSession,
        ai_result: TaskAIResponse,
        raw_content: str,
        project_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Task:
        return await TaskService.upsert_task_from_ai(
            db=db,
            ai_result=ai_result,
            raw_content=raw_content,
            project_id=project_id,
            user_id=user_id,
        )

    @staticmethod
    async def upsert_task_from_ai(
        db: AsyncSession,
        ai_result: TaskAIResponse,
        raw_content: str,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        deadline: datetime | None = None,
        task_id: uuid.UUID | None = None,
    ) -> Task:
        is_update = task_id is not None

        if is_update:
            stmt = select(Task).where(Task.id == task_id)
            result = await db.exec(stmt)
            task = result.first()

            if not task:
                raise HTTPException(status_code=404, detail="Task tidak ditemukan")

            if task.project_id != project_id:
                raise HTTPException(status_code=400, detail="Task tidak sesuai dengan project ini")

            task.title = ai_result.task_title
            task.raw_content = raw_content
            task.is_published = False
            if deadline is not None:
                task.deadline = deadline

            await db.exec(delete(SubTask).where(SubTask.task_id == task.id))
            log_action = "TASKS_UPDATED_FROM_INSTRUCTIONS"
            log_details = f"Task '{task.title}' diperbarui dari instruksi terbaru"
        else:
            task = Task(
                title=ai_result.task_title,
                raw_content=raw_content,
                deadline=deadline,
                is_published=False,
                project_id=project_id,
            )
            db.add(task)
            await db.flush()
            log_action = "TASKS_DRAFT_CREATED"
            log_details = f"AI berhasil memecah tugas menjadi draft: {task.title}"

        if is_update:
            db.add(task)
            await db.flush()

        for sub in ai_result.subtasks:
            new_sub = SubTask(
                title=sub.title,
                description=sub.description,
                task_id=task.id,
            )
            db.add(new_sub)

        if deadline is not None:
            log_details = f"{log_details} (deadline: {deadline.isoformat()})"

        log = ActivityLog(
            action=log_action,
            details=log_details,
            user_id=user_id,
            project_id=project_id,
        )
        db.add(log)

        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def publish_task(
        db: AsyncSession,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Task:
        stmt = select(Task).where(Task.id == task_id)
        result = await db.exec(stmt)
        task = result.first()

        if not task:
            raise HTTPException(status_code=404, detail="Task tidak ditemukan")

        task.is_published = True
        db.add(task)
        db.add(
            ActivityLog(
                action="TASKS_PUBLISHED",
                details=f"Task '{task.title}' dipublish ke anggota proyek",
                user_id=user_id,
                project_id=task.project_id,
            )
        )

        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def get_task_with_subtasks(db: AsyncSession, task_id: uuid.UUID):
        stmt = select(Task).where(Task.id == task_id)
        result = await db.exec(stmt)
        task = result.first()

        if not task:
            raise HTTPException(status_code=404, detail="Tugas tidak ditemukan")

        sub_stmt = select(SubTask).where(SubTask.task_id == task_id)
        sub_result = await db.exec(sub_stmt)
        subtasks = sub_result.all()

        return {"task": task, "subtasks": subtasks}

    @staticmethod
    async def get_subtask(db: AsyncSession, subtask_id: uuid.UUID):
        stmt = select(SubTask).where(SubTask.id == subtask_id).options(selectinload(SubTask.task))  # type: ignore[arg-type]
        result = await db.exec(stmt)
        return result.first()

    @staticmethod
    async def claim_subtask(
        db: AsyncSession,
        subtask_id: uuid.UUID,
        current_user_id: uuid.UUID
    ):
        subtask = await TaskService.get_subtask(db, subtask_id)

        if not subtask:
            raise HTTPException(status_code=404, detail="Subtask tidak ditemukan")

        if subtask.status != TaskStatus.TODO:
            raise HTTPException(status_code=400, detail="Subtask hanya bisa di-claim dari status TODO")

        subtask.assigned_to_id = current_user_id
        subtask.status = TaskStatus.IN_PROGRESS

        db.add(subtask)
        db.add(
            ActivityLog(
                action="TASK_CLAIMED",
                details=f"Subtask '{subtask.title}' di-claim oleh user {current_user_id}",
                user_id=current_user_id,
                project_id=subtask.task.project_id if subtask.task else None,
            )
        )

        await db.commit()
        await db.refresh(subtask)
        return subtask

    @staticmethod
    async def assign_subtask(
        db: AsyncSession,
        subtask_id: uuid.UUID,
        user_id: uuid.UUID,
        current_user_id: uuid.UUID
    ):
        subtask = await TaskService.get_subtask(db, subtask_id)

        if not subtask:
            raise HTTPException(status_code=404, detail="Subtask tidak ditemukan")

        if subtask.task is None:
            raise HTTPException(status_code=400, detail="Subtask tidak terhubung ke project")

        if user_id == current_user_id:
            raise HTTPException(status_code=400, detail="Assign harus ke member lain, bukan diri sendiri")

        current_membership_stmt = select(ProjectMember).where(
            ProjectMember.project_id == subtask.task.project_id,
            ProjectMember.user_id == current_user_id,
        )
        current_membership_result = await db.exec(current_membership_stmt)
        current_membership = current_membership_result.first()

        if not current_membership:
            raise HTTPException(status_code=403, detail="Anda bukan anggota project ini")

        if current_membership.role not in {RoleEnum.LEADER, RoleEnum.ASSISTANT}:
            raise HTTPException(status_code=403, detail="Hanya Leader atau Asisten yang dapat mengassign subtask")

        target_membership_stmt = select(ProjectMember).where(
            ProjectMember.project_id == subtask.task.project_id,
            ProjectMember.user_id == user_id,
        )
        target_membership_result = await db.exec(target_membership_stmt)
        target_membership = target_membership_result.first()

        if not target_membership:
            raise HTTPException(status_code=404, detail="Target user bukan member project ini")

        if subtask.status != TaskStatus.TODO:
            raise HTTPException(status_code=400, detail="Subtask hanya bisa di-assign dari status TODO")

        subtask.assigned_to_id = user_id
        subtask.status = TaskStatus.IN_PROGRESS

        db.add(subtask)
        db.add(
            ActivityLog(
                action="TASK_ASSIGNED",
                details=f"Subtask '{subtask.title}' di-assign ke user {user_id} oleh user {current_user_id}",
                user_id=current_user_id,
                project_id=subtask.task.project_id,
            )
        )

        await db.commit()
        await db.refresh(subtask)
        return subtask

    @staticmethod
    async def start_audit_process(
        db: AsyncSession,
        subtask_id: uuid.UUID,
        file_bytes: bytes
    ):
        stmt = select(SubTask).where(SubTask.id == subtask_id)
        result = await db.exec(stmt)
        subtask = result.first()

        if not subtask:
            raise HTTPException(status_code=404, detail="Subtask tidak ditemukan")

        # ✅ Gunakan aiofiles agar tidak blocking event loop
        os.makedirs("uploads", exist_ok=True)
        file_path = f"uploads/{subtask_id}.png"
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_bytes)

        subtask.evidence_url = file_path
        subtask.status = TaskStatus.PENDING_AI_REVIEW

        db.add(subtask)
        await db.commit()
        await db.refresh(subtask)

        return subtask

    @staticmethod
    async def process_background_audit(
        subtask_id: uuid.UUID,
        subtask_desc: str,
        image_bytes: bytes
    ):
        """Background task: panggil AI lalu update database dengan session sendiri."""
        # ✅ Gunakan AsyncSessionLocal yang sudah dibuat di database.py
        async with AsyncSessionLocal() as db:
            try:
                # Pastikan subtask_id adalah objek UUID, bukan string (penting untuk SQLite)
                if isinstance(subtask_id, str):
                    subtask_id = uuid.UUID(subtask_id)

                audit_result = await get_ai_service().audit_evidence(subtask_desc, image_bytes)

                stmt = select(SubTask).where(SubTask.id == subtask_id).options(selectinload(SubTask.task))  # type: ignore[arg-type]
                result = await db.exec(stmt)
                subtask = result.first()
                if not subtask:
                    return

                # Configurable auto-approve threshold
                threshold = getattr(settings, "AI_AUTO_APPROVE_CONFIDENCE", 85)

                if audit_result["is_valid"]:
                    # If confidence is high enough, auto-complete the subtask
                    if audit_result.get("confidence_score", 0) >= threshold:
                        subtask.status = TaskStatus.DONE
                        subtask.ai_rejection_reason = None
                        # Mark approved_by_id with system sentinel to indicate auto-approval
                        try:
                            subtask.approved_by_id = uuid.UUID(
                                settings.AI_AUTO_APPROVE_SYSTEM_USER_ID
                            )
                        except Exception:
                            subtask.approved_by_id = None
                        log_action = "TASK_AUTO_APPROVED_BY_AI"
                    else:
                        # AI thinks it's valid but confidence is not high — send to human QC
                        subtask.status = TaskStatus.PENDING_HUMAN_QC
                        subtask.ai_rejection_reason = None
                        log_action = "TASK_APPROVED_BY_AI_LOW_CONFIDENCE"
                else:
                    subtask.status = TaskStatus.REJECTED_BY_AI
                    subtask.ai_rejection_reason = audit_result.get("feedback")
                    log_action = "TASK_REJECTED_BY_AI"

                if subtask.assigned_to_id is not None:
                    db.add(
                        ActivityLog(
                            action=log_action,
                            details=audit_result["feedback"],
                            user_id=subtask.assigned_to_id,
                            project_id=subtask.task.project_id if subtask.task else None,
                        )
                    )

                db.add(subtask)
                await db.commit()

            except Exception as e:
                print(f"[BG AUDIT ERROR] subtask_id={subtask_id}: {e}")
