
from pathlib import Path

from app.services.resume_parser import extract_resume_text

# backend/resumes/
RESUME_DIR = Path(__file__).resolve().parents[2] / "resumes"


def load_resume_from_folder() -> dict:
    if not RESUME_DIR.exists():
        raise FileNotFoundError("The resumes folder does not exist.")

    files = [
        path
        for path in RESUME_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".pdf", ".docx"}
    ]

    if not files:
        raise FileNotFoundError(
            "No PDF or DOCX resume found in the resumes folder."
        )

    if len(files) > 1:
        raise ValueError(
            "Multiple resumes found. Keep only one resume in the folder."
        )

    resume_path = files[0]
    file_bytes = resume_path.read_bytes()

    if not file_bytes:
        raise ValueError("The resume file is empty.")

    if len(file_bytes) > 5 * 1024 * 1024:
        raise ValueError("Resume must not exceed 5 MB.")

    text = extract_resume_text(resume_path.name, file_bytes)

    if not text.strip():
        raise ValueError(
            "No readable text found. The PDF may require OCR."
        )

    return {
        "filename": resume_path.name,
        "file_path": str(resume_path),
        "character_count": len(text),
        "extracted_text": text,
        "status": "extracted_not_verified",
    }
