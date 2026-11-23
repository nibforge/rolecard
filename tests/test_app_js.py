"""app.js copy and print handlers, run in node with a minimal stubbed DOM."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

APP_JS = Path(__file__).resolve().parent.parent / "rolecard" / "static" / "js" / "app.js"

HARNESS = r"""
const vm = require("vm"), fs = require("fs");
const listeners = {}, log = [];
function el(attrs, text) {
  return { attrs, textContent: text, getAttribute: (n) => attrs[n] ?? null,
           closest(sel) { const n = sel.slice(1, -1); return n in attrs ? this : null; } };
}
const source = el({}, "Dear team,\n\nI build APIs.");
const copy = el({"data-copy": "texto-carta", "data-copied": "Copied"}, "Copy text");
const print = el({"data-print": ""}, "Print");
const ctx = {
  document: { addEventListener: (n, f) => { listeners[n] = f; },
              getElementById: (id) => (id === "texto-carta" ? source : null),
              querySelector: () => null },
  navigator: { clipboard: {
    writeText: (t) => { log.push(["copy", t]); return Promise.resolve(); } } },
  window: { print: () => log.push(["print"]) },
};
vm.runInNewContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
listeners.click({ target: copy });
listeners.click({ target: print });
setTimeout(() => console.log(JSON.stringify({ log, label: copy.textContent })), 0);
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_copy_and_print_buttons():
    out = subprocess.run(["node", "-e", HARNESS, str(APP_JS)], capture_output=True,
                         text=True, check=True, timeout=30).stdout
    result = json.loads(out)
    assert result["log"] == [["copy", "Dear team,\n\nI build APIs."], ["print"]]
    assert result["label"] == "Copied"


SELECT_ALL = r"""
const vm = require("vm"), fs = require("fs");
const listeners = {}, asked = [];
const rows = [{ checked: false }, { checked: true }];
const all = { checked: true, getAttribute: (n) => (n === "form" ? "bulk" : null),
              closest: (sel) => (sel === "[data-select-all]" ? all : null) };
const other = { closest: () => null };
const ctx = { document: {
  addEventListener: (n, f) => { listeners[n] = f; }, querySelector: () => null,
  querySelectorAll: (sel) => { asked.push(sel); return rows; } } };
vm.runInNewContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
listeners.change({ target: other });
listeners.change({ target: all });
const ticked = rows.map((r) => r.checked);
all.checked = false;
listeners.change({ target: all });
console.log(JSON.stringify({ asked, ticked, cleared: rows.map((r) => r.checked) }));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_select_all_ticks_the_rows_of_its_form():
    out = subprocess.run(["node", "-e", SELECT_ALL, str(APP_JS)], capture_output=True,
                         text=True, check=True, timeout=30).stdout
    result = json.loads(out)
    assert result["asked"] == ['input[name="ids"][form="bulk"]'] * 2
    assert result["ticked"] == [True, True] and result["cleared"] == [False, False]


SHORTCUTS = r"""
const vm = require("vm"), fs = require("fs");
const listeners = {}, log = [];
function classes() {
  const set = new Set();
  return { set, toggle: (c, on) => (on ? set.add(c) : set.delete(c)), contains: (c) => set.has(c) };
}
function sentence(id, pending) {
  const attrs = { "data-sentence": id, href: "#editar-" + id };
  if (pending) { attrs["data-pending"] = ""; }
  return { attrs, classList: classes(), getAttribute: (n) => attrs[n] ?? null };
}
function editor(id) {
  const details = { open: false };
  return { id, details, classList: classes(),
           getAttribute: (n) => (n === "data-editor" ? id : null),
           querySelector: (s) => (s === "details" ? details : null),
           scrollIntoView: () => log.push(["scroll", id]) };
}
const sents = [sentence("s1", true), sentence("s2", false), sentence("s3", true)];
const editors = sents.map((s) => editor(s.attrs["data-sentence"]));
const search = { focus: () => log.push(["focus-search"]) };
const body = { getAttribute: (n) => (n === "data-shortcut-new" ? "/jobs/new" : null) };
const ctx = {
  document: {
    addEventListener: (n, f) => { listeners[n] = f; },
    querySelector: (s) => ({ "[data-shortcut-search]": search, "[data-shortcut-new]": body,
                             "[data-sentence]": sents[0] })[s] || null,
    querySelectorAll: (s) => (s === "[data-editor]" ? editors
      : s === "[data-sentence][data-pending]" ? sents.filter((x) => "data-pending" in x.attrs)
      : s === "[data-sentence]" ? sents : []),
  },
  window: { location: { assign: (u) => log.push(["go", u]) } },
};
vm.runInNewContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
function press(k, target) {
  let prevented = false;
  listeners.keydown({ key: k, target: target || { tagName: "BODY" },
                      preventDefault: () => { prevented = true; } });
  return prevented;
}
const active = () => sents.filter((s) => s.classList.contains("rc-s--active"))
  .map((s) => s.attrs["data-sentence"]);
const steps = [];
press("j"); steps.push(active());
press("J"); steps.push(active());
press("j"); steps.push(active());
press("k"); steps.push(active());
const inField = press("j", { tagName: "TEXTAREA" });
const withCtrl = (() => { let p = false; listeners.keydown({ key: "n", ctrlKey: true,
  target: { tagName: "BODY" }, preventDefault: () => { p = true; } }); return p; })();
press("/"); press("n");
press("/", { tagName: "INPUT" });
let clicked = false;
listeners.click({ target: { closest: (s) => (s === "[data-sentence]" ? sents[1] : null) },
                  preventDefault: () => { clicked = true; } });
console.log(JSON.stringify({ steps, inField, withCtrl, log, clicked, after: active(),
                             open: editors.map((e) => e.details.open) }));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_shortcuts_and_sentence_panel():
    out = subprocess.run(["node", "-e", SHORTCUTS, str(APP_JS)], capture_output=True,
                         text=True, check=True, timeout=30).stdout
    result = json.loads(out)
    assert result["steps"] == [["s1"], ["s3"], ["s1"], ["s3"]]
    assert result["inField"] is False and result["withCtrl"] is False
    assert ["focus-search"] in result["log"] and ["go", "/jobs/new"] in result["log"]
    assert result["log"].count(["focus-search"]) == 1
    assert result["clicked"] is True and result["after"] == ["s2"]
    assert result["open"] == [True, True, True]


TABS_AND_BUSY = r"""
const vm = require("vm"), fs = require("fs");
const listeners = {}, log = [];
function node(attrs) {
  return { attrs, hidden: false, getAttribute: (n) => attrs[n] ?? null,
           setAttribute: (n, v) => { attrs[n] = v; }, removeAttribute: (n) => { delete attrs[n]; },
           hasAttribute: (n) => n in attrs,
           closest(sel) {
             const m = sel.match(/\[([\w-]+)/);
             return m && m[1] in attrs ? this : null;
           } };
}
const tabs = ["basics", "skills"].map((t) => node({ "data-tab": t, href: "/profile?tab=" + t }));
const panels = ["basics", "skills"].map((t) => node({ "data-tab-panel": t }));
panels[1].hidden = true;
const input = { value: "basics" };
const name = node({ name: "basics-name" });
name.closest = () => panels[0];
const buttons = [{ disabled: false }, { disabled: false }], label = { hidden: true };
const form = node({ "data-busy": "" });
form.querySelectorAll = () => buttons;
form.querySelector = () => label;
const ctx = {
  document: {
    addEventListener: (n, f, capture) => { listeners[n + (capture ? "!" : "")] = f; },
    querySelector: (s) => (s === "[data-tab-input]" ? input
      : tabs.find((t) => s.includes('"' + t.attrs["data-tab"] + '"')) || null),
    querySelectorAll: (s) => (s === "[data-tab-panel]" ? panels : s === "a[data-tab]" ? tabs : []),
  },
  window: { history: { replaceState: (a, b, url) => log.push(url) } },
  setTimeout: (f) => f(),
};
vm.runInNewContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
let prevented = false;
listeners.click({ target: tabs[1], preventDefault: () => { prevented = true; } });
const afterClick = { prevented, hidden: panels.map((p) => p.hidden), input: input.value,
                     current: tabs.map((t) => t.attrs["aria-current"] || null) };
panels[0].hidden = true;
listeners["invalid!"]({ target: name });
listeners.submit({ target: form, defaultPrevented: false });
console.log(JSON.stringify({ afterClick, log, basicsShown: !panels[0].hidden,
  disabled: buttons.map((b) => b.disabled), label: label.hidden }));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_profile_tabs_and_busy_forms():
    out = subprocess.run(["node", "-e", TABS_AND_BUSY, str(APP_JS)], capture_output=True,
                         text=True, check=True, timeout=30).stdout
    result = json.loads(out)
    assert result["afterClick"] == {"prevented": True, "hidden": [True, False],
                                    "input": "skills", "current": [None, "page"]}
    assert result["log"] == ["/profile?tab=skills", "/profile?tab=basics"]
    assert result["basicsShown"] and result["disabled"] == [True, True]
    assert result["label"] is False
