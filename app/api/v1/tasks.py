import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks, Form
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.core.database import get_db
from app.api.deps import get_current_user, get_project_membership
from app.models.domain import User, Task, RoleEnum
from app.schemas.task_schema import TaskResponse
from app.services.instruction_extractor import InstructionExtractor
from app.services import task_service as task_service_module
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks & AI Parsing"])

@router.post("/upload-instruction/{project_id}", response_model=TaskResponse)
async def upload_and_parse_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID | None = Form(None),
    instruction_text: str | None = Form(None),
    deadline: datetime | None = Form(None),
    file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload instruksi proyek dari PDF, DOCX, atau teks chat lalu parsing otomatis oleh AI. Bisa create atau update draft task."""
    membership = await get_project_membership(project_id, current_user, db)
    if membership.role not in {RoleEnum.LEADER, RoleEnum.ASSISTANT}:
        raise HTTPException(status_code=403, detail="Hanya Leader atau Asisten yang dapat mengunggah instruksi")

    if file:
        # Limit instruction file to 10MB
        content_length = file.size if hasattr(file, "size") else None
        if content_length and content_length > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File instruksi terlalu besar (Max 10MB)")
            
    file_bytes = await file.read() if file else None
    filename = file.filename if file else None
    text_content = InstructionExtractor.extract_text(filename, file_bytes, instruction_text)
    
    ai_result = await task_service_module.get_ai_service().parse_project_instructions(text_content)
    
    upserted_task = await TaskService.upsert_task_from_ai(
        db=db, 
        ai_result=ai_result, 
        raw_content=text_content, 
        project_id=project_id, 
        user_id=current_user.id,
        deadline=deadline,
        task_id=task_id,
    )

    return upserted_task

@router.post("/publish/{task_id}")
async def publish_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mem-publish task dari status draft agar dapat diklaim oleh member. Hanya Leader/Asisten yang dapat."""
    stmt = select(Task).where(Task.id == task_id)
    result = await db.exec(stmt)
    task = result.first()

    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")

    membership = await get_project_membership(task.project_id, current_user, db)
    if membership.role not in {RoleEnum.LEADER, RoleEnum.ASSISTANT}:
        raise HTTPException(status_code=403, detail="Hanya Leader atau Asisten yang dapat mem-publish task")

    published_task = await TaskService.publish_task(db, task_id, current_user.id)
    return {"status": "success", "task_id": published_task.id, "is_published": published_task.is_published}

@router.get("/{task_id}")
async def get_task_details(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mendapatkan detail task beserta semua subtask-nya."""
    return await TaskService.get_task_with_subtasks(db, task_id)

@router.patch("/subtasks/{subtask_id}/assign/{user_id}")
async def assign_subtask(
    subtask_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Assign subtask ke member lain. Hanya Leader atau Asisten yang dapat mengassign."""
    subtask = await TaskService.assign_subtask(db, subtask_id, user_id, current_user.id)
    return {
        "status": "success",
        "message": f"Tugas '{subtask.title}' sekarang di-assign ke User {subtask.assigned_to_id}"
    }

@router.post("/subtasks/{subtask_id}/claim")
async def claim_subtask(
    subtask_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mengklaim subtask yang masih TODO untuk mulai mengerjakannya. Status berubah menjadi IN_PROGRESS."""
    subtask = await TaskService.claim_subtask(db, subtask_id, current_user.id)
    return {
        "status": "success",
        "message": f"Tugas '{subtask.title}' berhasil di-claim"
    }

    return {
        "status": "success",
        "message": f"Tugas '{subtask.title}' berhasil di-claim"
    }