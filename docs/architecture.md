# Architecture, baseline status and PRD drift

This file records how the baseline is built, what was checked against the source, and where [PRD.md](PRD.md) and the code differ. It was written during backlog preparation on 2026-11-22 against commit `51c374a` (the only commit on `main`). Line numbers refer to that commit. Update this file in the same pull request as any change that makes a row untrue.

How to read the evidence marks:

- **[RUN]**: the command was run during preparation and the result was seen (Windows 11, Python 3.13.14).
- **[READ]**: established by reading the source only.
- **[NOT VERIFIED]**: a claim in the README or the PRD that was not reproduced.

Tickets are named by issue number. Three tickets proposed during preparation had no issue number when this file was written and appear here under placeholder names: NEW-A (browser test harness, seeded fixtures and a headless runner), NEW-B (recovery store on the server: schema v2, chunked documents and operation-log segments) and NEW-C (benchmark suite, published report and epic acceptance gate). The epic (#1) lists all eight tickets by number and title; once the three issues exist, the placeholder names in this file are replaced by their numbers.

## 1. Pattern

A single-process, three-layer application on the Python standard library with a static browser page. No framework, no router library, no build step, no third-party package, no JavaScript module system and no worker.

| Layer | File | Responsibility |
|---|---|---|
| Entry point | `line_editor/__main__.py` | Parses `--data-dir` and `--port` (both required), calls `create_server`, prints `Serving on http://127.0.0.1:<port>/`, serves until Ctrl+C. A `StoreError` or a bind error exits with code 2 and one line on stderr (`main`, lines 20-43). |
| Transport | `line_editor/app.py` | `Handler` on `ThreadingHTTPServer`: every method goes through `_handle` (101-125) and `_dispatch` (133-162). Host and Origin checks, JSON body reading with caps, the error envelope, four allowlisted static paths, security headers. |
| Limits and input rules | `line_editor/validation.py` | The four limits (lines 4-7), `ApiError` (12-30), and pure validators for title, text, `base_revision` and the payload shape (37-99). No I/O. |
| Persistence | `line_editor/storage.py` | `Store` over one SQLite file. A new connection per operation (`_conn`, 106-116), ordered forward-only migrations (`MIGRATIONS`, 14-29; `_migrate`, 126-148), one `BEGIN IMMEDIATE` transaction per write. Raises domain exceptions (`NotFound`, `DocumentLimit`, `RevisionConflict`, `StoreError`, `SchemaTooNew`); `app.py` maps them to HTTP status codes (`app.py:110-125`, `297-305`). |
| Fixture | `line_editor/sample.py` | The deterministic 200-line sample of PRD 5.6. Served by `GET /api/v1/sample`, never stored. |
| UI | `line_editor/static/index.html`, `app.js`, `styles.css` | One page, one IIFE (`app.js`, 340 lines), a plain `<textarea>` (`index.html:32`). |

Tests: `tests/__init__.py` holds `ServerCase`, which starts a real server on an ephemeral loopback port over a temporary data directory. `test_api.py` (HTTP contract, limits, security), `test_storage.py`, `test_validation.py` and `test_cli.py` (subprocess runs of the CLI) hold 59 tests. [RUN] No test loads the page in a browser.

## 2. Traced workflow: load the sample, save, save again, stale save

1. **Start.** `python -m line_editor --data-dir D --port P` calls `create_server` (`app.py:341-344`), which opens `storage.Store(D)` and binds `AppServer` to `127.0.0.1`. [RUN: printed `Serving on http://127.0.0.1:8797/`]
2. **Store open.** `Store.__init__` (`storage.py:92-104`) creates the directory, then `_migrate` (126-148) reads `PRAGMA user_version`, refuses a newer value (`_check_version`, 150-156), and otherwise applies the missing migrations inside `BEGIN IMMEDIATE`, re-checking the version under the write lock. [READ; covered by `test_migration_idempotent` and `test_newer_schema_refused` in the suite]
3. **Page load.** `GET /` is answered from the `STATIC_FILES` allowlist (`app.py:23-28`, `_serve_static` at 255-263) with the Content-Security-Policy header (`CSP`, 30-33). [RUN: 200 with the documented policy] The script starts with a blank editor and calls `refreshList()` (`app.js:336-339`), which sends `GET /api/v1/documents` (`_documents`, `app.py:274-284`; `Store.list_documents`, `storage.py:162-168`). [READ for the script]
4. **Load sample.** The **Load sample** handler (`app.js:195-214`) calls `GET /api/v1/sample` (`_sample`, `app.py:271-272`) and puts the title and text in the controls. Nothing is stored. [READ; `test_sample_endpoint` checks the pinned lines and that the list stays empty]
5. **Save, first time.** `submitSave` (`app.js:273-293`) runs the client checks (`validate`, 217-251) and, with no document id, sends `POST /api/v1/documents` with `{title, text}`. Server side, in order: `_check_host` (`app.py:168-171`), route and method (133-162), `_check_origin` (173-180), `_read_json_body` (195-217: content type, no `Transfer-Encoding`, a valid `Content-Length`, at most 1 MiB, strict JSON), `validate_payload` (`validation.py:82-99`), then `Store.create_document` (`storage.py:179-200`): `BEGIN IMMEDIATE`, a strictly increasing timestamp (`_next_stamp`, 70-77), the 500-document cap, insert at revision 1. The answer is 201 with a `Location` header. [RUN: 201, `Location: /api/v1/documents/1`, revision 1, CRLF in the text stored unchanged]
6. **Save again.** With a document id the client sends `PUT /api/v1/documents/{id}` with `base_revision` (`_document`, `app.py:286-306`). `Store.update_document` (`storage.py:202-224`) runs `UPDATE ... SET revision = revision + 1 ... WHERE id = ? AND revision = ?` inside `BEGIN IMMEDIATE`. [RUN: 200, revision 2]
7. **Stale save.** Zero changed rows means the id is missing (`NotFound`, 404) or the revision is stale (`RevisionConflict`), which `app.py:297-305` turns into 409 `revision_conflict` with `current.document`. [RUN: 409 with the current document at revision 2] The client keeps the editor content and shows **Save as copy** and **Load latest** (`handleFailure`, `app.js:253-265`; handlers at 300-310). [READ]
8. **Observable result.** The row in `<data-dir>/line_editor.sqlite3`. After the server process was stopped and a new one started on the same directory, `GET /api/v1/documents/1` returned the same document at revision 2. [RUN]

## 3. Data ownership

- The server and SQLite own every saved document: `documents(id, title, text, revision, created_at, updated_at)` with the whole text in one `TEXT` column (`storage.py:18-25`).
- The browser owns only the unsaved draft: the two form controls plus `state` (`id`, `revision`, a `snapshot` of title and text for the dirty check, `busy`) and `conflict` (`app.js:7-8`, `isDirty` at 31-33). There is no client-side persistence. A `beforeunload` handler warns when the draft is dirty (`app.js:327-332`).
- The list is refreshed from the server on load, after a save and when the window regains focus (`app.js:334`).

## 4. Invariants

| Invariant | Enforced by |
|---|---|
| A save based on an old revision changes nothing | The `revision` predicate in the `UPDATE`, inside `BEGIN IMMEDIATE` (`storage.py:204-212`). Two concurrent saves from one base give one 200 and one 409 (`test_concurrent_double_save`). |
| The revision rises by exactly 1 per successful save | `storage.py:209` |
| `updated_at` is strictly increasing across the table | `_next_stamp` (`storage.py:70-77`), called inside the write transaction |
| Title is 1 to 120 code points after trim, with no control or surrogate characters | `validate_title` (`validation.py:37-51`); the database checks only the length (`storage.py:20`) |
| Text is at most 262144 UTF-8 bytes, valid Unicode, no NUL | `validate_text` (`validation.py:54-71`); the database checks only the byte length (`storage.py:21`) |
| A request body is at most 1 MiB and is read only after its declared length passed the cap | `_read_json_body` (`app.py:195-217`) |
| At most 500 documents | `create_document` (`storage.py:184-186`) |
| The schema only moves forward, and a database from a newer version is refused | `_migrate` and `_check_version` (`storage.py:126-156`); exit code 2 from the CLI (`test_newer_schema_rejected`) |
| Only loopback, same-host clients are served, and a present `Origin` on a mutation must be the same origin | Bind address (`app.py:16`, `344`); `_check_host` on every request, `_check_origin` on POST and PUT (`app.py:168-180`) |
| No CORS header is ever sent; OPTIONS is 405 on a known path | `_dispatch` (`app.py:133-162`); `test_no_cors_headers_anywhere`, `test_options_and_other_methods` |
| Nothing outside four static paths is served, and no request input is joined into a file path | `STATIC_FILES` (`app.py:23-28`); `test_static_traversal_and_unlisted` |
| Every response closes the connection and carries `no-store`, `nosniff`, `no-referrer` and `Cross-Origin-Resource-Policy: same-origin` | `_send` (`app.py:219-231`), `end_headers` (71-76) |
| User text reaches the page only through `textContent` or `.value` | `app.js` throughout, for example `renderList` (135-156) [READ] |

## 5. Status against the PRD

Planned work is tracked in epic #1. Proposed dependency order of its tickets: NEW-A, #2, NEW-B, #3, #6, #4, #5, NEW-C.

| PRD item | Status | Evidence |
|---|---|---|
| M1 documents: create, read, update, list (2, 5.2) | Implemented | Routes at `app.py:133-162`. [RUN] suite, 59 tests `OK`; [RUN] create, update and read over HTTP. |
| Limits (5.1) | Implemented | `validation.py:4-7`. Boundary tests in `test_api.py` (`LimitTests`) and `test_validation.py`. [RUN] in the suite. |
| Schema and revision algorithm (5.3, 5.4) | Implemented | `storage.py:14-29`, `202-224`. [RUN] stale `PUT` returned 409 with `current.document`. |
| Security and validation (9) | Implemented | `app.py:164-217`. [RUN] a foreign `Origin` returned 403 `forbidden_origin`; `Transfer-Encoding: chunked` returned 400; a non-JSON content type returned 415. |
| Persistence across restart (7, A7) | Implemented | [RUN] in the suite (`test_persistence_across_restart`) and by hand with two server processes. |
| Sample fixture (5.6, A11) | Implemented | `sample.py`. [RUN] the pinned lines 1, 10, 25 and 200 were printed from `sample_line` and match PRD 5.6. |
| UI contract (5.5) | Implemented, needs verification | Labels, the status and alert regions, the conflict choices, Ctrl/Cmd+S and the unsaved-changes prompts are in `index.html` and `app.js` [READ]. No browser was run against the app during preparation. |
| Responsiveness and accessibility (6, A12) | Needs verification | `:focus-visible`, a stacked layout under 700 px and system fonts are in `styles.css` [READ]. Contrast, keyboard-only use and the 800x600 layout were not checked. |
| Browser check in the README (Chrome 157, external requests blocked) | Needs verification | [NOT VERIFIED] |
| Suite on Ubuntu 24.04 with Python 3.12.3 | Needs verification | README claim. [NOT VERIFIED]; only Python 3.13.14 on Windows was run. |
| P1 piece-table buffer (#2) | Planned | No buffer module. The text is one string in a `<textarea>`. |
| P2 windowed rendering, viewport mapping, jump to line (#3) | Planned | None. |
| P3 worker-backed find and replace, syntax classing (#4) | Planned | No worker file, no find control. |
| P4 history, undo and redo, multi-cursor, restart recovery (#5, with the server part in NEW-B) | Planned | Schema is version 1 with one table; no operation log. |
| P5 local file open and streaming save (#6) | Planned | No file input. |
| P5 cold and warm benchmark suite (NEW-C) | Planned | None. The PRD forbids any latency or memory claim before it is measured. |
| Browser test harness named in PRD 13 ("later tickets add the browser harnesses") (NEW-A) | Planned | `tests/` holds only Python `unittest` files. |

## 6. PRD drift and open points

"Material" means that an implementer who follows only the PRD would build or test the wrong thing.

| # | Finding | Evidence | Material | Handling |
|---|---|---|---|---|
| D1 | The end-state workflow (open a local file of 1,000,000 lines, save it back) cannot pass through the M1 contract: text is capped at 262144 bytes, a request body at 1 MiB, bodies must be JSON with a `Content-Length`, and the whole text is one row. | `validation.py:5-6`, `app.py:195-217`, `storage.py:21`. [RUN]: `Transfer-Encoding: chunked` returned 400 and `application/octet-stream` returned 415. | Yes | Large documents get their own storage and routes (NEW-B). The M1 routes and limits stay as they are for small documents. |
| D2 | `GET /api/v1/health` reports `storage.SCHEMA_VERSION`, and four tests pin version 1: `test_health` compares the whole body (`tests/test_api.py:11-14`), `test_migration_idempotent` asserts `user_version() == 1` (`tests/test_storage.py:24-31`), and both newer-schema tests write `user_version=2` as "too new" (`tests/test_storage.py:38-44`, `tests/test_cli.py:44-50`). | [READ]; [RUN] health returned `"schema_version": 1`. | Yes | The first schema migration (NEW-B) changes these four tests and PRD 5.2 and 5.3 in the same pull request. |
| D3 | The router drops the query string before matching (`app.py:136`), and `test_query_string_ignored_for_routing` pins that. Issue #5 specifies `GET .../ops?after=n`. | `tests/test_api.py:55-57`. [READ] | Yes | NEW-B puts the sequence number in the path (`.../ops/{seq}`), so no query parsing is needed and the existing test stays as it is. |
| D4 | There is no way to remove a document (PRD 3: "M1 has no delete"). With 500 documents allowed and large documents of about 56 MiB each, the data directory would only grow. | `app.py:133-162`. [READ] | Yes, for P4 | NEW-B proposes `DELETE /api/v1/documents/{id}` for large documents only, and #5 the control that calls it. `test_options_and_other_methods` (`tests/test_api.py:339-350`) pins 405 and `Allow: GET, PUT` for that request today and changes with it. The owner can strike the route; the tickets mark it as a default. |
| D5 | The operation record in issue #2 is `{v:1, kind, offset, text|length}`. A delete record with only a length cannot be undone after a restart, which issue #5 requires. | Issue #2 and #5 bodies. | Yes | The updated #2 makes `apply` return the inverse record, and #5 persists both directions. |
| D6 | Issue #2 indexes pieces "by line-feed count" and also says a lone CR and CRLF are line breaks. Line-break counts are then not additive across pieces: a CR at the end of one piece and an LF at the start of the next are one break, not two. | Issue #2 body. | Yes | The updated #2 states the rule, lists the boundary cases as acceptance criteria and names the simpler LF-only alternative as an owner decision. |
| D7 | Issue #4 has the worker hold "transferred chunks". JavaScript strings cannot be transferred, only copied, and a copy of the whole text per edit does not scale. | Web platform behaviour, not checked in a browser during preparation. [NOT VERIFIED] | Yes | The updated #4 keeps a replica in the worker and sends it the operation records, which is what the versioned record of #2 is for. |
| D8 | Issue #5 specifies the operation-log routes but no route for the base text chunks, and a 1 MiB chunk cannot fit in a JSON body under the 1 MiB body cap. | Issue #5 body; `validation.py:6`; `test_escaped_text_over_body_cap` (`tests/test_api.py:274-278`) shows the same effect at M1. | Yes | NEW-B defines chunk routes with a raw `application/octet-stream` body. |
| D9 | PRD 10 orders P5 last because its benchmark needs everything. The file open and save half of P5 depends only on P1 and P2, and until it exists nobody can load a large file into the app. | PRD 10; issue #6 body. | Planning | The batch splits P5: #6 keeps open and save and moves before find and history; the benchmark and the epic gate become NEW-C, last. |
| D10 | Issue #5 bundles client history, multi-cursor editing, new server routes, a schema migration and checkpoints. The server part has no dependency on the browser work. | Issue #5 body. | Planning | The server part becomes NEW-B and can start at once, in parallel. |
| D11 | The Content-Security-Policy has no `worker-src`, so a worker must be a same-origin file (the fallback is `script-src 'self'`), and each new script, worker or page needs a `STATIC_FILES` entry. `style-src 'self'` blocks `style` attributes and `<style>` elements; positions for windowed rendering have to be set through script (`element.style`), which the policy does not restrict. | `app.py:23-33`. [RUN]: `GET /static/buffer.js` returned 404. [RUN] with a probe page served under this policy string in headless Chrome 157: a worker from a same-origin file started, and a `fetch` POST to the same origin went through. The statements about styles are from the specification. [NOT VERIFIED] in a browser | Yes | Each ticket that adds a file extends the allowlist and its tests. #3 carries a check for the style rule; #4 for the worker. |
| D12 | The README says the textarea may convert CRLF to LF on load. The server stores CRLF unchanged. Once the textarea is replaced, a document keeps its line endings, and the README sentence becomes wrong. | README "Limits"; [RUN] a text with `\r\n` came back unchanged with `size_bytes` 19. | Minor | #3 updates the README sentence. |
| D13 | PRD 5.2 does not list the 400 `bad_request` code (missing or invalid `Content-Length`, `Transfer-Encoding`, incomplete body), and PRD 9 does not list the `Cross-Origin-Resource-Policy` header or the forced `Connection: close`. | `app.py:202-212`, `75`, `223`. [RUN] 400 `bad_request` seen. | Minor | NEW-B adds the code to PRD 5.2 when it touches the table. |
| D14 | The README and PRD name Python 3.12. The only local interpreter is 3.13.14. | [RUN] 59 tests `OK` on 3.13.14. | Minor | `CLAUDE.md` says "3.12 or newer" and names what was run. |
| D15 | The fixture of "1,000,000 lines, about 60 MB" and the seeds 1337, 99, 2024 and 7 are named in the issues without a generator, a line format or a random-number algorithm, so two implementers would not get the same bytes. | Issues #1 to #6. | Yes | NEW-A fixes them: the line formula of PRD 5.6 extended past line 200 (1,000,000 lines are 58,479,896 bytes with LF endings) and the `mulberry32` generator with pinned outputs. [RUN]: sizes and hashes computed from `sample.py`; the generator outputs agree between JavaScript and a Python port. |
| D16 | `performance.measureUserAgentSpecificMemory()` (issue #6) needs a cross-origin isolated page, which this server's headers do not provide. | `app.py:71-76`. Web platform behaviour. [NOT VERIFIED] | Minor | NEW-C records `heapBytes` as `null` with a reason unless the owner approves adding the two isolation headers to the benchmark page. |

Open choices in PRD 14 that the tickets now carry as marked defaults: download-only save (no File System Access API) in #6, native regular expressions with a watchdog in #4, the checkpoint rule in NEW-B and #5, scroll scaling in #3. The piece-table index (tree or Fenwick) stays the implementer's choice in #2.

## 7. Things an implementer will trip over

1. **The static allowlist.** A new file under `line_editor/static/` is not served until it has a `STATIC_FILES` entry with the right content type (`app.py:23-28`). A worker script must be served as JavaScript because `nosniff` is set.
2. **No inline style or script.** See D11. Use `element.style` properties or classes, never a `style` attribute in markup or `setAttribute("style", ...)`.
3. **Health and schema tests.** See D2 and D4. The first migration changes four tests and two PRD sections, and a delete route changes a fifth test.
4. **One connection per call and `Connection: close`.** Each request opens a TCP connection and each store call opens SQLite (`storage.py:106-116`). Batch operation-log writes; do not send one request per keystroke.
5. **The body reader is JSON-only.** `_read_json_body` rejects every other content type. Raw chunk bodies need their own reader with the same guards: a valid `Content-Length`, the cap checked before reading, no `Transfer-Encoding`, the Origin check.
6. **Limits live in three places.** 120, 262144, 1048576 and 500 are in `validation.py:4-7`, the two database checks (`storage.py:20-21`) and `app.js:4-5`, plus PRD 5.1 and the README.
7. **Scripted clients.** A POST or PUT with a foreign `Origin` gets 403; one without `Origin` is accepted. `Host` must be `127.0.0.1:<port>` or `localhost:<port>`.
8. **UTF-16 versus bytes.** The buffer counts UTF-16 code units, the limits and files count UTF-8 bytes, and the title counts code points. Name the unit in every API and test.
9. **The labels are a contract.** PRD 5.5 names **Document text** and the others. A custom editor surface must still be reachable by that name (`aria-labelledby`), and `test_index_html_and_csp` must keep passing.
10. **Stopping a server on Windows.** With the Microsoft Store Python, `python` is a launcher that starts a child process. Killing the launcher from Git Bash (`kill $!`) leaves the child listening. [RUN]: the port stayed open and a second server failed with "Only one usage of each socket address". Stop the server with Ctrl+C in its own terminal, or stop the process that owns the port (PowerShell: `Stop-Process -Id (Get-NetTCPConnection -LocalPort <port> -State Listen).OwningProcess`).
11. **Headless checks.** The installed Chrome can run a page with no extra package, but printing the DOM is not a way to wait for it. [RUN] with Chrome 157 against local probe pages, one run per strategy, not against this app. The three results below are from the review probe (a page with a 300 ms page timer, then a worker with its own 200 ms timer, then a `fetch` POST of its report):
    - `chrome --headless=new --user-data-dir=<temp> <url>`, with neither `--dump-dom` nor a virtual time budget, runs the page in real time: a 300 ms page timer took 311 ms on the serving process's clock, a worker's own 200 ms timer took 207 ms, and the page's `fetch` POST of its report arrived. The browser does not exit by itself; whoever started it has to end its process tree.
    - `--dump-dom` alone prints the DOM at load, before any timer.
    - `--dump-dom --virtual-time-budget=5000` waits for page timers on virtual time (a 300 ms timer fired 16 ms after it was set) and did not wait for a worker's timer, so the printed DOM had no result.

    One earlier run, the build-stage probe, is the only support for the fallback: a different page, with a single 300 ms page timer that wrote its result into the DOM, no worker and no request, did print its result under `--dump-dom --virtual-time-budget=5000`. That shows the fallback works for a timer-only page and nothing more.

    NEW-A therefore has the harness page post its report to a test-only route of the harness server, and the runner waits for it on the wall clock. Checks that assert on elapsed time (cancel within 100 ms, the 2 s watchdog, long tasks) are valid only in that real-time mode.
