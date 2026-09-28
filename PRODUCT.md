# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Candidates preparing for Staff/Principal ML and AI engineering interview loops (ML system design, coding, ML depth, and adjacent rounds). They are senior, technical, time-pressed, and already fluent in professional software/product UI (Linear, Notion, Stripe-caliber tools) - they will notice generic or inconsistent UI immediately and it will read as a signal about whether the interview feedback itself can be trusted.

## Product Purpose

Round Zero gives candidates a realistic, adaptive, full-loop interview simulator with evidence-backed feedback and a prioritized improvement plan, instead of a single generic mock interview. Success is measured by whether a candidate trusts the simulated interview enough to treat the feedback as real signal, and returns to practice again (Prep Plans, round history, progress tracking) rather than treating it as a one-off toy.

## Positioning

A serious practice tool, not a marketing surface. The product register throughout is **Operate**: the interface exists to get the candidate through a task (pick a round, have the interview, read the report, plan the next attempt) with as little friction and as much trustworthy density as possible. Nothing on these screens is trying to persuade a visitor to sign up - it's trying to not get in a candidate's way mid-interview.

## Operating Context

Next.js 16 (App Router) + React 19 + Tailwind v4 frontend (`apps/web`), FastAPI backend (`apps/api`), SQLite for local dev. Monaco (coding round editor), Excalidraw (system-design whiteboard), LiveKit (voice mode) are embedded, not chrome the team owns - their own UI does not need to match the token system, but everything Round Zero draws around them does. Self-hosted Inter Variable is the only font; no external font-loading network dependency.

## Capabilities and Constraints

- Three real round types today: `ml_system_design`, `coding`, `ml_depth` - each with its own interviewer prompt, and Coding additionally with a real code editor + test runner, not just chat.
- A deliberate semantic-token design system already exists (`apps/web/app/globals.css`, spec `003-premium-uiux-redesign`): oklch color tokens, a two-size named type scale (`text-body`/`text-label`), and a 5-step status scale (`status-strong-positive` -> `status-strong-concern`) used everywhere a signal is shown (round result, evaluator claims, connection state) - always paired with a label/icon, never color alone.
- `components/ui/Button.tsx` is the shared primary-action button/link (added to fix the radius/padding drift a design pass found). No shared `Input` component yet.
- No external icon library - icons are hand-authored inline SVG (`components/RoundTypeIcon.tsx`), one consistent stroke weight. Keep it that way; do not introduce an icon font/library.
- Dark mode is class-based (`next-themes` toggling `.dark` on `<html>`), not OS-preference-only - explicit user toggle wins.

## Brand Commitments

Restrained, professional, evidence-first. Round Zero speaks the way a serious technical assessment tool speaks: precise, calm, never hyped. Copy states facts and evidence ("Tried 2x - last 65% READY") rather than encouragement-speak ("You're crushing it!"). The tone is **credible** (claims are backed by evidence shown in the UI, never just asserted), **calm** (status colors and motion signal state, they don't celebrate or alarm), and **dense-but-legible** (candidates are senior engineers who want information, not marketing air).

Three-word personality: **credible, calm, precise**.

Avoid:
- **Generic AI-product visual tells**: gradient text, glassmorphism, glowing/neon accents, purple-blue gradient hero blocks. (None currently present - keep it that way.)
- **SaaS landing-page patterns leaking into product screens**: hero-metric tiles, identical icon+heading+text card grids, sparkline decoration, kicker/eyebrow labels above headings.
- **Encouragement-speak copy** that isn't backed by evidence shown on screen.
- **Reinvented standard affordances** - use native form controls, native `<dialog>`/modal semantics, standard dropdowns; candidates should never have to learn Round Zero's own invented widget behavior.

## Evidence on Hand

- `apps/web/app/globals.css` documents the token system and its own revision history (contrast fixes, type-scale audit vs. interviewing.io) in comments - read it before touching color or type.
- `specs/003-premium-uiux-redesign/` is the spec that produced the current design foundation, including `CONTRAST_AUDIT.md` with the WCAG contrast measurements behind the current border/text tokens.
- `components/RoundTypeIcon.tsx` is the reference for how icons should be authored (inline SVG, one stroke weight, `currentColor`).
- No user research repository or quantified UX metrics exist yet - do not invent testimonials, benchmarks, or usage stats.

## Product Principles

1. **Evidence over assertion.** Every claim the UI makes about a candidate's performance is backed by something visible (a transcript excerpt, a test result, a rubric line) - never a bare score with no trail.
2. **Consistency over novelty.** A candidate mid-interview should never have to figure out a new widget. Reuse the existing token system and component patterns before inventing new ones.
3. **Calm under evaluation.** This is a high-stress moment for the user (practicing for a real interview). Motion and color signal state changes; neither should add anxiety or spectacle.
4. **Dense, not cluttered.** Senior engineers want real information (round history, coverage maps, evidence) - hide nothing behind decoration, but keep hierarchy legible.

## Accessibility & Inclusion

Baseline: WCAG 2.1 AA. Key commitments already encoded in the token system:
- Every status/border/text token has a measured contrast ratio (see `specs/003-premium-uiux-redesign/CONTRAST_AUDIT.md`); don't introduce a new color without checking it the same way.
- Status is never color-alone - always paired with a label or icon.
- `prefers-reduced-motion` should be respected for the typewriter reveal and any future motion.
- Semantic HTML first; the coding editor (Monaco) and whiteboard (Excalidraw) carry their own a11y surface - don't fight it.
