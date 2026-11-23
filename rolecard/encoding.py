"""Repair UTF-8 text that was decoded as Windows-1252 somewhere ("TÃ©cnico")."""

from __future__ import annotations

import re

# A lead byte of a UTF-8 sequence (as cp1252/latin-1 text) followed by continuation
# bytes. Real CV text practically never contains these pairs.
_CONT = "\x80-\xbfŒœŠšŸŽžƒˆ˜" \
        "–—‘-‚“-„†-•…‰‹›" \
        "€™"
_MOJIBAKE = re.compile(f"[\xc2-\xf4][{_CONT}]+")


def _byte(char: str) -> int:
    try:
        return char.encode("cp1252")[0]
    except UnicodeEncodeError:
        return ord(char)  # the five bytes cp1252 leaves undefined map as latin-1


def _repair(match: re.Match) -> str:
    chunk = match.group(0)
    try:
        return bytes(_byte(c) for c in chunk).decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        return chunk


def fix_mojibake(text: str) -> str:
    """``text`` with every run that is valid double-encoded UTF-8 decoded back."""
    return _MOJIBAKE.sub(_repair, text) if text else text
