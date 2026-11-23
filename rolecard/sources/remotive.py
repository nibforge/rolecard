"""Remotive public API (no key). Terms: link to the Remotive URL and name Remotive as the
source; at most 4 requests a day (more than 2 a minute is blocked). Its ``search`` also
looks at the description: services/prefilter keeps only title matches (R15)."""

from __future__ import annotations

from rolecard.sources.base import FetchResult, Query, RawOffer, SourceInfo, items_of, text_field
from rolecard.sources.http import request_json
from rolecard.sources.limits import Limit

ENDPOINT = "https://remotive.com/api/remote-jobs"
MAX_RESULTS = 100


def fetch(query: Query, settings: dict) -> FetchResult:
    params = {"limit": MAX_RESULTS}
    if query.text:
        params["search"] = query.text
    result = FetchResult()
    for item in items_of(request_json(ENDPOINT, params), "jobs"):
        try:
            result.offers.append(RawOffer(
                source="remotive", external_id=text_field(item, "id"),
                url=text_field(item, "url"), title=text_field(item, "title"),
                company=text_field(item, "company_name"),
                location=text_field(item, "candidate_required_location"),
                description=text_field(item, "description"), remote=True))
        except (TypeError, AttributeError):
            result.bad_items += 1
    return result


SOURCE = SourceInfo(name="remotive", label="Remotive", site_url="https://remotive.com",
                    endpoint=ENDPOINT, limit=Limit(per_day=4, min_interval=60), fetch=fetch,
                    international=True, remote_only=True)
