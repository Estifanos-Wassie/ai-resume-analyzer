"""Bounded PDF extraction and application input limits."""

import fitz
from fastapi import HTTPException, UploadFile

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 20
MAX_RESUME_CHARACTERS = 50_000
MAX_JOB_DESCRIPTION_CHARACTERS = 20_000
READ_CHUNK_BYTES = 64 * 1024

# Parser diagnostics may contain document data; return fixed public errors instead.
fitz.TOOLS.mupdf_display_errors(False)
fitz.TOOLS.mupdf_display_warnings(False)


async def validate_inputs(file: UploadFile, job_description: str) -> tuple[str, str]:
    """Validate before provider use and close the upload on every handler path."""
    try:
        job_description = job_description.strip()
        if not job_description:
            raise HTTPException(422, "A nonempty job description is required.")
        if len(job_description) > MAX_JOB_DESCRIPTION_CHARACTERS:
            raise HTTPException(413, "Job description exceeds 20,000 characters.")
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(400, "Only PDF files are accepted.")

        content = bytearray()
        while True:
            chunk = await file.read(min(READ_CHUNK_BYTES, MAX_UPLOAD_BYTES + 1 - len(content)))
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, "Resume file exceeds 5 MiB.")
        if not content:
            raise HTTPException(400, "Resume file is empty. Upload a readable PDF.")

        return extract_resume_text(bytes(content)), job_description
    except OSError:
        raise HTTPException(400, "Resume file could not be read.") from None
    finally:
        await file.close()


def extract_resume_text(content: bytes) -> str:
    try:
        with fitz.open(stream=content, filetype="pdf") as document:
            if not document.is_pdf:
                raise HTTPException(400, "Resume file must be a readable PDF.")
            if document.needs_pass or document.is_encrypted or (
                document.metadata and document.metadata.get("encryption")
            ):
                raise HTTPException(422, "Encrypted or password-protected PDFs are unsupported. Upload an unencrypted PDF.")
            if document.page_count > MAX_PDF_PAGES:
                raise HTTPException(413, "Resume PDF exceeds 20 pages.")

            parts = []
            character_count = 0
            for page in document:
                text = page.get_text()
                character_count += len(text)
                if character_count > MAX_RESUME_CHARACTERS:
                    raise HTTPException(413, "Extracted resume text exceeds 50,000 characters.")
                parts.append(text)
            resume_text = "".join(parts)
    except (fitz.FileDataError, fitz.mupdf.FzErrorBase, RuntimeError, ValueError):
        raise HTTPException(400, "Resume PDF is corrupt or unreadable. Upload a readable PDF.") from None

    if not resume_text.strip():
        raise HTTPException(422, "A text-based PDF is required. Blank or image-only PDFs cannot be analyzed because OCR is unsupported.")
    return resume_text
