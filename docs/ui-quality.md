# UI quality rules

Ten rules for every screen and every piece of user-facing text in this repository. They are binding. Rules 1 and 2 were stated by the owner; rules 3 to 10 were proposed and approved on 2026-11-22. The record is in [owner-decisions.md](owner-decisions.md).

1. No thick accent border on one side of a card, callout, alert, list item or quote (for example `border-left: 4px solid <accent>`). Use spacing, type weight, an icon or a full hairline border instead.
2. No soft tinted background with a thin border of the same hue as the default way to mark a status, tag, callout or card. One neutral surface and one clear signal (text, icon or a solid chip) is enough.
3. No gradient text and no purple-to-blue gradient as a default accent.
4. No blur or glass panels, and no drop shadow plus large radius on every card.
5. No emoji used as icons or bullets, and no sparkle marks.
6. No pill or badge on things that are not states. No all-caps, letter-spaced micro labels as section decoration.
7. No centred hero with a slogan in an application screen. Screens open on the user's task.
8. One accent colour, used for the primary action and the current selection. Status colours only for status.
9. Dense, aligned layouts on a consistent spacing scale. No card grid where a table or a list is the right form.
10. User-facing copy is plain and specific: no filler, no exclamation marks, and the same word for the same thing everywhere.

This repository's own constraints still apply: no external font, image or script, and no inline style (see `CLAUDE.md`, "Hard constraints").

## How the rules are applied

- A ticket that changes a screen starts with the `ui-ux-pro-max` skill (design-system search for the product type, using `python .claude/skills/ui-ux-pro-max/scripts/search.py`) and ends with a check of every changed screen against this file.
- User-facing copy, documentation and pull request text go through the `unslop` skill before the pull request is opened.
- The Frontend Developer, Accessibility Auditor and Code Reviewer roles name this file in their checklists (UI Designer and UX Architect are not installed here).
- Enforcement is the review gate: Code Reviewer runs on every ticket. Rule 1 can be linted; rule 2 cannot be detected reliably from CSS, so a reviewer checks it by reading.

The colours, spacing, radii and motion come from the shared Pipenzo tokens in `line_editor/static/tokens.css`; see [design-tokens.md](design-tokens.md).
