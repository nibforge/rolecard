"""ORM mapping of the tables created by the SQL migrations.

These classes never create tables (no ``create_all``): ``rolecard/migrations/`` does.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

STATUSES = ("new", "prepared", "sent", "replied", "interview", "offer", "discarded")


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Aware UTC datetimes stored as ISO 8601 text."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime; use an aware UTC datetime")
        return value.astimezone(UTC).isoformat()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return datetime.fromisoformat(value).astimezone(UTC)


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str | None] = mapped_column(Text)
    url_key: Mapped[str | None] = mapped_column(Text, unique=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    company: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location: Mapped[str] = mapped_column(Text, nullable=False, default="")
    language: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="new")
    score: Mapped[int | None] = mapped_column(Integer)
    score_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    score_met: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    score_missing: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    scored_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    follow_up_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    doc_language: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    external_id: Mapped[str | None] = mapped_column(Text)
    match_key: Mapped[str | None] = mapped_column(Text)
    search_id: Mapped[int | None] = mapped_column(
        ForeignKey("searches.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    events: Mapped[list[JobEvent]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="JobEvent.at",
    )
    documents: Mapped[list[Document]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )


class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    job: Mapped[Job] = relationship(back_populates="events")


class Document(Base):
    """A tailored CV or cover letter for one job (one per kind). ``content`` holds the
    sections and sentences with their sources and review state (services/provenance)."""

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("job_id", "kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    job: Mapped[Job] = relationship(back_populates="documents")


class Search(Base):
    """A saved search over the job sources, with its prefilter (services/search)."""

    __tablename__ = "searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location: Mapped[str] = mapped_column(Text, nullable=False, default="")
    remote: Mapped[str] = mapped_column(Text, nullable=False, default="any")
    sources: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    required: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    excluded: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_summary: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow
    )


class SourceCall(Base):
    """Local call counter per source, so each API's usage limits are respected."""

    __tablename__ = "source_calls"

    source: Mapped[str] = mapped_column(Text, primary_key=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, default="")
    day: Mapped[str] = mapped_column(Text, nullable=False, default="")
    calls_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_call_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
