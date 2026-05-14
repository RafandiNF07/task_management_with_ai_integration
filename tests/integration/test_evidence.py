import pytest
import uuid
import io
from httpx import AsyncClient
from unittest.mock import patch

@pytest.fixture(autouse=True)
def mock_ai():
    with patch("app.services.task_service.get_ai_service") as mock_get:
        mock_ai_instance = mock_get.return_value
        
        # Mock parsing instructions (Async)
        async def mock_parse(*args, **kwargs):
            return type('obj', (object,), {
                "task_title": "Mock Task",
                "subtasks": [
                    type('obj', (object,), {"title": "Sub 1", "description": "Desc 1"})
                ]
            })
        mock_ai_instance.parse_project_instructions = mock_parse
        
        # Mock audit (Async)
        async def mock_audit(*args, **kwargs):
            return {
                "is_valid": True,
                "confidence_score": 90,
                "feedback": "Bagus"
            }
        mock_ai_instance.audit_evidence = mock_audit
        
        yield mock_ai_instance

@pytest.mark.asyncio
async def test_upload_evidence_success(client: AsyncClient, leader_client):
    """Scenario Sukses: User mengunggah file gambar yang valid."""
    headers = leader_client["headers"]
    project_id = leader_client["project_id"]

    # 1. Setup: Buat Task dan SubTask
    # Menggunakan endpoint yang ada (asumsi upload-instruction sudah ditest di tempat lain)
    # Kita buat manual di db untuk testing isolasi jika perlu, tapi kita gunakan API flow
    
    # Simulate AI parsing results via mock if needed, but here we just need a subtask
    # Let's use the task_service to create a subtask directly for speed
    from app.services.task_service import TaskService
    from app.core.database import AsyncSessionLocal
    from app.models.domain import TaskStatus

    async with AsyncSessionLocal() as db:
        # Get user id from leader_client (not easy, let's just use the API)
        # Actually, let's just use the API to create a task
        pass

    # Create a task via API
    task_resp = await client.post(
        f"/api/v1/tasks/upload-instruction/{project_id}",
        data={"instruction_text": "Tolong buatkan logo."},
        headers=headers
    )
    task_id = task_resp.json()["id"]
    
    # Get details to find subtask_id
    detail_resp = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    subtask_id = detail_resp.json()["subtasks"][0]["id"]

    # Claim subtask
    await client.post(f"/api/v1/tasks/subtasks/{subtask_id}/claim", headers=headers)

    # 2. Test Upload Evidence
    file_content = b"fake-image-binary-content"
    files = {"file": ("test.png", file_content, "image/png")}
    
    with patch("app.services.task_service.TaskService.process_background_audit") as mock_audit:
        resp = await client.post(
            f"/api/evidence/{subtask_id}",
            files=files,
            headers=headers
        )
        
        assert resp.status_code == 200
        assert resp.json()["status"] == "PENDING_AI_REVIEW"
        mock_audit.assert_called_once()

@pytest.mark.asyncio
async def test_upload_evidence_wrong_format(client: AsyncClient, leader_client):
    """Scenario Gagal: User mengunggah file dengan format salah (misal .pdf)."""
    headers = leader_client["headers"]
    project_id = leader_client["project_id"]

    # Setup Task
    task_resp = await client.post(
        f"/api/v1/tasks/upload-instruction/{project_id}",
        data={"instruction_text": "Tugas baru."},
        headers=headers
    )
    task_id = task_resp.json()["id"]
    detail_resp = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    subtask_id = detail_resp.json()["subtasks"][0]["id"]
    await client.post(f"/api/v1/tasks/subtasks/{subtask_id}/claim", headers=headers)

    # Test Upload Wrong Format
    files = {"file": ("document.pdf", b"pdf-content", "application/pdf")}
    resp = await client.post(
        f"/api/evidence/{subtask_id}",
        files=files,
        headers=headers
    )
    
    assert resp.status_code == 400
    assert "tidak didukung" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_upload_evidence_too_large(client: AsyncClient, leader_client):
    """Scenario Gagal: User mengunggah file yang melebihi batas ukuran (5MB)."""
    headers = leader_client["headers"]
    project_id = leader_client["project_id"]

    # Setup Task
    task_resp = await client.post(
        f"/api/v1/tasks/upload-instruction/{project_id}",
        data={"instruction_text": "Tugas baru."},
        headers=headers
    )
    task_id = task_resp.json()["id"]
    detail_resp = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    subtask_id = detail_resp.json()["subtasks"][0]["id"]
    await client.post(f"/api/v1/tasks/subtasks/{subtask_id}/claim", headers=headers)

    # Test Upload Too Large (6MB)
    large_content = b"0" * (6 * 1024 * 1024)
    files = {"file": ("large.png", large_content, "image/png")}
    resp = await client.post(
        f"/api/evidence/{subtask_id}",
        files=files,
        headers=headers
    )
    
    assert resp.status_code == 413
    assert "terlalu besar" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_upload_evidence_unauthorized(client: AsyncClient, leader_client):
    """Scenario Gagal: User lain mencoba mengunggah bukti untuk subtask yang bukan miliknya."""
    # Leader punya project_id dan headers
    project_id = leader_client["project_id"]
    
    # Buat user baru (bukan leader/member project)
    uid = uuid.uuid4().hex[:8]
    await client.post("/api/v1/auth/register", json={"username": f"other_{uid}", "password": "p"})
    login_resp = await client.post("/api/v1/auth/login", data={"username": f"other_{uid}", "password": "p"})
    other_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # Setup Task oleh Leader
    task_resp = await client.post(
        f"/api/v1/tasks/upload-instruction/{project_id}",
        data={"instruction_text": "Tugas rahasia."},
        headers=leader_client["headers"]
    )
    subtask_id = (await client.get(f"/api/v1/tasks/{task_resp.json()['id']}", headers=leader_client["headers"])).json()["subtasks"][0]["id"]

    # Other user mencoba upload
    files = {"file": ("test.png", b"data", "image/png")}
    resp = await client.post(
        f"/api/evidence/{subtask_id}",
        files=files,
        headers=other_headers
    )
    
    assert resp.status_code == 403
    assert "Hanya anggota yang mengerjakan" in resp.json()["detail"]
