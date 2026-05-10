# tests/integration/test_auth_flow.py
#
# Integration Test: Fase 1 - Onboarding (Auth & RBAC)
# Mengetes flow: Register → Login → Akses endpoint terproteksi → Tolak akses tanpa token

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        """Registrasi dengan data valid harus mengembalikan 201 dan data user."""
        response = await client.post("/api/v1/auth/register", json={
            "username": "mahasiswa_baru",
            "password": "Password123!"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "mahasiswa_baru"
        assert "id" in data
        # Pastikan password TIDAK dikembalikan ke response
        assert "password" not in data
        assert "password_hash" not in data

    async def test_register_duplicate_username(self, client: AsyncClient):
        """Registrasi dengan username yang sudah ada harus mengembalikan 400."""
        payload = {"username": "user_duplikat", "password": "pass123"}
        await client.post("/api/v1/auth/register", json=payload)

        # Registrasi kedua dengan username yang sama
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 400
        assert "sudah terdaftar" in response.json()["detail"]

    async def test_register_returns_uuid(self, client: AsyncClient):
        """ID user yang dikembalikan harus berformat UUID yang valid."""
        import uuid
        response = await client.post("/api/v1/auth/register", json={
            "username": "user_uuid_check",
            "password": "pass123"
        })
        assert response.status_code == 201
        # Tidak boleh raise exception jika formatnya UUID valid
        uuid.UUID(response.json()["id"])


class TestLogin:
    async def test_login_success(self, client: AsyncClient):
        """Login dengan kredensial benar harus mengembalikan access_token."""
        await client.post("/api/v1/auth/register", json={
            "username": "user_login_test",
            "password": "correctpass"
        })
        response = await client.post("/api/v1/auth/login", data={
            "username": "user_login_test",
            "password": "correctpass"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        # Token tidak boleh kosong
        assert len(data["access_token"]) > 20

    async def test_login_wrong_password(self, client: AsyncClient):
        """Login dengan password salah harus mengembalikan 401."""
        await client.post("/api/v1/auth/register", json={
            "username": "user_wrong_pass",
            "password": "benar123"
        })
        response = await client.post("/api/v1/auth/login", data={
            "username": "user_wrong_pass",
            "password": "salah456"
        })
        assert response.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Login dengan username yang tidak terdaftar harus mengembalikan 401."""
        response = await client.post("/api/v1/auth/login", data={
            "username": "hantu_user",
            "password": "apapun"
        })
        assert response.status_code == 401


class TestProtectedEndpoints:
    async def test_access_protected_endpoint_without_token(self, client: AsyncClient):
        """Mengakses endpoint terproteksi tanpa token harus ditolak 401."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_access_protected_endpoint_with_invalid_token(self, client: AsyncClient):
        """Mengakses endpoint terproteksi dengan token palsu harus ditolak 401."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer token_palsu_asal_tulis"}
        )
        assert response.status_code == 401

    async def test_access_protected_endpoint_with_valid_token(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Mengakses endpoint terproteksi dengan token valid harus berhasil 200."""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        # Cek apakah response mengandung sapaan (username ada di dalam token)
        assert "Halo" in response.json()["message"]
