"""Keys used to spot the same offer twice: a normalised URL and a hash of the text."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = frozenset({"gclid", "fbclid", "mc_cid", "mc_eid", "ref", "refid"})
DEFAULT_PORTS = {"http": 80, "https": 443}


def is_web_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018 - raises ValueError for a bad or out-of-range port
    except ValueError:
        return False
    return parts.scheme.lower() in ("http", "https") and bool(parts.hostname)


def url_key(url: str | None) -> str | None:
    """Scheme and host in lower case, no fragment, no tracking parameters, no
    default port and no trailing slash. ``None`` for an empty or non-web URL."""
    if not url or not is_web_url(url.strip()):
        return None
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if parts.port and parts.port != DEFAULT_PORTS[scheme]:
        host = f"{host}:{parts.port}"
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS]
    path = parts.path.rstrip("/")
    return urlunsplit((scheme, host, path, urlencode(query), ""))


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def text_key(text: str) -> str:
    """SHA-256 of the text with spaces collapsed and in lower case."""
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def fold(text: str) -> str:
    """Lower case, no accents, punctuation as spaces, spaces collapsed: for comparing words."""
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w]+", " ", plain).split())


def match_key(company: str, title: str, location: str = "") -> str | None:
    """The same offer from two sources: company + title + location, folded. ``None``
    without company or title (too little to call two offers the same)."""
    company, title = fold(company), fold(title)
    if not company or not title:
        return None
    return f"{company}|{title}|{fold(location)}"
