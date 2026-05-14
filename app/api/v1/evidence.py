import uuid
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.domain import User, TaskStatus
from app.services.evidence_service import EvidenceService
from app.services.task_service import TaskService

router = APIRouter(prefix="", tags=["Evidence"])

@router.post("/{subtask_id}")
async def upload_evidence(
    subtask_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Endpoint untuk mengunggah bukti pengerjaan subtask.
    Menerapkan validasi ukuran dan tipe file (SOLID & Security Hardened).
    """
    # 1. Ownership & State Check
    subtask = await TaskService.get_subtask(db, subtask_id)
    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask tidak ditemukan")

    if subtask.assigned_to_id != current_user.id:
        raise HTTPException(
            status_code=403, 
            detail="Hanya anggota yang mengerjakan subtask ini yang dapat mengunggah bukti"
        )
    
    if subtask.status not in {TaskStatus.IN_PROGRESS, TaskStatus.REJECTED_BY_AI, TaskStatus.TODO}:
         # Allow re-upload if rejected or in progress
         pass

    # 2. Service Call (Separation of Concerns)
    image_data = await EvidenceService.validate_and_save_evidence(
        db=db,
        subtask_id=subtask_id,
        file=file,
        user_id=current_user.id
    )

    # 3. Trigger Background Audit
    background_tasks.add_task(
        TaskService.process_background_audit,
        subtask_id=subtask_id,
        subtask_desc=subtask.description,
        image_bytes=image_data
    )

    await db.commit()

    return {
        "status": "PENDING_AI_REVIEW",
        "message": "Bukti berhasil diunggah. AI sedang melakukan audit otomatis."
    }
