from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import AsyncGenerator

from app.core.config import settings
from app.models.domain import User, Project, ProjectMember, Task, SubTask, ActivityLog

# echo=True akan mencetak query SQL ke terminal, sangat membantu saat proses debug
engine = create_async_engine(settings.DATABASE_URL, echo=True, future=True)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency Injection untuk menyediakan session ke setiap route FastAPI."""
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """Membuat struktur tabel secara otomatis jika belum ada."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)