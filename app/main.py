from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import auth, projects, tasks, appeals
from app.api.deps import get_current_user 
from app.models.domain import User
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dijalankan saat server mulai
    print("🚀 Memulai Sistem The Auditor's Command Center...")
    await init_db()
    print("✅ Database terhubung dan skema berhasil disinkronisasi.")
    yield
    # Dijalankan saat server dimatikan
    print("🛑 Mematikan koneksi sistem...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Mendaftarkan router auth ke aplikasi utama
app.include_router(auth.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(appeals.router, prefix="/api/v1")

@app.get("/api/v1/auth/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return {"message": f"Halo {current_user.username}, Anda berhasil login!", "user_id": current_user.id}
@app.get("/health")
async def health_check():
    return {
        "status": "ok", 
        "message": "Sistem The Auditor's Command Center Beroperasi"
    }