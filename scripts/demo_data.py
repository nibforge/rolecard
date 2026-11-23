"""Seed a throwaway data folder with an invented profile and offers.

Used for the README screenshots and for trying the app without real data:

    python scripts/demo_data.py DEMO_DIR [--extra 300] [--documents]
    rolecard --data-dir DEMO_DIR

Everything here is fictional: the person, the companies and the offers. The script
refuses to write into a folder that already holds a rolecard database, so it can never
touch real data.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from rolecard import create_app
from rolecard.ai.base import AIProvider
from rolecard.config import DB_FILE
from rolecard.models import Job, Profile
from rolecard.services.documents import generate
from rolecard.services.jobs import create_job
from rolecard.services.profile import save_profile
from rolecard.services.tracking import set_status, set_tracking

PROFILE = {
    "basics": {
        "name": "Alex Demo",
        "headline": "Backend developer (Python)",
        "email": "alex.demo@example.com",
        "phone": "",
        "location": "Valencia, Spain",
        "links": ["https://example.com/alex-demo"],
        "summary": "Backend developer with six years building APIs and data pipelines "
                   "in Python for small product teams.",
    },
    "experience": [
        {"role": "Senior backend developer", "company": "Northwind Labs", "start": "2022",
         "end": "", "location": "Remote",
         "highlights": ["Designed the billing API used by 40 internal services",
                        "Cut nightly report time from 3 hours to 20 minutes",
                        "Mentored two junior developers"]},
        {"role": "Backend developer", "company": "Fabrikam Studio", "start": "2019",
         "end": "2022", "location": "Valencia, Spain",
         "highlights": ["Built the booking backend in Flask and PostgreSQL",
                        "Introduced automated tests and code review"]},
    ],
    "projects": [
        {"name": "tidy-csv", "description": "Open source CSV cleaning tool.",
         "highlights": ["Used by around 300 people a month"]},
    ],
    "education": [
        {"degree": "BSc Computer Engineering", "institution": "Example University",
         "start": "2014", "end": "2018"},
    ],
    "languages": [{"language": "Spanish", "level": "Native"},
                  {"language": "English", "level": "C1"}],
    "skills": ["Python", "Flask", "PostgreSQL", "SQLite", "REST APIs", "Docker", "Git"],
}

# title, company, location, status, score, summary, met, missing, notes
OFFERS = [
    ("Python backend developer", "Contoso Travel", "Remote (EU)", "interview", 86,
     "Strong match: Python APIs and PostgreSQL are the core of the role.",
     ["Python and Flask", "PostgreSQL", "REST API design"], ["Kubernetes"],
     "Second interview on Thursday."),
    ("Senior Python engineer", "Tailspin Data", "Madrid, Spain", "sent", 78,
     "Good fit on Python and data pipelines; asks for more cloud experience.",
     ["Python", "Data pipelines"], ["AWS certification"], ""),
    ("Backend developer (Flask)", "Litware Health", "Valencia, Spain", "prepared", 91,
     "Very close to your current work: Flask, SQL and automated tests.",
     ["Flask", "SQL", "Automated testing"], [], ""),
    ("Full-stack developer", "Adventure Works", "Barcelona, Spain", "new", 64,
     "Partial match: backend is strong, but the role is half React.",
     ["Python backend"], ["React", "TypeScript"], ""),
    ("Data engineer", "Wide World Importers", "Remote", "new", 55,
     "Some overlap in pipelines; Spark and Airflow are missing.",
     ["Python", "SQL"], ["Spark", "Airflow"], ""),
    ("Java developer", "Proseware", "Bilbao, Spain", "discarded", 22,
     "Low match: the role is Java and Spring.",
     [], ["Java", "Spring Boot"], "Not my stack."),
]


def offer_text(title: str, company: str, location: str, missing: list[str]) -> str:
    extra = ", ".join(missing) or "nothing else"
    return (f"{title} at {company} ({location}).\n\nWe are a fictional company looking "
            f"for a {title.lower()} to join a small product team. You will design and "
            f"maintain APIs, write tests and review code.\n\nRequirements: Python, SQL, "
            f"REST APIs. Nice to have: {extra}.\n\nThis offer is invented for the demo.")


def _already_used(data_dir: Path) -> bool:
    return (data_dir / DB_FILE).exists()


def seed(data_dir: Path, today: date | None = None, extra: int = 0,
         documents: bool = False) -> int:
    """Create the demo data in ``data_dir`` plus ``extra`` filler offers (to see the board
    and the list in pages) and, with ``documents``, a CV and a letter for the first offer;
    return the number of offers created."""
    if _already_used(data_dir):
        raise SystemExit(f"{data_dir} already holds a rolecard database; use an empty folder.")
    today = today or date.today()
    app = create_app(data_dir)
    with app.extensions["rolecard.sessions"]() as db:
        save_profile(db, PROFILE, source_text="Demo profile (fictional).")
        for i, row in enumerate(OFFERS):
            _add_offer(db, i, row, today)
        _add_filler(db, extra, today)
        if documents:
            _add_documents(db)
    return len(OFFERS) + extra


FILLER_ROLES = ("Backend developer", "Python engineer", "Data engineer", "Platform engineer",
                "Full-stack developer", "Site reliability engineer")
FILLER_STATUSES = ("new", "new", "new", "prepared", "sent", "discarded")


def _add_filler(db, count: int, today: date) -> None:
    """Fictional offers named "<role> #n" at "Example Co n", spread over statuses."""
    start = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
    for n in range(count):
        role = FILLER_ROLES[n % len(FILLER_ROLES)]
        job = create_job(db, text=offer_text(role, f"Example Co {n}", "Remote", []),
                         url=f"https://example.com/jobs/filler-{n}", title=f"{role} #{n}",
                         company=f"Example Co {n}", location="Remote",
                         now=start - timedelta(hours=n))
        job.score = None if n % 4 == 0 else (n * 37) % 101
        db.commit()
        status = FILLER_STATUSES[n % len(FILLER_STATUSES)]
        if status != "new":
            set_status(db, job, status, now=start - timedelta(hours=n - 1))


def _add_offer(db, i: int, row: tuple, today: date) -> None:
    title, company, location, status, score, summary, met, missing, notes = row
    when = datetime.combine(today - timedelta(days=12 - 2 * i), datetime.min.time(),
                            tzinfo=UTC)
    slug = company.lower().replace(" ", "-")
    job = create_job(db, text=offer_text(title, company, location, missing),
                     url=f"https://example.com/jobs/{slug}", title=title,
                     company=company, location=location, now=when)
    job.score, job.score_summary = score, summary
    job.score_met, job.score_missing = met, missing
    job.language, job.scored_at = "en", when
    db.commit()
    if status != "new":
        set_status(db, job, status, now=when + timedelta(days=1))
    follow_up = today + timedelta(days=3) if status in ("sent", "interview") else None
    if notes or follow_up:
        set_tracking(db, job, notes=notes, follow_up_on=follow_up)


def _s(text: str, *sources: str) -> dict:
    return {"text": text, "sources": list(sources)}


# What a model could answer for the first offer. One sentence has no source and one
# letter sentence cites only the offer, so the review screen shows both highlights.
CV_ANSWER = {
    "summary": [_s("Backend developer with six years building APIs in Python.",
                   "basics.summary")],
    "experience": [
        {"index": 0, "highlights": [
            _s("Designed the billing API used by 40 internal services.",
               "experience.0.highlights.0"),
            _s("Cut nightly report time from 3 hours to 20 minutes.",
               "experience.0.highlights.1")]},
        {"index": 1, "highlights": [
            _s("Built the booking backend in Flask and PostgreSQL.",
               "experience.1.highlights.0"),
            _s("Led the migration to Kubernetes.")]},
    ],
    "projects": [],
    "skills": [0, 1, 2, 4, 5],
}
LETTER_ANSWER = {"paragraphs": [
    [_s("I am applying for the Python backend developer role at Contoso Travel.", "offer"),
     _s("For the last six years I have built APIs and data pipelines in Python.",
        "basics.summary")],
    [_s("At Northwind Labs I designed the billing API used by 40 internal services.",
        "experience.0.highlights.0"),
     _s("Your team works on REST APIs, which is the core of my current work.", "offer")],
]}


class _ScriptedAI(AIProvider):
    """Returns the fixed answers above: the demo never calls a real model."""

    name = "demo"

    def complete(self, prompt: str, schema: dict | None = None) -> str:
        is_letter = schema is not None and "paragraphs" in schema.get("properties", {})
        return json.dumps(LETTER_ANSWER if is_letter else CV_ANSWER)


def _add_documents(db) -> None:
    job = db.scalars(select(Job).order_by(Job.id)).first()
    profile = db.get(Profile, 1).data
    for kind in ("cv", "letter"):
        generate(db, job, profile, _ScriptedAI(), kind, ui_lang="en")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("data_dir", help="an empty or new folder (never your real one)")
    parser.add_argument("--extra", type=int, default=0, metavar="N",
                        help="also add N filler offers, to see the board and list in pages")
    parser.add_argument("--documents", action="store_true",
                        help="also add a tailored CV and letter for the first offer")
    args = parser.parse_args(argv)
    if not 0 <= args.extra <= 5000:
        parser.error("--extra must be between 0 and 5000")
    count = seed(Path(args.data_dir), extra=args.extra, documents=args.documents)
    print(f"Seeded a demo profile and {count} offers in {args.data_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
