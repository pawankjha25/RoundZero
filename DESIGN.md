# Design System: Round Zero

All token values below mirror `apps/web/app/globals.css` verbatim. That file is
the source of truth (and carries the full revision history in comments); if a
token changes there, update this file too.

## 1. Overview

Operate-mode product UI for a technical interview simulator. Neutral base,
one restrained indigo accent, and a five-step semantic status scale used
everywhere a signal is shown. Modeled explicitly on Linear / Stripe / Notion
information density and restraint, not on SaaS marketing conventions. See
`PRODUCT.md` for the full brief.

## 2. Colors

### Ground and surface

| Token | Light | Dark |
|---|---|---|
| `--background` | oklch(0.995 0 0) | oklch(0.16 0 0) |
| `--surface` | oklch(1 0 0) | oklch(0.2 0 0) |
| `--muted` | oklch(0.96 0 0) | oklch(0.25 0 0) |
| `--border` | oklch(0.66 0 0) | oklch(0.5 0 0) |
| `--border-strong` | oklch(0.5 0 0) | oklch(0.6 0 0) |

### Text

| Token | Light | Dark |
|---|---|---|
| `--foreground` | oklch(0.19 0 0) | oklch(0.95 0 0) |
| `--muted-foreground` | oklch(0.35 0 0) | oklch(0.78 0 0) |

`muted-foreground` is deliberately crisp (~11:1 against background), not a
washed-out gray - perceived weight matters as much as numeric contrast (see
the dated comment in `globals.css`). Never hand-roll a lighter secondary text
color; use this token.

### Accent

| Token | Light | Dark |
|---|---|---|
| `--accent` | oklch(0.4 0.11 265) | oklch(0.75 0.11 265) |
| `--accent-foreground` | oklch(0.98 0 0) | oklch(0.15 0 0) |

One accent. Used for primary actions, active/selected states, and focus -
never for decoration. This is a restrained indigo on purpose: it must not
read as "gradient AI product" blue/purple.

### Status scale

Five-step scale, each with a text/bg pair, used for round results, evaluator
claims, and connection state. Always pair with a label or icon - color alone
is never the only signal.

`status-strong-positive` / `status-positive` / `status-neutral` /
`status-concern` / `status-strong-concern` (each with a matching `-bg`
token). `status-strong-concern` is the fixed color for every destructive
action (Delete, Remove, Delete area) - used as the resting-state text color,
not just on hover.

### Color rules

- Never introduce a raw hex/rgb color in a component. Every color is one of
  the tokens above, referenced via its Tailwind utility (`bg-accent`,
  `text-status-strong-concern`, etc).
- The Google "G" logo on the login page is the one legitimate exception
  (brand mark, must render exact official colors).
- Don't invent a new status color for a one-off case; map it onto the
  existing five-step scale.

## 3. Typography

- **One family.** Self-hosted Inter Variable everywhere - headings, body,
  labels, data, buttons. No display face. No `font-mono` outside places that
  render actual code or measured data (Monaco editor, transcripts of
  numeric/id values).
- **Fixed rem scale, not fluid.** This is product UI viewed at consistent
  DPI - no `clamp()` heading sizes.
- **Two named content sizes**, chosen by role, not by "what looks like it
  fits":
  - `text-body` (16px/26px line-height) - the floor for anything a
    candidate has to actually read: prose, feedback narratives, problem
    statements, real list content.
  - `text-label` (14px/18px line-height) - short, tracked-out
    eyebrow/badge labels only. Never prose. Pair with `text-foreground` +
    `font-semibold`, not `text-muted-foreground` + `font-medium` - size and
    tracking alone already read as "quiet"; the color shouldn't also wash
    out.
- Plain `text-xs`/`text-sm` remain fine for buttons, form inputs, and
  secondary metadata that isn't the two named roles above - this scale is
  additive, not a forced migration.

## 4. Elevation and radius

- Shadows (where used) carry a real offset and soft blur - never a
  zero-offset colored halo, never a hard `4px 4px 0` block shadow (this app
  has no neobrutalist world to earn that).
- Card radius: `rounded-lg` is the dominant convention for cards and
  primary buttons app-wide (43 uses vs. 102 `rounded-md`, mixed across
  smaller chrome). Primary CTAs specifically should standardize on
  `rounded-lg` - see Do Not below for the drift this needs to fix.
- `rounded-full` only for genuinely pill-shaped small chrome (status dots,
  badges) - never for a rectangular button.

## 5. Components

### Icons

Hand-authored inline SVG only (`components/RoundTypeIcon.tsx` is the
reference: one stroke weight, `strokeWidth="1.75"`, `currentColor`, `viewBox
"0 0 24 24"`). No icon font, no icon library dependency, no emoji standing in
for an icon.

### Buttons

`components/ui/Button.tsx` is the shared primary-action button/link -
`<Button>` for a real `<button>`, `<Button href="...">` for a Next.js
`<Link>`, both with the identical visual treatment: `rounded-lg bg-accent
text-accent-foreground hover:opacity-90 disabled:opacity-50`, a themed
`focus-visible` ring, `size="default"` (px-4 py-2, text-sm) or
`size="large"` (px-5 py-3, text-base font-semibold), and `fullWidth` for
form submits. Use it for every new page-level primary action instead of
hand-rolling the classes again - that's exactly how the app ended up with
`rounded-md`/`rounded-lg` drift before this existed. Not yet covering:
compact/secondary action buttons (smaller `px-3 py-1.5` buttons inside
cards/lists) and external `target="_blank"` links - those still need their
own design pass before a shared component makes sense for them (see Known
open items). Destructive actions (`Delete`, `Remove`, `Delete area`) stay
on `text-status-strong-concern hover:underline` at rest, not this
component - they're text links, not filled buttons.

### Status badges

Built from the status token triplets (`StatusBadge.tsx`) - always
label+color, never a bare colored dot as the only signal.

## 6. Do and Do Not

### Do

- Reference tokens by name (`bg-accent`, `text-status-concern`,
  `text-body`), never raw oklch/hex values in component code.
- Pair every status signal with a label or icon, never color alone.
- Keep icons as hand-authored inline SVG, one stroke weight.
- Give every interactive control real hover, focus, disabled, and (where
  relevant) loading states.
- Keep destructive actions (`Delete`, `Remove`, `Delete area`) in
  `text-status-strong-concern` at rest, not just on hover.
- Converge new buttons on the shared pattern in Components > Buttons above.

### Do Not

- No gradient text, no glassmorphism/decorative `backdrop-blur`, no
  hard-offset block shadows - none currently exist in the codebase; keep it
  that way.
- No emoji standing in as an icon (one legitimate exception today: the accent
  inside the "Suggest questions" button label - a flourish inside text, not a
  replacement for an icon - don't extend the pattern further).
- No kicker/eyebrow label above a heading, no numbered section markers
  (01/02/03) unless the sequence itself carries real information.
- No identical icon+heading+text card grid as a page's default structure.
- No new primary button hand-rolling classes instead of using
  `components/ui/Button.tsx`.
- No modal for a task that doesn't need interruption or protected focus.
