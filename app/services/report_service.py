import base64
import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from weasyprint import HTML

from app.models.domain import ActivityLog, Project, SubTask, Task, TaskStatus


class ReportService:
	@staticmethod
	async def generate_project_report_pdf(db: AsyncSession, project_id: uuid.UUID) -> bytes:
		project_stmt = select(Project).where(Project.id == project_id)
		project_result = await db.exec(project_stmt)
		project = project_result.first()

		if not project:
			raise HTTPException(status_code=404, detail="Project tidak ditemukan")

		task_stmt = select(Task).where(Task.project_id == project_id).options(selectinload(Task.subtasks))  # type: ignore[arg-type]
		task_result = await db.exec(task_stmt)
		tasks = task_result.all()

		log_stmt = select(ActivityLog).where(ActivityLog.project_id == project_id).order_by(ActivityLog.created_at.asc())  # type: ignore[attr-defined]
		log_result = await db.exec(log_stmt)
		logs = log_result.all()

		completed_subtasks = [subtask for task in tasks for subtask in task.subtasks if subtask.status == TaskStatus.DONE]

		def embed_image(file_path: str | None) -> str:
			if not file_path:
				return ""

			resolved = Path(file_path)
			if not resolved.is_absolute():
				resolved = Path.cwd() / resolved

			if not resolved.exists():
				return ""

			return f"file://{resolved.absolute()}"

		completed_rows = []
		for subtask in completed_subtasks:
			image_src = embed_image(subtask.evidence_url)
			image_html = f"<img src='{image_src}' alt='Bukti' />" if image_src else "<p>Tidak ada bukti</p>"
			completed_rows.append(
				f"""
				<div class="card">
					<h3>{subtask.title}</h3>
					<p>{subtask.description}</p>
					<p>Status: {subtask.status}</p>
					{image_html}
				</div>
				"""
			)

		appeal_items = []
		for log in logs:
			if log.action in {"TASK_APPEALED", "APPEAL_APPROVED", "APPEAL_REJECTED"}:
				appeal_items.append(f"<li><strong>{log.action}</strong> - {log.details}</li>")

		html = f"""
		<html>
		<head>
			<style>
				body {{ font-family: Arial, sans-serif; margin: 24px; color: #111827; }}
				h1, h2, h3 {{ margin-bottom: 8px; }}
				.muted {{ color: #6b7280; }}
				table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
				th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; vertical-align: top; }}
				th {{ background: #f3f4f6; }}
				.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
				.card {{ border: 1px solid #e5e7eb; padding: 12px; margin-bottom: 12px; border-radius: 10px; }}
				img {{ max-width: 100%; height: auto; border: 1px solid #e5e7eb; margin-top: 8px; }}
			</style>
		</head>
		<body>
			<h1>Laporan UAS - {project.name}</h1>
			<p class="muted">Dibuat pada {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}</p>

			<div class="grid">
				<div class="card">
					<h2>Ringkasan</h2>
					<p>Total task: {len(tasks)}</p>
					<p>Subtask selesai: {len(completed_subtasks)}</p>
					<p>Total log aktivitas: {len(logs)}</p>
				</div>
				<div class="card">
					<h2>Transparansi Banding</h2>
					{('<ul>' + ''.join(appeal_items) + '</ul>') if appeal_items else '<p>Tidak ada banding.</p>'}
				</div>
			</div>

			<h2>Daftar Subtask Selesai</h2>
			{''.join(completed_rows) if completed_rows else '<p>Belum ada subtask yang selesai.</p>'}

			<h2>Aktivitas Proyek</h2>
			<table>
				<thead>
					<tr>
						<th>Waktu</th>
						<th>Action</th>
						<th>Detail</th>
					</tr>
				</thead>
				<tbody>
					{''.join(f'<tr><td>{log.created_at:%Y-%m-%d %H:%M}</td><td>{log.action}</td><td>{log.details}</td></tr>' for log in logs) or '<tr><td colspan="3">Belum ada aktivitas</td></tr>'}
				</tbody>
			</table>
		</body>
		</html>
		"""

		pdf_bytes = HTML(string=html, base_url=str(Path.cwd())).write_pdf()
		if pdf_bytes is None:
			raise HTTPException(status_code=500, detail="Failed to generate PDF")
		return pdf_bytes
