import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "The Auditor's Command Center"
    VERSION: str = "0.1.0"
    
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")

settings = Settings()

# Validasi Fail-Fast
if not settings.DATABASE_URL:
    raise ValueError("FATAL ERROR: DATABASE_URL tidak ditemukan di file .env!")