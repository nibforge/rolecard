import pytest

from rolecard.services import provenance as pv

PROFILE = {
    "basics": {"name": "Ana", "summary": "Backend developer since 2015.", "links": []},
    "experience": [
        {"role": "Dev", "company": "Acme", "start": "2019", "end": "",
         "highlights": ["Cut latency by 40%", "Led a team of 5"]},
    ],
    "projects": [], "education": [], "languages": [],
    "skills": ["Python", "SQL"],
}
OFFER = "We process 1,500 payments per second in Madrid."


def s(text, *sources, state="sourced"):
    return {"text": text, "sources": list(sources), "state": state, "reason": ""}


@pytest.mark.parametrize(("path", "expected"), [
    ("basics.name", "Ana"),
    ("experience.0.highlights.1", "Led a team of 5"),
    ("skills.1", "SQL"),
    ("experience.0.highlights", "Cut latency by 40% · Led a team of 5"),
])
def test_resolve_walks_the_profile(path, expected):
    assert pv.resolve(PROFILE, path) == expected


@pytest.mark.parametrize("path", [
    "experience.1", "skills.9", "basics.links", "basics.missing", "experience.x",
    "__class__", "basics.__dict__", "skills.-1", "skills[0]", "jobs.0", "", None, 3,
    "basics." + "a" * 90, "experience.0.highlights.0.0",
])
def test_resolve_rejects_bad_or_missing_paths(path):
    assert pv.resolve(PROFILE, path) is None


def test_figures_are_normalised():
    assert pv.figures("1,500 and 1.500 and 40% in 2019") == {"1500", "40", "2019"}
    assert pv.figures("1.5 TB, 1,5 TB, 15 servers, 12.345.678") == {"1.5", "15", "12345678"}


@pytest.mark.parametrize("path", ["experience", "skills", "basics", "education",
                                  "experience.role", "experience.0", "basics.name"])
def test_a_source_names_an_entry_or_a_basics_field(path):
    expected = path in ("experience.0", "basics.name")
    assert (pv.resolve(PROFILE, path) is not None) is expected


def test_letter_sentence_citing_only_the_offer_is_flagged():
    mixed = s("Cut latency for your payments", "experience.0.highlights.0", "offer")
    assert pv.verify(mixed, PROFILE, "payments", allow_offer=True) == ("sourced", "")


@pytest.mark.parametrize(("sentence", "allow", "expected"), [
    (s("Cut latency by 40% at Acme", "experience.0.highlights.0", "experience.0"), False,
     ("sourced", "")),
    (s("Python and SQL", "skills.0", "skills.1"), False, ("sourced", "")),
    (s("Expert in Rust"), False, ("unsourced", "no_sources")),
    ({"text": "x", "sources": "skills.0"}, False, ("unsourced", "no_sources")),
    (s("Rust", "skills.7"), False, ("unsourced", "bad_path")),
    (s("Cut latency by 60%", "experience.0.highlights.0"), False, ("unsourced", "number")),
    (s("Led a team of 12 since 2015", "experience.0.highlights.1", "basics.summary"), False,
     ("unsourced", "number")),
    (s("Your payment platform", "offer"), False, ("unsourced", "offer_not_allowed")),
    (s("Your payment platform in Madrid", "offer"), True, ("sourced", "offer_only")),
    (s("Handling 1500 payments per second", "offer"), True, ("sourced", "offer_only")),
    (s("Handling 3,000 payments per second", "offer"), True, ("unsourced", "number")),
])
def test_verify(sentence, allow, expected):
    assert pv.verify(sentence, PROFILE, OFFER, allow_offer=allow) == expected


def _doc(*sentences):
    return {"sentences": {f"s{i}": x for i, x in enumerate(sentences)}}


def test_check_flags_sentences_whose_source_changed_or_vanished():
    doc = _doc(s("Cut latency by 40%", "experience.0.highlights.0"),
               s("Python", "skills.0"),
               s("SQL", "skills.1"))
    snap = pv.snapshot(doc["sentences"], PROFILE)
    assert snap == {"experience.0.highlights.0": "Cut latency by 40%",
                    "skills.0": "Python", "skills.1": "SQL"}
    changed = {**PROFILE, "skills": ["Python"],
               "experience": [{**PROFILE["experience"][0],
                               "highlights": ["Cut latency by 30%", "Led a team of 5"]}]}
    pv.check(doc, changed, snap)
    states = {k: (v["state"], v["reason"]) for k, v in doc["sentences"].items()}
    assert states == {"s0": ("unsourced", "profile_changed"), "s1": ("sourced", ""),
                      "s2": ("unsourced", "profile_changed")}
    assert pv.unresolved(doc) == 2


def test_check_keeps_user_resolutions():
    doc = _doc(s("Rust", state="confirmed"), s("Go", state="deleted"),
               s("Mine", state="edited"), s("Rust guru"))
    pv.check(doc, PROFILE, {})
    assert [x["state"] for x in doc["sentences"].values()] == [
        "confirmed", "deleted", "edited", "unsourced"]


def test_resolve_sentence_records_the_action():
    sentence = s("Rust guru", state="unsourced")
    pv.resolve_sentence(sentence, "edit", "  Learning Rust ")
    assert sentence["text"] == "Learning Rust" and sentence["state"] == "edited"
    assert sentence["original"] == "Rust guru"
    with pytest.raises(ValueError):
        pv.resolve_sentence(sentence, "confirm")  # only an unsourced sentence
    other = s("Rust guru", state="unsourced")
    pv.resolve_sentence(other, "confirm")
    assert other["state"] == "confirmed"
    pv.resolve_sentence(other, "delete")
    with pytest.raises(ValueError):
        pv.resolve_sentence(other, "confirm")
    with pytest.raises(ValueError):
        pv.resolve_sentence(sentence, "edit", "  ")
    with pytest.raises(ValueError):
        pv.resolve_sentence(sentence, "eval")


def test_a_term_only_in_the_offer_claimed_for_the_user_is_to_confirm():
    claim = s("Led a team of 5 in Madrid", "experience.0.highlights.1")
    assert pv.verify(claim, PROFILE, OFFER, allow_offer=True) == ("sourced", "term")
    claim["state"], claim["reason"] = "sourced", "term"
    assert pv.needs_confirmation(claim)
    assert pv.verify(s("Led a team of 5 in Madrid", "experience.0.highlights.1", "offer"),
                     PROFILE, OFFER, allow_offer=True) == ("sourced", "")


@pytest.mark.parametrize(("text", "expected"), [
    ("Led a team. Then I cut latency", []),           # sentence starts and "I"
    ("Worked as Dev at Acme with Python", ["Dev", "Acme", "Python"]),
    ("Used PostgreSQL, C++ and Node.js daily", ["PostgreSQL", "C++", "Node.js"]),
    ("Desde Enero trabajo con SQL en «Acme»", ["Enero", "SQL"]),
])
def test_terms(text, expected):
    assert pv.terms(text) == expected


def test_terms_present_in_the_sources_are_not_missing():
    assert pv.missing_terms("Worked at ACME with python", "acme · Python") == []


@pytest.mark.parametrize("sentence", [
    s("Ana"), s("Ana", "nope.0"), s("Ana", "offer"), s("Ana in 2031", "basics.name"),
    s("Ana", "basics.name"), s("Ana", "offer"), s("Ana from Madrid", "basics.name"),
])
def test_verify_only_gives_the_documented_states_and_reasons(sentence):
    for allow in (False, True):
        state, reason = pv.verify(sentence, PROFILE, OFFER, allow_offer=allow)
        assert state in pv.STATES and (reason == "" or reason in pv.REASONS)
    assert pv.CONFIRM_REASONS <= set(pv.REASONS) and pv.USER_STATES <= set(pv.STATES)
