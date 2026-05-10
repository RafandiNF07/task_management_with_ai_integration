# app/api/v1/projects.py
from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select # <-- TAMBAHKAN IMPORT INI
import uuid
from sqlalchemy import func

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_project_leader
from app.models.domain import User, ProjectMember, Task, SubTask, Project # <-- TAMBAHKAN IMPORT MODEL
from app.schemas.project_schema import ProjectCreate, ProjectResponse, MemberInvite
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.post("/", response_model=ProjectResponse)
async def create_new_project(
    data: ProjectCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await ProjectService.create_project(db, data.name, current_user.id)

@router.post("/{project_id}/members")
async def invite_member(
    project_id: uuid.UUID,
    data: MemberInvite,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await ProjectService.add_member(db, project_id, data.username, data.role, current_user.id)

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
    subtask_query = select(SubTask).where(
        SubTask.task_id.in_(
            select(Task.id).where(Task.project_id == project_id)
        )
    )
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

    return {
        "project_name": project_name,
        "progress_percentage": round(progress, 2),
        "summary": {
            "total_subtasks": total_tasks,
            "completed": stats["DONE"],
            "failed_audit": stats["REJECTED_BY_AI"] + stats["REJECTED_BY_HUMAN"],
            # Masukkan semua yang butuh review ke dalam under_review
            "under_review": stats["PENDING_AI_REVIEW"] + stats["APPEAL_PENDING"] + stats["PENDING_HUMAN_QC"] 
        },
        "breakdown": stats
    }