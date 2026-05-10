import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from sqlmodel.ext.asyncio.session import AsyncSession

# ─────────────────────────────────────────────────────────────
# Unit Tests untuk PDFExtractor
# ─────────────────────────────────────────────────────────────
from app.services.pdf_extractor import PDFExtractor

def test_pdf_extractor_invalid_bytes():
    """PDFExtractor harus raise HTTPException jika bytes bukan PDF valid."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        PDFExtractor.extract_text(b"ini bukan pdf sama sekali")
    assert exc_info.value.status_code == 400
    assert "Gagal mengekstrak PDF" in exc_info.value.detail


# ─────────────────────────────────────────────────────────────
# Unit Tests untuk AuthService
# ─────────────────────────────────────────────────────────────
from app.services.auth_service import AuthService
from app.models.domain import User

@pytest.mark.asyncio
async def test_register_user_duplicate():
    """AuthService harus raise 400 jika username sudah ada."""
    from fastapi import HTTPException

    mock_db = AsyncMock(spec=AsyncSession)
    existing_user = User(id=uuid.uuid4(), username="testuser", password_hash="hash")

    # Simulasikan hasil query: user sudah ada di DB
    mock_result = MagicMock()
    mock_result.first.return_value = existing_user
    mock_db.exec.return_value = mock_result

    from app.schemas.auth_schema import UserCreate
    user_data = UserCreate(username="testuser", password="password123")

    with pytest.raises(HTTPException) as exc_info:
        await AuthService.register_user(mock_db, user_data)

    assert exc_info.value.status_code == 400
    assert "sudah terdaftar" in exc_info.value.detail

@pytest.mark.asyncio
async def test_register_user_success():
    """AuthService harus berhasil membuat user baru."""
    mock_db = AsyncMock(spec=AsyncSession)

    # Simulasikan query: user belum ada (return None)
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_db.exec.return_value = mock_result

    from app.schemas.auth_schema import UserCreate
    user_data = UserCreate(username="newuser", password="password123")

    result = await AuthService.register_user(mock_db, user_data)

    # Pastikan db.add dan db.commit dipanggil
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    assert result.username == "newuser"

@pytest.mark.asyncio
async def test_authenticate_user_wrong_password():
    """AuthService harus raise 401 jika password salah."""
    from fastapi import HTTPException

    mock_db = AsyncMock(spec=AsyncSession)
    # Hash asli dari kata 'correctpassword' — tidak akan cocok dengan 'wrongpassword'
    from app.core.security import get_password_hash
    hashed = get_password_hash("correctpassword")
    existing_user = User(id=uuid.uuid4(), username="testuser", password_hash=hashed)

    mock_result = MagicMock()
    mock_result.first.return_value = existing_user
    mock_db.exec.return_value = mock_result

    from app.schemas.auth_schema import UserCreate
    user_data = UserCreate(username="testuser", password="wrongpassword")

    with pytest.raises(HTTPException) as exc_info:
        await AuthService.authenticate_user(mock_db, user_data)

    assert exc_info.value.status_code == 401


# ─────────────────────────────────────────────────────────────
# Unit Tests untuk TaskService
# ─────────────────────────────────────────────────────────────
from app.services.task_service import TaskService
from app.models.domain import SubTask, TaskStatus

@pytest.mark.asyncio
async def test_get_task_with_subtasks_not_found():
    """TaskService harus raise 404 jika task tidak ditemukan."""
    from fastapi import HTTPException

    mock_db = AsyncMock(spec=AsyncSession)

    # Task tidak ditemukan
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_db.exec.return_value = mock_result

    fake_task_id = uuid.uuid4()
    with pytest.raises(HTTPException) as exc_info:
        await TaskService.get_task_with_subtasks(mock_db, fake_task_id)

    assert exc_info.value.status_code == 404

@pytest.mark.asyncio
async def test_start_audit_process_success():
    """TaskService harus mengubah status ke PENDING_AI_REVIEW setelah upload bukti."""
    import os
    mock_db = AsyncMock(spec=AsyncSession)

    fake_subtask = SubTask(
        id=uuid.uuid4(),
        title="Test Subtask",
        description="Buat halaman login",
        status=TaskStatus.IN_PROGRESS,
        task_id=uuid.uuid4()
    )
    mock_result = MagicMock()
    mock_result.first.return_value = fake_subtask
    mock_db.exec.return_value = mock_result

    dummy_image = b"fake image bytes"

    with patch("os.makedirs"), patch("builtins.open", MagicMock()):
        result = await TaskService.start_audit_process(mock_db, fake_subtask.id, dummy_image)

    assert result.status == TaskStatus.PENDING_AI_REVIEW
    mock_db.add.assert_called()
    mock_db.commit.assert_called_once()

@pytest.mark.asyncio
async def test_assign_subtask_not_found():
    """TaskService harus raise 404 jika subtask tidak ditemukan."""
    from fastapi import HTTPException

    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_db.exec.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await TaskService.assign_subtask(mock_db, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

    assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────
# Unit Tests untuk ProjectService
# ─────────────────────────────────────────────────────────────
from app.services.project_service import ProjectService
from app.models.domain import Project, ProjectMember, RoleEnum, ActivityLog

@pytest.mark.asyncio
async def test_add_member_user_not_found():
    """ProjectService harus raise 404 jika username tidak ditemukan."""
    from fastapi import HTTPException

    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.first.return_value = None  # user tidak ada
    mock_db.exec.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await ProjectService.add_member(
            mock_db, uuid.uuid4(), "nonexistent_user", RoleEnum.MEMBER, uuid.uuid4()
        )
    assert exc_info.value.status_code == 404

@pytest.mark.asyncio
async def test_add_member_already_joined():
    """ProjectService harus raise 400 jika user sudah ada di proyek."""
    from fastapi import HTTPException

    mock_db = AsyncMock(spec=AsyncSession)
    existing_user = User(id=uuid.uuid4(), username="member1", password_hash="hash")
    existing_member = ProjectMember(user_id=existing_user.id, project_id=uuid.uuid4(), role=RoleEnum.MEMBER)

    call_count = 0
    def side_effect(*args, **kwargs):
        nonlocal call_count
        mock_result = MagicMock()
        if call_count == 0:
            mock_result.first.return_value = existing_user   # query pertama: cari user
        else:
            mock_result.first.return_value = existing_member  # query kedua: cek membership
        call_count += 1
        return mock_result

    mock_db.exec.side_effect = side_effect

    with pytest.raises(HTTPException) as exc_info:
        await ProjectService.add_member(
            mock_db, uuid.uuid4(), "member1", RoleEnum.MEMBER, uuid.uuid4()
        )
    assert exc_info.value.status_code == 400
    assert "sudah bergabung" in exc_info.value.detail
