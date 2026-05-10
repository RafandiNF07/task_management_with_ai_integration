# app/api/deps.py
import uuid # <-- 1. Tambahkan import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.database import get_db
from app.models.domain import User, ProjectMember, RoleEnum
from app.core.security import ALGORITHM
# <-- 2. Hapus baris 'from app.api.deps import ...' yang membuat circular import

# Ini memberi tahu Swagger UI di mana letak URL login untuk tombol "Authorize"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency untuk mengekstrak user dari JWT token.
    Gunakan fungsi ini di setiap endpoint yang membutuhkan autentikasi.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token tidak valid atau sudah kedaluwarsa",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 1. Dekode token menggunakan Secret Key
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id_raw = payload.get("sub")
        
        if user_id_raw is None:
            raise credentials_exception
        user_id = str(user_id_raw)
            
    except jwt.PyJWTError:
        raise credentials_exception
        
    # 2. Cari user di database berdasarkan ID dari token
    stmt = select(User).where(User.id == uuid.UUID(user_id)) # Pastikan user_id di-cast ke UUID jika id di db adalah UUID
    result = await db.exec(stmt)
    user = result.first()
    
    if user is None:
        raise credentials_exception
        
    return user

async def get_current_project_leader(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Memastikan user adalah LEADER di proyek ini."""
    stmt = select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.id
    )
    result = await db.exec(stmt)
    membership = result.first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda bukan anggota proyek ini."
        )
    
    if membership.role != RoleEnum.LEADER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya Leader yang dapat mengakses fitur ini."
        )
    
    return membership

async def get_project_membership(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ProjectMember:
    stmt = select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.id
    )
    result = await db.exec(stmt)
    membership = result.first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda bukan anggota proyek ini."
        )

    return membership