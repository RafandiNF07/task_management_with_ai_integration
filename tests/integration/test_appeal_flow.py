import fitz
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

from app.schemas.task_schema import TaskAIResponse
import app.core.database as db_mod

pytestmark = pytest.mark.asyncio


def build_sample_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Instruksi proyek: buat login page dan dashboard")
    return doc.tobytes()


def build_sample_png_bytes() -> bytes:
    return b"fake-png-bytes"


class TestAppealWorkflow:
    async def test_full_appeal_flow(self, client: AsyncClient):
        leader_username = "leader_flow"
        member_username = "member_flow"

        await client.post("/api/v1/auth/register", json={"username": leader_username, "password": "p"})
        await client.post("/api/v1/auth/register", json={"username": member_username, "password": "p"})

        leader_login = await client.post("/api/v1/auth/login", data={"username": leader_username, "password": "p"})
        member_login = await client.post("/api/v1/auth/login", data={"username": member_username, "password": "p"})
        leader_headers = {"Authorization": f"Bearer {leader_login.json()['access_token']}"}
        member_headers = {"Authorization": f"Bearer {member_login.json()['access_token']}"}

        project_resp = await client.post("/api/v1/projects/", json={"name": "Flow Project"}, headers=leader_headers)
        assert project_resp.status_code == 200
        project_id = project_resp.json()["id"]

        invite_resp = await client.post(
            f"/api/v1/projects/{project_id}/members",
            json={"username": member_username, "role": "MEMBER"},
            headers=leader_headers,
        )
        assert invite_resp.status_code == 200

        sample_pdf = build_sample_pdf()
        ai_parse_result = TaskAIResponse(
            task_title="Build Login Flow",
            subtasks=[
                {"title": "Design login page", "description": "Buat form login"},
                {"title": "Connect auth endpoint", "description": "Hubungkan ke API login"},
            ],
        )

        with patch("app.services.task_service.get_ai_service") as mock_get_ai_service:
            mock_ai = AsyncMock()
            mock_ai.parse_project_instructions.return_value = ai_parse_result
            mock_get_ai_service.return_value = mock_ai

            upload_resp = await client.post(
                f"/api/v1/tasks/upload-instruction/{project_id}",
                files={"file": ("instructions.pdf", sample_pdf, "application/pdf")},
                headers=leader_headers,
            )

        assert upload_resp.status_code == 200
        task_id = upload_resp.json()["id"]

        publish_resp = await client.post(f"/api/v1/tasks/publish/{task_id}", headers=leader_headers)
        assert publish_resp.status_code == 200
        assert publish_resp.json()["is_published"] is True

        task_detail = await client.get(f"/api/v1/tasks/{task_id}", headers=leader_headers)
        assert task_detail.status_code == 200
        subtask_id = task_detail.json()["subtasks"][0]["id"]

        claim_resp = await client.post(f"/api/v1/tasks/subtasks/{subtask_id}/claim", headers=member_headers)
        assert claim_resp.status_code == 200

        submit_payload = build_sample_png_bytes()
        with patch("app.services.task_service.AsyncSessionLocal", db_mod.AsyncSessionLocal), patch(
            "app.services.task_service.get_ai_service"
        ) as mock_get_ai_service:
            mock_ai = AsyncMock()
            mock_ai.audit_evidence.return_value = {
                "is_valid": False,
                "confidence_score": 20,
                "feedback": "Bukti tidak sesuai instruksi",
            }
            mock_get_ai_service.return_value = mock_ai

            submit_resp = await client.post(
                f"/api/v1/tasks/subtasks/{subtask_id}/submit-and-audit",
                files={"file": ("evidence.png", submit_payload, "image/png")},
                headers=member_headers,
            )

        assert submit_resp.status_code == 200
        assert submit_resp.json()["status"] == "PENDING_AI_REVIEW"

        appeal_resp = await client.patch(
            f"/api/v1/appeals/{subtask_id}/appeal",
            params={"reason": "AI salah membaca bukti, ini sesuai tugas"},
            headers=member_headers,
        )
        assert appeal_resp.status_code == 200
        assert appeal_resp.json()["status"] == "APPEAL_PENDING"

        queue_resp = await client.get(f"/api/v1/appeals/projects/{project_id}/queue", headers=leader_headers)
        assert queue_resp.status_code == 200
        assert len(queue_resp.json()["items"]) == 1

        decision_resp = await client.patch(
            f"/api/v1/appeals/{subtask_id}/leader-decision",
            params={"is_approved": True},
            headers=leader_headers,
        )
        assert decision_resp.status_code == 200

        final_task_detail = await client.get(f"/api/v1/tasks/{task_id}", headers=leader_headers)
        final_subtask = final_task_detail.json()["subtasks"][0]
        assert final_subtask["status"] == "DONE"
        assert final_subtask["approved_by_id"] is not None

        report_resp = await client.get(f"/api/v1/reports/projects/{project_id}", headers=leader_headers)
        assert report_resp.status_code == 200
        assert report_resp.headers["content-type"].startswith("application/pdf")
