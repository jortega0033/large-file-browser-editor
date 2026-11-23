# Design tokens

The page uses the Pipenzo "Flow look" tokens: black page, Flow-style alpha layers, one accent (Pipenzo yellow `#FECE02`), red only for danger. Owner decision 13 in [owner-decisions.md](owner-decisions.md).

## Source and resync

`line_editor/static/tokens.css` is a byte-for-byte copy of `extension/sidepanel/tokens.css` in `jortega0033/clip-to-reel-studio` at commit `a13378ce73e5b27213c9a200fc960ec93afef054` (2026-11-21). Do not edit it here. Its header comment differs from the rule below: it lists the primary button, the current-step node, the turn chip and two dots as the yellow uses, and it does not list the current selection. The per-token comments differ too: `--primary` lists the turn chip and dots, and `--state-selected` is described as a selected row or segment fill. Those comments stay as they are, because the copy must stay identical to the source. This document takes precedence over any comment in `tokens.css`, including the `--primary` and `--state-selected` comments, and `--state-selected` does not mark the current selection (use the selection style below). To resync, copy the file over it; nothing else changes. The file is served at `/static/tokens.css` (entry in `STATIC_FILES`) and linked before `styles.css`.

## Token names by role

| Role | Tokens |
|---|---|
| Surfaces | `--bg` (page), `--surface` (panels), `--bg-raised` (inputs), `--bg-sunken` (wells, disabled) |
| Text | `--fg`, `--muted`, `--faint` |
| Lines | `--border`, `--hairline`, `--control-border`, `--input-border` |
| Accent | `--primary`, `--primary-press`, `--primary-edge`, `--on-primary` |
| Dark block | `--ink`, `--on-ink`, `--on-ink-muted`, `--ink-border` |
| Status | `--danger`, `--danger-bg`, `--success`, `--ok`, `--warn-fg`, `--info` |
| Focus | `--focus` |
| Alpha, shadow, motion, type, space, radius | `--glass*`, `--scrim`, `--state-*`, `--shadow-*`, `--dur-*`, `--font`, `--mono`, `--space-*`, `--radius-*` |

## Rules

- New UI uses these tokens; no new colour literals in `styles.css`, `app.js` or `index.html`.
- Yellow (`--primary`) goes on three things only: the primary action, the current-step marker and the current selection. The owner decided these three uses on 2026-11-23 (decision 14); they are read into rule 8 in [ui-quality.md](ui-quality.md).
- Red only for danger.
- Current selection: a solid `--primary` fill with `--on-primary` text, plus a second sign that is not colour (weight, icon or text) and the existing `aria` attribute (for example `aria-selected` or `aria-current`). Not a yellow border alone: it is about 1.5:1 against white on light. Never a tint with a border of the same hue, and never a thick border on one side.
- Focus ring: `--focus` is a focus indicator and is exempt from the accent limit, including where it is yellow in dark. A ticket that says the focus style stays unchanged means the rule on main after the token pull request.
- Themes: contrast and no-colour-alone checks cover both the light block (`:root`) and the dark block of `tokens.css`.
- Linking: a ticket that creates a page or its static allowlist links `tokens.css` before any other stylesheet and serves it (allowlist and its test).
- Text never sits on a bare alpha layer; use the opaque surface tokens.

The selection style (D1, how), focus (D2), themes (D3) and linking (D4) were recommended by the orchestrator and adopted under the owner's delegation of 2026-11-23. Details are in entry 14 of [owner-decisions.md](owner-decisions.md).

## Light and dark

Dark is the primary design. `tokens.css` defines the light theme in `:root` and overrides it inside a `prefers-color-scheme: dark` media block, so the operating system colour scheme decides. There is no in-page switch.

## Status of the page

The page does not follow the selection rule yet. The document list marks the current document with `aria-current`, weight 600 and a 2px neutral (`--fg`) border on a `--bg-sunken` fill, not a `--primary` fill. A ticket has to change this; none is named here. This document records the rule, not finished work.
