"""Accessibility review of every page (DISENO.md): lang, one h1, skip link, landmarks,
labelled controls, named buttons and links, alt text, no positive tabindex."""

import importlib.util
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import pytest
from sqlalchemy import select

from rolecard import create_app
from rolecard.models import Job

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "demo_data.py"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source",
        "track", "wbr"}
NAMED = {"button", "a"}


class Page(HTMLParser):
    """Collects what the checks need in one pass: labels, ids, controls and the text
    inside each open button or link."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags, self.ids, self.label_for, self.controls = [], set(), set(), []
        self.stack, self.unnamed, self.h1, self.lang = [], [], 0, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append((tag, a))
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "h1":
            self.h1 += 1
        if tag == "label" and a.get("for"):
            self.label_for.add(a["for"])
        inside_label = any(t == "label" for t, _, _ in self.stack)
        if tag in ("input", "select", "textarea") and a.get("type") not in ("hidden", "submit"):
            self.controls.append((tag, a, inside_label))
        if tag in VOID:
            if tag == "img":
                for frame in self.stack:
                    frame[2].append(a.get("alt") or "")
            return
        self.stack.append((tag, a, []))

    def handle_endtag(self, tag):
        while self.stack:
            open_tag, a, text = self.stack.pop()
            if open_tag in NAMED and not ("".join(text).strip() or a.get("aria-label")
                                          or a.get("aria-labelledby") or a.get("title")):
                self.unnamed.append((open_tag, a))
            if self.stack:
                self.stack[-1][2].extend(text)
            if open_tag == tag:
                break

    def handle_data(self, data):
        if self.stack:
            self.stack[-1][2].append(data)


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("demo_data", SCRIPT)
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    home = tmp_path_factory.mktemp("a11y")
    demo.seed(home, today=date(2026, 5, 4))
    app = create_app(home, testing=True)
    with app.extensions["rolecard.sessions"]() as db:
        job_id = db.scalars(select(Job.id).where(Job.status == "prepared")).first()
    urls = [r.rule for r in app.url_map.iter_rules()
            if "GET" in r.methods and not r.arguments and not r.rule.startswith("/static")]
    urls += [f"/jobs/{job_id}", f"/jobs/{job_id}/documents/cv"]
    client, out = app.test_client(), {}
    for url in urls:
        response = client.get(url)
        if response.status_code == 200 and response.mimetype == "text/html":
            body = response.get_data(as_text=True)
            if "<html" in body:
                out[url] = Page()
                out[url].feed(body)
    assert {"/", "/board", "/jobs", "/profile", "/settings", f"/jobs/{job_id}"} <= set(out)
    return out


def test_every_page_has_lang_one_h1_and_skip_link(pages):
    assert not {url: page.h1 for url, page in pages.items() if page.h1 != 1}
    for url, page in pages.items():
        assert page.lang in ("en", "es"), url
        assert "principal" in page.ids, url
        assert any(t == "a" and a.get("href") == "#principal" for t, a in page.tags), url
        assert any(t == "main" for t, _ in page.tags), url


def test_every_control_has_a_label(pages):
    for url, page in pages.items():
        for tag, a, inside_label in page.controls:
            named = (inside_label or a.get("id") in page.label_for or a.get("aria-label")
                     or a.get("aria-labelledby") or a.get("title"))
            assert named, (url, tag, a)


def test_buttons_and_links_have_an_accessible_name(pages):
    for url, page in pages.items():
        assert not page.unnamed, (url, page.unnamed[:3])


def test_images_have_alt_and_no_positive_tabindex(pages):
    for url, page in pages.items():
        for tag, a in page.tags:
            if tag == "img":
                assert "alt" in a, (url, a)
            assert int(a.get("tabindex") or 0) <= 0, (url, tag, a)


def test_described_by_and_current_page_point_somewhere(pages):
    for url, page in pages.items():
        for tag, a in page.tags:
            for ref in (a.get("aria-describedby") or "").split():
                assert ref in page.ids, (url, tag, ref)
        assert sum(a.get("aria-current") == "page" for _, a in page.tags) >= 1 or url == "/", url


def test_follow_up_label_reads_as_one_sentence(app):
    with app.test_request_context():
        from flask import g, render_template_string
        g.lang = "en"
        html = render_template_string(
            '{% from "_macros.html" import follow_up_label %}{{ follow_up_label(d, today) }}',
            d=date(2026, 11, 30), today=date(2026, 11, 24))
    assert '<span class="solo-lectores">Follow up: 30 Nov</span>' in html
    assert '<span aria-hidden="true">30 Nov</span>' in html
