"""Connectors against recorded (invented) answers; no real network (R7, R8, R9)."""

import logging
import urllib.error

import pytest

from rolecard.sources import REGISTRY, adzuna, arbeitnow, remotive
from rolecard.sources.base import Query, RawOffer
from rolecard.sources.http import SourceError
from tests.source_fakes import fixture, install

KEYS = {"adzuna_app_id": "id-123", "adzuna_app_key": "key-SECRET-456", "adzuna_country": "es"}


def test_registry_has_the_three_sources():
    assert list(REGISTRY) == ["remotive", "arbeitnow", "adzuna"]
    assert REGISTRY["adzuna"].missing({}) == ["adzuna_app_id", "adzuna_app_key"]
    assert REGISTRY["remotive"].missing({}) == []


def test_remotive_parses_and_skips_bad_items(monkeypatch):
    net = install(monkeypatch, fixture("remotive.json"))
    result = remotive.fetch(Query(text="python dev"), {})
    assert net.requests[0].full_url == (
        "https://remotive.com/api/remote-jobs?limit=100&search=python+dev")
    assert [o.external_id for o in result.offers] == ["1001", "1002"]
    assert result.bad_items == 1
    first = result.offers[0]
    assert (first.title, first.company, first.location, first.remote) == (
        "Python Developer", "Fictional Example Ltd", "Europe", True)
    assert first.url.startswith("https://remotive.com/remote-jobs/")


def test_arbeitnow_two_pages_and_local_query(monkeypatch):
    net = install(monkeypatch, fixture("arbeitnow_p1.json"), fixture("arbeitnow_p2.json"))
    result = arbeitnow.fetch(Query(text="Python"), {})
    assert [r.full_url.rsplit("=", 1)[1] for r in net.requests] == ["1", "2"]
    assert [o.external_id for o in result.offers] == [
        "python-developer-berlin-1", "python-data-engineer-hamburg-4"]
    assert result.bad_items == 1  # "remote": "yes" is not a boolean
    assert [o.remote for o in result.offers] == [True, False]


def test_arbeitnow_query_matches_the_title_only():
    """R15: a word only in the description does not make the offer match."""
    offer = RawOffer(source="arbeitnow", external_id="x", url="", title="Java Developer",
                     company="Ficticia", location="Berlin",
                     description="We also use Python here.")
    assert not arbeitnow._matches(["python"], offer)
    assert arbeitnow._matches(["java"], offer)


def test_source_flags_for_location_and_spain():
    assert REGISTRY["adzuna"].filters_location and not REGISTRY["adzuna"].international
    assert REGISTRY["remotive"].international and REGISTRY["arbeitnow"].international
    assert not REGISTRY["remotive"].filters_location


def test_arbeitnow_stops_without_next_page(monkeypatch):
    net = install(monkeypatch, fixture("arbeitnow_p2.json"))
    assert len(arbeitnow.fetch(Query(), {}).offers) == 1
    assert len(net.requests) == 1


def test_adzuna_builds_query_and_parses(monkeypatch):
    net = install(monkeypatch, fixture("adzuna.json"))
    result = adzuna.fetch(Query(text="python", location="Madrid"), KEYS)
    url = net.requests[0].full_url
    assert url.startswith("https://api.adzuna.com/v1/api/jobs/es/search/1?")
    assert "title_only=python" in url and "what=" not in url
    assert "where=Madrid" in url and "app_key=key-SECRET-456" in url
    assert [(o.company, o.location, o.remote) for o in result.offers] == [
        ("Empresa Ficticia SL", "Madrid, Comunidad de Madrid", None),
        ("Otra Empresa Inventada SA", "Barcelona", None)]


@pytest.mark.parametrize("answer", [
    urllib.error.URLError(ConnectionRefusedError("key-SECRET-456")),
    b"{}",
    b"[1, 2]",
])
def test_adzuna_errors_never_show_the_key(monkeypatch, caplog, answer):
    caplog.set_level(logging.DEBUG)
    install(monkeypatch, answer)
    monkeypatch.setattr("rolecard.sources.http.BACKOFF", (0, 0))
    with pytest.raises(SourceError) as err:
        adzuna.fetch(Query(text="python"), KEYS)
    assert "SECRET" not in str(err.value) and "SECRET" not in caplog.text
