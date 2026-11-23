import json

import pytest

from rolecard import get_db
from rolecard.ai import AIError, FakeProvider
from rolecard.services.jobs import create_job
from rolecard.services.scoring import score_job
from tests.helpers import PROFILE

TEXT = "Acme Data seeks a backend developer in Valencia: Python, SQL, Kubernetes. " * 2


def answer(**changes):
    data = {"score": 82, "summary": "Good fit.", "met": ["Python", "SQL"],
            "missing": ["Kubernetes"], "language": "EN", "title": "Backend developer",
            "company": "Acme Data", "location": "Valencia"}
    data.update(changes)
    return json.dumps(data)


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()


def test_score_stores_everything_and_fills_missing_details(db):
    job = create_job(db, text=TEXT, title="My own title")
    fake = FakeProvider(answer())
    score_job(db, job, PROFILE, fake, "es")
    assert job.score == 82 and job.score_summary == "Good fit."
    assert job.score_met == ["Python", "SQL"] and job.score_missing == ["Kubernetes"]
    assert job.language == "en" and job.scored_at is not None
    assert job.title == "My own title" and job.company == "Acme Data"
    assert job.location == "Valencia"
    prompt = fake.prompts[0]
    assert "Spanish" in prompt and "Ana Test Example" in prompt
    assert prompt.rstrip().endswith("</untrusted_document>")


@pytest.mark.parametrize(
    "bad",
    [
        answer(score=150), answer(score=-5), answer(score="80"), answer(score=80.5),
        answer(summary=""), answer(met="Python"), answer(apply_url="https://evil"),
        answer(met=["x"] * 16), json.dumps({"score": 80}), "Score: 80",
    ],
)
def test_bad_answers_change_nothing(db, bad):
    job = create_job(db, text=TEXT)
    with pytest.raises(AIError):
        score_job(db, job, PROFILE, FakeProvider(bad), "en")
    db.refresh(job)
    assert job.score is None and job.company == "" and job.score_met == []
