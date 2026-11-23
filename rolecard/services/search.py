"""Run a saved search: each chosen source in turn, normalise, prefilter, de-duplicate and
add the survivors to the board as unscored ``new`` offers.

A source that fails, lacks its keys or hit its limit is reported and skipped; the others
go on (constitution IX). The summary of the last run is stored on the search.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime

from sqlalchemy.orm import Session

from rolecard.models import Search, utcnow
from rolecard.services import jobs as jobs_svc
from rolecard.services.dedup import match_key, text_key, url_key
from rolecard.services.prefilter import Rules, reason
from rolecard.sources import REGISTRY, enabled, source_settings
from rolecard.sources.base import FetchResult, Query
from rolecard.sources.geo import in_spain
from rolecard.sources.http import SourceError
from rolecard.sources.limits import RateLimited, check, record
from rolecard.sources.normalize import Offer, normalize

MAX_NEW_PER_SOURCE = 50
log = logging.getLogger(__name__)
# One run at a time in this process: two clicks or tabs must not both pass the per-source
# limit check before either records its call, nor add the same offer twice.
_RUN_LOCK = threading.Lock()


class _Seen:
    """Keys of offers already met in this run (across sources)."""

    def __init__(self):
        self.keys: set[str] = set()

    def add(self, *keys: str | None) -> bool:
        """False if any key was already seen; records all of them otherwise."""
        present = [k for k in keys if k]
        if any(k in self.keys for k in present):
            return False
        self.keys.update(present)
        return True


def _row(name: str) -> dict:
    return {"name": name, "label": REGISTRY[name].label, "status": "ok", "error": "",
            "retry_at": "", "received": 0, "bad_items": 0, "too_short": 0,
            "duplicates": 0, "filtered": {}, "over_cap": 0, "added": 0}


def _fetch(db: Session, name: str, query: Query, merged: dict, on: list[str],
           now: datetime, row: dict) -> FetchResult | None:
    info = REGISTRY[name]
    if name not in on:
        row["status"] = "disabled"
        return None
    if info.missing(merged):
        row["status"] = "not_configured"
        return None
    try:
        check(db, name, info.limit, now)
    except RateLimited as limited:
        row["status"], row["retry_at"] = "rate_limited", limited.retry_at.isoformat()
        return None
    try:
        return info.fetch(query, merged)
    except SourceError as exc:
        row["status"], row["error"] = "error", exc.code
    except Exception as exc:  # noqa: BLE001 - one source must never break the search
        row["status"], row["error"] = "error", "bad_response"
        log.warning("source %s failed: %s", name, type(exc).__name__)
    finally:
        record(db, name, info.endpoint, now)
    return None


def _store(db: Session, search: Search, offer: Offer, seen: _Seen, row: dict) -> None:
    ukey, tkey = url_key(offer.url), text_key(offer.text)
    mkey = match_key(offer.company, offer.title, offer.location)
    if not seen.add(ukey, mkey, tkey) or jobs_svc.find_duplicate(db, ukey, tkey, mkey=mkey):
        row["duplicates"] += 1
        return
    if row["added"] >= MAX_NEW_PER_SOURCE:
        row["over_cap"] += 1
        return
    job = jobs_svc.create_job(
        db, text=offer.text, url=offer.url, title=offer.title, company=offer.company,
        location=offer.location, source=offer.source, external_id=offer.external_id,
        search_id=search.id)
    if isinstance(job, jobs_svc.Duplicate):
        row["duplicates"] += 1
    else:
        row["added"] += 1


def skips_international(search: Search) -> bool:
    """Decision D: a location in Spain leaves out the international sources (Remotive,
    Arbeitnow) unless the search is remote-only."""
    return in_spain(search.location) and search.remote != "only"


def run_search(db: Session, search: Search, settings: dict,
               now: datetime | None = None) -> dict:
    """Run ``search`` (serialised with any other run); see ``_run_search``."""
    with _RUN_LOCK:
        return _run_search(db, search, settings, now)


def _run_search(db: Session, search: Search, settings: dict,
                now: datetime | None = None) -> dict:
    """Run ``search`` and return (and store) its summary; every offer goes through
    ``services/prefilter`` before it is stored."""
    now = now or utcnow()
    merged, on = source_settings(settings), enabled(settings)
    query = Query(text=search.query, location=search.location, remote=search.remote)
    rules, skip_intl = Rules.of(search), skips_international(search)
    seen, rows = _Seen(), []
    for name in [n for n in search.sources if n in REGISTRY]:
        row, info = _row(name), REGISTRY[name]
        rows.append(row)
        if skip_intl and info.international:
            row["status"] = "international"
            continue
        if info.remote_only and search.remote == "exclude":
            row["status"] = "remote_only"
            continue
        result = _fetch(db, name, query, merged, on, now, row)
        if result is None:
            continue
        row["received"], row["bad_items"] = len(result.offers), result.bad_items
        for raw in result.offers:
            offer = normalize(raw)
            if offer is None:
                row["too_short"] += 1
                continue
            why = reason(rules, offer, local_location=not info.filters_location)
            if why:
                row["filtered"][why] = row["filtered"].get(why, 0) + 1
                continue
            _store(db, search, offer, seen, row)
    summary = {"at": now.isoformat(), "sources": rows,
               "added": sum(r["added"] for r in rows)}
    search.last_run_at, search.last_summary = now, summary
    db.commit()
    return summary
