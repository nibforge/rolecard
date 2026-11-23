import json

import pytest

from rolecard import get_db
from rolecard.ai import AIError, FakeProvider
from rolecard.models import Job
from rolecard.services.profile import save_profile
from tests.helpers import PROFILE

TEXT = "Acme Data seeks a backend developer: Python, SQL, Kubernetes. Hybrid in Valencia. " * 2
SCORE = json.dumps({"score": 82, "summary": "Good <b>fit</b>.", "met": ["<script>x</script>"],
                    "missing": ["Kubernetes"], "language": "en", "title": "Backend dev",
                    "company": "Acme", "location": "Valencia"})


@pytest.fixture
def with_profile(app):
    with app.app_context():
        save_profile(get_db(), PROFILE)


def provider(app, answers):
    app.config["AI_PROVIDER_FACTORY"] = lambda: FakeProvider(answers)


def jobs(app):
    with app.app_context():
        return get_db().query(Job).all()


def create(client, csrf, **extra):
    return client.post("/jobs", data={"csrf_token": csrf, "text": TEXT, **extra})


def test_create_scores_and_shows_escaped(client, csrf, app, with_profile):
    provider(app, [SCORE])
    resp = create(client, csrf, url="https://jobs.example.com/1")
    assert resp.status_code == 302 and resp.location.endswith("/jobs/1")
    page = client.get("/jobs/1").get_data(as_text=True)
    assert "Backend dev" in page and 'aria-label="Score 82 out of 100"' in page
    assert "<script>x" not in page and "&lt;script&gt;" in page and "<b>fit" not in page
    assert 'href="https://jobs.example.com/1" target="_blank" rel="noopener noreferrer"' in page


def test_duplicate_links_to_existing(client, csrf, app):
    provider(app, [SCORE])
    create(client, csrf, url="https://x.com/1")
    resp = create(client, csrf, url="https://x.com/1?utm_source=mail", text=TEXT + "!")
    assert resp.status_code == 409 and 'href="/jobs/1"' in resp.get_data(as_text=True)
    assert len(jobs(app)) == 1


@pytest.mark.parametrize(("extra", "message"), [
    ({"text": "short"}, "too short"), ({"url": "javascript:alert(1)"}, "full http://")])
def test_invalid_offer_not_created(client, csrf, app, extra, message):
    resp = create(client, csrf, **extra)
    assert resp.status_code == 400 and message in resp.get_data(as_text=True)
    assert jobs(app) == []


def test_without_profile_job_is_unscored(client, csrf, app):
    provider(app, [SCORE])
    create(client, csrf)
    page = client.get("/jobs/1").get_data(as_text=True)
    assert "there is no profile" in page and 'href="/profile"' in page
    assert jobs(app)[0].score is None


def test_ai_failure_keeps_job_unscored_and_rescore_works(client, csrf, app, with_profile):
    provider(app, [AIError("timeout")])
    create(client, csrf)
    assert "took too long" in client.get("/jobs/1").get_data(as_text=True)
    assert jobs(app)[0].score is None
    provider(app, [SCORE])
    client.post("/jobs/1/score", data={"csrf_token": csrf})
    assert jobs(app)[0].score == 82


def test_quota_error_says_when_to_try_again(client, csrf, app, with_profile):
    provider(app, [AIError("quota", "HTTP 429", retry_after=3600)])
    create(client, csrf)
    page = client.get("/jobs/1").get_data(as_text=True)
    assert "usage limit is used up" in page and "try again in 1 h 0 min" in page
    assert jobs(app)[0].score is None


def test_edit_delete_and_404(client, csrf, app):
    provider(app, [SCORE])
    create(client, csrf)
    client.post("/jobs/1", data={"csrf_token": csrf, "title": "New", "company": "Co",
                                 "location": "Remote", "url": "https://x.com/z"})
    job = jobs(app)[0]
    assert (job.title, job.company, job.location) == ("New", "Co", "Remote")
    resp = client.post("/jobs/1", data={"csrf_token": csrf, "url": "ftp://x"})
    assert resp.status_code == 400
    assert 'data-confirm' in client.get("/jobs/1").get_data(as_text=True)
    client.post("/jobs/1/delete", data={"csrf_token": csrf})
    assert jobs(app) == [] and client.get("/jobs/1").status_code == 404


def test_status_and_tracking(client, csrf, app):
    provider(app, [SCORE])
    create(client, csrf)
    client.post("/jobs/1/status", data={"csrf_token": csrf, "status": "sent"})
    client.post("/jobs/1/tracking", data={"csrf_token": csrf, "notes": "Called HR",
                                          "follow_up_on": "2026-11-27"})
    job = jobs(app)[0]
    assert job.status == "sent" and job.notes == "Called HR"
    assert str(job.follow_up_on) == "2026-11-27"
    with app.app_context():
        events = [e.status for e in get_db().get(Job, 1).events]
    assert events == ["new", "sent"]
    bad = client.post("/jobs/1/status", data={"csrf_token": csrf, "status": "x"})
    assert bad.status_code == 400
    bad = client.post("/jobs/1/tracking", data={"csrf_token": csrf, "follow_up_on": "nope"})
    assert bad.status_code == 400


def test_show_credits_the_source_but_not_manual_offers(client, csrf, app, with_profile):
    provider(app, [SCORE])
    create(client, csrf, url="https://remotive.com/remote-jobs/x-1")
    page = client.get("/jobs/1").get_data(as_text=True)
    assert "via <a" not in page
    with app.app_context():
        get_db().get(Job, 1).source = "remotive"
        get_db().commit()
    page = client.get("/jobs/1").get_data(as_text=True)
    assert "via <a href=\"https://remotive.com" in page and "Remotive</a>" in page


def test_show_has_two_columns_and_history_tab(client, csrf, app, with_profile):
    provider(app, [SCORE])
    create(client, csrf, url="https://jobs.example.com/9")
    page = client.get("/jobs/1").get_data(as_text=True)
    assert 'class="rc-detail"' in page and 'class="rail"' in page
    assert "High fit" in page and "rc-score--lg" in page and "Acme Data seeks" in page
    assert 'href="/jobs/1?tab=history"' in page and 'aria-current="page">Description' in page
    history = client.get("/jobs/1?tab=history").get_data(as_text=True)
    assert 'aria-current="page">History' in history and "Acme Data seeks" not in history
    assert "rc-status--new" in history
    assert 'data-confirm="Delete this offer' in page and "Not prepared yet" in page


def test_new_job_is_a_compact_form_on_the_grid(client):
    page = client.get("/jobs/new").get_data(as_text=True)
    assert 'class="rc-dialog rc-dialog--page"' in page and 'action="/jobs"' in page
    assert 'class="rc-field span-6"' in page and 'name="text"' in page and "required" in page


def test_new_job_errors_stay_next_to_the_field(client, csrf):
    resp = client.post("/jobs", data={"csrf_token": csrf, "text": "short"})
    page = resp.get_data(as_text=True)
    assert resp.status_code == 400 and 'id="text-error"' in page and "rc-hint--error" in page
