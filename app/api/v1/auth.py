# app/api/v1/auth.py
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel.ext.asyncio.session import AsyncSession
from app.core.database import get_db
from app.schemas.auth_schema import UserCreate, UserResponse, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Mendaftarkan mahasiswa/user baru ke dalam sistem."""
    return await AuthService.register_user(db, user_data)

# UBAH BAGIAN INI: Menggunakan OAuth2PasswordRequestForm
@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: AsyncSession = Depends(get_db)
):
    """Login untuk mendapatkan JWT Token."""
    # OAuth2PasswordRequestForm secara default menyimpan username di atribut 'username' dan 'password'
    user_data = UserCreate(username=form_data.username, password=form_data.password)
    token = await AuthService.authenticate_user(db, user_data)
    return {"access_token": token, "token_type": "bearer"}