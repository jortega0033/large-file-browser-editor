# Design tokens

The page uses the Pipenzo "Flow look" tokens: black page, Flow-style alpha layers, one accent (Pipenzo yellow `#FECE02`), red only for danger. Owner decision 13 in [owner-decisions.md](owner-decisions.md).

## Source and resync

`line_editor/static/tokens.css` is a byte-for-byte copy of `extension/sidepanel/tokens.css` in `jortega0033/clip-to-reel-studio` at commit `a13378ce73e5b27213c9a200fc960ec93afef054` (2026-11-21). Do not edit it here. To resync, copy the file over it; nothing else changes. The file is served at `/static/tokens.css` (entry in `STATIC_FILES`) and linked before `styles.css`.

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
- Yellow only on the primary action and the current-step marker (and the focus ring in dark). Red only for danger.
- Text never sits on a bare alpha layer; use the opaque surface tokens.

## Light and dark

Dark is the primary design. `tokens.css` defines the light theme in `:root` and overrides it inside a `prefers-color-scheme: dark` media block, so the operating system colour scheme decides. There is no in-page switch.
