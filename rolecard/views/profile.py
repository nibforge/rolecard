"""Master profile: upload a CV, review and edit the profile, delete it."""

from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from rolecard import get_db
from rolecard.ai import AIError
from rolecard.services import profile as svc
from rolecard.services.profile_schema import LIST_FIELDS, SECTIONS, from_form
from rolecard.views import current_provider

bp = Blueprint("profile", __name__, url_prefix="/profile")

MAX_FIELD_ERRORS = 10
MAX_PATH_SHOWN = 80  # paths come from the AI and live in the session cookie (4 KB)
# Tabs of the one profile form: hiding a tab never drops its fields from the form.
TABS = ("basics", "experience", "projects", "education", "languages", "skills")


def _tab(name: str | None) -> str:
    return name if name in TABS else "basics"


def _error_tab(errors: dict) -> str:
    """The tab holding the first field with an error (``experience-1-role`` → experience)."""
    first = next(iter(errors), "basics").split("-", 1)[0]
    return _tab(first)


def _render(data=None, errors=None, status=200, tab=None):
    db = get_db()
    stored = svc.get_profile(db)
    return render_template(
        "profile.html",
        profile=data if data is not None else svc.profile_data(db),
        stored=stored,
        errors=errors or {},
        sections=SECTIONS,
        list_fields=LIST_FIELDS,
        blank_entries={s: {f: [] if f in LIST_FIELDS else '' for f in fields}
                       for s, fields in SECTIONS.items()},
        has_provider=current_provider() is not None,
        tabs=TABS, tab=_tab(tab or request.args.get("tab")),
    ), status


@bp.get("")
def edit():
    return _render()


@bp.post("/upload")
def upload():
    db = get_db()
    if svc.get_profile(db) is not None and request.form.get("replace") != "1":
        flash("profile.error.confirm_replace", "error")
        return redirect(url_for("profile.edit"))
    provider = current_provider()
    if provider is None:
        flash("profile.error.no_provider", "error")
        return redirect(url_for("profile.edit"))
    upload_file = request.files.get("cv")
    try:
        if upload_file is None or not upload_file.filename:
            raise svc.ProfileError("empty")
        text = svc.extract_text(upload_file.filename, upload_file.read(svc.MAX_BYTES + 1))
        data = svc.extract_profile(text, provider)
        svc.save_profile(db, data, source_text=text, needs_review=True)
    except svc.ProfileError as exc:
        flash(exc.message_key, "error")
        return redirect(url_for("profile.edit"))
    except AIError as exc:
        current_app.logger.info("profile extraction failed: %s", exc.code)
        flash(exc.message_key, "error")
        for path, problem in exc.errors[:MAX_FIELD_ERRORS]:
            flash([path[:MAX_PATH_SHOWN], f"ai.problem.{problem}"], "campo")
        return redirect(url_for("profile.edit"))
    flash("profile.extracted", "aviso")
    return redirect(url_for("profile.edit"))


@bp.post("")
def save():
    data, errors = from_form(request.form)
    tab = _tab(request.form.get("tab"))
    if errors:
        return _render(data, errors, 400, _error_tab(errors))
    try:
        svc.save_profile(get_db(), data, needs_review=False)
    except svc.ProfileError as exc:
        return _render(data, {"form": exc.message_key}, 400, tab)
    flash("profile.saved", "exito")
    return redirect(url_for("profile.edit", tab=tab))


@bp.post("/delete")
def delete():
    svc.delete_profile(get_db())
    flash("profile.deleted", "exito")
    return redirect(url_for("profile.edit"))
