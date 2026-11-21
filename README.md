# Large-file Browser Editor

A local, offline editor for text and log files. The M1 baseline is a named-document editor with a plain textarea, backed by SQLite on your machine. Nothing leaves `127.0.0.1`.

M1 implements durable documents with conflict handling. See the baseline verification below. Large-file features (piece-table buffer, windowed rendering, find, history, file streaming, benchmarks) are planned, not built. **M1 makes no large-file or performance claims.**

Full spec: [docs/PRD.md](docs/PRD.md).

## Requirements

Python 3.12. Standard library only. No build step, no packages, no network.

## Launch

Linux:

```
python3 -m line_editor --data-dir ./data --port 8765
```

Windows:

```
python -m line_editor --data-dir .\data --port 8765
```

Open the printed URL (`http://127.0.0.1:8765/`). `--port 0` picks a free port. The data directory is created if needed. A bad directory or a database from a newer version exits with code 2. Stop with Ctrl+C.

## M1 smoke steps

1. Open the page: empty editor, list says "No saved documents yet."
2. Select **Load sample** (200 fictional log lines, unsaved). Type a title in **Document title**, select **Save**: status shows revision 1 and the title appears in the document list.
3. Edit **Document text**, press Ctrl+S: revision 2.
4. Open a second tab, load the document, save a change; go back to the first tab, edit and **Save**. A conflict message appears, your text stays, and you can choose **Save as copy** or **Load latest**.
5. Stop and restart the server on the same `--data-dir`: the document is still listed.
6. Resize to 800×600: no horizontal page scroll.

## Limits

- Title: 1–120 code points. Text: up to 256 KiB (262144 bytes UTF-8), no NUL characters.
- Request body: 1 MiB. Documents: 500.
- The textarea may convert CRLF to LF when a document is loaded, so edited text saves with LF.

## Local persistence

Documents live in `<data-dir>/line_editor.sqlite3` (WAL mode). Each save increments a revision; a save based on an old revision is refused with 409 and your text is kept.

## Tests

```
python -m unittest discover -s tests -t .
```

Use `python3` on Linux. Tests use temporary directories. The browser UI has no automated tests in M1.

## Security notes

Binds 127.0.0.1 only. Rejects foreign Host and Origin headers, sends no CORS headers, serves only four allowlisted static paths, and enforces a strict CSP.

## Planned (high level)

1. Indexed piece-table buffer with stable operation and line retrieval contracts.
2. Windowed rendering, selections and jump to line for 1,000,000-line files.
3. Worker-backed find/replace and syntax classing with cancellation.
4. Undo/redo history, multi-cursor grouping and restart recovery.
5. Local file open/save streaming and a measured cold/warm benchmark suite (results reported, not promised).

Details and acceptance criteria are in [docs/PRD.md](docs/PRD.md).

## Baseline verification

- Windows with Python 3.13.14 and Ubuntu 24.04 WSL with Python 3.12.3 each passed 59 unit and API tests. WSL unit tests used temporary storage on tmpfs.
- Chrome 157 verified the main workflow with external requests blocked. A stale save returned 409 without erasing the draft, and the winning revision reopened after a server restart.
