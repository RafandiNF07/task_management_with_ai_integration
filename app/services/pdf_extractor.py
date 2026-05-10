import pdfplumber
import io
from fastapi import HTTPException

class PDFExtractor:
    @staticmethod
    def extract_text(file_bytes: bytes) -> str:
        text_content = ""
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text_content += extracted
            return text_content
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Gagal mengekstrak PDF: {str(e)}")
