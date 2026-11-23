"""Tailored documents of a job: generate, re-check, resolve sentences, mark reviewed.

A document can be exported only when no sentence is unsourced AND the user has marked
it reviewed. Any change to its sentences clears the review.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rolecard.ai import AIProvider
from rolecard.ai.doc_schema import CV_SCHEMA, LETTER_SCHEMA
from rolecard.ai.prompts import cv_prompt, letter_prompt
from rolecard.models import Document, Job, utcnow
from rolecard.services import provenance
from rolecard.services.tailoring import build_cv, build_letter, structure
from rolecard.services.tracking import set_status

KINDS = ("cv", "letter")
# Snapshot key of the copied profile facts (never a valid source path).
STRUCTURE = "_structure"
DOC_LANGUAGES = ("es", "en")


class DocumentError(Exception):
    """``code`` maps to the i18n key ``document.error.<code>``."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code

    @property
    def message_key(self) -> str:
        return f"document.error.{self.code}"


def doc_language(job: Job, ui_lang: str) -> str:
    """Forced language for this job, else the offer's (if es/en), else the UI's."""
    for lang in (job.doc_language, job.language, ui_lang):
        if lang in DOC_LANGUAGES:
            return lang
    return "en"


def get_document(db: Session, job: Job, kind: str) -> Document | None:
    return db.scalars(select(Document).filter_by(job_id=job.id, kind=kind)).one_or_none()


def generate(db: Session, job: Job, profile: dict, provider: AIProvider, kind: str,
             ui_lang: str, replace: bool = False) -> Document:
    """Ask the AI, build and store the document (raises ``AIError``: nothing is saved)."""
    if kind not in KINDS:
        raise DocumentError("kind")
    existing = get_document(db, job, kind)
    if existing is not None and not replace:
        raise DocumentError("exists")
    lang = doc_language(job, ui_lang)
    if kind == "cv":
        answer = provider.complete_json(cv_prompt(profile, job.text, lang), CV_SCHEMA)
        content = build_cv(profile, answer)
    else:
        answer = provider.complete_json(letter_prompt(profile, job.text, lang), LETTER_SCHEMA)
        content = build_letter(profile, answer, lang, job.text)
    doc = existing or Document(job_id=job.id, kind=kind)
    doc.language = lang
    doc.content = content
    doc.source_snapshot = {**provenance.snapshot(content["sentences"], profile),
                           STRUCTURE: structure(profile, kind)}
    doc.reviewed_at = None
    db.add(doc)
    db.commit()
    return doc


def _save(db: Session, doc: Document, content: dict) -> None:
    doc.content = content
    flag_modified(doc, "content")
    db.commit()


def refresh(db: Session, doc: Document, profile: dict, save: bool = True) -> Document:
    """Re-check the sentences against the CURRENT profile (and the offer for a letter).

    With ``save=False`` (pages read with GET) the result stays in memory: it is never
    committed, and the request's session is closed without a commit."""
    content = deepcopy(doc.content)
    provenance.check(content, profile, doc.source_snapshot, doc.job.text,
                     allow_offer=doc.kind == "letter")
    old = doc.source_snapshot.get(STRUCTURE)
    if old is not None and old != structure(profile, doc.kind):
        content["structure_changed"] = True
    if content != doc.content:
        if (provenance.unresolved(content) or provenance.pending_offer(content)
                or content.get("structure_changed")):
            doc.reviewed_at = None
        if save:
            _save(db, doc, content)
        else:
            doc.content = content
    return doc


def resolve_sentence(db: Session, doc: Document, sid: str, action: str,
                     text: str = "") -> dict:
    content = deepcopy(doc.content)
    sentence = content["sentences"].get(sid)
    if sentence is None:
        raise DocumentError("sentence")
    try:
        provenance.resolve_sentence(sentence, action, text[:600])
    except ValueError as exc:
        raise DocumentError("action") from exc
    doc.reviewed_at = None
    _save(db, doc, content)
    return sentence


def blocked_reason(doc: Document) -> str | None:
    """Why the export is blocked (``structure_changed`` | ``unresolved`` |
    ``offer_unconfirmed`` | ``not_reviewed``), or None."""
    if doc.content.get("structure_changed"):
        return "structure_changed"
    if provenance.unresolved(doc.content):
        return "unresolved"
    if provenance.pending_offer(doc.content):
        return "offer_unconfirmed"
    if doc.reviewed_at is None:
        return "not_reviewed"
    return None


def mark_reviewed(db: Session, doc: Document, now: datetime | None = None) -> None:
    """Mark reviewed; a reviewed CV moves a ``new`` job to ``prepared``."""
    reason = blocked_reason(doc)
    if reason in ("structure_changed", "unresolved", "offer_unconfirmed"):
        raise DocumentError(reason)
    now = now or utcnow()
    doc.reviewed_at = now
    if doc.kind == "cv" and doc.job.status == "new":
        set_status(db, doc.job, "prepared", now)
    db.commit()
