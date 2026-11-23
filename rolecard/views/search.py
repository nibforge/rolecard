"""Saved searches over the job sources: list, create, edit, run, delete and the bulk
"discard the unscored" and "score the added" actions."""

from __future__ import annotations

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from rolecard import config as cfg
from rolecard import get_db
from rolecard import sources as src
from rolecard.ai import AIError
from rolecard.i18n import current_language
from rolecard.models import Job, Search
from rolecard.services.prefilter import parse_words
from rolecard.services.profile import get_profile
from rolecard.services.scoring import SCORE_BATCH, score_job
from rolecard.services.search import run_search
from rolecard.services.tracking import set_status
from rolecard.views import current_provider

bp = Blueprint("search", __name__, url_prefix="/search")

MAX_FIELD = 200
REMOTE = ("any", "only", "exclude")
NEW_LISTED = 10


def _search(search_id: int) -> Search:
    search = get_db().get(Search, search_id)
    if search is None:
        abort(404)
    return search


def _settings() -> dict:
    return current_app.config["ROLECARD"]


def _form_of(search: Search | None) -> dict:
    if search is None:
        return {"name": "", "query": "", "location": "", "remote": "any",
                "sources": src.enabled(_settings()), "required": [], "excluded": []}
    return {"name": search.name, "query": search.query, "location": search.location,
            "remote": search.remote, "sources": list(search.sources),
            "required": list(search.required or []), "excluded": list(search.excluded or [])}


def _validate(form) -> tuple[dict, dict]:
    values = {k: form.get(k, "").strip() for k in ("name", "query", "location")}
    values["remote"] = form.get("remote", "any")
    values["sources"] = [n for n in cfg.SOURCE_NAMES if n in form.getlist("sources")]
    for key in ("required", "excluded"):
        values[key] = parse_words(form.get(key, ""))
    if not values["name"]:
        values["name"] = auto_name(values["query"], values["location"])
    errors = {}
    if not values["name"]:
        errors["name"] = "search.error.name"
    for key in ("name", "query", "location"):
        if len(values[key]) > MAX_FIELD:
            errors[key] = "search.error.too_long"
    if values["remote"] not in REMOTE:
        errors["remote"] = "search.error.remote"
    if not values["sources"]:
        errors["sources"] = "search.error.sources"
    return values, errors


def auto_name(query: str, location: str) -> str:
    """The name of a search saved without one: ``keywords · location``."""
    return " · ".join(part for part in (query, location) if part)[:MAX_FIELD]


def _pending(search: Search):
    return (get_db().query(Job)
            .filter(Job.search_id == search.id, Job.status == "new", Job.score.is_(None)))


def _summary_context(search: Search) -> dict:
    pending = _pending(search)
    return {"search": search, "unscored": pending.count(),
            "new_jobs": pending.order_by(Job.id.desc()).limit(NEW_LISTED).all()}


def _render(search: Search | None, form: dict, errors: dict, status=200):
    db = get_db()
    context = _summary_context(search) if search else {"search": None, "unscored": 0}
    return render_template(
        "search/index.html", form=form, errors=errors, remote_choices=REMOTE,
        sources=src.status(_settings()),
        searches=db.query(Search).order_by(Search.name).all(), **context,
    ), status


def _after_save(search: Search):
    """«Search now» saves and runs in one step; «Save» only saves."""
    if request.form.get("then") == "run":
        run_search(get_db(), search, _settings())
    else:
        flash("search.saved", "exito")
    return redirect(url_for("search.show", search_id=search.id))


@bp.get("")
def index():
    return _render(None, _form_of(None), {})


@bp.post("")
def create():
    values, errors = _validate(request.form)
    if errors:
        return _render(None, values, errors, 400)
    search = Search(**values)
    db = get_db()
    db.add(search)
    db.commit()
    return _after_save(search)


@bp.get("/<int:search_id>")
def show(search_id: int):
    search = _search(search_id)
    return _render(search, _form_of(search), {})


@bp.post("/<int:search_id>")
def update(search_id: int):
    search = _search(search_id)
    values, errors = _validate(request.form)
    if errors:
        return _render(search, values, errors, 400)
    for key, value in values.items():
        setattr(search, key, value)
    get_db().commit()
    return _after_save(search)


@bp.post("/<int:search_id>/run")
def run(search_id: int):
    search = _search(search_id)
    run_search(get_db(), search, _settings())
    if request.headers.get("HX-Request"):
        return render_template("search/_summary.html", **_summary_context(search))
    return redirect(url_for("search.show", search_id=search.id))


@bp.post("/<int:search_id>/delete")
def delete(search_id: int):
    """Delete the search; its offers stay on the board (``search_id`` is set to NULL)."""
    search = _search(search_id)
    db = get_db()
    db.query(Job).filter(Job.search_id == search.id).update({Job.search_id: None})
    db.delete(search)
    db.commit()
    flash("search.deleted", "exito")
    return redirect(url_for("search.index"))


@bp.post("/<int:search_id>/discard-unscored")
def discard_unscored(search_id: int):
    """Move this search's unscored ``new`` offers to ``discarded`` (logged one by one)."""
    search = _search(search_id)
    db = get_db()
    for job in _pending(search).all():
        set_status(db, job, "discarded")
    flash("search.discarded", "exito")
    return redirect(url_for("search.show", search_id=search.id))


@bp.post("/<int:search_id>/score")
def score_added(search_id: int):
    """Score up to ``SCORE_BATCH`` of this search's unscored ``new`` offers with the F1
    flow; the first AI error stops the batch (what was scored stays)."""
    search = _search(search_id)
    db = get_db()
    profile, provider = get_profile(db), current_provider()
    if profile is None or provider is None:
        flash("job.unscored.no_profile" if profile is None else "job.unscored.no_provider",
              "aviso")
        return redirect(url_for("search.show", search_id=search.id))
    jobs = _pending(search).order_by(Job.id).limit(SCORE_BATCH).all()
    if not jobs:
        flash("search.none_to_score", "aviso")
        return redirect(url_for("search.show", search_id=search.id))
    for job in jobs:
        try:
            score_job(db, job, profile.data, provider, current_language())
        except AIError as exc:
            db.rollback()
            current_app.logger.info("scoring failed: %s", exc.code)
            flash(exc.message_key, "error")
            break
        except Exception:
            db.rollback()  # what was scored before stays; the error page takes over
            raise
    else:
        flash("search.scored", "exito")
    return redirect(url_for("search.show", search_id=search.id))

