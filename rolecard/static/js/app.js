// rolecard: the only hand-written script. No inline JS anywhere (CSP script-src 'self').
"use strict";

var rolecardRepeatCounter = 0;

function rolecardCsrfToken() {
  var meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute("content") : "";
}

// <form data-confirm="..."> or <button data-confirm="...">: ask before submitting.
function rolecardConfirm(event) {
  var submitter = event.submitter;
  var message = (submitter && submitter.getAttribute("data-confirm")) ||
    event.target.getAttribute("data-confirm");
  if (message && !window.confirm(message)) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
}

// Drop zone: <div data-dropzone> wrapping an <input type="file">.
function rolecardDropzone(zone) {
  var input = zone.querySelector('input[type="file"]');
  var label = zone.querySelector("[data-dropzone-name]");
  if (!input || zone.getAttribute("data-dropzone") === "ready") { return; }
  zone.setAttribute("data-dropzone", "ready");
  function show() {
    if (label && input.files.length) { label.textContent = input.files[0].name; }
  }
  ["dragenter", "dragover"].forEach(function (name) {
    zone.addEventListener(name, function (event) {
      event.preventDefault();
      zone.classList.add("encima");
    });
  });
  ["dragleave", "drop"].forEach(function (name) {
    zone.addEventListener(name, function () { zone.classList.remove("encima"); });
  });
  zone.addEventListener("drop", function (event) {
    event.preventDefault();
    if (event.dataTransfer && event.dataTransfer.files.length) {
      input.files = event.dataTransfer.files;
      show();
    }
  });
  input.addEventListener("change", show);
}

// Repeatable entries: <template data-repeat-template="name"> + button[data-repeat-add="name"]
// appends a copy into [data-repeat-list="name"]; button[data-repeat-remove] removes its entry.
function rolecardAddEntry(name) {
  var tpl = document.querySelector('template[data-repeat-template="' + name + '"]');
  var list = document.querySelector('[data-repeat-list="' + name + '"]');
  if (!tpl || !list) { return; }
  rolecardRepeatCounter += 1;
  var html = tpl.innerHTML.split("__new__").join("n" + Date.now() + rolecardRepeatCounter);
  list.insertAdjacentHTML("beforeend", html);
  var first = list.lastElementChild && list.lastElementChild.querySelector("input, textarea");
  if (first) { first.focus(); }
}

// button[data-copy="id"]: copy that element's text; button[data-print]: print the page.
function rolecardCopy(button) {
  var source = document.getElementById(button.getAttribute("data-copy"));
  if (!source || !navigator.clipboard) { return; }
  navigator.clipboard.writeText(source.textContent).then(function () {
    button.textContent = button.getAttribute("data-copied") || button.textContent;
  });
}

// Review: a.rc-s[data-sentence] opens its editor ([data-editor]) in the side panel.
function rolecardShowEditor(sid) {
  var target = null;
  document.querySelectorAll("[data-editor]").forEach(function (box) {
    var on = box.getAttribute("data-editor") === sid;
    box.classList.toggle("is-active", on);
    if (on) { target = box; }
  });
  document.querySelectorAll("[data-sentence]").forEach(function (s) {
    s.classList.toggle("rc-s--active", s.getAttribute("data-sentence") === sid);
  });
  if (!target) { return; }
  var details = target.querySelector("details");
  if (details) { details.open = true; }
  if (target.scrollIntoView) { target.scrollIntoView({ block: "nearest" }); }
  var summary = target.querySelector("summary");
  if (summary && summary.focus) { summary.focus(); }
}

// J / K: the next / previous pending sentence, counted from the active one.
function rolecardStepPending(step) {
  var pending = Array.prototype.slice.call(
    document.querySelectorAll("[data-sentence][data-pending]"));
  if (!pending.length) { return; }
  var current = -1;
  pending.forEach(function (s, i) { if (s.classList.contains("rc-s--active")) { current = i; } });
  var next = current === -1 ? (step > 0 ? 0 : pending.length - 1)
    : (current + step + pending.length) % pending.length;
  rolecardShowEditor(pending[next].getAttribute("data-sentence"));
}

function rolecardInField(el) {
  var tag = el && el.tagName ? el.tagName.toLowerCase() : "";
  return Boolean(el && el.isContentEditable) ||
    tag === "input" || tag === "textarea" || tag === "select";
}

// Shortcuts: "/" search, "N" add offer, "J"/"K" pending sentences. Never inside a field.
function rolecardKeydown(event) {
  if (event.ctrlKey || event.metaKey || event.altKey || rolecardInField(event.target)) { return; }
  var pressed = String(event.key || "").toLowerCase();
  if (pressed === "/") {
    var search = document.querySelector("[data-shortcut-search]");
    if (search) { event.preventDefault(); search.focus(); }
  } else if (pressed === "n") {
    var add = document.querySelector("[data-shortcut-new]");
    if (add) { event.preventDefault(); window.location.assign(add.getAttribute("data-shortcut-new")); }
  } else if ((pressed === "j" || pressed === "k") && document.querySelector("[data-sentence]")) {
    event.preventDefault();
    rolecardStepPending(pressed === "j" ? 1 : -1);
  }
}

// Profile tabs: a[data-tab] shows its [data-tab-panel] without reloading, so edits in the
// other tabs stay in the form; [data-tab-input] sends the tab back to land on it again.
function rolecardShowTab(name, href) {
  document.querySelectorAll("[data-tab-panel]").forEach(function (panel) {
    panel.hidden = panel.getAttribute("data-tab-panel") !== name;
  });
  document.querySelectorAll("a[data-tab]").forEach(function (a) {
    if (a.getAttribute("data-tab") === name) { a.setAttribute("aria-current", "page"); }
    else { a.removeAttribute("aria-current"); }
  });
  var input = document.querySelector("[data-tab-input]");
  if (input) { input.value = name; }
  if (window.history && window.history.replaceState) { window.history.replaceState(null, "", href); }
}

// A required field in a hidden tab: show its tab so the browser can point at it.
function rolecardInvalid(event) {
  var panel = event.target.closest && event.target.closest("[data-tab-panel]");
  var name = panel && panel.hidden && panel.getAttribute("data-tab-panel");
  var tab = name && document.querySelector('a[data-tab="' + name + '"]');
  if (tab) { rolecardShowTab(name, tab.getAttribute("href")); }
}

function rolecardClick(event) {
  var copy = event.target.closest("[data-copy]");
  if (copy) { rolecardCopy(copy); return; }
  if (event.target.closest("[data-print]")) { window.print(); return; }
  var said = event.target.closest("[data-sentence]");
  if (said && said.getAttribute("href")) {
    event.preventDefault();
    rolecardShowEditor(said.getAttribute("data-sentence"));
    return;
  }
  if (event.target.closest("[data-next-pending]")) {
    event.preventDefault();
    rolecardStepPending(1);
    return;
  }
  var tab = event.target.closest("a[data-tab]");
  if (tab) {
    event.preventDefault();
    rolecardShowTab(tab.getAttribute("data-tab"), tab.getAttribute("href"));
    return;
  }
  var add = event.target.closest("[data-repeat-add]");
  if (add) {
    rolecardAddEntry(add.getAttribute("data-repeat-add"));
    return;
  }
  var remove = event.target.closest("[data-repeat-remove]");
  var entry = remove && remove.closest("[data-repeat-entry]");
  if (entry) { entry.remove(); }
}

// input[data-select-all][form=x]: tick or untick every row (input[name=ids][form=x]).
function rolecardSelectAll(event) {
  var all = event.target.closest && event.target.closest("[data-select-all]");
  if (!all) { return; }
  var selector = 'input[name="ids"][form="' + all.getAttribute("form") + '"]';
  document.querySelectorAll(selector).forEach(function (box) { box.checked = all.checked; });
}

// <form data-busy>: once it submits, its buttons go disabled (after the submitter's value
// is taken) and its [data-busy-label] shows, so a slow search is not sent twice.
function rolecardBusy(event) {
  var form = event.target;
  if (event.defaultPrevented || !form.hasAttribute || !form.hasAttribute("data-busy")) { return; }
  setTimeout(function () {
    form.querySelectorAll("button").forEach(function (b) { b.disabled = true; });
    var label = form.querySelector("[data-busy-label]");
    if (label) { label.hidden = false; }
  }, 0);
}

function rolecardInit(root) {
  root.querySelectorAll("[data-dropzone]").forEach(rolecardDropzone);
}

document.addEventListener("htmx:configRequest", function (event) {
  event.detail.headers["X-CSRF-Token"] = rolecardCsrfToken();
});
// A rejected sentence action (400) or autosave (400, 409) still returns the page with its
// error message: show it instead of ignoring the response (htmx skips 4xx swaps).
// An autosave also keeps open the <details id> that were open before the swap.
var rolecardOpenDetails = [];
function rolecardAutosaveElt(event) {
  var config = event.detail.requestConfig;
  var elt = config && config.elt;
  return elt && elt.hasAttribute && elt.hasAttribute("data-autosave") ? elt : null;
}
document.addEventListener("htmx:beforeSwap", function (event) {
  var target = event.detail.target;
  var status = event.detail.xhr.status;
  var autosave = rolecardAutosaveElt(event);
  if ((status === 400 && target && target.id === "documento") ||
      (autosave && (status === 400 || status === 409))) {
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
  if (autosave) {
    rolecardOpenDetails = Array.prototype.map.call(
      document.querySelectorAll("details[id][open]"), function (d) { return d.id; });
  }
});
// After an autosave: reopen those details and show "Saved" on the form, if it saved.
document.addEventListener("htmx:afterSettle", function (event) {
  var autosave = rolecardAutosaveElt(event);
  if (!autosave) { return; }
  rolecardOpenDetails.forEach(function (id) {
    var details = document.getElementById(id);
    if (details) { details.open = true; }
  });
  var form = autosave.id && document.getElementById(autosave.id);
  var saved = form && form.querySelector("[data-saved]");
  if (saved && event.detail.xhr.status < 400) { saved.hidden = false; }
});
document.addEventListener("submit", rolecardConfirm, true);
document.addEventListener("submit", rolecardBusy);
document.addEventListener("invalid", rolecardInvalid, true);
document.addEventListener("click", rolecardClick);
document.addEventListener("keydown", rolecardKeydown);
document.addEventListener("change", rolecardSelectAll);
document.addEventListener("DOMContentLoaded", function () { rolecardInit(document); });
document.addEventListener("htmx:load", function (event) { rolecardInit(event.target); });
