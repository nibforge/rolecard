"""WCAG AA for every text/background pair the design system documents, in both themes."""

import re
from pathlib import Path

import pytest

TOKENS = Path(__file__).resolve().parent.parent / "rolecard" / "static" / "css" / "tokens.css"
BACKGROUNDS = ("canvas", "surface", "surface-sunken")
PAIRS = [
    *[(fg, bg, 4.5) for fg in ("text", "text-muted", "text-subtle", "accent-text")
      for bg in BACKGROUNDS],
    ("text", "surface-hover", 4.5), ("text-muted", "surface-hover", 4.5),
    ("accent-text", "accent-subtle", 4.5), ("text", "accent-subtle", 4.5),
    ("on-accent", "accent", 4.5), ("on-danger", "danger-solid", 4.5),
    ("success", "success-subtle", 4.5), ("warning", "warning-subtle", 4.5),
    ("danger", "danger-subtle", 4.5), ("danger", "surface", 4.5),
    ("success", "surface", 4.5), ("warning", "surface", 4.5),
    *[("border-control", bg, 3) for bg in BACKGROUNDS],
    *[("accent", bg, 3) for bg in BACKGROUNDS],  # focus ring
]


def _block(css: str, selector: str) -> dict[str, str]:
    start = css.index(selector)
    body = css[css.index("{", start) + 1:css.index("}", start)]
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-f]{6})\s*;", body, re.I))


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _ratio(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _themes() -> dict[str, dict[str, str]]:
    css = TOKENS.read_text(encoding="utf-8")
    light = _block(css, ":root {")
    return {
        "light": light,
        "dark (preference)": {**light, **_block(css, 'html:not([data-theme="light"])')},
        "dark (attribute)": {**light, **_block(css, ':root[data-theme="dark"]')},
    }


@pytest.mark.parametrize("theme", ["light", "dark (preference)", "dark (attribute)"])
def test_documented_pairs_meet_aa(theme):
    colors = _themes()[theme]
    low = [f"{fg} on {bg}: {_ratio(colors[fg], colors[bg]):.2f}"
           for fg, bg, minimum in PAIRS if _ratio(colors[fg], colors[bg]) < minimum]
    assert low == []


def test_dark_blocks_define_the_same_colors():
    themes = _themes()
    assert themes["dark (preference)"] == themes["dark (attribute)"]
    assert themes["dark (preference)"]["canvas"] != themes["light"]["canvas"]
