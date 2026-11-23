"""scripts/demo_data.py seeds a throwaway folder with fictional data only."""

import importlib.util
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select

from rolecard import create_app
from rolecard.models import Job, Profile

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "demo_data.py"


def _load():
    spec = importlib.util.spec_from_file_location("demo_data", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seeds_profile_and_offers_in_every_column(tmp_path):
    demo = _load()
    count = demo.seed(tmp_path / "demo", today=date(2026, 5, 4))
    app = create_app(tmp_path / "demo", testing=True)
    with app.extensions["rolecard.sessions"]() as db:
        assert db.get(Profile, 1).data["basics"]["name"] == "Alex Demo"
        jobs = db.scalars(select(Job)).all()
    assert len(jobs) == count == len(demo.OFFERS)
    assert {j.status for j in jobs} >= {"new", "prepared", "sent", "interview", "discarded"}
    assert all(j.score is not None and j.url.startswith("https://example.com/") for j in jobs)


def test_refuses_a_folder_that_already_has_data(tmp_path):
    demo = _load()
    demo.seed(tmp_path)
    with pytest.raises(SystemExit):
        demo.seed(tmp_path)


def test_demo_data_is_fictional():
    text = SCRIPT.read_text(encoding="utf-8").lower()
    for marker in ("applyline-data", "@gmail.", "c:/users", "/home/"):
        assert marker not in text


def test_extra_filler_offers_fill_the_columns(tmp_path):
    demo = _load()
    count = demo.seed(tmp_path / "demo", today=date(2026, 5, 4), extra=60)
    from rolecard import create_app
    from rolecard.models import Job
    app = create_app(tmp_path / "demo")
    with app.extensions["rolecard.sessions"]() as db:
        assert db.query(Job).count() == count == len(demo.OFFERS) + 60
        assert db.query(Job).filter(Job.status == "new").count() > 20
        assert db.query(Job).filter(Job.score.is_(None)).count() >= 15


def test_documents_option_adds_a_cv_and_a_letter_to_review(tmp_path):
    from rolecard.models import Document

    demo = _load()
    demo.seed(tmp_path / "demo", today=date(2026, 5, 4), documents=True)
    app = create_app(tmp_path / "demo", testing=True)
    with app.extensions["rolecard.sessions"]() as db:
        docs = {d.kind: d for d in db.scalars(select(Document)).all()}
    assert set(docs) == {"cv", "letter"}
    reasons = {s["reason"] for d in docs.values() for s in d.content["sentences"].values()}
    assert {"", "no_sources", "offer_only"} <= reasons  # both highlights are on show
    assert all(d.reviewed_at is None for d in docs.values())
