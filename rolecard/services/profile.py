"""CV text extraction, AI extraction of the profile and its storage.

The uploaded file is never stored: only its text. Errors carry a code that maps to the
i18n key ``profile.error.<code>``; on any error the stored profile is left untouched.
"""

from __future__ import annotations

import io
import zipfile

from sqlalchemy import delete
from sqlalchemy.orm import Session

from rolecard.ai import AIProvider
from rolecard.ai.prompts import MAX_DOCUMENT, profile_prompt
from rolecard.ai.schema import SchemaError
from rolecard.encoding import fix_mojibake
from rolecard.models import Document, Profile, utcnow
from rolecard.services.profile_schema import PROFILE_SCHEMA, empty_profile, normalize

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 40
MAX_UNZIPPED = 60 * 1024 * 1024
MIN_TEXT = 40


class ProfileError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code

    @property
    def message_key(self) -> str:
        return f"profile.error.{self.code}"


def extract_text(filename: str, data: bytes) -> str:
    """Plain text of a PDF or DOCX CV (raises ``ProfileError``)."""
    name = (filename or "").lower()
    if not data:
        raise ProfileError("empty")
    if len(data) > MAX_BYTES:
        raise ProfileError("too_large")
    if name.endswith(".pdf") and data.startswith(b"%PDF"):
        text = _pdf_text(data)
    elif name.endswith(".docx") and data.startswith(b"PK"):
        text = _docx_text(data)
    else:
        raise ProfileError("type")
    text = "\n".join(line.rstrip() for line in fix_mojibake(text).splitlines()).strip()
    if len(text) < MIN_TEXT:
        raise ProfileError("no_text")
    return text


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ProfileError("corrupt")
        pages = reader.pages[:MAX_PAGES]
        return "\n".join(page.extract_text() or "" for page in pages)
    except ProfileError:
        raise
    except (PyPdfError, ValueError, KeyError, TypeError, OSError) as exc:
        raise ProfileError("corrupt") from exc


def _docx_text(data: bytes) -> str:
    from docx import Document

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(info.file_size for info in archive.infolist()) > MAX_UNZIPPED:
                raise ProfileError("too_large")
        doc = Document(io.BytesIO(data))
    except ProfileError:
        raise
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        raise ProfileError("corrupt") from exc
    lines = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            lines.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(lines)


def extract_profile(text: str, provider: AIProvider) -> dict:
    """Ask the AI for the structured profile; the answer is validated strictly. A CV
    longer than the prompt takes is refused, never cut."""
    if len(text) > MAX_DOCUMENT:
        raise ProfileError("text_too_long")
    data = provider.complete_json(profile_prompt(text), PROFILE_SCHEMA)
    return normalize(data)


def get_profile(db: Session) -> Profile | None:
    return db.get(Profile, 1)


def profile_data(db: Session) -> dict:
    profile = get_profile(db)
    return profile.data if profile else empty_profile()


def save_profile(db: Session, data: dict, *, source_text: str | None = None,
                 needs_review: bool = False) -> Profile:
    """Store the profile (validated again here) in the single profile row."""
    try:
        data = normalize(data)
    except SchemaError as exc:
        raise ProfileError("too_long") from exc
    profile = get_profile(db) or Profile(id=1, source_text="")
    profile.data = data
    if source_text is not None:
        profile.source_text = source_text
    profile.needs_review = needs_review
    profile.updated_at = utcnow()
    db.add(profile)
    db.commit()
    return profile


def delete_profile(db: Session) -> None:
    """Delete the profile AND every tailored document (they are derived from it)."""
    db.execute(delete(Document))
    profile = get_profile(db)
    if profile is not None:
        db.delete(profile)
    db.commit()
