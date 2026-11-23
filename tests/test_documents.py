import json
from copy import deepcopy
from datetime import UTC, datetime

import pytest

from rolecard import get_db
from rolecard.ai import AIError, FakeProvider
from rolecard.models import Document
from rolecard.services import documents as docs
from rolecard.services.jobs import create_job
from tests.helpers import PROFILE

OFFER = "Python backend role at Pagos SL, 1,500 payments per second. " * 3
CV = {"summary": [{"text": "Backend developer.", "sources": ["basics.headline"]}],
      "experience": [{"index": 0, "highlights": [
          {"text": "Built billing APIs.", "sources": ["experience.0.highlights.0"]}]}],
      "projects": [], "skills": [0]}
LETTER = {"paragraphs": [[{"text": "Your 1500 payments per second.", "sources": ["offer"]},
                          {"text": "I am a Rust guru.", "sources": []}]]}
NOW = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()


@pytest.fixture
def job(db):
    return create_job(db, text=OFFER, url="", title="Dev")


def gen(db, job, kind="cv", answer=CV, **kw):
    return docs.generate(db, job, PROFILE, FakeProvider(json.dumps(answer)), kind, "en", **kw)


@pytest.mark.parametrize(("forced", "detected", "ui", "expected"), [
    ("es", "en", "en", "es"), ("", "es", "en", "es"), ("", "de", "es", "es"),
    ("", "", "fr", "en"),
])
def test_doc_language(job, forced, detected, ui, expected):
    job.doc_language, job.language = forced, detected
    assert docs.doc_language(job, ui) == expected


def test_generate_stores_cv_with_snapshot_and_language(db, job):
    job.language = "es"
    doc = gen(db, job)
    assert (doc.kind, doc.language, doc.reviewed_at) == ("cv", "es", None)
    assert doc.source_snapshot["_structure"]["skills"] == PROFILE["skills"]
    assert {k: v for k, v in doc.source_snapshot.items() if k != "_structure"} == {
        "basics.headline": "Backend developer",
                                   "experience.0.highlights.0": "Built billing APIs"}
    assert docs.blocked_reason(doc) == "not_reviewed"


def test_generate_letter_flags_unsourced(db, job):
    doc = gen(db, job, "letter", LETTER)
    states = [s["state"] for s in doc.content["sentences"].values()]
    assert states == ["sourced", "unsourced"]
    assert docs.blocked_reason(doc) == "unresolved"


def test_existing_document_needs_replace(db, job):
    gen(db, job)
    with pytest.raises(docs.DocumentError) as err:
        gen(db, job)
    assert err.value.code == "exists"
    other = deepcopy(CV)
    other["skills"] = [1]
    doc = gen(db, job, answer=other, replace=True)
    assert db.query(Document).count() == 1
    assert doc.content["blocks"][-2]["items"] == ["SQL"]


@pytest.mark.parametrize("raw", ["not json", json.dumps({**CV, "skills": [9]}),
                                 json.dumps({**CV, "name": "x"})])
def test_bad_answer_saves_nothing(db, job, raw):
    with pytest.raises(AIError):
        docs.generate(db, job, PROFILE, FakeProvider(raw), "cv", "en")
    assert db.query(Document).count() == 0


def test_profile_change_unsources_and_clears_review(db, job):
    doc = gen(db, job)
    docs.mark_reviewed(db, doc, NOW)
    changed = deepcopy(PROFILE)
    changed["experience"][0]["highlights"] = ["Built payment APIs"]
    docs.refresh(db, doc, changed)
    assert doc.reviewed_at is None
    assert docs.blocked_reason(doc) == "unresolved"
    reasons = [s["reason"] for s in doc.content["sentences"].values()]
    assert reasons == ["", "profile_changed"]


def test_resolve_and_review_moves_new_job_to_prepared(db, job):
    doc = gen(db, job, "letter", LETTER)
    with pytest.raises(docs.DocumentError):
        docs.mark_reviewed(db, doc)
    docs.resolve_sentence(db, doc, "s2", "confirm")
    assert docs.blocked_reason(doc) == "offer_unconfirmed"
    with pytest.raises(docs.DocumentError) as err:
        docs.mark_reviewed(db, doc)
    assert err.value.code == "offer_unconfirmed"
    docs.resolve_sentence(db, doc, "s1", "confirm")
    db.expire_all()
    assert doc.content["sentences"]["s2"]["state"] == "confirmed"
    docs.mark_reviewed(db, doc, NOW)
    assert job.status == "new"  # only a reviewed CV moves the job
    cv = gen(db, job)
    docs.mark_reviewed(db, cv, NOW)
    assert job.status == "prepared" and job.events[-1].status == "prepared"
    assert docs.blocked_reason(cv) is None
    docs.resolve_sentence(db, cv, "s1", "edit", "Backend engineer.")
    assert docs.blocked_reason(cv) == "not_reviewed"


@pytest.mark.parametrize(("sid", "action"), [("s9", "confirm"), ("s1", "eval"),
                                             ("s1", "edit")])
def test_resolve_errors(db, job, sid, action):
    doc = gen(db, job)
    with pytest.raises(docs.DocumentError):
        docs.resolve_sentence(db, doc, sid, action)


@pytest.mark.parametrize(("kind", "answer", "change"), [
    ("cv", CV, lambda p: p["experience"][0].update(end="2025")),
    ("cv", CV, lambda p: p["skills"].pop()),
    ("letter", LETTER, lambda p: p["basics"].update(name="Other Name")),
])
def test_copied_profile_facts_changed_block_export(db, job, kind, answer, change):
    doc = gen(db, job, kind, answer)
    if kind == "letter":
        docs.resolve_sentence(db, doc, "s1", "confirm")
        docs.resolve_sentence(db, doc, "s2", "confirm")
    docs.mark_reviewed(db, doc, NOW)
    changed = deepcopy(PROFILE)
    change(changed)
    docs.refresh(db, doc, changed)
    assert doc.reviewed_at is None and docs.blocked_reason(doc) == "structure_changed"
    with pytest.raises(docs.DocumentError):
        docs.mark_reviewed(db, doc)
    regenerated = docs.generate(db, job, changed, FakeProvider(json.dumps(answer)), kind,
                                "en", replace=True)
    assert docs.blocked_reason(regenerated) in ("not_reviewed", "unresolved")


def test_unrelated_profile_change_keeps_review(db, job):
    doc = gen(db, job)
    docs.mark_reviewed(db, doc, NOW)
    changed = deepcopy(PROFILE)
    changed["basics"]["summary"] = "A new summary nobody cites."
    docs.refresh(db, doc, changed)
    assert docs.blocked_reason(doc) is None
