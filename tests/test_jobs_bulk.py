"""POST /jobs/bulk: actions on the offers ticked in the list."""

import pytest

from rolecard import get_db
from rolecard.ai import AIError, FakeProvider
from rolecard.models import Job
from rolecard.services.profile import save_profile
from tests.helpers import PROFILE
from tests.test_jobs_views import SCORE


def add_jobs(app, count, **fields):
    with app.app_context():
        db = get_db()
        jobs = [Job(text=f"Offer {n} " * 20, text_key=f"b{n}", title=f"Job {n}", **fields)
                for n in range(count)]
        db.add_all(jobs)
        db.commit()
        return [job.id for job in jobs]


def jobs(app):
    with app.app_context():
        return {j.id: (j.status, j.score, [e.status for e in j.events])
                for j in get_db().query(Job).order_by(Job.id)}


def post(client, csrf, ids, action, **extra):
    data = {"csrf_token": csrf, "ids": [str(i) for i in ids], "action": action, **extra}
    return client.post("/jobs/bulk", data=data)


def test_status_change_goes_through_the_history(app, client, csrf):
    ids = add_jobs(app, 3)
    resp = post(client, csrf, ids[:2], "status", value="sent", next="/jobs?status=new&page=2")
    assert resp.status_code == 302 and resp.headers["Location"] == "/jobs?status=new&page=2"
    state = jobs(app)
    assert state[ids[0]] == ("sent", None, ["sent"]) and state[ids[1]][0] == "sent"
    assert state[ids[2]] == ("new", None, [])


def test_discard_and_unknown_ids_are_ignored(app, client, csrf):
    ids = add_jobs(app, 2)
    resp = post(client, csrf, [ids[0], 9999], "discard")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/jobs")
    assert jobs(app)[ids[0]] == ("discarded", None, ["discarded"])
    assert jobs(app)[ids[1]][0] == "new"


def test_bulk_requires_the_csrf_token(app, client):
    ids = add_jobs(app, 1)
    resp = client.post("/jobs/bulk", data={"ids": [str(ids[0])], "action": "discard"})
    assert resp.status_code in (400, 403) and jobs(app)[ids[0]][0] == "new"


@pytest.mark.parametrize(
    ("ids", "action", "extra"),
    [
        (["1"], "delete", {}),
        (["1"], "status", {"value": "hired"}),
        (["1"], "status", {}),
        (["abc"], "discard", {}),
        (["-1"], "discard", {}),
        (["1 OR 1=1"], "discard", {}),
        ([str(i) for i in range(101)], "discard", {}),
    ],
)
def test_bad_requests_are_rejected(app, client, csrf, ids, action, extra):
    add_jobs(app, 1)
    resp = client.post("/jobs/bulk", data={"csrf_token": csrf, "ids": ids, "action": action,
                                           **extra})
    assert resp.status_code == 400 and list(jobs(app).values())[0][0] == "new"


def test_nothing_ticked_says_so(app, client, csrf):
    page = client.post("/jobs/bulk", data={"csrf_token": csrf, "action": "discard"},
                       headers={"Accept-Language": "en"}, follow_redirects=True)
    assert "Tick at least one offer." in page.get_data(as_text=True)


def test_redirect_stays_inside_the_list(app, client, csrf):
    ids = add_jobs(app, 1)
    for target in ("https://evil.example/jobs", "//evil.example", "/jobs//evil", "/settings",
                   "/jobs/5/delete", "/jobsX", "\\\\evil.example"):
        resp = post(client, csrf, ids, "status", value="sent", next=target)
        assert resp.headers["Location"].endswith("/jobs")


def test_score_at_most_a_batch_and_only_unscored(app, client, csrf):
    ids = add_jobs(app, 7)
    with app.app_context():
        db = get_db()
        db.get(Job, ids[0]).score = 10
        db.commit()
        save_profile(db, PROFILE)
    app.config["AI_PROVIDER_FACTORY"] = lambda: FakeProvider([SCORE] * 7)
    post(client, csrf, ids, "score")
    scores = [score for _, score, _ in jobs(app).values()]
    assert scores == [10, 82, 82, 82, 82, 82, None]


def test_score_stops_at_the_first_ai_error(app, client, csrf):
    ids = add_jobs(app, 3)
    with app.app_context():
        save_profile(get_db(), PROFILE)
    app.config["AI_PROVIDER_FACTORY"] = lambda: FakeProvider([SCORE, AIError("timeout")])
    post(client, csrf, ids, "score")
    assert [score for _, score, _ in jobs(app).values()] == [82, None, None]


def test_score_without_profile_warns(app, client, csrf):
    ids = add_jobs(app, 1)
    page = client.post("/jobs/bulk", data={"csrf_token": csrf, "ids": [str(ids[0])],
                                           "action": "score"},
                       headers={"Accept-Language": "en"}, follow_redirects=True)
    assert page.status_code == 200 and jobs(app)[ids[0]][1] is None


def test_list_page_has_the_bulk_form(app, client):
    add_jobs(app, 1)
    html = client.get("/jobs", headers={"Accept-Language": "en"}).get_data(as_text=True)
    assert 'form id="bulk"' in html and 'name="csrf_token"' in html
    assert 'form="bulk" name="ids"' in html and "Score (up to 5)" in html
    assert 'data-confirm="Discard the ticked offers?"' in html
