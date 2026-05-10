import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

from app.schemas.task_schema import TaskAIResponse

pytestmark = pytest.mark.asyncio


class TestFlexibleInstructionInput:
    async def test_create_task_from_chat_text_with_deadline(self, client: AsyncClient):
        leader_username = "leader_chat"
        await client.post("/api/v1/auth/register", json={"username": leader_username, "password": "p"})
        leader_login = await client.post("/api/v1/auth/login", data={"username": leader_username, "password": "p"})
        leader_headers = {"Authorization": f"Bearer {leader_login.json()['access_token']}"}

        project_resp = await client.post("/api/v1/projects/", json={"name": "Chat Project"}, headers=leader_headers)
        assert project_resp.status_code == 200
        project_id = project_resp.json()["id"]

        ai_parse_result = TaskAIResponse(
            task_title="Build Chat Input Flow",
            subtasks=[
                {"title": "Create input form", "description": "Buat form input instruksi"},
            ],
        )

        with patch("app.services.task_service.get_ai_service") as mock_get_ai_service:
            mock_ai = AsyncMock()
            mock_ai.parse_project_instructions.return_value = ai_parse_result
            mock_get_ai_service.return_value = mock_ai

            resp = await client.post(
                f"/api/v1/tasks/upload-instruction/{project_id}",
                data={
                    "instruction_text": "Buat aplikasi login sederhana dengan dashboard",
                    "deadline": "2026-06-01T12:00:00",
                },
                headers=leader_headers,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Build Chat Input Flow"
        assert body["deadline"] is not None