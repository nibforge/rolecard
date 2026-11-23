"""Running a saved search over the sources (R4, R6, R11), with recorded answers."""

import json
import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from rolecard import config as cfg
from rolecard import db
from rolecard.models import Job, Search
from rolecard.services import jobs as jobs_svc
from rolecard.services import search as svc
from tests.source_fakes import fixture, http_error, install

T0 = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)
SETTINGS = cfg.validate_config({"sources": {"enabled": "remotive,arbeitnow,adzuna"}})


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("rolecard.sources.http.BACKOFF", (0, 0))
    monkeypatch.delenv(cfg.ENV_ADZUNA_ID, raising=False)
    monkeypatch.delenv(cfg.ENV_ADZUNA_KEY, raising=False)
    path = tmp_path / "x.sqlite3"
    db.migrate(path)
    with Session(db.make_engine(path)) as s:
        yield s


def _search(session, sources, **kw):
    kw.setdefault("query", "python")
    search = Search(name="Python", sources=sources, **kw)
    session.add(search)
    session.commit()
    return search


def _row(summary, name):
    return next(r for r in summary["sources"] if r["name"] == name)


def test_adds_new_unscored_offers_with_source_and_search(session, monkeypatch):
    install(monkeypatch, fixture("remotive.json"), fixture("arbeitnow_p1.json"),
            fixture("arbeitnow_p2.json"))
    search = _search(session, ["remotive", "arbeitnow"])
    summary = svc.run_search(session, search, SETTINGS, now=T0)
    remotive = _row(summary, "remotive")
    assert (remotive["received"], remotive["bad_items"], remotive["added"]) == (2, 1, 1)
    assert remotive["filtered"] == {"title": 1}  # "Python" only in its description (R15)
    assert _row(summary, "arbeitnow")["added"] == 2 and summary["added"] == 3
    jobs = session.scalars(select(Job).order_by(Job.id)).all()
    assert {j.source for j in jobs} == {"remotive", "arbeitnow"}
    assert all(j.status == "new" and j.score is None and j.search_id == search.id
               for j in jobs)
    assert jobs[0].match_key == "fictional example ltd|python developer|europe"
    assert search.last_summary == json.loads(json.dumps(summary))
    assert search.last_run_at == T0


def test_second_run_finds_only_duplicates(session, monkeypatch):
    install(monkeypatch, fixture("remotive.json"))
    search = _search(session, ["remotive"])
    svc.run_search(session, search, SETTINGS, now=T0)
    summary = svc.run_search(session, search, SETTINGS, now=T0 + timedelta(minutes=2))
    assert _row(summary, "remotive")["duplicates"] == 1 and summary["added"] == 0


def test_same_offer_from_another_place_is_a_duplicate(session, monkeypatch):
    jobs_svc.create_job(session, text="Some other text " * 10, url="https://other.test/1",
                        title="Python Developer", company="Fictional Example Ltd.",
                        location="EUROPE")
    install(monkeypatch, fixture("remotive.json"))
    summary = svc.run_search(session, _search(session, ["remotive"]), SETTINGS, now=T0)
    assert _row(summary, "remotive")["duplicates"] == 1


def test_one_failing_source_does_not_stop_the_others(session, monkeypatch):
    install(monkeypatch, http_error(500), http_error(500), http_error(500),
            fixture("arbeitnow_p2.json"))
    summary = svc.run_search(session, _search(session, ["remotive", "arbeitnow"]),
                             SETTINGS, now=T0)
    assert _row(summary, "remotive")["status"] == "error"
    assert _row(summary, "remotive")["error"] == "http_5xx"
    assert _row(summary, "arbeitnow")["added"] == 1


def test_unexpected_connector_bug_is_contained(session, monkeypatch, caplog):
    def boom(query, settings):
        raise KeyError("x")
    monkeypatch.setitem(svc.REGISTRY, "remotive", replace(svc.REGISTRY["remotive"], fetch=boom))
    summary = svc.run_search(session, _search(session, ["remotive"]), SETTINGS, now=T0)
    assert _row(summary, "remotive")["error"] == "bad_response"
    assert "KeyError" in caplog.text


def test_missing_keys_disabled_and_rate_limited(session, monkeypatch):
    install(monkeypatch, fixture("remotive.json"))
    only_remotive = cfg.validate_config({"sources": {"enabled": "remotive,adzuna"}})
    search = _search(session, ["remotive", "arbeitnow", "adzuna"])
    svc.run_search(session, search, only_remotive, now=T0)
    summary = svc.run_search(session, search, only_remotive, now=T0 + timedelta(seconds=10))
    assert [r["status"] for r in summary["sources"]] == [
        "rate_limited", "disabled", "not_configured"]
    assert _row(summary, "remotive")["retry_at"] == (T0 + timedelta(seconds=60)).isoformat()


def test_remotive_four_runs_a_day(session, monkeypatch):
    install(monkeypatch, fixture("remotive.json"))
    search = _search(session, ["remotive"])
    for minute in range(0, 20, 5):
        svc.run_search(session, search, SETTINGS, now=T0 + timedelta(minutes=minute))
    summary = svc.run_search(session, search, SETTINGS, now=T0 + timedelta(hours=3))
    assert _row(summary, "remotive")["status"] == "rate_limited"


def test_cap_per_source_and_prefilter_reasons(session, monkeypatch):
    monkeypatch.setattr(svc, "MAX_NEW_PER_SOURCE", 1)
    install(monkeypatch, fixture("remotive.json"))
    summary = svc.run_search(session, _search(session, ["remotive"], query=""), SETTINGS,
                             now=T0)
    row = _row(summary, "remotive")
    assert row["filtered"] == {} and (row["added"], row["over_cap"]) == (1, 1)


def test_adzuna_failure_keeps_key_out_of_summary_and_log(session, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    keys = cfg.validate_config({"sources": {"enabled": "adzuna", "adzuna_app_id": "id9",
                                            "adzuna_app_key": "TOPSECRET"}})
    install(monkeypatch, http_error(500))
    search = _search(session, ["adzuna"])
    summary = svc.run_search(session, search, keys, now=T0)
    assert _row(summary, "adzuna")["error"] == "http_5xx"
    assert "TOPSECRET" not in json.dumps(summary) and "TOPSECRET" not in caplog.text


def test_runs_are_serialised_while_fetching(session, monkeypatch):
    seen = []
    net = install(monkeypatch, fixture("remotive.json"))
    original = net.__call__

    def watching(req, timeout):
        seen.append(svc._RUN_LOCK.locked())
        return original(req, timeout)

    monkeypatch.setattr("rolecard.sources.http._open", watching)
    svc.run_search(session, _search(session, ["remotive"]), SETTINGS, now=T0)
    assert seen == [True] and not svc._RUN_LOCK.locked()


def test_prefilter_words_and_location_in_the_run(session, monkeypatch):
    """R10: excluded words in the title and the location applied to Arbeitnow locally."""
    install(monkeypatch, fixture("arbeitnow_p1.json"), fixture("arbeitnow_p2.json"))
    search = _search(session, ["arbeitnow"], excluded=["data"], location="Berlin")
    row = _row(svc.run_search(session, search, SETTINGS, now=T0), "arbeitnow")
    assert row["filtered"] == {"excluded:data": 1} and row["added"] == 1
    install(monkeypatch, fixture("arbeitnow_p1.json"), fixture("arbeitnow_p2.json"))
    search = _search(session, ["arbeitnow"], location="Hamburg")
    row = _row(svc.run_search(session, search, SETTINGS, now=T0 + timedelta(minutes=5)),
               "arbeitnow")
    assert row["filtered"] == {"location": 1}  # Berlin is out; Hamburg was already added


def test_location_in_spain_skips_international_sources(session, monkeypatch):
    """R16: Remotive and Arbeitnow are not called for Barcelona unless remote-only."""
    net = install(monkeypatch, fixture("remotive.json"))
    search = _search(session, ["remotive", "arbeitnow"], location="Barcelona")
    summary = svc.run_search(session, search, SETTINGS, now=T0)
    assert [r["status"] for r in summary["sources"]] == ["international", "international"]
    assert net.requests == []
    search.remote = "only"
    row = _row(svc.run_search(session, search, SETTINGS, now=T0), "remotive")
    assert row["status"] == "ok" and row["added"] == 1
    assert len(net.requests) == 2  # both international sources are called again


def test_excluding_remote_skips_remote_only_sources(session, monkeypatch):
    """Remotive only lists remote offers: with remote excluded it is not called."""
    net = install(monkeypatch, fixture("remotive.json"))
    search = _search(session, ["remotive"], remote="exclude")
    row = _row(svc.run_search(session, search, SETTINGS, now=T0), "remotive")
    assert row["status"] == "remote_only" and net.requests == []
