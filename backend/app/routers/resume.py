
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, Depends
from pymongo.database import Database

from app.database import get_db
from app.services.fact_extractor import extract_facts
from app.services.fact_persistence import save_extracted_facts

from app.services.resume_parser import extract_resume_text
from app.services.resume_loader import load_resume_from_folder

router = APIRouter(
    prefix="/api/resume",
    tags=["Resume"],
)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


@router.post("/extract")
async def extract_resume(file: UploadFile = File(...)):
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are supported.",
        )

    # Read at most 5 MB + 1 byte to enforce the size limit.
    file_bytes = await file.read(MAX_FILE_SIZE + 1)

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File size must not exceed 5 MB.",
        )

    try:
        extracted_text = extract_resume_text(filename, file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Unable to read this document. Check that it is a valid PDF or DOCX.",
        )
    finally:
        await file.close()

    if not extracted_text.strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "No readable text was found. "
                "The PDF may be scanned and require OCR."
            ),
        )

    return {
        "filename": filename,
        "file_type": extension[1:],
        "character_count": len(extracted_text),
        "extracted_text": extracted_text,
        "status": "extracted_not_verified",
        "message": (
            "Text extracted successfully. "
            "No profile facts have been verified or saved."
        ),
    }

@router.post("/extract-from-folder")
def extract_from_folder():
    try:
        return load_resume_from_folder()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/extract-facts-from-folder")
def extract_facts_from_folder(
    db: Database = Depends(get_db),
):
    try:
        # Step 1: Read the resume from the resumes folder.
        resume = load_resume_from_folder()
        resume_text = resume.get("extracted_text", "")

        if not resume_text.strip():
            raise HTTPException(
                status_code=422,
                detail="No readable text found in the resume.",
            )

        # Step 2: Extract structured facts using Ollama.
        extracted = extract_facts(resume_text)

        # Step 3: Save facts as unverified in MongoDB.
        filename = resume.get("filename", "resume")

        saved = save_extracted_facts(
            db=db,
            extracted=extracted,
            evidence_source=filename,
        )

        return {
            "filename": filename,
            "extraction_status": "pending_review",
            "database_status": "unverified",
            "saved": saved,
            "extracted_counts": {
                "skills": len(extracted.get("skills", [])),
                "projects": len(extracted.get("projects", [])),
                "experiences": len(extracted.get("experiences", [])),
                "achievements": len(extracted.get("achievements", [])),
                "education": len(extracted.get("education", [])),
            },
            "message": (
                "Resume facts extracted and saved for review. "
                "No facts have been marked verified."
            ),
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        print(f"Resume fact extraction failed: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Resume fact extraction or database saving failed.",
        ) from exc
