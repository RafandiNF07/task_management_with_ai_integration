import uuid
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_current_project_leader
from app.core.database import get_db
from app.models.domain import User, ProjectMember
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/projects/{project_id}")
async def generate_project_report(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    leader_access: ProjectMember = Depends(get_current_project_leader),
):
    """Generate laporan PDF proyek lengkap dengan subtask, evidence, audit trail, dan riwayat banding. Hanya Leader yang dapat."""
    pdf_bytes = await ReportService.generate_project_report_pdf(db, project_id)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="project-{project_id}-report.pdf"'},
    )