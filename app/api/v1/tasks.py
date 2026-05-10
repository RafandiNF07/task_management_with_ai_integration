import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.domain import User
from app.schemas.task_schema import TaskResponse
from app.services.ai_service import AIService
from app.services.pdf_extractor import PDFExtractor
from app.services.task_service import TaskService, get_ai_service

router = APIRouter(prefix="/tasks", tags=["Tasks & AI Parsing"])

@router.post("/upload-instruction/{project_id}", response_model=TaskResponse)
async def upload_and_parse_task(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Guard: filename bisa None jika klien tidak mengirim nama file
    if not file.filename or not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Hanya file PDF yang diizinkan")

    content = await file.read()
    text_content = PDFExtractor.extract_text(content)
    
    ai_result = await get_ai_service().parse_project_instructions(text_content)
    
    new_task = await TaskService.create_task_from_ai(
        db=db, 
        ai_result=ai_result, 
        raw_content=text_content, 
        project_id=project_id, 
        user_id=current_user.id
    )

    return new_task

@router.get("/{task_id}")
async def get_task_details(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await TaskService.get_task_with_subtasks(db, task_id)

@router.patch("/subtasks/{subtask_id}/assign/{user_id}")
async def assign_subtask(
    subtask_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    subtask = await TaskService.assign_subtask(db, subtask_id, user_id, current_user.id)
    return {
        "status": "success",
        "message": f"Tugas '{subtask.title}' sekarang dikerjakan oleh User {user_id}"
    }

@router.post("/subtasks/{subtask_id}/submit-and-audit")
async def submit_and_audit(
    subtask_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Guard: filename bisa None jika klien tidak mengirim nama file
    if not file.filename or not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        raise HTTPException(status_code=400, detail="Bukti harus berupa gambar (PNG/JPG)")

    image_data = await file.read()
    
    subtask = await TaskService.start_audit_process(db, subtask_id, image_data)

    # Tambahkan tugas ke background worker FastAPI
    background_tasks.add_task(
        TaskService.process_background_audit,
        subtask_id=subtask.id,
        subtask_desc=subtask.description,
        image_bytes=image_data
    )
    
    return {
        "status": subtask.status,
        "message": "Bukti berhasil diunggah. AI sedang melakukan audit di background."
    }