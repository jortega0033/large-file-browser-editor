# AGENTS.md

The full repository instructions are in [CLAUDE.md](CLAUDE.md). This file repeats only what an agent needs before it reads that.

## Test commands

```
python -m unittest discover -s tests -t .
```

Python 3.12 or newer, standard library only (`python3` on Linux). There is no lint step, no build step and no package manifest. Do not add pip or npm dependencies. The browser UI has no automated test at baseline.

## Run

```
python -m line_editor --data-dir ./data --port 8765
```

`--port 0` picks a free port. Stop every server you start.

## Ticket workflow

To implement a GitHub issue, follow [`.claude/skills/implement-ticket/SKILL.md`](.claude/skills/implement-ticket/SKILL.md) and the section "Project agents and ticket implementation" in [CLAUDE.md](CLAUDE.md). Each role file in `.claude/agents/` starts with a section "In this repository"; an agent that cannot delegate to those roles does the role's step itself with that section as its checklist, and says so in the pull request.

## Loop conventions

- The loop runs at L1: report-only, started by hand. It proposes; it does not label, comment, close, edit source, push or merge.
- No scheduler and no workflow file is installed. Do not add one without the owner's approval.
- See [LOOP.md](LOOP.md) for the manual command and the human gates.
