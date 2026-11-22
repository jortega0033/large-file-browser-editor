---
name: next-ticket
description: Owner-started driver that takes one ticket of epic #1 up to a ready pull request (draft first, ready only on green CI). Starting it is the owner's go signal.
argument-hint: "[issue number]"
disable-model-invocation: true
---

# Next ticket

Only the owner starts this skill (`/next-ticket` or `/next-ticket <issue number>`). Starting it is the go signal for exactly one ticket. It never merges and never starts another run.

Labels: `status:ready`, `status:blocked`, `status:in-progress`, `needs-decision`. The epic is issue #1; the dependency order is the table in the epic body (parents in table order). Big tickets are split into sub-issues; a ticket labelled `tracking` or `epic`, or with open sub-issues, is a container and is never work. If a label does not exist yet, say so and stop; do not create labels.

## Steps

1. **Refresh the queue.** `gh issue list --state open --limit 100` and `gh issue view 1`. A `status:blocked` ticket whose blockers are all closed is ready: set `status:ready` on it. Parents too: for each open ticket with sub-issues (`gh api repos/jortega0033/large-file-browser-editor/issues/<n>/sub_issues`), if all its sub-issues are closed, close it with a comment. If you lack permission, report it instead and leave the change to the owner or the orchestrator.
2. **Pick a leaf ticket.** With an issue number, check it first: if it is labelled `tracking` or has open sub-issues, refuse and list its open sub-issues; do not start work. Otherwise take the first `status:ready` leaf ticket in the epic's order (the order of the parents in the epic's table, then the sub-issues of each parent in their order) that is neither `status:in-progress` nor `needs-decision`. If none, report that and stop.
3. **Claim.** Label the issue `status:in-progress`.
4. **Branch in a fresh worktree** from the tip of `origin/main`, named `<type>/<issue-number>-<short-slug>` as `CLAUDE.md` ("Git workflow") says: `git fetch origin` then `git worktree add ../<repo>-<issue-number> -b <branch> origin/main`. Never work on `main`.
5. **Run the `implement-ticket` playbook** (`.claude/skills/implement-ticket/SKILL.md`) in that worktree for the one ticket. Before calling Code Reviewer and Reality Checker (they have no shell), write `git diff --stat origin/main...HEAD`, `git diff origin/main...HEAD` and the local check outputs to `.claude/state/review/` in the worktree and name those files in each request.
6. **Draft pull request and CI.** After the gates passed, `gh pr create --draft` and `git push`. If this ticket is the last open sub-issue of a parent, the pull request body says `Closes #<sub-issue>` and `Closes #<parent>`. Bind the pull request to the session when the app offers it, then end the turn with the line "Draft pull request #N is waiting for CI". Do not loop, sleep or watch. When the session is woken (a CI event from the app, or the owner says "continue"), read `gh pr checks <n>` once: green, go to step 7; red, fix, re-run local checks and both gates, push and end the turn with the same line; still running, end the turn with the same line.
7. **Ready.** When CI is green, mark the pull request ready (`gh pr ready`; the gate hook allows it only after the gate roles ran) and comment on the issue with the pull request link, the CI run link and the evidence summary. Steps that need a person go under "Owner checks" in the pull request. Do not merge. Only the owner merges.
8. **Stop.** One ticket per run. Report what was done and what was not verified.

If a ticket needs an owner decision that has no stated default, label it `needs-decision`, comment on the issue and stop.
