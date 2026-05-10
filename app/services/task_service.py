import uuid
import os
import aiofiles
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.models.domain import Task, SubTask, ActivityLog, TaskStatus
from app.core.database import engine, AsyncSessionLocal
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
        new_task = Task(
            title=ai_result.task_title,
            raw_content=raw_content,
            project_id=project_id
        )
        db.add(new_task)
        await db.flush()

        for sub in ai_result.subtasks:
            new_sub = SubTask(
                title=sub.title,
                description=sub.description,
                task_id=new_task.id
            )
            db.add(new_sub)

        log = ActivityLog(
            action="TASKS_PUBLISHED",
            details=f"AI berhasil memecah tugas: {new_task.title}",
            user_id=user_id,
            project_id=project_id
        )
        db.add(log)

        await db.commit()
        await db.refresh(new_task)
        return new_task

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
    async def assign_subtask(
        db: AsyncSession,
        subtask_id: uuid.UUID,
        user_id: uuid.UUID,
        current_user_id: uuid.UUID
    ):
        stmt = (
            select(SubTask)
            .where(SubTask.id == subtask_id)
            .options(selectinload(SubTask.task))  # type: ignore[arg-type]
        )
        result = await db.exec(stmt)
        subtask = result.first()

        if not subtask:
            raise HTTPException(status_code=404, detail="Subtask tidak ditemukan")

        subtask.assigned_to_id = user_id
        subtask.status = TaskStatus.IN_PROGRESS

        project_id = subtask.task.project_id if subtask.task else None

        log = ActivityLog(
            action="TASK_ASSIGNED",
            details=f"Subtask '{subtask.title}' ditugaskan ke User ID {user_id}",
            user_id=current_user_id,
            project_id=project_id
        )

        db.add(subtask)
        db.add(log)

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
                audit_result = await get_ai_service().audit_evidence(subtask_desc, image_bytes)

                stmt = select(SubTask).where(SubTask.id == subtask_id)
                result = await db.exec(stmt)
                subtask = result.first()
                if not subtask:
                    return

                if audit_result["is_valid"] and audit_result["confidence_score"] >= 70:
                    subtask.status = TaskStatus.PENDING_HUMAN_QC
                    subtask.ai_rejection_reason = None
                else:
                    subtask.status = TaskStatus.REJECTED_BY_AI
                    subtask.ai_rejection_reason = audit_result["feedback"]

                db.add(subtask)
                await db.commit()

            except Exception as e:
                print(f"[BG AUDIT ERROR] subtask_id={subtask_id}: {e}")
