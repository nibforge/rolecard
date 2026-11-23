"""The app shell's navigation: sections, their counters and which one is active."""

from __future__ import annotations

from dataclasses import dataclass

from flask import Flask, Response, request
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from rolecard import get_db
from rolecard.models import Job, Search

OFFERS_VIEW_COOKIE = "offers_view"
OFFERS_VIEW_MAX_AGE = 365 * 24 * 3600

# The active section is decided by the view, not the URL: the job detail, its CV and its
# letter belong to Offers. A template may still set ``section`` itself.
SECTION_BY_BLUEPRINT = {
    "dashboard": "home",
    "board": "offers",
    "jobs": "offers",
    "documents": "offers",
    "search": "searches",
    "profile": "profile",
    "settings": "settings",
}


@dataclass(frozen=True)
class NavItem:
    section: str
    endpoint: str
    label_key: str
    icon: str
    count: int | None = None


def offers_endpoint(app: Flask) -> str:
    """Offers opens the last view used (board or list), remembered in a cookie."""
    wants_list = request.cookies.get(OFFERS_VIEW_COOKIE) == "list"
    return "jobs.index" if wants_list and "jobs.index" in app.view_functions else "board.index"


def remember_offers_view(response: Response, view: str) -> Response:
    """Offers in the menu reopens this view ('board' or 'list')."""
    response.set_cookie(OFFERS_VIEW_COOKIE, view, max_age=OFFERS_VIEW_MAX_AGE,
                        httponly=True, samesite="Lax")
    return response


def _counts() -> tuple[int | None, int | None]:
    try:
        db = get_db()
        offers = db.query(func.count(Job.id)).filter(Job.status != "discarded").scalar()
        return offers, db.query(func.count(Search.id)).scalar()
    except SQLAlchemyError:  # an error page must still render
        return None, None


def nav_items(app: Flask) -> list[NavItem]:
    offers, searches = _counts()
    items = [
        NavItem("home", "dashboard.index", "nav.home", "home"),
        NavItem("offers", offers_endpoint(app), "nav.offers", "offers", offers),
        NavItem("searches", "search.index", "nav.searches", "search", searches),
        NavItem("profile", "profile.edit", "nav.profile", "profile"),
    ]
    return [item for item in items if item.endpoint in app.view_functions]


def current_section() -> str:
    return SECTION_BY_BLUEPRINT.get(request.blueprint or "", "")
