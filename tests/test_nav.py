"""The app shell: sections, the active one decided by the view, and their counters."""

import re

import pytest

from rolecard import get_db
from rolecard.models import Job, Search
from rolecard.services.jobs import create_job
from rolecard.services.profile import save_profile
from tests.helpers import PROFILE
from tests.test_documents import CV, OFFER
from tests.test_documents_views import generate

CURRENT = re.compile(r'<a class="rc-nav" href="([^"]*)" aria-current="page">')


def active_links(html: str) -> list[str]:
    return CURRENT.findall(html)


@pytest.fixture
def job_id(app):
    with app.app_context():
        return create_job(get_db(), text=OFFER, url="", title="Dev", company="Pagos").id


@pytest.mark.parametrize(("url", "href"), [
    ("/", "/"), ("/board", "/board"), ("/jobs/new", "/board"), ("/search", "/search"),
    ("/profile", "/profile"), ("/settings", "/settings")])
def test_one_section_is_current_per_page(client, url, href):
    assert active_links(client.get(url).get_data(as_text=True)) == [href]


def test_job_detail_and_its_documents_mark_offers(app, client, csrf, job_id):
    assert active_links(client.get(f"/jobs/{job_id}").get_data(as_text=True)) == ["/board"]
    with app.app_context():
        save_profile(get_db(), PROFILE)
    generate(client, csrf, app, "cv", CV)
    review = client.get(f"/jobs/{job_id}/documents/cv").get_data(as_text=True)
    assert active_links(review) == ["/board"]


def test_add_offer_is_an_action_not_a_section(client):
    html = client.get("/board", headers={"Accept-Language": "en"}).get_data(as_text=True)
    side = html[html.index('class="rc-side"'):html.index("</nav>")]
    assert "/jobs/new" not in side
    assert 'href="/jobs/new"' in html


def test_counters_show_offers_without_discarded_and_searches(app, client):
    with app.app_context():
        db = get_db()
        for n, status in enumerate(["new", "sent", "discarded"]):
            db.add(Job(text=f"t{n}", text_key=f"k{n}", title=f"J{n}", status=status))
        db.add(Search(name="s", query="python"))
        db.commit()
    html = client.get("/").get_data(as_text=True)
    side = html[html.index('class="rc-side"'):html.index("</nav>")]
    assert re.search(r'href="/board"[^>]*>.*?<span class="rc-count">2</span>', side, re.S)
    assert re.search(r'href="/search"[^>]*>.*?<span class="rc-count">1</span>', side, re.S)


@pytest.mark.parametrize(("lang", "text"), [("es", "1.042"), ("en", "1,042")])
def test_thousands_follow_the_language(monkeypatch, lang, text):
    from rolecard import i18n

    monkeypatch.setattr(i18n, "current_language", lambda: lang)
    assert i18n.number(1042) == text
