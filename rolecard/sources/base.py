"""Common shapes for job sources: the query, what a connector returns, its metadata."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from rolecard.sources.http import SourceError
from rolecard.sources.limits import Limit


@dataclass(frozen=True)
class Query:
    text: str = ""
    location: str = ""
    remote: str = "any"  # any · only · exclude (services/prefilter)


@dataclass
class RawOffer:
    """One offer as a connector read it. Every field is UNTRUSTED (sources/normalize)."""

    source: str
    external_id: str
    url: str
    title: str
    company: str
    location: str
    description: str  # HTML or text
    remote: bool | None = None  # None: the source does not say


@dataclass
class FetchResult:
    offers: list[RawOffer] = field(default_factory=list)
    bad_items: int = 0  # items whose shape did not match and were skipped


@dataclass(frozen=True)
class SourceInfo:
    name: str
    label: str
    site_url: str  # attribution link
    endpoint: str  # without query: what source_calls stores
    limit: Limit
    fetch: Callable[[Query, dict], FetchResult]
    required_keys: tuple[str, ...] = ()  # keys of [sources] that must be set
    filters_location: bool = False  # the API itself filters by location (prefilter skips it)
    international: bool = False  # skipped for a location in Spain unless remote-only (D)
    remote_only: bool = False  # every offer is remote: skipped when remote is excluded

    def missing(self, settings: dict) -> list[str]:
        return [key for key in self.required_keys if not settings.get(key)]


def text_field(item: dict, key: str) -> str:
    """A string field, or '' if absent/null; any other type raises ``TypeError``."""
    value = item.get(key)
    if value is None:
        return ""
    if isinstance(value, bool) or not isinstance(value, str | int):
        raise TypeError(key)
    return str(value)


def items_of(data: object, key: str) -> list:
    """The list under ``key`` of a JSON object; anything else is a bad response."""
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        raise SourceError("bad_response", f"no '{key}' list")
    return data[key]
