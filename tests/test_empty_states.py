from datetime import UTC, date, datetime

import pytest

from rolecard import get_db
from rolecard.ai import FakeProvider
from rolecard.models import Job
from rolecard.services.profile import save_profile
from tests.helpers import PROFILE

EN = {"Accept-Language": "en"}


def page(client):
    return client.get("/", headers=EN).get_data(as_text=True)


def set_provider(app, present):
    app.config["AI_PROVIDER_FACTORY"] = (lambda: FakeProvider([])) if present else (lambda: None)


def add_job(app, **fields):
    with app.app_context():
        db = get_db()
        db.add(Job(text="offer", text_key="k1", title="Backend <i>dev</i>", **fields))
        db.commit()


def test_fresh_install_shows_three_steps(app, client):
    set_provider(app, False)
    html = page(client)
    for text in ("Set up the AI", "Upload your CV", "Add your first offer"):
        assert text in html
    assert 'href="/settings"' in html and 'href="/profile"' in html and 'href="/jobs/new"' in html
    assert "This week" not in html


@pytest.mark.parametrize(
    ("provider", "profile", "missing", "present"),
    [
        (True, False, "Upload your CV", "Set up the AI"),
        (False, True, "Set up the AI", "Upload your CV"),
    ],
)
def test_only_missing_steps_are_shown(app, client, provider, profile, missing, present):
    set_provider(app, provider)
    if profile:
        with app.app_context():
            save_profile(get_db(), PROFILE)
    html = page(client)
    assert missing in html
    assert f"<h2>{present}</h2>" not in html


def test_ready_app_shows_week_and_follow_ups(app, client):
    set_provider(app, True)
    app.config["CLOCK"] = lambda: datetime(2026, 11, 20, 12, tzinfo=UTC)
    with app.app_context():
        save_profile(get_db(), PROFILE)
    add_job(app, follow_up_on=date(2026, 11, 17), status="sent", score=86,
            created_at=datetime(2026, 11, 18, tzinfo=UTC))
    html = page(client)
    assert "First steps" not in html
    assert "This week" in html and "Since Monday 16 Nov" in html
    assert "Overdue follow-ups" in html
    assert "Backend &lt;i&gt;dev&lt;/i&gt;" in html
    assert "Overdue: 17 Nov" in html


def test_no_pending_follow_ups_message(app, client):
    set_provider(app, True)
    add_job(app, status="sent", score=60)
    assert "No follow-ups due today." in page(client)


def test_home_lists_today_best_fit_and_funnel(app, client):
    set_provider(app, True)
    add_job(app)  # new and unscored: shows up in "For today"
    html = page(client)
    assert "For today" in html and "1 new offers not scored yet" in html
    assert "Best fit not sent yet" in html and "Funnel of the last 4 weeks" in html
    assert 'class="fill" width="100' in html and "style=" not in html
