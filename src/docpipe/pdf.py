"""PDF text extraction (text-based PDFs only) and content hashing."""
from __future__ import annotations

import hashlib
import io

import pdfplumber


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def extract_text(content: bytes) -> str:
    """Return the concatenated text of a text-based PDF.

    No OCR is performed; scanned/image-only PDFs yield little or no text.
    """
    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)
