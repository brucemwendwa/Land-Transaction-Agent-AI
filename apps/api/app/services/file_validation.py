from __future__ import annotations

from pathlib import Path

SUPPORTED_DOCUMENT_TYPES = {
    "application/pdf": {".pdf"},
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/webp": {".webp"},
}


def validate_declared_file(*, filename: str, content_type: str) -> str | None:
    extension = Path(filename).suffix.lower()
    allowed_extensions = SUPPORTED_DOCUMENT_TYPES.get(content_type)
    if not allowed_extensions:
        return "Unsupported document type. Upload PDF, PNG, JPG, JPEG, or WEBP files only."
    if extension not in allowed_extensions:
        return f"File extension {extension or '(none)'} does not match declared type {content_type}."
    return None


def validate_file_signature(*, content: bytes, content_type: str) -> str | None:
    if not content:
        return "Uploaded file is empty."
    if content_type == "application/pdf" and not content.startswith(b"%PDF"):
        return "File content is not a valid PDF signature."
    if content_type == "image/png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "File content is not a valid PNG signature."
    if content_type == "image/jpeg" and not content.startswith(b"\xff\xd8\xff"):
        return "File content is not a valid JPEG signature."
    if content_type == "image/webp" and not (content.startswith(b"RIFF") and content[8:12] == b"WEBP"):
        return "File content is not a valid WEBP signature."
    return None
