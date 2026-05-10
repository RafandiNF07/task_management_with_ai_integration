from fastapi import APIRouter, Depends, HTTPException
import uuid
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.domain import User, SubTask, ActivityLog, TaskStatus
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

    # Flow "Jika Reject: Status balik ke TODO untuk dikerjakan ulang."
    if is_approved:
        subtask.status = TaskStatus.DONE
        subtask.approved_by_id = current_user.id
        action_log = "APPEAL_APPROVED"
        detail_log = f"Banding diterima oleh {current_user.username}"
    else:
        subtask.status = TaskStatus.TODO
        subtask.ai_rejection_reason = f"Ditolak oleh Leader: {reason}"
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
