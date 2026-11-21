(function () {
  "use strict";

  var MAX_TITLE = 120;
  var MAX_BYTES = 262144;

  var state = { id: null, revision: null, snapshot: { title: "", text: "" }, busy: false };
  var conflict = null; // current document from a 409, or null
  var loadToken = 0;
  var encoder = new TextEncoder();

  function $(id) { return document.getElementById(id); }
  var form = $("editor-form");
  var titleEl = $("doc-title");
  var textEl = $("doc-text");
  var saveBtn = $("save");
  var newBtn = $("new-doc");
  var sampleBtn = $("load-sample");
  var statusEl = $("status");
  var errorEl = $("error");
  var conflictBox = $("conflict-actions");
  var copyBtn = $("save-copy");
  var latestBtn = $("load-latest");
  var listEl = $("doc-list");
  var emptyEl = $("list-empty");
  var titleCount = $("title-count");
  var textCount = $("text-count");

  var NETWORK_MSG = "Could not reach the local server. Your text is still here; try Save again.";

  function isDirty() {
    return titleEl.value !== state.snapshot.title || textEl.value !== state.snapshot.text;
  }

  function setStatus(msg) { statusEl.textContent = msg; }

  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.hidden = false;
  }

  function clearError() {
    errorEl.textContent = "";
    errorEl.hidden = true;
  }

  function setConflict(cur) {
    conflict = cur || null;
    conflictBox.hidden = !conflict;
  }

  function setBusy(b) {
    state.busy = b;
    // Read-only while a save is in flight so typing is not replaced by the response.
    titleEl.readOnly = b;
    textEl.readOnly = b;
    saveBtn.setAttribute("aria-disabled", b ? "true" : "false");
    copyBtn.setAttribute("aria-disabled", b ? "true" : "false");
    latestBtn.setAttribute("aria-disabled", b ? "true" : "false");
  }

  function cpLen(s) { return Array.from(s).length; }
  function byteLen(s) { return encoder.encode(s).length; }

  function updateCounts() {
    var n = cpLen(titleEl.value);
    titleCount.textContent = n + " / " + MAX_TITLE + (n > MAX_TITLE ? " (too long)" : "");
    titleCount.classList.toggle("over", n > MAX_TITLE);
    var t = textEl.value;
    var lines = t.split("\n").length - (t.length > 0 && t.charAt(t.length - 1) === "\n" ? 1 : 0);
    var b = byteLen(t);
    textCount.textContent = lines + (lines === 1 ? " line, " : " lines, ") + b + " / " + MAX_BYTES +
      " bytes" + (b > MAX_BYTES ? " (too large)" : "");
    textCount.classList.toggle("over", b > MAX_BYTES);
  }

  // Put a document (or blank) in the editor and reset the snapshot from what the controls hold.
  function applyDoc(doc) {
    titleEl.value = doc ? doc.title : "";
    textEl.value = doc ? doc.text : "";
    state.id = doc ? doc.id : null;
    state.revision = doc ? doc.revision : null;
    state.snapshot = { title: titleEl.value, text: textEl.value };
    setConflict(null);
    updateCounts();
    markCurrent();
  }

  function markCurrent() {
    var items = listEl.querySelectorAll("button[data-id]");
    for (var i = 0; i < items.length; i++) {
      if (state.id !== null && Number(items[i].getAttribute("data-id")) === state.id) {
        items[i].setAttribute("aria-current", "true");
      } else {
        items[i].removeAttribute("aria-current");
      }
    }
  }

  function confirmDiscard() {
    return !isDirty() || window.confirm("You have unsaved changes. Discard them?");
  }

  // Returns {status, body}; throws on network failure.
  function api(method, path, payload) {
    var opts = { method: method, headers: {}, cache: "no-store" };
    if (payload !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(payload);
    }
    return fetch(path, opts).then(function (res) {
      return res.text().then(function (txt) {
        var body = null;
        try { body = JSON.parse(txt); } catch (e) { body = null; }
        return { status: res.status, ok: res.ok, body: body };
      });
    });
  }

  function errMessage(r) {
    if (r.body && r.body.error && typeof r.body.error.message === "string") return r.body.error.message;
    return "Request failed (HTTP " + r.status + ").";
  }

  function focusField(field) {
    if (field === "title") titleEl.focus();
    else if (field === "text") textEl.focus();
  }

  // ---- list ----
  function formatSize(n) {
    return n < 1024 ? n + " B" : (n / 1024).toFixed(1) + " KiB";
  }

  function renderList(docs) {
    listEl.textContent = "";
    emptyEl.hidden = docs.length > 0;
    docs.forEach(function (d) {
      var li = document.createElement("li");
      var btn = document.createElement("button");
      btn.type = "button";
      btn.setAttribute("data-id", String(d.id));
      var name = document.createElement("span");
      name.className = "name";
      name.textContent = d.title;
      var meta = document.createElement("span");
      meta.className = "meta";
      meta.setAttribute("aria-hidden", "true");
      meta.textContent = "r" + d.revision + " " + formatSize(d.size_bytes);
      btn.appendChild(name);
      btn.appendChild(meta);
      li.appendChild(btn);
      listEl.appendChild(li);
    });
    markCurrent();
  }

  function refreshList() {
    return api("GET", "/api/v1/documents").then(function (r) {
      if (r.ok && r.body && Array.isArray(r.body.documents)) renderList(r.body.documents);
    }).catch(function () { /* list refresh is best effort */ });
  }

  listEl.addEventListener("click", function (ev) {
    var btn = ev.target.closest("button[data-id]");
    if (!btn || state.busy) return;
    var id = Number(btn.getAttribute("data-id"));
    if (!confirmDiscard()) return;
    var token = ++loadToken;
    clearError();
    api("GET", "/api/v1/documents/" + id).then(function (r) {
      if (token !== loadToken) return;
      if (r.ok && r.body && r.body.document) {
        applyDoc(r.body.document);
        setStatus("Loaded revision " + r.body.document.revision + ".");
      } else {
        showError(errMessage(r));
        refreshList();
      }
    }).catch(function () {
      if (token === loadToken) showError(NETWORK_MSG);
    });
  });

  // ---- actions ----
  newBtn.addEventListener("click", function () {
    if (state.busy || !confirmDiscard()) return;
    loadToken++;
    clearError();
    applyDoc(null);
    setStatus("New document, not saved yet.");
    titleEl.focus();
  });

  sampleBtn.addEventListener("click", function () {
    if (state.busy || !confirmDiscard()) return;
    var token = ++loadToken;
    clearError();
    api("GET", "/api/v1/sample").then(function (r) {
      if (token !== loadToken) return;
      if (r.ok && r.body && typeof r.body.text === "string") {
        applyDoc(null);
        titleEl.value = String(r.body.title || "Sample log");
        textEl.value = r.body.text;
        updateCounts();
        setStatus("Loaded sample, not saved yet.");
        textEl.focus();
      } else {
        showError(errMessage(r));
      }
    }).catch(function () {
      if (token === loadToken) showError(NETWORK_MSG);
    });
  });

  // Client-side validation; returns payload fields or null after showing an error.
  function validate() {
    var title = titleEl.value.trim();
    var text = textEl.value;
    if (cpLen(title) < 1) {
      showError("Title is required.");
      titleEl.focus();
      return null;
    }
    if (cpLen(title) > MAX_TITLE) {
      showError("Title must be at most " + MAX_TITLE + " characters.");
      titleEl.focus();
      return null;
    }
    if (/[\u0000-\u001f\u007f-\u009f]/.test(title)) {
      showError("Title must not contain control characters.");
      titleEl.focus();
      return null;
    }
    if (text.indexOf("\u0000") !== -1) {
      showError("Text must not contain NUL characters.");
      textEl.focus();
      return null;
    }
    if (/[\ud800-\udbff](?![\udc00-\udfff])|(?:^|[^\ud800-\udbff])[\udc00-\udfff]/.test(text)) {
      showError("Text contains invalid Unicode.");
      textEl.focus();
      return null;
    }
    if (byteLen(text) > MAX_BYTES) {
      showError("Text is too large (limit " + MAX_BYTES + " bytes).");
      textEl.focus();
      return null;
    }
    return { title: title, text: text };
  }

  function handleFailure(r) {
    if (r.status === 409 && r.body && r.body.current && r.body.current.document) {
      var cur = r.body.current.document;
      setConflict(cur);
      showError("This document was changed in another tab (now revision " + cur.revision +
        "). Your text is still here.");
      setStatus("Unsaved changes.");
      return;
    }
    showError(errMessage(r));
    var f = r.body && r.body.error && r.body.error.field;
    if (f) focusField(f);
  }

  function afterSaved(doc) {
    applyDoc(doc);
    setStatus("Saved (revision " + doc.revision + ").");
    return refreshList();
  }

  function submitSave(asCopy) {
    if (state.busy) return;
    clearError();
    var fields = validate();
    if (!fields) return;
    var creating = asCopy || state.id === null;
    var method = creating ? "POST" : "PUT";
    var path = creating ? "/api/v1/documents" : "/api/v1/documents/" + state.id;
    var payload = { title: fields.title, text: fields.text };
    if (!creating) payload.base_revision = state.revision;
    loadToken++;
    setBusy(true);
    api(method, path, payload).then(function (r) {
      if (r.ok && r.body && r.body.document) return afterSaved(r.body.document);
      handleFailure(r);
    }).catch(function () {
      showError(NETWORK_MSG);
    }).then(function () {
      setBusy(false);
    });
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    submitSave(false);
  });

  copyBtn.addEventListener("click", function () { submitSave(true); });

  latestBtn.addEventListener("click", function () {
    if (state.busy || !conflict) return;
    if (!window.confirm("Replace the editor with the latest saved version? Your edits will be lost.")) return;
    var doc = conflict;
    clearError();
    applyDoc(doc);
    setStatus("Loaded latest (revision " + doc.revision + ").");
    refreshList();
  });

  function onEdit() {
    updateCounts();
    if (isDirty()) setStatus("Unsaved changes.");
  }
  titleEl.addEventListener("input", onEdit);
  textEl.addEventListener("input", onEdit);

  document.addEventListener("keydown", function (ev) {
    if ((ev.ctrlKey || ev.metaKey) && !ev.altKey && (ev.key === "s" || ev.key === "S")) {
      ev.preventDefault();
      if (typeof form.requestSubmit === "function") form.requestSubmit(saveBtn);
      else submitSave(false);
    }
  });

  window.addEventListener("beforeunload", function (ev) {
    if (isDirty()) {
      ev.preventDefault();
      ev.returnValue = "";
    }
  });

  window.addEventListener("focus", refreshList);

  // Startup: blank editor and the saved-document list only. The sample is never loaded here.
  updateCounts();
  setBusy(false);
  refreshList();
})();
