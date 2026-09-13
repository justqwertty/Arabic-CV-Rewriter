"""Text extraction for uploaded CV files.

Text-layer extraction only - no OCR. A scanned (image-only) PDF produces no
text and is reported as such rather than silently returning nothing.
"""
from __future__ import annotations

import io

from docx import Document
from pypdf import PdfReader


class ExtractionError(RuntimeError):
    """The uploaded file could not be turned into usable text."""


def extract_text(file_bytes: bytes, ext: str) -> str:
    ext = ext.lower()
    if ext == ".pdf":
        text = _extract_pdf(file_bytes)
    elif ext == ".docx":
        text = _extract_docx(file_bytes)
    else:
        raise ExtractionError(f"Unsupported file type: {ext or 'unknown'}")

    text = text.strip()
    if not text:
        raise ExtractionError(
            "No selectable text found in that file — this looks like a "
            "scanned image, which isn't supported yet."
        )
    return text


def _extract_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception as exc:  # noqa: BLE001 - pypdf raises several error types
        raise ExtractionError(f"Could not read that PDF: {exc}") from exc

    if reader.is_encrypted:
        raise ExtractionError(
            "That PDF is password-protected — remove the password and try again."
        )

    try:
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError(f"Could not read that PDF: {exc}") from exc

    return "\n\n".join(pages)


def _extract_docx(file_bytes: bytes) -> str:
    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as exc:  # noqa: BLE001 - python-docx raises several error types
        raise ExtractionError(f"Could not read that Word file: {exc}") from exc

    return "\n".join(p.text for p in doc.paragraphs)
