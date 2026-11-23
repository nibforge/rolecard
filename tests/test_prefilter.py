"""The cheap prefilter before AI scoring: title-only words, remote and location (R10, R15)."""

from types import SimpleNamespace

import pytest

from rolecard.services.prefilter import Rules, city, is_remote, parse_words, reason
from rolecard.sources.normalize import Offer


def _offer(title="Técnico de soporte", location="Barcelona", remote=None, text="") -> Offer:
    return Offer(source="adzuna", external_id="1", url="", title=title, company="Ficticia",
                 location=location, text=text or f"{title} — Ficticia — {location}",
                 remote=remote)


def test_query_matches_the_title_only():
    rules = Rules(query="soporte tecnico")
    assert reason(rules, _offer()) is None  # accents and case ignored
    assert reason(rules, _offer(title="Administrativo",
                                text="Administrativo con soporte técnico")) == "title"
    assert reason(Rules(query="soporte"), _offer(title="Soportes varios")) == "title"


def test_required_and_excluded_words_look_at_the_title_only():
    rules = Rules(required=("helpdesk",), excluded=("senior", "ingeniero"))
    assert reason(rules, _offer(title="Helpdesk N1")) is None
    assert reason(rules, _offer(title="Soporte",
                                text="Soporte helpdesk")) == "missing:helpdesk"
    assert reason(rules, _offer(title="Senior Helpdesk")) == "excluded:senior"
    assert reason(rules, _offer(title="Helpdesk", text="Helpdesk senior")) is None
    assert reason(Rules(excluded=("home office",)),
                  _offer(title="Soporte home office")) == "excluded:home office"


@pytest.mark.parametrize(("remote", "title", "location", "expected"), [
    ("only", "Soporte", "Madrid", "remote"),
    ("only", "Soporte remoto", "Madrid", None),
    ("exclude", "Soporte", "Teletrabajo", "remote"),
    ("exclude", "Soporte", "Madrid", None),
])
def test_remote_rules(remote, title, location, expected):
    assert reason(Rules(remote=remote), _offer(title=title, location=location)) == expected


def test_source_flag_wins_over_words():
    assert is_remote(_offer(title="Remote support", remote=False)) is False
    assert is_remote(_offer(title="Support", remote=True)) is True


def test_location_is_applied_locally_unless_the_api_filtered_it():
    rules = Rules(location="Barcelona, España")
    assert city(rules.location) == "barcelona"
    assert reason(rules, _offer(location="Barcelona, Cataluña")) is None
    assert reason(rules, _offer(location="Worldwide", remote=True)) == "location"
    assert reason(rules, _offer(location="Berlin")) == "location"
    assert reason(rules, _offer(location="Berlin"), local_location=False) is None
    only = Rules(location="Barcelona", remote="only")
    assert reason(only, _offer(location="Worldwide", remote=True)) is None


def test_rules_of_a_search_and_parse_words():
    search = SimpleNamespace(query="helpdesk", required=["n1"], excluded=None,
                             location="", remote=None)
    assert Rules.of(search) == Rules(query="helpdesk", required=("n1",))
    assert parse_words(" Senior, ingeniero ,, SENIOR,  home   office ") == [
        "senior", "ingeniero", "home office"]
    assert len(parse_words(",".join(f"w{i}" for i in range(30)))) == 20
    assert parse_words("--, ¿?") == []
