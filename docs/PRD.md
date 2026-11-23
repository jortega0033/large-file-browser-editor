# Large-file Browser Editor: Product Requirements and Technical Spec

Status legend: **[Implemented M1]** is implemented in this repository. See the [baseline verification](../README.md#baseline-verification) for observed checks. **[Planned]** is future work with no code.

How the baseline is built, what was re-checked against the source, and where this document and the code differ is recorded in [architecture.md](architecture.md).

## 1. Intended user and workflow

One developer on one machine. They need to inspect and edit big text or log files in a browser without sending the content anywhere. The app runs as a local Python process bound to `127.0.0.1`. There is no sign-in, sync or remote service.

Workflow, end state: open a local file, jump to a line, search, edit, undo, and save it back to disk. Workflow, M1: create or load a small document, edit it in a textarea, save it to the local SQLite store, and reopen it later.

## 2. Milestones

| Milestone | Content | Status |
|---|---|---|
| M1 | Named documents, local list, textarea editor, bundled 200-line sample on explicit action, title and text validation, SQLite persistence, optimistic revision check across tabs | **[Implemented M1]** |
| P1 | Indexed piece-table buffer, operation and line retrieval contracts | [Planned] |
| P2 | Windowed rendering, viewport mapping, selections, jump to line | [Planned] |
| P3 | Worker-backed find/replace and syntax classing, cancellation | [Planned] |
| P4 | Transactional history, undo/redo, multi-cursor grouping, restart recovery | [Planned] |
| P5 | Local file upload/download streaming, cold/warm browser benchmark suite | [Planned] |

M1 uses a plain `<textarea>` and a 256 KiB cap. **M1 makes no large-file or performance claim.** Any later latency or memory figure must be measured and reported with its environment.

## 3. Scope boundaries

In M1: the items above only. Out of scope everywhere: paid services, accounts, remote sync, deployment, real user data, external media or model integration, telemetry. M1 has no delete, rename-only, search or history. Any external package or tool a later ticket might need must be planned to work offline and be approved before it is added. The current plan needs none.

## 4. System stack **[Implemented M1]**

- Python 3.12, standard library only: `http.server.ThreadingHTTPServer`, `sqlite3`, `argparse`, `json`.
- Static HTML, CSS and native JavaScript from `line_editor/static/`. No build step, no external URL, system fonts.
- Layout: `line_editor/{__main__,app,storage,validation,sample}.py`, `line_editor/static/{index.html,app.js,styles.css,tokens.css}`, `tests/`.
- Launch: `python -m line_editor --data-dir <path> --port <port>` (Windows), `python3 -m ...` (Linux). Binds `127.0.0.1` only; `--port 0` picks a free port.

## 5. Contracts **[Implemented M1]**

### 5.1 Limits

| Item | Limit |
|---|---|
| Title | 1–120 code points after trim, no control characters |
| Text | 0–262144 bytes UTF-8, no NUL, valid Unicode |
| Request body | 1 MiB |
| Documents | 500 |

### 5.2 HTTP API (version prefix `/api/v1`)

Errors: `{"error":{"code","message","field?"}}`. Document: `{id, title, text, revision, size_bytes, created_at, updated_at}`; list entries omit `text`.

| Request | Success | Failures |
|---|---|---|
| `GET /` | HTML | – |
| `GET /static/app.js`, `/static/styles.css`, `/static/tokens.css` | file | other `/static/*` is 404 |
| `GET /api/v1/health` | 200 `{"status":"ok","version":"0.1.0","schema_version":1}` | – |
| `GET /api/v1/sample` | 200 `{"title":"Sample log","text":...}` (not stored) | – |
| `GET /api/v1/documents` | 200 `{"documents":[...]}` newest first | – |
| `POST /api/v1/documents` `{title,text}` | 201 `{"document":...}` | 400 `invalid_json`/`invalid_field`, 403, 409 `document_limit`, 413, 415 |
| `GET /api/v1/documents/{id}` | 200 `{"document":...}` | 404 |
| `PUT /api/v1/documents/{id}` `{title,text,base_revision}` | 200 with revision+1 | 400, 403, 404, 409 `revision_conflict` (body includes `current.document`), 413, 415 |

Other codes: 503 `storage_unavailable` and 500 `internal_error` (no internals in the message), 405 for unsupported methods (including OPTIONS; no CORS headers are ever sent), 413 `text_too_large` or `body_too_large`, 415 for non-JSON mutations, 403 `forbidden_host`/`forbidden_origin`.

### 5.3 Schema (SQLite, `PRAGMA user_version = 1`)

`documents(id INTEGER PK AUTOINCREMENT, title TEXT CHECK length 1..120, text TEXT CHECK byte length <= 262144, revision INTEGER >= 1, created_at, updated_at)` and an index on `(updated_at DESC, id DESC)`. A database with a newer `user_version` is refused. WAL mode, 5 s busy timeout, one connection per operation.

### 5.4 Revision algorithm

`UPDATE documents SET title=?, text=?, revision=revision+1, updated_at=? WHERE id=? AND revision=?` inside `BEGIN IMMEDIATE`. Zero rows changed means 404 (missing id) or 409 (stale; the current document is returned). Two concurrent saves from the same base revision produce one 200 and one 409.

### 5.5 UI contract

Labels: **New document**, **Document title**, **Document text**, **Save**, **Load sample**; each list entry is a button named by the document title. Status is in a `role="status"` region, errors in `role="alert"`. On conflict the editor content is left untouched and the user chooses **Save as copy** or **Load latest**; text is never discarded. Ctrl/Cmd+S saves. Unsaved edits trigger a confirm on navigation inside the app and a `beforeunload` prompt.

### 5.6 Sample fixture (deterministic)

200 lines, joined with `\n` and a trailing `\n`. For `i` in 1..200 and `s=i-1`: `2026-01-01T{s//3600:02d}:{(s//60)%60:02d}:{s%60:02d}Z service-{i%4} {LEVEL} event={i:03d} value={(i*37)%101}`; LEVEL is `ERROR` if `i%25==0`, else `WARN` if `i%10==0`, else `INFO`.

| Line | Expected text |
|---|---|
| 1 | `2026-01-01T00:00:00Z service-1 INFO event=001 value=37` |
| 10 | `2026-01-01T00:00:09Z service-2 WARN event=010 value=67` |
| 25 | `2026-01-01T00:00:24Z service-1 ERROR event=025 value=16` |
| 200 | `2026-01-01T00:03:19Z service-0 ERROR event=200 value=27` |

Counts: ERROR 8 lines (25, 50, ..., 200), WARN 16 lines (multiples of 10 that are not multiples of 25: 20 minus 4 = 16), INFO 176.

## 6. Responsiveness and accessibility **[Implemented M1]**

Works at 800×600 with no horizontal body overflow; under 700 px the list stacks above the editor. Labels are associated with controls, `:focus-visible` is styled, text contrast is at least 4.5:1, system fonts only, reduced-motion respected. User text is inserted only via `textContent` or `.value`. CSP forbids inline script and style.

## 7. Errors, retry, restart, concurrency

- Network failure: text stays in the editor, status says so, Save can be retried. Double submit is blocked while a request is in flight.
- Validation failure: server message shown, offending field focused.
- Conflict: see 5.5. Retrying with a stale revision conflicts again by design.
- Restart: documents persist in `<data-dir>/line_editor.sqlite3`; a new server on the same directory serves them.
- Bad directory (empty, a file, unwritable) or newer schema: exit code 2 with a one-line message.
- Concurrency: threaded server; SQLite transactions and the `revision` predicate serialise writers.

## 8. Versioning

API prefix `/api/v1`; breaking changes need `/api/v2`. Package version `0.1.0`. Schema versions are integers in `user_version` with ordered forward-only migrations.

## 9. Security and validation

Loopback bind only; Host must be `127.0.0.1:<port>` or `localhost:<port>`; a present Origin on POST/PUT must be the same; no CORS headers; mutations need `application/json`; strict shape checks (types, unknown keys, bool is not int); body and text caps; static allowlist of four paths with no filesystem joining from request input; `nosniff`, `no-referrer`, CSP, `no-store`; socket timeout 10 s.

## 10. Future work: one epic, five issues **[Planned]**

**Epic: Large-file editing core for the offline browser editor.** Goal: edit text and log files of at least 1,000,000 lines in a browser tab, locally. User stories: as a developer I can open a big log and jump to any line; find what I need without freezing the page; undo a mistake after a restart; and save the file back with identical bytes.
| Key | Issue | Depends on | Core acceptance (numbers are check parameters, not results) |
|---|---|---|---|
| P1 | Indexed piece-table buffer, stable operation and line retrieval contracts | – | 20,000 seeded edits (seed 1337) equal a plain-string oracle; no edit splits a surrogate pair; replay gives identical CRC32 |
| P2 | Windowed rendering, viewport mapping, selections, jump to line | P1 | DOM line nodes ≤ viewport + 40 at 1,000,000 lines; go to line 1 / 500000 / 1000000; click maps to the exact (line, column) |
| P3 | Worker-backed find/replace and syntax classing, cancellation, bounded scan | P1, P2 | Matches equal plain search after 1,000 seeded edits (seed 99); cancel within 100 ms of a slice boundary; replace-all on the sample changes exactly 50 `service-1` lines |
| P4 | Transactional history, undo/redo, multi-cursor grouping, restart recovery | P1, P2 | 10,000 seeded edits (seed 2024) undo to identical bytes (SHA-256); state survives server restart at edit 7,321 |
| P5 | Local file open/save streaming and cold/warm benchmark suite | P1–P4 | Open then save a 1,000,000-line file is byte-identical; invalid UTF-8 byte offset reported; JSON benchmark report from 1 cold and 3 warm runs per size; only loopback traffic |

Dependencies: P1 → P2 → P3; P1+P2 → P4; P5 last. Any new external package, tool or reference must be offline-plannable and approved before staging; none is currently needed.

## 11. Acceptance matrix, M1

| # | Check | Expected |
|---|---|---|
| A1 | `GET /api/v1/health` | 200, `status` `ok` |
| A2 | `GET /` | 200 HTML containing labels New document, Document title, Document text, Save |
| A3 | Title of 120 code points / 121 | 201 / 400 `invalid_field` |
| A4 | Text of 262144 bytes / 262145 bytes | 201 / 413 `text_too_large` |
| A5 | PUT with stale `base_revision` | 409 with `current.document` |
| A6 | Two threads PUT same base revision | one 200, one 409 |
| A7 | Restart server on same data dir | documents still listed |
| A8 | `GET /static/../x`, encoded variants | 404 |
| A9 | Foreign Host or Origin on POST | 403 |
| A10 | `OPTIONS` on an existing API path | 405, no `Access-Control-*` header (unknown paths are 404) |
| A11 | `GET /api/v1/sample` | 200 lines, pinned lines in 5.6 |
| A12 | Browser at 800×600 | no horizontal body scroll |

## 12. Sample demo (M1)

1. Start the server. The editor is empty and the list says "No saved documents yet."
2. Select **Load sample**. 200 lines appear, unsaved. Enter title `Demo`, select **Save**. Status shows revision 1; the list shows `Demo`.
3. Edit line 1, **Save**: revision 2. Open the page in a second tab, load `Demo`, save an edit there, then return to the first tab and **Save**: conflict message, text intact.
4. Stop and restart the server with the same data directory; `Demo` is still listed.

## 13. Test plan

Automated (`python -m unittest discover -s tests -t .`): API shape and codes, limits at boundaries, astral characters, conflict and concurrent-save race, restart persistence, migration idempotence and newer-schema refusal, static allowlist and traversal, Host/Origin/CORS, CLI bad-directory exit codes, sample content. Manual browser smoke: section 12 plus keyboard-only use, 800×600 resize, focus visibility. The browser UI has no automated test in M1. Later tickets add the browser harnesses named in their acceptance.

## 14. Open choices

- Piece-table index: balanced tree or Fenwick over line-feed counts (P1).
- Scroll-height scaling method beyond browser limits (P2).
- Whether regex find uses the native engine only, with time slicing, or adds a bounded matcher (P3).
- Operation log segment format and checkpoint cadence (P4).
- Whether Save in P5 uses the File System Access API where available, or download only.
