"""Cheap prefilter run on every offer BEFORE any AI scoring (spec 003, R10, R15).

Words are compared folded (no case, no accents, whole words) against the job TITLE only:
the query, the required words and the excluded words never look at the description.
``reason()`` returns why an offer is dropped (``"title"``, ``"missing:<word>"``,
``"excluded:<word>"``, ``"remote"``, ``"location"``) or ``None`` to keep it.
"""

from __future__ import annotations

from dataclasses import dataclass

from rolecard.services.dedup import fold

REMOTE_WORDS = ("remote", "remoto", "teletrabajo", "home office", "telework")
MAX_WORDS = 20
MAX_WORD = 60


@dataclass(frozen=True)
class Rules:
    query: str = ""
    required: tuple[str, ...] = ()
    excluded: tuple[str, ...] = ()
    location: str = ""
    remote: str = "any"  # any · only · exclude

    @classmethod
    def of(cls, search) -> Rules:
        return cls(query=search.query or "", required=tuple(search.required or ()),
                   excluded=tuple(search.excluded or ()), location=search.location or "",
                   remote=search.remote or "any")


def parse_words(text: str) -> list[str]:
    """Comma-separated words or phrases as typed in the form: trimmed, lower case,
    without empties or repeats, at most ``MAX_WORDS`` of ``MAX_WORD`` characters."""
    out: list[str] = []
    for part in (text or "").split(","):
        word = " ".join(part.split()).lower()[:MAX_WORD]
        if fold(word) and word not in out:
            out.append(word)
    return out[:MAX_WORDS]


def _padded(text: str) -> str:
    return f" {fold(text)} "


def _has(haystack: str, phrase: str) -> bool:
    folded = fold(phrase)
    return bool(folded) and f" {folded} " in haystack


def is_remote(offer) -> bool:
    """The source's own flag when it gives one; otherwise remote words in title or place."""
    if offer.remote is not None:
        return offer.remote
    haystack = _padded(f"{offer.title} {offer.location}")
    return any(_has(haystack, word) for word in REMOTE_WORDS)


def city(location: str) -> str:
    """The part of a search location compared with offers: before the first comma."""
    return fold((location or "").split(",")[0])


def _location_ok(rules: Rules, offer, remote: bool) -> bool:
    wanted = city(rules.location)
    if not wanted or f" {wanted} " in _padded(offer.location):
        return True
    return rules.remote == "only" and remote


def reason(rules: Rules, offer, local_location: bool = True) -> str | None:
    """Why ``offer`` is dropped, or ``None``. ``local_location`` is False for a source
    whose API already filtered by location (Adzuna's ``where``)."""
    title = _padded(offer.title)
    if not all(_has(title, word) for word in fold(rules.query).split()):
        return "title"
    for word in rules.required:
        if not _has(title, word):
            return f"missing:{word}"
    for word in rules.excluded:
        if _has(title, word):
            return f"excluded:{word}"
    remote = is_remote(offer)
    if (rules.remote == "only" and not remote) or (rules.remote == "exclude" and remote):
        return "remote"
    if local_location and not _location_ok(rules, offer, remote):
        return "location"
    return None
