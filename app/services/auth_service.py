# app/services/auth_service.py
from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.domain import User, ActivityLog, RefreshToken
from app.schemas.auth_schema import UserCreate
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
)
import jwt
from app.core.config import settings
import uuid
from datetime import datetime, timedelta, timezone
from app.core.security import REFRESH_TOKEN_EXPIRE_MINUTES

class AuthService:
    @staticmethod
    async def register_user(session: AsyncSession, user_data: UserCreate) -> User:
        # 1. Cek apakah username sudah ada di database
        stmt = select(User).where(User.username == user_data.username)
        result = await session.exec(stmt)
        if result.first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Username sudah terdaftar"
            )
        
        # 2. Buat User baru dengan password yang sudah di-hash
        new_user = User(
            username=user_data.username,
            password_hash=get_password_hash(user_data.password)
        )
        
        # 3. Simpan ke database
        session.add(new_user)
        await session.flush()

        session.add(
            ActivityLog(
                action="USER_REGISTERED",
                details=f"User {new_user.username} berhasil melakukan registrasi",
                user_id=new_user.id,
                project_id=None,
            )
        )
        await session.commit()
        await session.refresh(new_user)
        
        return new_user

    @staticmethod
    async def authenticate_user(session: AsyncSession, user_data: UserCreate) -> dict:
        # 1. Cari user berdasarkan username
        stmt = select(User).where(User.username == user_data.username)
        result = await session.exec(stmt)
        user = result.first()
        
        # 2. Verifikasi keberadaan user dan kecocokan password
        if not user or not verify_password(user_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Username atau password salah"
            )
        
        # 3. Generate JWT Token (menyimpan ID user di dalam payload)
        access_token = create_access_token(data={"sub": str(user.id), "username": user.username})
        refresh_token = create_refresh_token(data={"sub": str(user.id), "username": user.username})

        # Persist refresh token for revocation support
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
        token_row = RefreshToken(
            token=refresh_token,
            user_id=user.id,
            expires_at=expires_at.replace(tzinfo=None),
            revoked=False,
        )
        session.add(token_row)
        await session.commit()

        return {"access_token": access_token, "refresh_token": refresh_token}

    @staticmethod
    async def refresh_access_token(session: AsyncSession, refresh_token: str) -> str:
        """Validasi refresh token dan keluarkan access token baru jika valid."""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token tidak valid atau sudah kedaluwarsa",
            headers={"WWW-Authenticate": "Bearer"},
        )

        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id_raw = payload.get("sub")
            if user_id_raw is None:
                raise credentials_exception
            user_id = str(user_id_raw)
        except jwt.PyJWTError:
            raise credentials_exception

        # Verify user exists and refresh token not revoked
        stmt = select(RefreshToken).where(RefreshToken.token == refresh_token)
        result = await session.exec(stmt)
        token_row = result.first()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if not token_row or token_row.revoked or token_row.expires_at < now:
            raise credentials_exception

        # Verify user exists
        stmt = select(User).where(User.id == uuid.UUID(user_id))
        result = await session.exec(stmt)
        user = result.first()
        if not user:
            raise credentials_exception

        # Issue new access token
        access_token = create_access_token(data={"sub": str(user.id), "username": user.username})
        return access_token

    @staticmethod
    async def revoke_refresh_token(session: AsyncSession, refresh_token: str) -> bool:
        stmt = select(RefreshToken).where(RefreshToken.token == refresh_token)
        result = await session.exec(stmt)
        token_row = result.first()
        if not token_row:
            return False
        token_row.revoked = True
        session.add(token_row)
        await session.commit()
        return True