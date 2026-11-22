# Agency Agents roles used in this repository

The Markdown files in `.claude/agents/` whose names start with `engineering-` or `testing-` are copies of role definitions from Agency Agents. They are project-local Claude Code subagents. The file `loop-verifier.md` in the same folder is not from Agency Agents; it belongs to the Loop Engineering setup described in [`LOOP.md`](../../LOOP.md).

## Source and licence

- Upstream: https://github.com/msitarzewski/agency-agents
- Pinned revision: `8ae6164602c95ca78828b148b9052460ee426885` (upstream `main`, committed 2026-11-09)
- Licence: MIT, "Copyright (c) 2025 AgentLand Contributors". The upstream licence text at the pinned revision is kept unchanged in [`LICENSE`](LICENSE) next to this file (SHA-256 `9a45258434d5cedf0af73c9ad4771373701225038d246c49219026c33677f66f`). It covers only the copied role files, not the rest of this repository.
- Fetched with `gh api -H "Accept: application/vnd.github.raw" "repos/msitarzewski/agency-agents/contents/<path>?ref=<revision>"`.

## Installed roles

"Upstream SHA-256" is the hash of the file as fetched at the pinned revision (LF line endings). Reviewer roles have one added frontmatter line, `tools: Read, Grep, Glob`, so they cannot edit files or run commands. Nothing else in any file was changed.

| File in `.claude/agents/` | `name:` | Upstream path | Upstream SHA-256 | Local change |
|---|---|---|---|---|
| `engineering-software-architect.md` | Software Architect | `engineering/engineering-software-architect.md` | `b85121691776147bacde26673e68fbbacd6a7f0816d1ca8e203c264d25ce1d30` | added `tools: Read, Grep, Glob` |
| `engineering-code-reviewer.md` | Code Reviewer | `engineering/engineering-code-reviewer.md` | `7509fcc3ea1dda46511b2801996305bf3d4a125576f9655ff0b63df25602f446` | added `tools: Read, Grep, Glob` |
| `engineering-codebase-onboarding-engineer.md` | Codebase Onboarding Engineer | `engineering/engineering-codebase-onboarding-engineer.md` | `07aa548b45887c3ad768efad5fdbf6e57bea639df4f1b74c7e383142f454e2a1` | added `tools: Read, Grep, Glob` |
| `testing-accessibility-auditor.md` | Accessibility Auditor | `testing/testing-accessibility-auditor.md` | `362935907af23839775b9c6162f38c0c5a740542ab4350cb5c5b5a0d9f9a4268` | added `tools: Read, Grep, Glob` |
| `testing-reality-checker.md` | Reality Checker | `testing/testing-reality-checker.md` | `6d32fcdb114233e13902ec6372d50293b120e85d490b5e81d372c29808f988a1` | added `tools: Read, Grep, Glob` |
| `testing-performance-benchmarker.md` | Performance Benchmarker | `testing/testing-performance-benchmarker.md` | `16a841f67392d084b773c6d9f05341d093e9017f3e116f6df0de59a5a3f59c34` | added `tools: Read, Grep, Glob` |
| `engineering-backend-architect.md` | Backend Architect | `engineering/engineering-backend-architect.md` | `ac717bde4848d7663fff8a3c7edc711fd119256de6a7ce38c036619372f42c99` | none |
| `engineering-frontend-developer.md` | Frontend Developer | `engineering/engineering-frontend-developer.md` | `1ae4cc10b2e0163bd3ed921ad54080b865cd02e591becd8919b64b73fab06dad` | none |
| `testing-api-tester.md` | API Tester | `testing/testing-api-tester.md` | `ab91de9188d48bd9c417282c33673a37b066215e90e08c0f1b270d036084e3bb` | none |

## Why these roles

| Role | Use in this repository |
|---|---|
| Software Architect (read-only) | Review a ticket's design before code is written, against [`docs/architecture.md`](../../docs/architecture.md): the piece-table index and its line-break rule, the operation record shared by buffer, worker, history and server, the schema v2 layout, the checkpoint rule. |
| Code Reviewer (read-only) | Review a diff for correctness, missed edge cases and broken invariants: surrogate pairs, CR and LF split across pieces, the revision and sequence guards, the request guards on new routes, the static allowlist. |
| Codebase Onboarding Engineer (read-only) | Trace a code path and report facts with file and line citations. |
| Accessibility Auditor (read-only) | Review the editor that replaces the `<textarea>`: the `role="textbox"` surface, keyboard-only operation, the line and column readout, focus visibility, labels on Find and Go to line, and meaning that does not rest on colour alone. PRD sections 5.5 and 6 make these requirements. |
| Reality Checker (read-only) | Compare claimed evidence with what was actually run before a ticket or the epic is called done. The PRD forbids any latency or memory claim that was not measured and reported with its environment. |
| Performance Benchmarker (read-only) | Review the method of a measurement before its numbers are published: fixture size and seed, cold versus warm runs, what the timer encloses, and whether the report names the browser, OS and CPU count. It reviews; it does not run benchmarks. |
| Backend Architect | Implement work in `line_editor/*.py`: routes, storage and migrations, validation. |
| Frontend Developer | Implement work in `line_editor/static/` and the browser harness pages under `tests/browser/`. |
| API Tester | Write the HTTP-level `unittest` cases in `tests/` for new and existing routes. |

The three implementing roles and the Performance Benchmarker are written for larger stacks (frameworks, cloud services, Postman, k6, Lighthouse, Playwright). In this repository the rules in [`CLAUDE.md`](../../CLAUDE.md) win: Python standard library only, native HTML, CSS and JavaScript, `unittest`, no pip or npm dependencies, no external requests.

Roles that were considered and left out: Test Automation Engineer and Evidence Collector (their browser automation needs a dependency this repository does not allow; the backlog uses plain harness pages and an installed browser instead), Database Optimizer (one local SQLite file with primary-key lookups, no query tuning in the backlog), Rapid Prototyper (a runnable baseline already exists).

## Name collision with user-level agents

A developer who has installed Agency Agents in `~/.claude/agents/` already has agents with the same `name:` values. Claude Code gives the project-level definition precedence, so inside this repository the copies here are used, including the read-only tool limits. The upstream names were kept on purpose so that the roles stay recognisable and can be compared with upstream.

A Claude Code session that was already running when these files were added keeps the definitions it loaded at start. Start a new session to pick up the project copies.

## Check that the roles load

From the repository root, in a new session:

```text
claude -p "List the project-level subagents defined in .claude/agents with the tools each one may use. Then run the Reality Checker subagent and ask it which tools it has."
```

The six reviewer roles and `loop-verifier` must report exactly `Read, Grep, Glob`.

### What was observed, and what was not

Observed on 2026-11-22 with Claude Code 2.1.323, headless (`claude -p`, model `haiku` requested, no MCP servers), one run from the repository root, on a machine that also has a user-level Agency Agents install:

- All ten names were listed: Software Architect, Code Reviewer, Codebase Onboarding Engineer, Accessibility Auditor, Reality Checker, Performance Benchmarker and `loop-verifier` with `Read, Grep, Glob`; Backend Architect, Frontend Developer and API Tester with all tools.
- A launched Reality Checker and a launched `loop-verifier` each reported exactly `Read`, `Grep`, `Glob`. A launched Performance Benchmarker named the same three and said it could not print a verbatim list.
- The user-level copies have no `tools:` line, so for the six reviewers the project copies were the ones loaded.
- **Not shown:** that the project copy wins for the three implementing roles. They are unchanged from the pinned upstream and carry no tool limit, so the listing cannot tell the two copies apart, and no further run was made to separate them.
- **Not shown:** behaviour in an interactive session, and behaviour on a machine without a user-level install (there the ten names must simply be listed).
- The listing gives names and tools only, not the file a definition comes from. The model said so itself and matched the names against `CLAUDE.md`.

## Updating

Fetch the same paths at a newer revision, re-apply the `tools:` line to the six reviewer roles, and update the revision and hashes in this file in the same commit.

## Local change: automatic delegation (2026-11-22)

One sentence beginning "Use proactively" was appended to the `description:` line of every Agency Agents role in `.claude/agents/` (not to `loop-verifier`). Claude Code uses that field to decide when to delegate, so the roles now run during ticket work without being named.

A section headed "In this repository" was then inserted directly after the frontmatter of every Agency Agents role (not in `loop-verifier`), before the upstream text. It is project-specific text written for this repository, not upstream text: the constraints that bind the role here, the files it owns or reviews, its commands or the inputs it must be given, a checklist with the document and section each point comes from, the parts of the upstream text that do not apply, and what the role hands back. The section ends with the line "This section and CLAUDE.md override the generic text below wherever they differ." The upstream text below it is unchanged.

This supersedes any statement above that a role file is unmodified or that the `tools:` line is the only local change. To compare a role with the pinned upstream file, first remove all local changes: the "Use proactively" sentence, the "In this repository" section (from its heading through its closing line and the blank line after it), and the `tools:` line where one was added. When updating to a newer upstream revision, re-apply all three, and re-check the section against the repository.

The steps at which each role runs are in `.claude/skills/implement-ticket/SKILL.md` and in the section "Project agents and ticket implementation" of [`CLAUDE.md`](../../CLAUDE.md).

Verification, 2026-11-22: one headless run from the repository root with Claude Code 2.1.323 (`claude -p "List every project subagent defined in .claude/agents with its exact name and tools, say for each whether its instructions begin with a section titled In this repository, and say whether a skill named implement-ticket is available. Plain list, no commentary." --model haiku`), on a machine that also has a user-level Agency Agents install. It listed all ten names. Code Reviewer, Software Architect, Codebase Onboarding Engineer, Accessibility Auditor, Performance Benchmarker, Reality Checker and `loop-verifier` were listed with `Read, Grep, Glob`; Backend Architect, Frontend Developer and API Tester with no tools declared in the frontmatter. The nine Agency Agents roles were reported as beginning with "In this repository" and `loop-verifier` as not. The skill `implement-ticket` was reported as available. Not shown: whether the model took this from the loaded definitions or from reading the files, and behaviour in an interactive session.

## Local change: SDLC kit (2026-11-22)

This pass added the review gate hook (`.claude/hooks/role_gate.py`, gate roles Code Reviewer and Reality Checker, both already installed), `.claude/settings.json`, CI, the pull request and issue templates, `CODEOWNERS`, `dependabot.yml`, `SECURITY.md`, `CHANGELOG.md`, `docs/RELEASING.md`, the `next-ticket` skill, the `ui-ux-pro-max` and `unslop` skills, `docs/ui-quality.md` and `docs/owner-decisions.md`. The Frontend Developer, Accessibility Auditor and Code Reviewer checklists gained one line naming `docs/ui-quality.md`. UI Designer and UX Architect are not installed here. No agent role was added or removed.
