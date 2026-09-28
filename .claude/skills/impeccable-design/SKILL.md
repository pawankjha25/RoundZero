---
name: impeccable-design
description: Design-taste checklist for any UI work on Round Zero's frontend (apps/web) - use when building, redesigning, or reviewing a page or component, to avoid generic "AI-generated" UI patterns and keep new UI consistent with the existing token system. Adapted from the open-source Impeccable design skill (github.com/pbakaus/impeccable).
---

# Round Zero design taste

Before touching UI, read `PRODUCT.md` and `DESIGN.md` at the repo root - they
capture who Round Zero is for, the product register (Operate, not
marketing), and the real token system already in `apps/web/app/globals.css`.
Don't rebuild those from scratch per-page; reuse the tokens and patterns
already established.

## Verify (run on anything you build)

- **Contrast:** body/placeholder text >=4.5:1, large text >=3:1. Use
  `text-muted-foreground` for secondary text, never a raw lighter gray.
- **Spacing:** tight groups, generous separation between sections, more
  space above a heading than below it.
- **Type:** use `text-body`/`text-label` for the roles DESIGN.md defines,
  plain `text-sm`/`text-xs` elsewhere. Body measure ~65-75ch for prose.
- **States:** every interactive control needs hover, focus, disabled, and
  (where relevant) loading and error states - not just the happy path.
- **Copy:** name the actual action ("Delete area", not "Remove"+"Delete
  area" meaning different things); errors name the problem and the
  recovery.

## Refuse (Round Zero specifically has none of these today - keep it that way)

- Gradient text, glassmorphism/decorative `backdrop-blur`, hard-offset
  block shadows (`shadow-[4px_4px_0...]`).
- A kicker/eyebrow label above a heading; numbered section markers
  (01/02/03) with no real informational sequence.
- Identical icon+heading+text card grids as a page's default structure.
- Emoji or unicode glyphs standing in for an icon - icons are hand-authored
  inline SVG (`components/RoundTypeIcon.tsx` is the reference: one stroke
  weight, `currentColor`).
- A modal for a task that doesn't need interruption or protected focus.
- A new primary button hand-rolling `bg-accent`/`rounded-lg` classes
  instead of importing `components/ui/Button.tsx` (see DESIGN.md
  Components > Buttons).

## Operate-mode notes (this product's register)

- One font family throughout; no display face in UI labels/buttons/data.
- Fixed rem type scale, not fluid/`clamp()` - this is task UI, not a
  marketing page.
- Accent color for primary actions, current selection, and state
  indicators only - never decoration.
- Motion (where used) is 150-250ms, conveys state only, never a page-load
  choreography sequence.
- Consistent affordances across screens: if a button/control looks
  different on two pages for the same role, one of them is wrong - check
  DESIGN.md before introducing a new pattern.

## Known open items (as of the last design pass)

- `components/ui/Button.tsx` covers page-level primary actions only. Two
  things it deliberately does not cover yet, and both still hand-roll
  classes: compact/secondary action buttons (the smaller `px-3 py-1.5`
  buttons inside cards and lists - Progress page, Loops list, the Coding
  round's Run button, the chat Send button) and external `target="_blank"`
  links (Progress page's Substack/consultancy links, which sit next to a
  non-accent "Join class" button and a disabled-looking "Coming soon" span
  as a deliberate 3-state row - redesigning just the accent one would make
  that row worse, not better; this needs its own look at all three states
  together, not a mechanical swap).
- No shared `Input`/form-field component yet - text inputs, selects, and
  textareas are still styled inline per page.
