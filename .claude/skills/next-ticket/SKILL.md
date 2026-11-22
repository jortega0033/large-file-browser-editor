---
name: next-ticket
description: Owner-started driver that takes one ticket of epic #1 up to a ready pull request. Starting it is the owner's go signal.
argument-hint: "[issue number]"
disable-model-invocation: true
---

# Next ticket

Only the owner starts this skill (`/next-ticket` or `/next-ticket <issue number>`). Starting it is the go signal for exactly one ticket. It never merges and never starts another run.

Labels: `status:ready`, `status:blocked`, `status:in-progress`, `needs-decision`. The epic is issue #1; its children are #2 to #9 and the dependency order is in the epic body. If a label does not exist yet, say so and stop; do not create labels.

## Steps

1. **Refresh the queue.** `gh issue list --state open --limit 100` and `gh issue view 1`. A `status:blocked` ticket whose blockers are all closed is ready: report it (the label change is the owner's or the orchestrator's if you lack permission).
2. **Pick.** With an issue number, use it. Otherwise take the first `status:ready` child of #1 in the epic's dependency order that is neither `status:in-progress` nor `needs-decision`. If none, report that and stop.
3. **Claim.** Label the issue `status:in-progress`.
4. **Branch in a fresh worktree** from the tip of `origin/main`, named `<type>/<issue-number>-<short-slug>` as `CLAUDE.md` ("Git workflow") says: `git fetch origin` then `git worktree add ../<repo>-<issue-number> -b <branch> origin/main`. Never work on `main`.
5. **Run the `implement-ticket` playbook** (`.claude/skills/implement-ticket/SKILL.md`) in that worktree for the one ticket.
6. **Finish.** When the review gate, the acceptance gate and CI are green, mark the pull request ready (`gh pr ready`; the gate hook allows it only after the gate roles ran) and comment on the issue with the pull request link and the evidence summary. Do not merge. Only the owner merges.
7. **Stop.** One ticket per run. Report what was done and what was not verified.

If a ticket needs an owner decision that has no stated default, label it `needs-decision`, comment on the issue and stop.
