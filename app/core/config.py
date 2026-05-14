import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "The Auditor's Command Center"
    VERSION: str = "0.1.0"
    
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    # Confidence threshold (0-100) above which AI auto-approves evidence
    AI_AUTO_APPROVE_CONFIDENCE: int = int(os.getenv("AI_AUTO_APPROVE_CONFIDENCE", "85"))
    # System sentinel user id used to mark auto-approvals performed by AI
    AI_AUTO_APPROVE_SYSTEM_USER_ID: str = os.getenv(
        "AI_AUTO_APPROVE_SYSTEM_USER_ID", "00000000-0000-0000-0000-000000000000"
    )

settings = Settings()

# Validasi Fail-Fast
if not settings.DATABASE_URL:
    raise ValueError("FATAL ERROR: DATABASE_URL tidak ditemukan di file .env!")