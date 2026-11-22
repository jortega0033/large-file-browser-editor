# CLAUDE.md

Large-file Browser Editor is a local, offline editor for text and log files: a Python process on the loopback interface serves one browser page and keeps documents in SQLite. The baseline (milestone M1) is a small-document editor with a plain `<textarea>` and is built. The large-file editing core (epic issue #1) is not: there is no buffer, windowed renderer, find, history, file open or benchmark yet.

## Commands

Both commands were run on 2026-11-22 on Windows 11 with Python 3.13.14, from the repository root.

| Purpose | Command | Observed |
|---|---|---|
| Test | `python -m unittest discover -s tests -t .` | `Ran 59 tests`, `OK`, about 16 seconds |
| Run | `python -m line_editor --data-dir ./data --port 8765` | Observed with a scratch data directory and another port (`--port 8797`): it printed `Serving on http://127.0.0.1:8797/`. The command as shown, with `./data` and port 8765, is the README form and was not run in that exact form. Open the URL it prints. |

- There is no install step. Python 3.12 or newer is the only requirement. The README names 3.12; only 3.13.14 was run during preparation.
- Both `--data-dir` and `--port` are required. `--port 0` picks a free port and prints it. Use it for scratch runs so that you do not collide with a server someone left on 8765.
- There is no lint, format, type-check or build command; do not claim that any of these passed. CI runs the test command on Linux and Windows (see "Delivery workflow").
- The browser page has no automated test at baseline. The first ticket of the epic (#7, split into sub-issues) adds a browser harness; until it has landed on `main`, run what can be scripted and describe the remaining browser step as a manual run under "Owner checks" in the pull request.
- On Linux use `python3`. That was not re-run during preparation.
- Stop every server you start. On Windows with the Microsoft Store Python, killing the `python` launcher from Git Bash leaves the real server process listening; stop it with Ctrl+C in its own terminal or by the port owner (see [docs/architecture.md](docs/architecture.md), section 7, item 10).
- `data/` and `*.sqlite*` are ignored by Git; use a scratch `--data-dir` for experiments.

## Hard constraints

These come from [docs/PRD.md](docs/PRD.md) sections 2, 3, 4 and 9.

- Python standard library only on the server and in the tests. Native HTML, CSS and JavaScript in the browser. No pip or npm dependency, no package manifest, no build step. A tool or package a ticket seems to need must work offline and be approved by the owner before it is added (PRD 3).
- No external request of any kind: no CDN, web font, remote URL or telemetry. Document bytes never leave `127.0.0.1`.
- The server binds `127.0.0.1` only. Keep the Host and Origin checks, the body cap checked before reading, and the security headers on every new route.
- The Content-Security-Policy is `default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; ...` with no inline script or style. A new script, worker or page must be a same-origin file with an entry in `STATIC_FILES` in `line_editor/app.py`, or it is not served.
- Put user text into the page only with `textContent` or `.value`.
- **No performance claim without a measurement.** M1 makes no large-file or performance claim. A latency or memory figure may appear in the README, the PRD or an issue only when it was measured, with the machine, browser, operating system and date next to it. Numbers in acceptance criteria are check parameters, not results.
- All sample and fixture data is generated and fictional.

## Sources of truth

| Question | Where to look |
|---|---|
| What the product is, the limits, the HTTP API, the schema, the UI labels, the sample fixture, the M1 acceptance matrix (11), the planned milestones (2, 10) and the open choices (14) | [docs/PRD.md](docs/PRD.md) |
| How the code is layered, the traced save workflow, invariants, what is implemented, planned or still unverified, and where the PRD or the issues and the code differ | [docs/architecture.md](docs/architecture.md) |
| What to build next and in which order | Epic issue #1 on GitHub and its sub-issues |
| What was observed to work at baseline, and on which platforms | [README.md](README.md), "Baseline verification" |

Code and tests show what the product does. The PRD says what it should do. When they disagree, do not pick one silently: add a row to the drift table in `docs/architecture.md` and raise it in the ticket.

## Architecture boundaries

Details and source citations are in [docs/architecture.md](docs/architecture.md). The rules that a change must keep:

- `line_editor/validation.py` holds the limits and pure input rules: no I/O, no SQLite, no HTTP.
- `line_editor/storage.py` owns SQLite. Each write is one `BEGIN IMMEDIATE` transaction on its own connection. It raises domain exceptions and knows nothing about HTTP. Schema changes are new entries in `MIGRATIONS`, forward only; a database from a newer version is refused.
- `line_editor/app.py` owns HTTP: guards, routing, the error envelope, static files. It validates first and calls the store second, and it maps store exceptions to status codes.
- `line_editor/static/` is the whole UI. The server owns every saved document; the browser owns only the unsaved draft.
- The M1 contract in PRD section 5 (routes, limits, the revision check, the labels) stays valid while the epic is built. Large documents get their own routes and storage next to it; do not loosen the M1 limits to make a large file fit.
- New browser code that has to run both on the page and in a worker (the buffer) must not touch the DOM.
- Test-only code lives under `tests/` and is never added to `STATIC_FILES`.

## Git workflow

Observed state at preparation time: `main` is the default branch with one commit, it is not protected, there was no CI (CI was added later by the SDLC kit, see "Delivery workflow") and there were no contribution rules in the repository. The rules below are the working defaults until the owner replaces them.

- Never commit to `main` directly. Branch from the tip of `origin/main`, one branch per ticket, named `<type>/<issue-number>-<short-slug>` (for example `feat/2-piece-table-buffer`).
- Keep commits small and use the existing subject style (`feat: ...`, `fix: ...`, `docs: ...`, `test: ...`, `chore: ...`).
- Open a draft pull request that names the issue (`Part of epic #1`, `Closes #N`). The owner reviews and merges. Do not merge, force-push or rewrite published history.
- Do not commit a data directory, a SQLite file, `__pycache__`, a generated fixture file or a browser report folder. `.gitignore` covers the first three and the report folders; keep generated fixtures outside the repository or in an ignored directory.
- A change to behaviour updates the matching PRD section, the README where it states the behaviour, and `docs/architecture.md` in the same pull request.

## Evidence before claiming a ticket done

Report only what you ran and saw. For each ticket, capture:

1. The full-suite command and its last lines: `python -m unittest discover -s tests -t .`, with the test count and `OK`. The count must not go down from 59.
2. The names of the new tests or harness suites and the acceptance criteria they cover.
3. For API changes: one request and response for the main case and one for a rejected case, taken from a real server on a scratch data directory, including the status code.
4. For browser changes: the browser name and version, how the page was run (headless runner or by hand), the steps, and the report the harness page produced. Say plainly if no browser run was done. Keyboard operation, labels, the status and alert regions and focus visibility are acceptance criteria (PRD 5.5 and 6), not polish.
5. For anything with a seed or a fixture: the seed, the fixture size in lines and bytes, and the digest that was compared.
6. For any timing or memory number: the machine (CPU count), operating system, browser and version, fixture, cold or warm, and the date. State that it is one machine's measurement.
7. For schema changes: a run that opens a database created by the previous schema version and shows the documents intact.
8. `git status --short` showing no stray files, and confirmation that every server and browser process started for the check was stopped.
9. For a pull request: the order is local checks, Code Reviewer and Reality Checker on the recorded local evidence, a draft pull request, CI on that draft, and only then ready. CI green is checked by the driver before `gh pr ready` and the CI run link goes on the issue; it is not evidence the gates can judge, because the run does not exist until the draft is open.
10. A step that needs a person ("by hand in a normal browser") is done as far as an agent can (scripted or headless run, with evidence) and the rest is listed under "Owner checks" in the pull request; Reality Checker accepts that only when the ticket marks the step as manual.

State what was not verified. A README or PRD claim that you did not reproduce is a claim, not evidence.

## Project agents and ticket implementation

`.claude/agents/` holds nine project-local roles copied from Agency Agents at a pinned revision, plus the Loop verifier (`loop-verifier.md`, see "Loop" below). Source paths, licence, local changes, the name collision with a user-level install, and how to check that the roles load are in [.claude/agency-agents/README.md](.claude/agency-agents/README.md).

Each role file starts with a section "In this repository" that is tailored to this project: the constraints that bind the role, the files it owns or reviews, its commands or the inputs it must be given, its checklist, the parts of the upstream text that do not apply, and what it hands back. The upstream text below that section was written for larger stacks (frameworks, cloud services, test tools, new dependencies); that section and this file win wherever they differ.

When asked to implement, continue or finish a GitHub issue, follow the playbook in [`.claude/skills/implement-ticket/SKILL.md`](.claude/skills/implement-ticket/SKILL.md). Claude Code loads it on its own for ticket work; `/implement-ticket <issue number>` starts it by hand. Delegate to the roles without waiting to be asked: each role's `description` ends with a "Use proactively ..." sentence, which is what makes Claude Code delegate to it.

| When | Roles | Access |
|---|---|---|
| Before coding | Codebase Onboarding Engineer (an unfamiliar area); Software Architect (a module boundary, data model, storage schema, public API or dependency changes) | read-only |
| While coding | Backend Architect (`line_editor/*.py`); Frontend Developer (`line_editor/static/` and `tests/browser/`) | can edit |
| After coding, when the trigger matches | Accessibility Auditor (UI, keyboard handling, focus order, markup); Performance Benchmarker (a performance budget, a benchmark, large-input behaviour) | read-only |
| After coding, when the trigger matches | API Tester (`tests/`: an HTTP endpoint, status code or contract changes) | can edit |
| On every ticket, before it is called done | Code Reviewer on the full diff (review gate), then Reality Checker on the acceptance criteria and the evidence (acceptance gate) | read-only |

- The review gate and the acceptance gate run on every ticket, however small the change.
- The session or role that wrote a change does not count as its reviewer.
- Read-only roles have `tools: Read, Grep, Glob` and cannot run commands. Give them the diff, the acceptance criteria and the recorded command output.
- List the roles that ran and their verdicts in the pull request description under "Agent roles run".

## Loop

Loop Engineering is set up with the `issue-triage` pattern at L1: report-only and started by hand. It has no scheduler and makes no GitHub writes. See [LOOP.md](LOOP.md) and [loop-constraints.md](loop-constraints.md).

## Delivery workflow

- **Tooling is installed, not ticketed.** Every open ticket is about app implementation (owner-decisions entry 3).
- **Start and playbook.** The owner starts one ticket with [`/next-ticket`](.claude/skills/next-ticket/SKILL.md); it runs the [`implement-ticket`](.claude/skills/implement-ticket/SKILL.md) playbook. It picks leaf tickets only: a ticket labelled `tracking` or with open sub-issues is a container and is never picked (an explicit number of one is refused and its open sub-issues are listed); the pull request of a parent's last sub-issue also says `Closes #<parent>`. It writes the review diff and evidence to `.claude/state/review/` before the gates, and after the draft pull request and push it ends its turn with "Draft pull request #N is waiting for CI" instead of polling. There is no scheduler.
- **Review gate.** [`.claude/hooks/role_gate.py`](.claude/hooks/role_gate.py) blocks `gh pr create` and `gh pr ready` until Code Reviewer and Reality Checker ran after the last code edit, so no pull request is opened, not even a draft, with a gate not run. Order: local checks, both gates, draft pull request, CI, then ready only on green CI. `ROLE_GATE=off` in the environment Claude Code is started from switches it off for that session.
- **Permissions.** [`.claude/settings.json`](.claude/settings.json): documented commands allowed; force pushes, pushes to `main`, `gh pr merge`, releases and reads of `.env` denied; edits to CI, agent configuration and Loop files ask first; the agent configuration paths ask at any depth, so their copies inside a ticket worktree ask too. A ticket never changes agent configuration.
- **CI.** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the test command and the gate self-test on Linux and Windows. It runs on the draft pull request and must be green before the pull request is marked ready; the driver checks that, not Reality Checker. A failure means fix, re-run local checks and both gates, and push.
- **Pull request.** Use [`.github/pull_request_template.md`](.github/pull_request_template.md). Labels: `status:ready`, `status:blocked`, `status:in-progress`, `needs-decision`.
- **Changelog.** Every ticket pull request adds a line to [CHANGELOG.md](CHANGELOG.md) under Unreleased.
- **UI and copy.** [docs/ui-quality.md](docs/ui-quality.md) holds the ten binding UI rules; the `ui-ux-pro-max` and `unslop` skills in `.claude/skills/` are used for UI work and for copy.
- **Decisions and releases.** [docs/owner-decisions.md](docs/owner-decisions.md) records the owner's decisions. Only the owner merges and releases ([docs/RELEASING.md](docs/RELEASING.md)).
