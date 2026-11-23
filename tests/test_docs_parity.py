"""The public documents only point at files that exist."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_PATH = re.compile(r"`((?:rolecard|tests|scripts|docs)/[\w./-]+)`")


@pytest.mark.parametrize("doc", ["ARCHITECTURE.md", "SECURITY.md"])
def test_every_file_named_exists(doc):
    text = (ROOT / doc).read_text(encoding="utf-8")
    named = {m.rstrip("/") for m in _PATH.findall(text) if "NNNN" not in m}
    assert named, doc
    assert sorted(p for p in named if not (ROOT / p).exists()) == []


PAIRS = [("README.md", "README.es.md"), ("docs/guide.en.md", "docs/guide.es.md"),
         ("docs/ai.en.md", "docs/ai.es.md"), ("INSTALL.md", "INSTALACION.md"),
         ("docs/install.en.md", "docs/install.es.md")]
PUBLIC = [doc for pair in PAIRS for doc in pair] + ["docs/index.md"]
_HEADING = re.compile(r"^(#+) ", re.M)
_LINK = re.compile(r"(!?)\[[^\]]*\]\(([^)\s]+)\)")
_FENCE = re.compile(r"^```.*?^```", re.M | re.S)


def _text(doc: str) -> str:
    return (ROOT / doc).read_text(encoding="utf-8")


def _links(doc: str) -> list[tuple[bool, str]]:
    return [(bang == "!", target) for bang, target in _LINK.findall(_text(doc))]


def _figures(doc: str) -> list[str]:
    """Numbers outside code blocks, in a form both languages share (8,000 = 8.000)."""
    prose = _FENCE.sub("", _text(doc))
    return [re.sub(r"[.,]", "", n) for n in re.findall(r"\d[\d.,]*\d|\d", prose)]


@pytest.mark.parametrize("en,es", PAIRS)
def test_each_pair_has_the_same_shape(en, es):
    assert _HEADING.findall(_text(en)) == _HEADING.findall(_text(es))
    images = [t.replace("/en/", "/es/") for is_img, t in _links(en) if is_img]
    assert images == [t for is_img, t in _links(es) if is_img]
    external = sorted(t for _, t in _links(en) if t.startswith("http"))
    assert external == sorted(t for _, t in _links(es) if t.startswith("http"))
    assert _figures(en) == _figures(es)


def _steps(doc: str) -> list[int]:
    """Numbered steps and bullets per section, outside code blocks."""
    sections = re.split(r"^#+ .*$", _FENCE.sub("", _text(doc)), flags=re.M)
    return [len(re.findall(r"^\s*(?:\d+\.|-) ", s, re.M)) for s in sections]


@pytest.mark.parametrize("en,es", PAIRS)
def test_each_pair_has_the_same_steps_in_each_section(en, es):
    assert _steps(en) == _steps(es)


def test_the_ai_guide_explains_keys_and_common_problems():
    for doc, key, gemini, problems in [
        ("docs/ai.en.md", "## What is an API key?", "## Set up Gemini", "## Common problems"),
        ("docs/ai.es.md", "## ¿Qué es una clave de API?", "## Configurar Gemini",
         "## Problemas frecuentes"),
    ]:
        sections = re.findall(r"^## .*$", _text(doc), re.M)
        assert sections[-1] == problems, doc
        assert sections[sections.index(key) + 1].startswith(gemini), doc  # just before it


@pytest.mark.parametrize("en,es", PAIRS)
def test_each_document_links_to_its_translation_at_the_top(en, es):
    assert f"({Path(es).name})" in "".join(_text(en).splitlines()[:3])
    assert f"({Path(en).name})" in "".join(_text(es).splitlines()[:3])


@pytest.mark.parametrize("doc", PUBLIC)
def test_every_relative_link_and_image_exists(doc):
    base = (ROOT / doc).parent
    local = {t.split("#")[0] for _, t in _links(doc) if not t.startswith(("http", "#"))}
    assert local, doc
    assert sorted(t for t in local if not (base / t).exists()) == []


def test_the_screenshots_exist_in_both_languages():
    en = sorted(p.name for p in (ROOT / "docs/img/en").glob("*.png"))
    assert en and en == sorted(p.name for p in (ROOT / "docs/img/es").glob("*.png"))
    used = {Path(t).name for doc in PUBLIC for is_img, t in _links(doc) if is_img}
    assert sorted(set(en) - used) == []  # no screenshot published for nothing
