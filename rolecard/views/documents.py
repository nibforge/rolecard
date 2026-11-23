"""Tailored CV and cover letter of a job: generate, review sentence by sentence, mark
reviewed and export (PDF, print view)."""

from __future__ import annotations

import re
import unicodedata

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from rolecard import get_db
from rolecard.ai import AIError
from rolecard.i18n import current_language
from rolecard.models import Job
from rolecard.services import documents as svc
from rolecard.services import export_pdf, provenance
from rolecard.services.profile import get_profile, profile_data
from rolecard.views import current_provider

bp = Blueprint("documents", __name__, url_prefix="/jobs/<int:job_id>/documents")


def _job(job_id: int) -> Job:
    job = get_db().get(Job, job_id)
    if job is None:
        abort(404)
    return job


def _kind(kind: str) -> str:
    if kind not in svc.KINDS:
        abort(404)
    return kind


def _document(job: Job, kind: str):
    doc = svc.get_document(get_db(), job, _kind(kind))
    if doc is None:
        abort(404)
    # A GET never writes: the refreshed state is shown but only saved by a POST action.
    return svc.refresh(get_db(), doc, profile_data(get_db()), save=request.method == "POST")


def _context(job: Job, doc, error: str = "") -> dict:
    profile = profile_data(get_db())

    def source_text(path: str) -> str:
        return provenance.source_text(path, profile, "") or ""

    return {"job": job, "doc": doc, "content": doc.content, "error": error,
            "kinds": [k for k in svc.KINDS if svc.get_document(get_db(), job, k)],
            "blocked": svc.blocked_reason(doc), "source_text": source_text,
            "pending": provenance.unresolved(doc.content) + provenance.pending_offer(doc.content),
            "lines": export_pdf.lines(doc.kind, doc.content, doc.language),
            "substitutions": export_pdf.substitutions(doc.kind, doc.content, doc.language)}


def _render_review(job: Job, doc, error: str = "", status: int = 200):
    template = ("documents/_document.html" if request.headers.get("HX-Request")
                else "documents/review.html")
    return render_template(template, **_context(job, doc, error)), status


@bp.post("/<kind>")
def generate(job_id: int, kind: str):
    job, kind = _job(job_id), _kind(kind)
    db = get_db()
    replace = request.form.get("replace") == "1"
    if svc.get_document(db, job, kind) is not None and not replace:
        return redirect(url_for("documents.review", job_id=job.id, kind=kind))
    profile = get_profile(db)
    provider = current_provider()
    if profile is None:
        flash("job.unscored.no_profile", "aviso")
        return redirect(url_for("profile.edit"))
    if provider is None:
        flash("job.unscored.no_provider", "aviso")
        return redirect(url_for("settings.edit"))
    try:
        svc.generate(db, job, profile.data, provider, kind, current_language(),
                     replace=replace)
    except AIError as exc:
        db.rollback()
        current_app.logger.info("document generation failed: %s", exc.code)
        flash(exc.message_key, "error")
        return redirect(url_for("jobs.show", job_id=job.id))
    return redirect(url_for("documents.review", job_id=job.id, kind=kind))


@bp.get("/<kind>")
def review(job_id: int, kind: str):
    job = _job(job_id)
    return _render_review(job, _document(job, kind))


@bp.post("/<kind>/sentences/<sid>")
def sentence(job_id: int, kind: str, sid: str):
    job = _job(job_id)
    doc = _document(job, kind)
    try:
        svc.resolve_sentence(get_db(), doc, sid, request.form.get("action", ""),
                             request.form.get("text", ""))
    except svc.DocumentError as exc:
        return _render_review(job, doc, exc.message_key, 400)
    if request.headers.get("HX-Request"):
        return _render_review(job, doc)
    return redirect(url_for("documents.review", job_id=job.id, kind=kind))


@bp.post("/<kind>/review")
def mark_reviewed(job_id: int, kind: str):
    job = _job(job_id)
    doc = _document(job, kind)
    try:
        svc.mark_reviewed(get_db(), doc)
    except svc.DocumentError as exc:
        return _render_review(job, doc, exc.message_key, 400)
    flash("document.reviewed", "exito")
    return redirect(url_for("documents.review", job_id=job.id, kind=kind))


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:40].strip("-")


def filename(job: Job, kind: str) -> str:
    """``cv-<company>-<title>.pdf`` (or ``cover-letter-…``), ASCII only."""
    parts = ["cv" if kind == "cv" else "cover-letter", _slug(job.company), _slug(job.title)]
    return "-".join(p for p in parts if p) + ".pdf"


def _exportable(job_id: int, kind: str):
    """(job, doc, None) when it can be exported, else (job, doc, 409 response)."""
    job = _job(job_id)
    doc = _document(job, kind)
    reason = svc.blocked_reason(doc)
    if reason:
        return job, doc, _render_review(job, doc, f"document.blocked.{reason}", 409)
    return job, doc, None


@bp.get("/<kind>.pdf")
def pdf(job_id: int, kind: str):
    job, doc, blocked = _exportable(job_id, kind)
    if blocked:
        return blocked
    title = f"{job.title or ''} {job.company or ''}".strip()
    body = export_pdf.render(doc.kind, doc.content, doc.language, title)
    return Response(body, mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename(job, doc.kind)}"'})


@bp.get("/<kind>/print")
def print_view(job_id: int, kind: str):
    job, doc, blocked = _exportable(job_id, kind)
    if blocked:
        return blocked
    return render_template("documents/print.html", **_context(job, doc))
