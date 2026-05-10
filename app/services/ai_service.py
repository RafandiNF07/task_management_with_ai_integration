# app/services/ai_service.py
from google import genai
from google.genai import types
import json
from app.core.config import settings
from app.schemas.task_schema import TaskAIResponse
from fastapi import HTTPException

class AIService:
    def __init__(self):
        # Memastikan API Key terbaca
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY tidak ditemukan di .env")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def parse_project_instructions(self, text_content: str) -> TaskAIResponse:
        prompt = f"""
        Anda adalah Senior Project Auditor. Tugas Anda adalah menganalisis teks instruksi tugas di bawah ini 
        dan memecahnya menjadi daftar langkah pengerjaan yang konkret untuk mahasiswa.

        INSTRUKSI TUGAS:
        {text_content}

        Keluaran harus dalam format JSON murni dengan struktur:
        {{
            "task_title": "Judul",
            "subtasks": [
                {{"title": "Langkah", "description": "Detail"}}
            ]
        }}
        """
        
        try:
            # Di tahun 2026, gunakan gemini-2.0-flash yang merupakan standar terbaru
            response = self.client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=prompt,
                config={
                    "response_mime_type": "application/json"
                }
            )
            
            if not response.text:
                raise HTTPException(status_code=500, detail="AI gagal menghasilkan respon")

            data = json.loads(response.text)
            return TaskAIResponse(**data)
            
        except Exception as e:
            print(f"Kesalahan AI Service: {str(e)}")
            # Jika 2.0 tidak ditemukan, sistem akan memberikan pesan yang lebih jelas
            raise HTTPException(
                status_code=500, 
                detail=f"Gagal memproses instruksi dengan AI: {str(e)}"
            )

    async def audit_evidence(self, subtask_desc: str, image_bytes: bytes) -> dict:
        """Menganalisis screenshot dan membandingkannya dengan deskripsi tugas."""
        prompt = f"""
        Anda adalah Auditor Kode/UI. 
        Tugas: {subtask_desc}

        Instruksi Audit:
        1. Lihat gambar yang diunggah.
        2. Periksa apakah gambar tersebut menunjukkan bukti pengerjaan tugas di atas.
        3. Jika itu kode, apakah terlihat benar? Jika itu UI, apakah komponennya lengkap?
        
        Keluaran harus JSON:
        {{
            "is_valid": true/false,
            "confidence_score": 0-100,
            "feedback": "Alasan singkat kenapa diterima atau ditolak"
        }}
        """
        
        try:
            # --- PERBAIKAN DI SINI ---
            # Menggunakan types.Part untuk membungkus data bytes
            response = self.client.models.generate_content(
                model="gemini-2.5-flash", # Samakan model agar konsisten
                contents=[
                    prompt,
                    types.Part.from_bytes(
                        data=image_bytes, 
                        mime_type="image/png"
                    )
                ],
                config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Error Audit Visual: {e}")
            raise HTTPException(status_code=500, detail=f"AI Auditor Gagal: {str(e)}")