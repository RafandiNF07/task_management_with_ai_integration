import os
import uuid
import aiofiles
import io
from PIL import Image
from fastapi import HTTPException, UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.domain import SubTask, TaskStatus, ActivityLog
from app.core.config import settings

class EvidenceService:
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}

    @staticmethod
    async def validate_and_save_evidence(
        db: AsyncSession,
        subtask_id: uuid.UUID,
        file: UploadFile,
        user_id: uuid.UUID
    ) -> bytes:
        # 1. Validate File Extension
        ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
        if ext not in EvidenceService.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Format file {ext} tidak didukung. Gunakan PNG/JPG."
            )

        # 2. Validate File Size
        content_length = file.size if hasattr(file, "size") else None
        if content_length and content_length > EvidenceService.MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="Ukuran file terlalu besar (Max 5MB)")

        # Read content
        content = await file.read()
        
        if len(content) > EvidenceService.MAX_FILE_SIZE:
             raise HTTPException(status_code=413, detail="Ukuran file terlalu besar (Max 5MB)")

        # 3. Optimize Image (Compression & Resizing)
        try:
            img = Image.open(io.BytesIO(content))
            
            # Convert to RGB if necessary (e.g. from RGBA/PNG)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Resize if too large (Max 1200px)
            max_size = 1200
            if img.width > max_size or img.height > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Compress
            output_buffer = io.BytesIO()
            img.save(output_buffer, format="JPEG", quality=75, optimize=True)
            optimized_content = output_buffer.getvalue()
        except Exception as e:
            # Fallback to original content if image processing fails
            optimized_content = content

        # 4. Save to Disk
        os.makedirs("uploads", exist_ok=True)
        # We use .jpg for all optimized images
        file_path = f"uploads/{subtask_id}.jpg"
        
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(optimized_content)

        # 5. Update Subtask Status
        subtask = await db.get(SubTask, subtask_id)
        if not subtask:
            raise HTTPException(status_code=404, detail="Subtask tidak ditemukan")
            
        subtask.evidence_url = file_path
        subtask.status = TaskStatus.PENDING_AI_REVIEW
        
        db.add(subtask)
        await db.flush()
        
        return content

    @staticmethod
    def get_audit_background_task():
        # Avoiding circular import by importing here
        from app.services.task_service import TaskService
        return TaskService.process_background_audit
