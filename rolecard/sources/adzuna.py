"""Adzuna search API with the user's own ``app_id``/``app_key``. Terms: "Permitted use:
Personal job search"; every offer shown carries "Adzuna" linked to its site.

EXCEPTION to "a credential never travels in the URL" (spec 003, P1): Adzuna only accepts
the key as query parameters. ``sources/http`` never logs a URL nor puts it in an error,
and ``source_calls`` stores ``ENDPOINT`` without the query."""

from __future__ import annotations

from rolecard.sources.base import FetchResult, Query, RawOffer, SourceInfo, items_of, text_field
from rolecard.sources.http import request_json
from rolecard.sources.limits import Limit

ENDPOINT = "https://api.adzuna.com/v1/api/jobs"
PER_PAGE = 50


def _name(item: dict, key: str) -> str:
    value = item.get(key)
    if value is None:
        return ""
    if not isinstance(value, dict):
        raise TypeError(key)
    return text_field(value, "display_name")


def fetch(query: Query, settings: dict) -> FetchResult:
    params = {"app_id": settings["adzuna_app_id"], "app_key": settings["adzuna_app_key"],
              "results_per_page": PER_PAGE, "content-type": "application/json"}
    if query.text:
        params["title_only"] = query.text  # the query matches the job title only (R15)
    if query.location:
        params["where"] = query.location
    url = f"{ENDPOINT}/{settings.get('adzuna_country') or 'es'}/search/1"
    result = FetchResult()
    for item in items_of(request_json(url, params), "results"):
        try:
            result.offers.append(RawOffer(
                source="adzuna", external_id=text_field(item, "id"),
                url=text_field(item, "redirect_url"), title=text_field(item, "title"),
                company=_name(item, "company"), location=_name(item, "location"),
                description=text_field(item, "description")))
        except (TypeError, AttributeError):
            result.bad_items += 1
    return result


SOURCE = SourceInfo(name="adzuna", label="Adzuna", site_url="https://www.adzuna.com",
                    endpoint=ENDPOINT, limit=Limit(per_day=100), fetch=fetch,
                    required_keys=("adzuna_app_id", "adzuna_app_key"), filters_location=True)
