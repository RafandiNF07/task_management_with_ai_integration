# app/api/v1/tasks.py
import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from sqlalchemy.orm import selectinload # Tambahkan ini
import pdfplumber
import io
import uuid

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.domain import User, Task, SubTask, ActivityLog
from app.services.ai_service import AIService
from app.schemas.task_schema import TaskResponse

router = APIRouter(prefix="/tasks", tags=["Tasks & AI Parsing"])
ai_service = AIService()

@router.post("/upload-instruction/{project_id}", response_model=TaskResponse)
async def upload_and_parse_task(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Hanya file PDF yang diizinkan")

    # 1. Ekstraksi Teks dari PDF
    content = await file.read()
    text_content = ""
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text_content += page.extract_text() or ""

    # 2. Kirim ke Gemini AI
    ai_result = await ai_service.parse_project_instructions(text_content)

    # 3. Simpan ke Database (Task Utama)
    new_task = Task(
        title=ai_result.task_title,
        raw_content=text_content,
        project_id=project_id
    )
    db.add(new_task)
    await db.flush()

    # 4. Simpan SubTasks (Langkah-langkah dari AI)
    for sub in ai_result.subtasks:
        new_sub = SubTask(
            title=sub.title,
            description=sub.description,
            task_id=new_task.id
        )
        db.add(new_sub)

    # 5. Log Aktivitas
    log = ActivityLog(
        action="TASKS_PUBLISHED",
        details=f"AI berhasil memecah tugas: {new_task.title}",
        user_id=current_user.id,
        project_id=project_id
    )
    db.add(log)
    
    await db.commit()
    await db.refresh(new_task)
    return new_task

# app/api/v1/tasks.py

@router.get("/{task_id}", response_model=None)
async def get_task_details(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Melihat detail tugas beserta seluruh subtask di dalamnya."""
    stmt = select(Task).where(Task.id == task_id)
    result = await db.exec(stmt)
    task = result.first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Tugas tidak ditemukan")
        
    # Ambil subtasks terkait
    sub_stmt = select(SubTask).where(SubTask.task_id == task_id)
    sub_result = await db.exec(sub_stmt)
    subtasks = sub_result.all()
    
    return {
        "task": task,
        "subtasks": subtasks
    }

# app/api/v1/tasks.py

@router.post("/subtasks/{subtask_id}/submit-evidence")
async def submit_task_evidence(
    subtask_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mengunggah screenshot bukti pengerjaan tugas."""
    # 1. Validasi format file (Hanya Gambar)
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        raise HTTPException(status_code=400, detail="Bukti harus berupa gambar (PNG/JPG)")

    # 2. Cari Subtask
    stmt = select(SubTask).where(SubTask.id == subtask_id)
    result = await db.exec(stmt)
    subtask = result.first()
    
    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask tidak ditemukan")

    # 3. Logika Simpan File (Untuk sekarang kita simpan path-nya saja)
    # Di dunia nyata, gunakan S3 atau Local Storage yang aman
    file_path = f"uploads/evidence_{subtask_id}_{uuid.uuid4().hex}.png"
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    # 4. Update Data
    subtask.evidence_url = file_path
    subtask.status = "REVIEW_PENDING" # Berubah dari IN_PROGRESS ke REVIEW
    
    db.add(subtask)
    await db.commit()

    return {
        "message": "Bukti berhasil diunggah. Menunggu audit AI.",
        "status": subtask.status,
        "file_path": file_path
    }

@router.patch("/subtasks/{subtask_id}/assign/{user_id}")
async def assign_subtask(
    subtask_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Gunakan .options(selectinload(SubTask.task)) agar data task ikut diambil secara async
    stmt = (
        select(SubTask)
        .where(SubTask.id == subtask_id)
        .options(selectinload(SubTask.task)) 
    )
    result = await db.exec(stmt)
    subtask = result.first()
    
    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask tidak ditemukan")

    subtask.assigned_to_id = user_id
    subtask.status = "IN_PROGRESS" 
    
    # Sekarang subtask.task sudah ada di memori, tidak perlu fetch lagi
    project_id = subtask.task.project_id if subtask.task else None
    
    log = ActivityLog(
        action="TASK_ASSIGNED",
        details=f"Subtask '{subtask.title}' ditugaskan ke User ID {user_id}",
        user_id=current_user.id,
        project_id=project_id
    )
    
    db.add(subtask)
    db.add(log)
    
    await db.commit()
    await db.refresh(subtask)
    
    return {
        "status": "success",
        "message": f"Tugas '{subtask.title}' sekarang dikerjakan oleh User {user_id}"
    }

@router.post("/subtasks/{subtask_id}/submit-and-audit")
async def submit_and_audit(
    subtask_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Ambil data subtask
    stmt = select(SubTask).where(SubTask.id == subtask_id)
    result = await db.exec(stmt)
    subtask = result.first()
    
    if not subtask:
        raise HTTPException(status_code=404, detail="Tugas tidak ditemukan")

    # 2. Baca file gambar
    image_data = await file.read()
    
    # 3. Jalankan Audit AI
    audit_result = await ai_service.audit_evidence(subtask.description, image_data)

    # 4. Tentukan Status Berdasarkan Hasil Audit
    if audit_result["is_valid"] and audit_result["confidence_score"] >= 70:
        subtask.status = "DONE"
        subtask.ai_rejection_reason = None
    else:
        subtask.status = "REJECTED"
        subtask.ai_rejection_reason = audit_result["feedback"]

    # 5. Simpan Bukti (Simulasi penyimpanan path)
    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{subtask_id}.png"
    with open(file_path, "wb") as f:
        f.write(image_data)
    
    subtask.evidence_url = file_path
    
    db.add(subtask)
    await db.commit()
    
    return {
        "status": subtask.status,
        "ai_feedback": audit_result["feedback"],
        "confidence": audit_result["confidence_score"]
    }

@router.patch("/subtasks/{subtask_id}/leader-decision")
async def leader_decision(
    subtask_id: uuid.UUID,
    is_approved: bool, # True untuk Terima, False untuk Tolak
    reason: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fungsi bagi Leader/Dosen untuk memberikan keputusan final manual."""
    stmt = select(SubTask).where(SubTask.id == subtask_id)
    result = await db.exec(stmt)
    subtask = result.first()

    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask tidak ditemukan")

    if is_approved:
        subtask.status = TaskStatus.DONE
    else:
        subtask.status = TaskStatus.REJECTED_BY_HUMAN
        subtask.ai_rejection_reason = f"Ditolak oleh Leader: {reason}"

    db.add(subtask)
    await db.commit()
    
    return {"message": f"Keputusan berhasil disimpan. Status sekarang: {subtask.status}"}

@router.patch("/subtasks/{subtask_id}/appeal")
async def appeal_subtask(
    subtask_id: uuid.UUID,
    reason: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mahasiswa melakukan banding terhadap hasil audit AI."""
    stmt = select(SubTask).where(SubTask.id == subtask_id)
    result = await db.exec(stmt)
    subtask = result.first()

    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask tidak ditemukan")

    # Banding hanya bisa dilakukan jika status sebelumnya adalah REJECTED_BY_AI
    if subtask.status != TaskStatus.REJECTED_BY_AI:
        raise HTTPException(
            status_code=400, 
            detail="Hanya tugas yang ditolak AI yang bisa diajukan banding."
        )

    # Update status dan alasan banding
    subtask.status = TaskStatus.APPEAL_PENDING
    subtask.appeal_reason = reason
    
    # Catat ke Activity Log
    log = ActivityLog(
        action="TASK_APPEALED",
        details=f"User {current_user.username} mengajukan banding: {reason}",
        user_id=current_user.id,
        project_id=subtask.task.project_id if hasattr(subtask, 'task') else None
    )

    db.add(subtask)
    db.add(log)
    await db.commit()
    
    return {
        "message": "Banding berhasil diajukan. Menunggu tinjauan manual Leader/QC.",
        "status": subtask.status
    }