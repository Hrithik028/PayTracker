from __future__ import annotations

import hashlib
import io
import uuid
from dataclasses import dataclass
from pathlib import Path

import fitz
from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import AppSettings, PROJECT_ROOT, project_path


ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MIME_BY_FORMAT = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpeg": "image/jpeg",
}


@dataclass(slots=True)
class ValidatedFile:
    content: bytes
    detected_format: str
    extension: str
    sha256: str
    original_filename: str


async def validate_upload(upload: UploadFile, settings: AppSettings) -> ValidatedFile:
    original = Path(upload.filename or "upload").name
    extension = Path(original).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Only PDF, PNG, JPG and JPEG files are supported")

    content = await upload.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if not content:
        raise HTTPException(400, "The uploaded file is empty")
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds the {settings.max_upload_mb} MB limit")

    detected = _detect_and_verify(content)
    allowed_for_extension = {
        ".pdf": {"pdf"},
        ".png": {"png"},
        ".jpg": {"jpeg"},
        ".jpeg": {"jpeg"},
    }
    if detected not in allowed_for_extension[extension]:
        raise HTTPException(400, "File contents do not match the file extension")

    return ValidatedFile(
        content=content,
        detected_format=detected,
        extension=".jpg" if detected == "jpeg" else f".{detected}",
        sha256=hashlib.sha256(content).hexdigest(),
        original_filename=original[:255],
    )


def _detect_and_verify(content: bytes) -> str:
    if content.startswith(b"%PDF-"):
        try:
            with fitz.open(stream=content, filetype="pdf") as document:
                if document.page_count < 1:
                    raise ValueError("PDF has no pages")
                document.load_page(0)
            return "pdf"
        except Exception as exc:
            raise HTTPException(400, "The PDF is corrupted or unsupported") from exc

    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
            detected = (image.format or "").lower()
            if detected in {"png", "jpeg"}:
                return detected
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(400, "The image is corrupted or unsupported") from exc
    raise HTTPException(400, "Unsupported file contents")


def store_validated_file(file: ValidatedFile, subdirectory: str) -> str:
    if subdirectory not in {"payslips", "timing-screenshots"}:
        raise ValueError("Invalid upload destination")
    destination = project_path(Path("uploads") / subdirectory)
    destination.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{file.extension}"
    absolute = (destination / filename).resolve()
    absolute.relative_to(destination.resolve())
    absolute.write_bytes(file.content)
    return absolute.relative_to(PROJECT_ROOT).as_posix()


def resolve_stored_file(relative_path: str) -> Path:
    path = project_path(relative_path)
    uploads_root = project_path("uploads")
    try:
        path.relative_to(uploads_root)
    except ValueError as exc:
        raise HTTPException(404, "Document not found") from exc
    if not path.is_file():
        raise HTTPException(404, "Document not found")
    return path

