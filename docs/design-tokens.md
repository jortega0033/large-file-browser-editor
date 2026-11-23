# Design tokens

The page uses the Pipenzo "Flow look" tokens: black page, Flow-style alpha layers, one accent (Pipenzo yellow `#FECE02`), red only for danger. Owner decision 13 in [owner-decisions.md](owner-decisions.md).

## Source and resync

`line_editor/static/tokens.css` is a byte-for-byte copy of `extension/sidepanel/tokens.css` in `jortega0033/clip-to-reel-studio` at commit `a13378ce73e5b27213c9a200fc960ec93afef054` (2026-11-21). Do not edit it here. Its header comment states a narrower yellow rule (primary button, current-step node and a few chips and dots). That comment stays as it is, because the copy must stay identical to the source; this document takes precedence over it. To resync, copy the file over it; nothing else changes. The file is served at `/static/tokens.css` (entry in `STATIC_FILES`) and linked before `styles.css`.

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
- Yellow (`--primary`) goes on three things only: the primary action, the current-step marker and the current selection. Red only for danger. This is rule 8 in [ui-quality.md](ui-quality.md); the owner decided it on 2026-11-23 (decision 14).
- Current selection: a solid `--primary` fill with `--on-primary` text, plus a second sign that is not colour (weight, icon or text) and the existing `aria` attribute (for example `aria-selected` or `aria-current`). Not a yellow border alone: it is about 1.5:1 against white on light. Never a tint with a border of the same hue, and never a thick border on one side.
- Focus ring: `--focus` is a focus indicator and is exempt from the accent limit, including where it is yellow in dark. A ticket that says the focus style stays unchanged means the rule on main after the token pull request.
- Themes: contrast and no-colour-alone checks cover both the light block (`:root`) and the dark block of `tokens.css`.
- Text never sits on a bare alpha layer; use the opaque surface tokens.

## Light and dark

Dark is the primary design. `tokens.css` defines the light theme in `:root` and overrides it inside a `prefers-color-scheme: dark` media block, so the operating system colour scheme decides. There is no in-page switch.

## Status of the page

Where the page still marks the current selection in a neutral colour, it does not yet follow the selection rule above. The page follows in ticket work; this document records the rule, not finished work.
