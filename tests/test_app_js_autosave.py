"""app.js autosave: error pages are swapped in, open details stay open, "Saved" shows."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

APP_JS = Path(__file__).resolve().parent.parent / "rolecard" / "static" / "js" / "app.js"

HARNESS = r"""
const vm = require("vm"), fs = require("fs");
const listeners = {};
const saved = { hidden: true };
const form = { id: "datos", hasAttribute: (n) => n === "data-autosave",
               querySelector: (sel) => (sel === "[data-saved]" ? saved : null) };
const plain = { id: "x", hasAttribute: () => false };
const editBefore = { id: "editar", open: true }, editAfter = { id: "editar", open: false };
let swapped = false;
const ctx = { document: {
  addEventListener: (n, f) => { listeners[n] = f; }, querySelector: () => null,
  querySelectorAll: (sel) => (sel === "details[id][open]" ? [editBefore] : []),
  getElementById: (id) => (id === "editar" ? editAfter : id === "datos" ? form : null) } };
vm.runInNewContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
function swap(elt, status) {
  const detail = { requestConfig: { elt }, xhr: { status }, target: { id: "principal" },
                   shouldSwap: status < 400, isError: status >= 400 };
  listeners["htmx:beforeSwap"]({ detail });
  return detail;
}
const plainError = swap(plain, 400);
const conflict = swap(form, 409);
listeners["htmx:afterSettle"]({ detail: { requestConfig: { elt: form }, xhr: { status: 409 } } });
const savedAfterError = !saved.hidden;
editAfter.open = false;
swap(form, 200);
listeners["htmx:afterSettle"]({ detail: { requestConfig: { elt: form }, xhr: { status: 200 } } });
console.log(JSON.stringify({ plainSwap: plainError.shouldSwap, conflictSwap: conflict.shouldSwap,
  conflictError: conflict.isError, savedAfterError, saved: !saved.hidden, open: editAfter.open }));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_autosave_swaps_errors_keeps_details_and_shows_saved():
    out = subprocess.run(["node", "-e", HARNESS, str(APP_JS)], capture_output=True,
                         text=True, check=True, timeout=30).stdout
    result = json.loads(out)
    assert result["plainSwap"] is False  # only autosave forms swap a 400 page in
    assert result["conflictSwap"] is True and result["conflictError"] is False
    assert result["savedAfterError"] is False
    assert result["saved"] is True
    assert result["open"] is True
