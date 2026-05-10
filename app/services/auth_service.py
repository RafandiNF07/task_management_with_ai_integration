# app/services/auth_service.py
from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.domain import User
from app.schemas.auth_schema import UserCreate
from app.core.security import get_password_hash, verify_password, create_access_token

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
        await session.commit()
        await session.refresh(new_user)
        
        return new_user

    @staticmethod
    async def authenticate_user(session: AsyncSession, user_data: UserCreate) -> str:
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
        return access_token