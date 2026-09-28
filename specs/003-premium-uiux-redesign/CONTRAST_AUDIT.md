# Design token contrast audit

Ad-hoc audit prompted by a user question ("are we using the right font/color?")
plus explicit feedback that borders felt too faint. Computed WCAG 2.1 contrast
ratios for every token pair in `apps/web/app/globals.css` (OKLCH -> linear
sRGB -> relative luminance -> contrast ratio, standard formula). Two real
issues found and fixed; documented here so the next palette change doesn't
regress them.

## Method

For each token pair, contrast ratio = (L1 + 0.05) / (L2 + 0.05) where L1 >= L2
are relative luminances. WCAG 2.1 targets used:

- **1.4.3 (text contrast):** >=4.5:1 for normal text, >=3:1 for large text
  (>=18pt, or >=14pt bold). Every status badge in this app renders at
  `text-xs` (12px) - normal text, so status text needs >=4.5:1 against its
  own background, not the relaxed 3:1.
- **1.4.11 (non-text contrast):** >=3:1 for the visual boundary of an
  interactive UI component (inputs, buttons, selects) against the adjacent
  background. `--border` is used for exactly this throughout the app
  (`AIInterviewerPanel`'s reply input, every `<select>`/`<input>` on
  `/setup`, `CodingWorkspace`'s language picker, etc.), not just decorative
  dividers, so it's held to the component-boundary bar.

## Findings and fixes

| Token pair | Before | After | Bar | Status |
|---|---|---|---|---|
| `--border` / `--background` (light) | 1.33:1 | 3.07:1 | 3:1 | fixed |
| `--border-strong` / `--background` (light) | 1.84:1 | 5.91:1 | 3:1 | fixed |
| `--border` / `--background` (dark) | 1.42:1 | 3.23:1 | 3:1 | fixed |
| `--border-strong` / `--background` (dark) | 2.11:1 | 4.92:1 | 3:1 | fixed |
| `--status-positive` / `--status-positive-bg` (light) | 4.11:1 | 5.04:1 | 4.5:1 | fixed |
| `--status-neutral` / `--status-neutral-bg` (light) | 4.38:1 | 5.41:1 | 4.5:1 | fixed |
| `--status-concern` / `--status-concern-bg` (light) | 4.29:1 | 5.54:1 | 4.5:1 | fixed |
| `--status-strong-positive` / its bg (light) | 4.83:1 | - | 4.5:1 | already passing |
| `--status-strong-concern` / its bg (light) | 5.19:1 | - | 4.5:1 | already passing |
| all 5 status pairs (dark) | 4.76-6.15:1 | - | 4.5:1 | already passing |
| `--foreground` / `--background` (both modes) | 16.8-18.2:1 | - | 4.5:1 | already passing |
| `--muted-foreground` / `--background`/`--surface` (both modes) | 5.8-6.8:1 | - | 4.5:1 | already passing |
| `--accent-foreground` / `--accent` (button text, both modes) | 8.8:1 | - | 4.5:1 | already passing |

Fix applied by darkening the light-mode `--border`/`--border-strong`
lightness (0.9 -> 0.66, 0.8 -> 0.5) and brightening the dark-mode pair
(0.3 -> 0.5, 0.4 -> 0.6) - same neutral gray (chroma 0), just moved to a
lightness that actually reads as a visible edge. Status text darkened
(0.55/0.55/0.56 -> 0.5 lightness, same hue/chroma) rather than lightening
the badge backgrounds, so the soft-background look of the badges is
unchanged.

## Not a contrast issue, flagged separately

- **Status hue progression (green 155 deg -> olive 80 deg -> orange 40 deg ->
  red 25 deg)** sits on the axis that's hardest to distinguish under
  red-green color blindness (~8% of men). Mitigated by the spec's own rule
  that every status token is always paired with a text label
  (`StatusBadge` never renders color alone) - the label carries the primary
  signal, color is reinforcement. No change made; flagged for awareness.
- **Typography** is a system-font stack (`-apple-system, "Segoe UI", Inter,
  Roboto, ...`), not a self-hosted webfont - a pragmatic choice made when
  `next/font/google` couldn't reach fonts.googleapis.com during a build in
  this dev environment, not a deliberate brand decision. It's a legitimate,
  fast, zero-dependency professional choice (GitHub, Stripe Dashboard use
  similar stacks), but it means the product's type doesn't have a single
  consistent identity across OSes the way a self-hosted Inter/Geist would.
  Left as-is; self-hosting a webfont (shipping the font file directly
  instead of fetching from Google at build time) is a straightforward
  upgrade if a more distinctive typographic identity is wanted later.
