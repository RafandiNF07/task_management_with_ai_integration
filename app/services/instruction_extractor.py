import io
import zipfile
import xml.etree.ElementTree as ET

import pdfplumber
from fastapi import HTTPException


class InstructionExtractor:
    @staticmethod
    def extract_text(filename: str | None, file_bytes: bytes | None, instruction_text: str | None = None) -> str:
        parts: list[str] = []

        if instruction_text and instruction_text.strip():
            parts.append(instruction_text.strip())

        if file_bytes:
            if not filename:
                raise HTTPException(status_code=400, detail="Nama file diperlukan untuk memproses instruksi")

            lowered = filename.lower()
            if lowered.endswith(".pdf"):
                parts.append(InstructionExtractor._extract_pdf_text(file_bytes))
            elif lowered.endswith(".docx"):
                parts.append(InstructionExtractor._extract_docx_text(file_bytes))
            else:
                raise HTTPException(status_code=400, detail="Hanya file PDF atau DOCX yang diizinkan")

        combined = "\n\n".join(part for part in parts if part).strip()
        if not combined:
            raise HTTPException(status_code=400, detail="Isi instruksi tidak boleh kosong")
        return combined

    @staticmethod
    def _extract_pdf_text(file_bytes: bytes) -> str:
        try:
            text_content = ""
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text_content += extracted + "\n"
            return text_content.strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Gagal mengekstrak PDF: {str(e)}")

    @staticmethod
    def _extract_docx_text(file_bytes: bytes) -> str:
        try:
            namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
                document_xml = archive.read("word/document.xml")

            root = ET.fromstring(document_xml)
            paragraphs: list[str] = []

            for paragraph in root.findall(".//w:p", namespace):
                text_parts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
                paragraph_text = "".join(text_parts).strip()
                if paragraph_text:
                    paragraphs.append(paragraph_text)

            return "\n".join(paragraphs).strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Gagal mengekstrak DOCX: {str(e)}")