"""Job offers: add, view, edit, score, track and delete."""

from __future__ import annotations

from urllib.parse import urlsplit

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from rolecard import get_db
from rolecard.ai import AIError
from rolecard.i18n import current_language
from rolecard.models import STATUSES, Job
from rolecard.services import documents as docs_svc
from rolecard.services import jobs as svc
from rolecard.services import provenance
from rolecard.services.board import BoardFilters
from rolecard.services.offers_list import PER_PAGE, ListParams, list_page
from rolecard.services.profile import get_profile
from rolecard.services.scoring import SCORE_BATCH, score_job
from rolecard.services.tracking import TrackingError, parse_follow_up, set_status, set_tracking
from rolecard.views import current_provider, local_now
from rolecard.views.nav import remember_offers_view

bp = Blueprint("jobs", __name__, url_prefix="/jobs")


def _job(job_id: int) -> Job:
    job = get_db().get(Job, job_id)
    if job is None:
        abort(404)
    return job


def _doc_state(doc) -> dict:
    """Review state of a document for the job page: blocked reason and pending count."""
    return {"blocked": docs_svc.blocked_reason(doc),
            "pending": provenance.unresolved(doc.content)
            + provenance.pending_offer(doc.content)}


def _show(job: Job, errors: dict | None = None, status: int = 200):
    documents = {k: docs_svc.get_document(get_db(), job, k) for k in docs_svc.KINDS}
    return render_template(
        "jobs/show.html", job=job, statuses=STATUSES, errors=errors or {},
        has_profile=get_profile(get_db()) is not None,
        has_provider=current_provider() is not None,
        documents=documents, doc_state={k: _doc_state(d) for k, d in documents.items() if d},
        tab="history" if request.args.get("tab") == "history" else "description",
        doc_language=docs_svc.doc_language(job, current_language()),
        doc_languages=docs_svc.DOC_LANGUAGES, today=local_now().date(),
    ), status


def _saved(key: str) -> None:
    """Flash a save, except for an autosave (htmx): its field shows "Saved" instead, and a
    banner on every change would push the page down."""
    if not request.headers.get("HX-Request"):
        flash(key, "exito")


def _score(job: Job) -> None:
    """Score if there is a profile and a provider; failures become a message."""
    db = get_db()
    profile = get_profile(db)
    provider = current_provider()
    if profile is None or provider is None:
        flash("job.unscored.no_profile" if profile is None else "job.unscored.no_provider",
              "aviso")
        return
    try:
        score_job(db, job, profile.data, provider, current_language())
    except AIError as exc:
        db.rollback()
        current_app.logger.info("scoring failed: %s", exc.code)
        flash(exc.message_key, "error")


@bp.get("")
def index():
    """The list view: a dense table with the board's filters, order and pages."""
    db = get_db()
    filters = BoardFilters.from_args(request.args)
    params = ListParams.from_args(request.args)
    today = local_now().date()
    html = render_template(
        "jobs/index.html", filters=filters, params=params, today=today,
        result=list_page(db, filters, params, today), per_page_options=PER_PAGE,
        score_batch=SCORE_BATCH,
        statuses=STATUSES, has_jobs=db.query(Job.id).first() is not None,
    )
    return remember_offers_view(make_response(html), "list")


@bp.get("/new")
def new():
    return render_template("jobs/new.html", form={}, errors={}, duplicate=None)


@bp.post("")
def create():
    form = {k: request.form.get(k, "").strip() for k in ("text", "url", "title", "company")}
    errors = svc.validate_fields(form["text"], form["url"], form["title"], form["company"])
    if errors:
        return render_template("jobs/new.html", form=form, errors=errors, duplicate=None), 400
    result = svc.create_job(get_db(), **form)
    if isinstance(result, svc.Duplicate):
        return render_template("jobs/new.html", form=form, errors={},
                               duplicate=result.job), 409
    _score(result)
    return redirect(url_for("jobs.show", job_id=result.id))


@bp.get("/<int:job_id>")
def show(job_id: int):
    return _show(_job(job_id))


@bp.post("/<int:job_id>")
def update(job_id: int):
    job = _job(job_id)
    form = {k: request.form.get(k, "").strip() for k in ("title", "company", "location", "url")}
    text = request.form.get("text")  # None: a form without the text field keeps it
    text = text.strip() if text is not None else None
    errors = svc.validate_fields(text, form["url"], form["title"], form["company"],
                                 form["location"])
    if errors:
        return _show(job, errors, 400)
    result = svc.update_job(get_db(), job, text=text, **form)
    if isinstance(result, svc.Duplicate):
        taken = "text" if text and result.job.text_key == svc.text_key(text) else "url"
        return _show(job, {taken: f"job.error.{taken}_taken"}, 409)
    _saved("job.saved")
    return redirect(url_for("jobs.show", job_id=job.id))


@bp.post("/<int:job_id>/score")
def rescore(job_id: int):
    job = _job(job_id)
    _score(job)
    return redirect(url_for("jobs.show", job_id=job.id))


@bp.post("/<int:job_id>/status")
def status(job_id: int):
    job = _job(job_id)
    try:
        set_status(get_db(), job, request.form.get("status", ""))
    except TrackingError:
        abort(400)
    return redirect(url_for("jobs.show", job_id=job.id))


@bp.post("/<int:job_id>/tracking")
def tracking(job_id: int):
    job = _job(job_id)
    try:
        follow_up = parse_follow_up(request.form.get("follow_up_on", ""))
        set_tracking(get_db(), job, notes=request.form.get("notes", ""), follow_up_on=follow_up)
    except TrackingError as exc:
        return _show(job, {"tracking": exc.key}, 400)
    _saved("tracking.saved")
    return redirect(url_for("jobs.show", job_id=job.id))


@bp.post("/<int:job_id>/language")
def language(job_id: int):
    """Force the language of this job's documents ("" = automatic)."""
    job = _job(job_id)
    lang = request.form.get("language", "")
    if lang and lang not in docs_svc.DOC_LANGUAGES:
        abort(400)
    job.doc_language = lang
    get_db().commit()
    _saved("job.documents.language_saved")
    return redirect(url_for("jobs.show", job_id=job.id))


@bp.post("/<int:job_id>/delete")
def delete(job_id: int):
    svc.delete_job(get_db(), _job(job_id))
    flash("job.deleted", "exito")
    return redirect(url_for("dashboard.index"))


MAX_BULK = max(PER_PAGE)  # one page of the list at most
BULK_ACTIONS = ("score", "status", "discard")


def _bulk_ids() -> list[int]:
    raw = request.form.getlist("ids")
    if len(raw) > MAX_BULK or not all(i.isascii() and i.isdigit() and len(i) < 10 for i in raw):
        abort(400)
    return list(dict.fromkeys(int(i) for i in raw))


def _back_to_list():
    """Back to the list page the form came from: only ``/jobs`` with its query string."""
    target = urlsplit(request.form.get("next", ""))
    safe = not (target.scheme or target.netloc) and target.path == url_for("jobs.index")
    query = f"?{target.query}" if safe and target.query else ""
    return redirect(url_for("jobs.index") + query)


@bp.post("/bulk")
def bulk():
    """Act on the offers ticked in the list: score (``SCORE_BATCH`` at most), set a
    status or discard. Every status change goes through ``set_status`` (history)."""
    action, value = request.form.get("action", ""), request.form.get("value", "")
    if action not in BULK_ACTIONS or (action == "status" and value not in STATUSES):
        abort(400)
    ids = _bulk_ids()
    db = get_db()
    jobs = db.query(Job).filter(Job.id.in_(ids)).order_by(Job.id).all() if ids else []
    if not jobs:
        flash("bulk.none_selected", "aviso")
    elif action == "score":
        _bulk_score([job for job in jobs if job.score is None][:SCORE_BATCH])
    else:
        for job in jobs:
            set_status(db, job, "discarded" if action == "discard" else value)
        flash("bulk.discarded" if action == "discard" else "bulk.status_changed", "exito")
    return _back_to_list()


def _bulk_score(jobs: list[Job]) -> None:
    """The F1 flow on each offer; the first AI error stops (what was scored stays)."""
    db = get_db()
    profile, provider = get_profile(db), current_provider()
    if not jobs or profile is None or provider is None:
        key = ("bulk.none_to_score" if not jobs else
               "job.unscored.no_profile" if profile is None else "job.unscored.no_provider")
        flash(key, "aviso")
        return
    for job in jobs:
        try:
            score_job(db, job, profile.data, provider, current_language())
        except AIError as exc:
            db.rollback()
            current_app.logger.info("scoring failed: %s", exc.code)
            flash(exc.message_key, "error")
            return
        except Exception:
            db.rollback()
            raise
    flash("bulk.scored", "exito")
