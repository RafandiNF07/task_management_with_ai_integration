# tests/integration/conftest.py
import os
import pytest
import uuid
import asyncio

# ✅ LANGKAH 1: Paksa environment variable ke SQLite SEBELUM import app
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Sekarang baru import app dan core
from app.main import app as fastapi_app
from app.core.database import get_db
import app.core.database as db_mod

# ── Database SQLite in-memory dengan STATIC POOL ─────────────────────────────
# Kita buat engine baru yang sama dengan yang akan digunakan app (karena DATABASE_URL sudah di-override)
test_engine = create_async_engine(
    os.environ["DATABASE_URL"],
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True,
)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

# ✅ LANGKAH 2: Pastikan modul database menggunakan engine & session yang sama
db_mod.engine = test_engine
db_mod.AsyncSessionLocal = TestSessionLocal

async def override_get_db():
    async with TestSessionLocal() as session:
        yield session

fastapi_app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session", autouse=True)
async def init_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def auth_headers(client: AsyncClient):
    uid = uuid.uuid4().hex[:8]
    username = f"u_{uid}"
    await client.post("/api/v1/auth/register", json={"username": username, "password": "p"})
    resp = await client.post("/api/v1/auth/login", data={"username": username, "password": "p"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}

@pytest.fixture
async def leader_client(client: AsyncClient):
    uid = uuid.uuid4().hex[:8]
    username = f"l_{uid}"
    await client.post("/api/v1/auth/register", json={"username": username, "password": "p"})
    resp = await client.post("/api/v1/auth/login", data={"username": username, "password": "p"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    p = await client.post("/api/v1/projects/", json={"name": f"Project_{uid}"}, headers=headers)
    return {"headers": headers, "project_id": p.json()["id"]}
