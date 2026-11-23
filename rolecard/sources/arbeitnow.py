"""Arbeitnow free public job board API (no key, "please do not abuse"). It has no search:
two pages at most per run (300 offers each) and the query is applied here, to the job
title only (spec 003, R15)."""

from __future__ import annotations

from rolecard.services.dedup import fold
from rolecard.sources.base import FetchResult, Query, RawOffer, SourceInfo, items_of, text_field
from rolecard.sources.http import request_json
from rolecard.sources.limits import Limit

ENDPOINT = "https://www.arbeitnow.com/api/job-board-api"
PAGES = 2


def _matches(words: list[str], offer: RawOffer) -> bool:
    haystack = f" {fold(offer.title)} "
    return all(f" {word} " in haystack for word in words)


def _offer(item: dict) -> RawOffer:
    remote = item.get("remote")
    if remote is not None and not isinstance(remote, bool):
        raise TypeError("remote")
    return RawOffer(source="arbeitnow", external_id=text_field(item, "slug"),
                    url=text_field(item, "url"), title=text_field(item, "title"),
                    company=text_field(item, "company_name"),
                    location=text_field(item, "location"),
                    description=text_field(item, "description"), remote=remote)


def fetch(query: Query, settings: dict) -> FetchResult:
    words = fold(query.text).split()
    result = FetchResult()
    for page in range(1, PAGES + 1):
        data = request_json(ENDPOINT, {"page": page})
        for item in items_of(data, "data"):
            try:
                offer = _offer(item)
            except (TypeError, AttributeError):
                result.bad_items += 1
                continue
            if _matches(words, offer):
                result.offers.append(offer)
        links = data.get("links") if isinstance(data, dict) else None
        if not isinstance(links, dict) or not links.get("next"):
            break
    return result


SOURCE = SourceInfo(name="arbeitnow", label="Arbeitnow", site_url="https://www.arbeitnow.com",
                    endpoint=ENDPOINT, limit=Limit(min_interval=60), fetch=fetch,
                    international=True)
