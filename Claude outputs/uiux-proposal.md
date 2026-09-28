# Round Zero vs. interviewing.io: UI/UX comparison and proposal

## TL;DR

Yes — font size is a real, measurable problem, not a subjective impression. interviewing.io's actual body text renders at **18px**. Round Zero's actual body text — in the screens that matter most, the interview report and the coding problem statement — renders at **14px, and in places 12px**. That's not a style choice difference; it's 25-33% smaller text carrying the most important content in the product. Everything else (color system, contrast, dark mode) is already in good shape and shouldn't be touched.

## What I actually looked at

I opened interviewing.io in a browser and read real computed CSS values off the live page (not a guess from screenshots), and I opened Google-authenticated in that same browser session, which happened to already be signed in — it landed on the real logged-in dashboard, not just the marketing page. I did not submit or change anything there. In parallel, I grepped Round Zero's own `apps/web` source for every `text-*` Tailwind class in use, so the Round Zero side of this comparison is exact counts from the real codebase, not a vibe.

## What interviewing.io does that reads as "better"

**Body text is large.** The homepage's actual paragraph copy computes to `font-size: 18px; line-height: 22px`. Their base document font-size is the standard 16px, but they don't write body copy at the base size — they bump it up a notch, and that alone is most of why the page feels easy to read at a glance instead of like fine print.

**Headings have personality without hurting legibility.** They use a custom rounded display typeface ("Blender") for H1s at 30px with slightly tightened tracking (-0.75px), while all UI chrome (buttons, nav, body) stays in Inter — the same font family Round Zero already uses. So the "premium" feeling isn't coming from an exotic font system, it's one accent display face on top of a normal UI font.

**High contrast, confident color use.** Black text, white background, one saturated accent color (a warm yellow/gold) used sparingly but boldly for every primary CTA. Buttons are large, rounded-pill shaped, with generous internal padding — they read as "the one obvious next action," not one option among several similar-looking controls.

**The in-product dashboard (the authenticated view, not just the marketing site) carries the same discipline**: a bold ~28-32px black heading in modals, form fields with real height and breathing room, one primary blue button per screen, generous padding throughout. The visual confidence isn't just a marketing-page veneer — it continues into the actual product.

## What Round Zero's own code says about itself

Round Zero's `globals.css` design-token system (from the specs/003 premium redesign pass) is genuinely solid: a restrained neutral palette, one accent color, a semantic status scale (strong-positive → strong-concern) for scores, and WCAG-audited border contrast with a documented audit trail. That part doesn't need rework — it's the typography and density that don't match the quality of that color system.

There is no defined type scale. Unlike colors (which have named tokens: `--accent`, `--status-concern`, etc.), font sizes are picked ad hoc, per component, from Tailwind's raw utility classes. Counting every use across `app/` and `components/`:

| Class | Actual size | Count in codebase |
|---|---|---|
| `text-xs` | 12px | 82 |
| `text-sm` | 14px | 141 |
| `text-base` | 16px | 4 |
| `text-lg` | 18px | 2 |
| `text-xl` | 20px | 10 |
| `text-2xl` | 24px | 3 |

223 uses of 12-14px text against 19 uses of 16px or larger. The two screens where this shows up worst:

- **The interview report page** (`app/reports/[roundId]/page.tsx`) — the actual payoff screen of the whole product, where the evaluator's written feedback, strengths/weaknesses, and improvement plan live — renders almost all of that prose at `text-sm` (14px), including the section headers ("Dimension-by-dimension", "Improvement plan"), which are also 14px, so headers barely stand out from body text at all.
- **The coding workspace problem panel** (just rewritten this session) — the actual problem statement the candidate has to solve — renders at `text-xs` (12px). This one's on me; it inherited an existing pattern from the placeholder I generalized rather than being a new decision, but it's exactly the kind of case this audit is meant to catch.

By contrast, the one place Round Zero already gets this right is the *live* interviewer turn in the chat panel (`text-base`, `leading-relaxed`) — proof the team already knows what good body text looks like, it just didn't get applied consistently everywhere else.

Spacing and corner-rounding are moderate but not a real problem: `rounded-md` (6px) dominates (58 uses) with some `rounded-lg` (25), nothing close to interviewing.io's larger pill buttons — but this is a much smaller gap than the font-size one and lower priority to fix.

## Proposal, prioritized

**P0 — stop the type scale from being ad hoc.** Add a real type-scale convention next to the existing color tokens in `globals.css`, the same way `--accent`/`--status-*` already work: something like `--text-body: 1rem` (16px body copy, matching interviewing.io's decision to not undersize the content people actually read), `--text-label: 0.8125rem` (13px, reserved for uppercase eyebrow labels/badges — the one legitimate use of small text), and a documented rule: **`text-xs` is for short all-caps labels and badges only, never for prose or feedback content.**

**P0 — fix the two worst offenders directly.** Bump the report page's evaluator narrative, strengths/weaknesses, and improvement-plan text from `text-sm` to `text-base`, and its section headers to something visually distinct from body text (currently they're the same size). Bump the coding problem statement from `text-xs` to `text-base` to match how the report should read once P0 lands.

**P1 — line-height follow-through.** Only 9 uses of `leading-relaxed` exist in the whole app; most `text-sm` blocks use Tailwind's tight default line-height for that size. Once body copy moves to 16px, pair it with `leading-relaxed` consistently, the way the chat panel's live turn already does.

**P1 — make primary CTAs bolder.** Not a rebuild — Round Zero's button system is fine — but interviewing.io's primary actions ("Continue with Google", "Let's go") are visually unmissable: larger, more internal padding, unambiguous single focal point per screen. Worth doing the same for Round Zero's real equivalents (Start interview, Submit round) specifically, not every button in the app.

**P2 — corner radius / spacing nudge.** Lowest priority. Current `rounded-md`/`rounded-lg` convention is coherent and not actually a usability problem, just a slightly more "dense SaaS dashboard" feel than interviewing.io's rounder, airier one. Only worth touching after P0/P1 land, if at all.

## What I'd suggest next

This is a proposal, not a change — nothing here has been implemented. If it looks right, I'd suggest starting with the P0 items only (the type-scale convention plus the report page and coding problem statement fixes), since those are the two screens carrying the most important content in the product and the fix is mechanical once the convention exists. I can do that as a focused pass and show you a diff before anything ships, the same way we've been working.
