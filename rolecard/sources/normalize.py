"""Turn an untrusted ``RawOffer`` into the fields of a ``Job``, with the same limits as an
offer pasted by hand (``services/jobs``). HTML becomes plain text; nothing of it is kept."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

from rolecard.encoding import fix_mojibake
from rolecard.services.dedup import is_web_url
from rolecard.services.jobs import MAX_FIELD, MAX_TEXT, MAX_URL, MIN_TEXT
from rolecard.sources.base import RawOffer

MAX_ID = 200
_CONTROL = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\u2028-\u202e\ufeff]")
_BLOCK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr",
          "section", "article", "header", "footer", "blockquote", "pre", "table"}
_SKIP = {"script", "style", "template", "noscript", "iframe", "svg", "head", "title"}


@dataclass
class Offer:
    """A normalised offer, ready to store (services/search)."""

    source: str
    external_id: str
    url: str
    title: str
    company: str
    location: str
    text: str
    remote: bool | None


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skipping += 1
        elif tag in _BLOCK:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self.skipping = max(0, self.skipping - 1)
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)


def html_to_text(value: str) -> str:
    """Visible text of an HTML fragment: no tags, attributes, scripts or styles."""
    parser = _Text()
    parser.feed(value or "")
    parser.close()
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def clean(value: str, limit: int) -> str:
    """One line: repaired encoding, no control characters, spaces collapsed, truncated."""
    value = _CONTROL.sub(" ", fix_mojibake(value or ""))
    return " ".join(value.split())[:limit]


def normalize(raw: RawOffer) -> Offer | None:
    """The offer, or ``None`` if its text is too short to be worth anything."""
    title = clean(html_to_text(raw.title), MAX_FIELD)
    company = clean(html_to_text(raw.company), MAX_FIELD)
    location = clean(html_to_text(raw.location), MAX_FIELD)
    body = _CONTROL.sub(" ", fix_mojibake(html_to_text(raw.description)))
    header = " — ".join(part for part in (title, company, location) if part)
    text = f"{header}\n\n{body}".strip()[:MAX_TEXT]
    if len(text) < MIN_TEXT:
        return None
    url = (raw.url or "").strip()
    if len(url) > MAX_URL or not is_web_url(url):
        url = ""
    return Offer(source=raw.source, external_id=clean(raw.external_id, MAX_ID), url=url,
                 title=title, company=company, location=location, text=text,
                 remote=raw.remote)
