# app/api/v1/projects.py
from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select # <-- TAMBAHKAN IMPORT INI
import uuid
from sqlalchemy import func

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_project_leader
from app.models.domain import User, ProjectMember, Task, SubTask, Project # <-- TAMBAHKAN IMPORT MODEL
from app.schemas.project_schema import ProjectCreate, ProjectResponse, MemberInvite, MemberRoleUpdate
from app.services.project_service import ProjectService
from datetime import datetime, timezone
from sqlalchemy.orm import selectinload
from app.models.domain import TaskStatus

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.post("/", response_model=ProjectResponse)
async def create_new_project(
    data: ProjectCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Membuat proyek baru. User yang membuat akan otomatis menjadi Leader."""
    return await ProjectService.create_project(db, data.name, current_user.id)

@router.post("/{project_id}/members")
async def invite_member(
    project_id: uuid.UUID,
    data: MemberInvite,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    leader_access: ProjectMember = Depends(get_current_project_leader)
):
    """Mengundang anggota ke proyek dengan role tertentu. Hanya Leader yang dapat mengundang."""
    return await ProjectService.add_member(db, project_id, data.username, data.role, current_user.id)

@router.patch("/{project_id}/members/{user_id}/role")
async def update_member_role(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    data: MemberRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    leader_access: ProjectMember = Depends(get_current_project_leader),
):
    """Mengubah role member di project. Hanya Leader yang dapat mengubah role."""
    return await ProjectService.update_member_role(db, project_id, user_id, data.role, current_user.id)

@router.get("/{project_id}/dashboard")
async def get_project_dashboard(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    # RBAC: Hanya leader yang bisa lewat sini
    leader_access: ProjectMember = Depends(get_current_project_leader) 
):
    """Statistik Proyek: Hanya dapat diakses oleh Leader Proyek."""
    
    # Ambil nama proyek (Mencegah MissingGreenlet error)
    project = await db.get(Project, project_id)
    project_name = project.name if project else "Project Statistics"

    # 1. Query untuk mendapatkan semua subtasks di bawah proyek ini
    subtask_query = select(SubTask).join(Task).where(Task.project_id == project_id)
    result = await db.exec(subtask_query)
    all_subtasks = result.all()

    total_tasks = len(all_subtasks)
    
    # 2. Menghitung statistik berdasarkan 8 STATUS LENGKAP
    stats = {
        "TODO": 0,
        "IN_PROGRESS": 0,
        "PENDING_AI_REVIEW": 0,  # <-- Ditambahkan
        "REJECTED_BY_AI": 0,
        "APPEAL_PENDING": 0,
        "PENDING_HUMAN_QC": 0,   # <-- Ditambahkan
        "REJECTED_BY_HUMAN": 0,
        "DONE": 0
    }

    # Distribusikan perhitungan
    for st in all_subtasks:
        # Pengecekan aman, memastikan status ada di dictionary
        if st.status in stats:
            stats[st.status] += 1

    # 3. Kalkulasi Persentase Selesai
    progress = (stats["DONE"] / total_tasks * 100) if total_tasks > 0 else 0

    # 4. Hitung overdue berdasarkan deadline pada Task (jika ada)
    overdue = 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for st in all_subtasks:
        # subtasks inherit task.deadline
        if st.task and getattr(st.task, "deadline", None):
            due = st.task.deadline
            if due and due < now and st.status != "DONE":
                overdue += 1

    return {
        "project_name": project_name,
        "progress_percentage": round(progress, 2),
        "summary": {
            "total_subtasks": total_tasks,
            "completed": stats["DONE"],
            "failed_audit": stats["REJECTED_BY_AI"] + stats["REJECTED_BY_HUMAN"],
            # Masukkan semua yang butuh review ke dalam under_review
            "under_review": stats["PENDING_AI_REVIEW"] + stats["APPEAL_PENDING"] + stats["PENDING_HUMAN_QC"],
            "overdue_subtasks": overdue,
        },
        "breakdown": stats,
    }


@router.get("/{project_id}/kanban")
async def get_project_kanban(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Kanban view: subtasks grouped per status with due date and overdue flag."""
    # Ensure requester is member
    membership_stmt = select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.id,
    )
    membership_res = await db.exec(membership_stmt)
    if not membership_res.first():
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Anda bukan anggota proyek ini")

    # Fetch all subtasks with task preloaded
    stmt = select(SubTask).join(Task).where(Task.project_id == project_id).options(selectinload(SubTask.task))  # type: ignore[arg-type]
    res = await db.exec(stmt)
    subtasks = res.all()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    columns = []
    for status in [s.value for s in TaskStatus]:
        items = []
        for st in subtasks:
            if st.status == status:
                due = st.task.deadline if st.task else None
                is_overdue = False
                if due and due < now and st.status != TaskStatus.DONE:
                    is_overdue = True

                items.append({
                    "id": str(st.id),
                    "title": st.title,
                    "description": st.description,
                    "assigned_to": str(st.assigned_to_id) if st.assigned_to_id else None,
                    "due_date": due.isoformat() if due else None,
                    "is_overdue": is_overdue,
                    "status": st.status,
                })

        columns.append({
            "status": status,
            "count": len(items),
            "subtasks": items,
        })

    return {"project_id": project_id, "columns": columns}