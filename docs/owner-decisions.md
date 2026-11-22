# Owner decisions

Decisions the owner made for this repository on 2026-11-22. Changing any entry needs the owner. An agent that finds a decision blocking a ticket stops and says so.

| # | Date | Decision | Implemented in |
|---|---|---|---|
| 1 | 2026-11-22 | The instructions, tooling and playbook live on the default branch. | `CLAUDE.md`, `.claude/` |
| 2 | 2026-11-22 | Persona agents run automatically during ticket work and carry instructions tailored to this project. | `.claude/agents/`, `.claude/agency-agents/README.md` |
| 3 | 2026-11-22 | Every open ticket is about app implementation; tooling is installed, not ticketed. | `CLAUDE.md` ("Delivery workflow"), `.claude/skills/next-ticket/SKILL.md` |
| 4 | 2026-11-22 | Agents may take a ticket up to a ready pull request. Only the owner merges and releases. | `.claude/skills/implement-ticket/SKILL.md`, `.claude/settings.json`, `docs/RELEASING.md` |
| 5 | 2026-11-22 | No scheduler. Ticket work starts only on the owner's go signal (`/next-ticket`), because the repository is used to train AI models. | `.claude/skills/next-ticket/SKILL.md`, `LOOP.md` |
| 6 | 2026-11-22 | A review gate hook blocks opening or readying a pull request until the gate roles have run after the last code edit. | `.claude/hooks/role_gate.py`, `.claude/settings.json` |
| 7 | 2026-11-22 | Loop Engineering stays at L1, report-only and unscheduled. | `LOOP.md` |
| 8 | 2026-11-22 | Continuous integration runs on Linux and Windows; the default branch requires a pull request and green checks. | `.github/workflows/ci.yml` (branch protection is set by the owner on GitHub) |
| 9 | 2026-11-22 | Permission rules: documented commands are allowed; force pushes, pushes to the default branch, merges, releases and reads of secrets are denied; edits to CI, agent configuration and Loop files ask first. | `.claude/settings.json` |
| 10 | 2026-11-22 | Open decisions on tickets are settled with the ticket's stated default (list below). | the epic issue #1 and its children |
| 12 | 2026-11-22 | The ten UI rules in `docs/ui-quality.md` are binding, and the `ui-ux-pro-max` and `unslop` skills are installed and used for UI work and for copy. | `docs/ui-quality.md`, `.claude/skills/ui-ux-pro-max/`, `.claude/skills/unslop/` |

Entry 11 (Rust verified in CI only) does not apply: this repository has no Rust.

## Entry 10: decisions settled by the ticket default

| Issue | Decision | Default taken |
|---|---|---|
| #2 | Line numbering in the API | 0-based; the UI shows 1-based |
| #2 | What counts as a line break | LF, CR and CRLF each; not LF only |
| #3 | Tab key in the editor | Moves focus out; not inserted |
| #3 | Enter key | Inserts LF, or CRLF when the document's first line break is CRLF |
| #3 | Lines over 10,000 code units | Rendered up to that length plus a marker with the remaining count |
| #4 | Regular expression flags and engine | JavaScript syntax, always the `u` flag, native engine with time slicing and a watchdog |
| #4 | Results after an edit during a scan | Scan ends as `stale`; the UI searches again after a pause |
| #4 | Replace all in regular expression mode | `$1` and `$&` work as in JavaScript |
| #4 | Watchdog | Search ends as timed out 2 to 3 s after the worker's last message |
| #5 | Maximum number of carets | 1,000; Add caret buttons next to the Ctrl+Alt+arrow keys |
| #5 | Recovery log segment sending | After 1 s without edits or at 256 KiB pending |
| #5 | Undo for M1 text documents | Session only; save and conflict behaviour unchanged |
| #6 | Saving a file | Download only; Ctrl/Cmd+S runs Save to file; no File System Access API |
| #6 | Byte order mark, NUL, size cap, several dropped files | BOM kept and drawn with zero width; NUL kept with a placeholder; 512 MiB cap; first file used |
| #5, #6 | Opening a file from disk | Becomes a `chunked` document with a recovery copy |
| #6 | Save and Save as copy | Off for file documents; the download is the only save |
| #7 | Random generator and mixed line endings | `mulberry32`; line i ends CRLF when the i-th output is odd |
| #7 | Headless figures | Printed as measurements; published figures come from a normal browser window |
| #8 | Chunk routes and limits | Route shapes as in the ticket; at most 512 chunks per generation; NUL allowed in chunks |
| #8 | Deleting large documents | Allowed in any state through `DELETE /api/v1/documents/{id}` |
| #9 | Benchmark page location | `tests/browser/`, not shipped in the app |
| #9 | Benchmark runs | 1 cold and 3 warm per size |
| #9 | Memory measurement | `performance.memory.usedJSHeapSize` where present, otherwise `null` with the reason; no cross-origin isolation headers |

No ticket in the epic is missing a stated default. If one is found later, take the conservative option and flag it in the issue.
