"""Home page: this week's numbers, the work for today, the best unsent offers, the saved
searches and the funnel; the first steps while something is missing."""

from flask import Blueprint, render_template

from rolecard import get_db
from rolecard.models import Job, Search
from rolecard.services import home
from rolecard.services.profile import get_profile
from rolecard.services.stats import week_numbers
from rolecard.views import current_provider, local_now

bp = Blueprint("dashboard", __name__)


@bp.get("/")
def index() -> str:
    db = get_db()
    now = local_now()
    has_jobs = db.query(Job.id).first() is not None
    return render_template(
        "dashboard.html",
        has_provider=current_provider() is not None,
        has_profile=get_profile(db) is not None,
        has_jobs=has_jobs,
        week=week_numbers(db, now) if has_jobs else None,
        today_work=home.for_today(db, now.date()) if has_jobs else None,
        best=home.best_unsent(db) if has_jobs else [],
        searches=db.query(Search).order_by(Search.name).all() if has_jobs else [],
        funnel=home.funnel(db, now) if has_jobs else [],
        today=now.date(),
    )
