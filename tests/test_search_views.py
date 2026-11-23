"""The "Search" page: saved searches, running them and their summary (R1, R2, R11, R12)."""

import pytest

from rolecard import config as cfg
from rolecard import get_db
from rolecard.ai import AIError, FakeProvider
from rolecard.models import Job, Search
from rolecard.services.profile import save_profile
from tests.helpers import PROFILE
from tests.source_fakes import fixture, install
from tests.test_jobs_views import SCORE

ES = {"Accept-Language": "es-ES"}


@pytest.fixture(autouse=True)
def quiet_sources(monkeypatch):
    monkeypatch.setattr("rolecard.sources.http.BACKOFF", (0, 0))
    monkeypatch.delenv(cfg.ENV_ADZUNA_ID, raising=False)
    monkeypatch.delenv(cfg.ENV_ADZUNA_KEY, raising=False)


def form(csrf, **values):
    data = {"csrf_token": csrf, "name": "Python remote", "query": "python",
            "location": "", "remote": "any", "sources": ["remotive"]}
    data.update(values)
    return data


def make(client, csrf, **values) -> int:
    values.setdefault("query", "")  # both fixture offers pass the title-only query
    resp = client.post("/search", data=form(csrf, **values))
    assert resp.status_code == 302
    return int(resp.location.rsplit("/", 1)[1])


def rows(app, model):
    with app.app_context():
        return get_db().query(model).all()


def test_index_lists_enabled_sources_in_spanish(client):
    page = client.get("/search", headers=ES).get_data(as_text=True)
    assert resp_ok(page) and "Remotive" in page and "Arbeitnow" in page
    assert 'href="/search"' in page


def resp_ok(page: str) -> bool:
    return "<form" in page and 'name="csrf_token"' in page


def test_create_edit_and_show(client, csrf, app):
    search_id = make(client, csrf)
    page = client.get(f"/search/{search_id}", headers=ES).get_data(as_text=True)
    assert "Python remote" in page and "Aún no se ha ejecutado." in page
    resp = client.post(f"/search/{search_id}", data=form(csrf, name="Renamed",
                                                         sources=["remotive", "arbeitnow"]))
    assert resp.status_code == 302
    (search,) = rows(app, Search)
    assert search.name == "Renamed" and search.sources == ["remotive", "arbeitnow"]


@pytest.mark.parametrize("values, field", [
    ({"name": ""}, "name"), ({"name": "x" * 201}, "name"),
    ({"remote": "maybe"}, "remote"), ({"sources": ["jooble"]}, "sources"),
])
def test_invalid_form_is_rejected(client, csrf, app, values, field):
    values.setdefault("query", "")  # both fixture offers pass the title-only query
    resp = client.post("/search", data=form(csrf, **values))
    assert resp.status_code == 400 and rows(app, Search) == []


def test_unknown_search_is_404(client, csrf):
    assert client.get("/search/99").status_code == 404
    assert client.post("/search/99/run", data={"csrf_token": csrf}).status_code == 404


def test_post_without_csrf_is_refused(client, app):
    assert client.post("/search", data=form("bad")).status_code in (400, 403)
    assert rows(app, Search) == []


def test_run_adds_offers_and_shows_summary(client, csrf, app, monkeypatch):
    install(monkeypatch, fixture("remotive.json"))
    search_id = make(client, csrf)
    resp = client.post(f"/search/{search_id}/run", data={"csrf_token": csrf})
    assert resp.status_code == 302
    jobs = rows(app, Job)
    assert len(jobs) == 2 and {j.search_id for j in jobs} == {search_id}
    page = client.get(f"/search/{search_id}", headers=ES).get_data(as_text=True)
    assert "Ofertas añadidas: 2." in page and "unscored=1" in page


def test_run_with_htmx_returns_only_the_summary(client, csrf, monkeypatch):
    install(monkeypatch, fixture("remotive.json"))
    search_id = make(client, csrf)
    resp = client.post(f"/search/{search_id}/run", data={"csrf_token": csrf},
                       headers={"HX-Request": "true", **ES})
    page = resp.get_data(as_text=True)
    assert resp.status_code == 200 and "<html" not in page
    assert "Ofertas añadidas: 2." in page


def test_unconfigured_source_links_to_settings(client, csrf, app, monkeypatch):
    net = install(monkeypatch, {"results": []})
    app.config["ROLECARD"]["sources"]["enabled"] = "remotive,arbeitnow,adzuna"
    search_id = make(client, csrf, sources=["adzuna"])
    resp = client.post(f"/search/{search_id}/run", data={"csrf_token": csrf},
                       headers={"HX-Request": "true", **ES})
    page = resp.get_data(as_text=True)
    assert "Sin configurar" in page and 'href="/settings#fuentes"' in page
    assert net.requests == []


def test_delete_keeps_offers_on_the_board(client, csrf, app, monkeypatch):
    install(monkeypatch, fixture("remotive.json"))
    search_id = make(client, csrf)
    client.post(f"/search/{search_id}/run", data={"csrf_token": csrf})
    resp = client.post(f"/search/{search_id}/delete", data={"csrf_token": csrf})
    assert resp.status_code == 302 and resp.location.endswith("/search")
    assert rows(app, Search) == []
    jobs = rows(app, Job)
    assert len(jobs) == 2 and all(j.search_id is None for j in jobs)


def test_discard_unscored_only_touches_this_search_new_unscored(client, csrf, app,
                                                                 monkeypatch):
    install(monkeypatch, fixture("remotive.json"))
    search_id = make(client, csrf)
    client.post(f"/search/{search_id}/run", data={"csrf_token": csrf})
    with app.app_context():
        db = get_db()
        scored, kept = db.query(Job).order_by(Job.id).all()
        scored.score = 70
        db.add(Job(text="Manual offer " * 20, text_key="manual", status="new"))
        db.commit()
    page = client.get(f"/search/{search_id}", headers=ES).get_data(as_text=True)
    assert "discard-unscored" in page
    resp = client.post(f"/search/{search_id}/discard-unscored", data={"csrf_token": csrf})
    assert resp.status_code == 302
    status = {j.id: j.status for j in rows(app, Job)}
    assert status == {scored.id: "new", kept.id: "discarded", 3: "new"}


def test_run_button_is_disabled_while_running(client, csrf):
    search_id = make(client, csrf)
    page = client.get(f"/search/{search_id}").get_data(as_text=True)
    assert "data-busy aria-label" in page and "data-busy-label hidden" in page


def test_name_is_optional_and_generated(client, csrf, app):
    make(client, csrf, name="", query="python", location="Barcelona")
    (search,) = rows(app, Search)
    assert search.name == "python · Barcelona"


def test_search_now_saves_and_runs_in_one_step(client, csrf, app, monkeypatch):
    install(monkeypatch, fixture("remotive.json"))
    resp = client.post("/search", data=form(csrf, name="", query="", location="",
                                            then="run"))
    assert resp.status_code == 400 and rows(app, Search) == []
    search_id = make(client, csrf, then="run")
    assert {j.search_id for j in rows(app, Job)} == {search_id}
    page = client.get(f"/search/{search_id}", headers=ES).get_data(as_text=True)
    assert "Ofertas añadidas: 2." in page and "2 sin puntuar" in page
    assert page.count('href="/jobs/') >= 2 and 'aria-current="page"' in page


def test_required_and_excluded_words_are_saved_and_shown(client, csrf, app):
    """R10: comma-separated words, trimmed and de-duplicated, shown back in the form."""
    search_id = make(client, csrf, required=" Helpdesk, n1 ", excluded="Senior,senior, <b>x</b>")
    (search,) = rows(app, Search)
    assert search.required == ["helpdesk", "n1"]
    assert search.excluded == ["senior", "<b>x</b>"]
    page = client.get(f"/search/{search_id}", headers=ES).get_data(as_text=True)
    assert 'value="helpdesk, n1"' in page and "&lt;b&gt;x&lt;/b&gt;" in page
    assert "Casa solo con el puesto" in page and "Remotive y Arbeitnow son internacionales" in page


def test_summary_lists_discards_by_reason(client, csrf, monkeypatch):
    """R11: how many were dropped and why, the word escaped."""
    install(monkeypatch, fixture("remotive.json"))
    search_id = make(client, csrf, query="python", excluded="<i>dev</i>, developer")
    page = client.post(f"/search/{search_id}/run", headers={**ES, "HX-Request": "true"},
                       data={"csrf_token": csrf}).get_data(as_text=True)
    assert "Descartadas en Remotive:" in page
    assert "1 con un formato no válido" in page and "1 no casan con el puesto" in page
    assert "1 con «developer» en el puesto" in page


def test_spanish_location_marks_international_sources(client, csrf, monkeypatch):
    """R16: Remotive is not queried for a location in Spain and the summary says why."""
    net = install(monkeypatch, fixture("remotive.json"))
    search_id = make(client, csrf, location="Barcelona")
    page = client.post(f"/search/{search_id}/run", headers={**ES, "HX-Request": "true"},
                       data={"csrf_token": csrf}).get_data(as_text=True)
    assert "No consultada: es internacional" in page and net.requests == []


def _with_added(client, csrf, app, count: int) -> int:
    search_id = make(client, csrf)
    with app.app_context():
        db = get_db()
        for i in range(count):
            db.add(Job(text=f"Offer {i} " * 20, text_key=f"k{i}", status="new", source="remotive",
                       search_id=search_id))
        db.commit()
    return search_id


def test_score_added_scores_five_per_click(client, csrf, app, monkeypatch):
    """R11: up to 5 unscored offers of this search per click, with the F1 flow."""
    search_id = _with_added(client, csrf, app, 6)
    resp = client.post(f"/search/{search_id}/score", data={"csrf_token": csrf}, headers=ES)
    assert resp.status_code == 302 and all(j.score is None for j in rows(app, Job))
    with app.app_context():
        save_profile(get_db(), PROFILE)
    app.config["AI_PROVIDER_FACTORY"] = lambda: FakeProvider([SCORE] * 6)
    page = client.get(f"/search/{search_id}", headers=ES).get_data(as_text=True)
    assert "Puntuar 5 de las añadidas" in page
    client.post(f"/search/{search_id}/score", data={"csrf_token": csrf})
    assert [j.score for j in rows(app, Job)] == [82] * 5 + [None]


def test_score_added_stops_at_the_first_ai_error(client, csrf, app, monkeypatch):
    search_id = _with_added(client, csrf, app, 3)
    with app.app_context():
        save_profile(get_db(), PROFILE)
    app.config["AI_PROVIDER_FACTORY"] = lambda: FakeProvider([SCORE, AIError("timeout")])
    client.post(f"/search/{search_id}/score", data={"csrf_token": csrf})
    assert [j.score for j in rows(app, Job)] == [82, None, None]



def test_score_added_with_nothing_pending_says_so(client, csrf, app):
    search_id = _with_added(client, csrf, app, 0)
    with app.app_context():
        save_profile(get_db(), PROFILE)
    app.config["AI_PROVIDER_FACTORY"] = lambda: FakeProvider([])
    page = client.post(f"/search/{search_id}/score", data={"csrf_token": csrf}, headers=ES,
                       follow_redirects=True).get_data(as_text=True)
    assert "No hay ofertas de esta búsqueda pendientes" in page
    assert "Ofertas puntuadas" not in page


def test_score_added_rolls_back_an_unexpected_error(client, csrf, app, monkeypatch):
    """A non-AI error leaves the earlier offers scored and the session clean."""
    import rolecard.views.search as view
    search_id = _with_added(client, csrf, app, 2)
    with app.app_context():
        save_profile(get_db(), PROFILE)
    app.config["AI_PROVIDER_FACTORY"] = lambda: FakeProvider([SCORE] * 2)
    real, calls = view.score_job, []

    def flaky(db, job, *args):
        calls.append(job.id)
        if len(calls) == 2:
            job.score = 1  # pending change that must not survive
            raise RuntimeError("boom")
        return real(db, job, *args)

    monkeypatch.setattr(view, "score_job", flaky)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    resp = client.post(f"/search/{search_id}/score", data={"csrf_token": csrf})
    assert resp.status_code == 500
    assert [j.score for j in rows(app, Job)] == [82, None]
