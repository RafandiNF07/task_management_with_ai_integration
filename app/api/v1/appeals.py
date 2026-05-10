from fastapi import APIRouter, Depends, HTTPException
import uuid
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.core.database import get_db
from app.api.deps import get_current_user, get_project_membership
from app.models.domain import User, SubTask, ActivityLog, TaskStatus, RoleEnum, Task
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/appeals", tags=["Appeals"])

@router.patch("/{subtask_id}/appeal")
async def appeal_subtask(
    subtask_id: uuid.UUID,
    reason: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mahasiswa melakukan banding terhadap hasil audit AI."""
    stmt = select(SubTask).where(SubTask.id == subtask_id).options(selectinload(SubTask.task))  # type: ignore[arg-type]
    result = await db.exec(stmt)
    subtask = result.first()

    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask tidak ditemukan")

    if subtask.status != TaskStatus.REJECTED_BY_AI:
        raise HTTPException(
            status_code=400, 
            detail="Hanya tugas yang ditolak AI yang bisa diajukan banding."
        )

    if subtask.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Hanya anggota yang mengerjakan subtask ini yang dapat mengajukan banding")

    subtask.status = TaskStatus.APPEAL_PENDING
    subtask.appeal_reason = reason
    
    log = ActivityLog(
        action="TASK_APPEALED",
        details=f"User {current_user.username} mengajukan banding: {reason}",
        user_id=current_user.id,
        project_id=subtask.task.project_id if subtask.task else None
    )

    db.add(subtask)
    db.add(log)
    await db.commit()
    
    return {
        "message": "Banding berhasil diajukan. Menunggu tinjauan manual Leader/QC.",
        "status": subtask.status
    }

@router.get("/projects/{project_id}/queue")
async def get_appeal_queue(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mendapatkan antrian banding yang menunggu keputusan Leader/QC. Hanya Leader/QC yang dapat mengakses."""
    membership = await get_project_membership(project_id, current_user, db)
    if membership.role not in {RoleEnum.LEADER, RoleEnum.QC}:
        raise HTTPException(status_code=403, detail="Hanya Leader atau QC yang dapat mengakses antrian banding")

    stmt = (
        select(SubTask)
        .join(Task)
        .where(Task.project_id == project_id)
        .where(SubTask.status == TaskStatus.APPEAL_PENDING)
    )
    result = await db.exec(stmt)
    subtasks = result.all()

    return {
        "project_id": project_id,
        "items": [
            {
                "id": subtask.id,
                "title": subtask.title,
                "description": subtask.description,
                "evidence_url": subtask.evidence_url,
                "ai_rejection_reason": subtask.ai_rejection_reason,
                "appeal_reason": subtask.appeal_reason,
            }
            for subtask in subtasks
        ],
    }

@router.patch("/{subtask_id}/leader-decision")
async def leader_decision(
    subtask_id: uuid.UUID,
    is_approved: bool,
    reason: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fungsi bagi Leader/Dosen untuk memberikan keputusan final manual."""
    stmt = select(SubTask).where(SubTask.id == subtask_id).options(selectinload(SubTask.task))  # type: ignore[arg-type]
    result = await db.exec(stmt)
    subtask = result.first()

    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask tidak ditemukan")

    if subtask.task is None:
        raise HTTPException(status_code=400, detail="Subtask tidak terhubung ke project")

    membership = await get_project_membership(subtask.task.project_id, current_user, db)
    if membership.role not in {RoleEnum.LEADER, RoleEnum.QC}:
        raise HTTPException(status_code=403, detail="Hanya Leader atau QC yang dapat memberi keputusan final")

    if subtask.status not in {TaskStatus.APPEAL_PENDING, TaskStatus.PENDING_HUMAN_QC}:
        raise HTTPException(status_code=400, detail="Keputusan final hanya bisa diberikan pada subtask yang menunggu review human")

    if not is_approved and not reason:
        raise HTTPException(status_code=400, detail="Alasan penolakan wajib diisi")

    # Flow "Jika Reject: Status balik ke TODO untuk dikerjakan ulang."
    if is_approved:
        subtask.status = TaskStatus.DONE
        subtask.approved_by_id = current_user.id
        subtask.human_rejection_reason = None
        action_log = "APPEAL_APPROVED"
        detail_log = f"Banding diterima oleh {current_user.username}"
    else:
        subtask.status = TaskStatus.TODO
        subtask.human_rejection_reason = reason
        subtask.approved_by_id = None
        action_log = "APPEAL_REJECTED"
        detail_log = f"Banding ditolak oleh {current_user.username}: {reason}"

    log = ActivityLog(
        action=action_log,
        details=detail_log,
        user_id=current_user.id,
        project_id=subtask.task.project_id if subtask.task else None
    )

    db.add(subtask)
    db.add(log)
    await db.commit()
    
    return {"message": f"Keputusan berhasil disimpan. Status sekarang: {subtask.status}"}
