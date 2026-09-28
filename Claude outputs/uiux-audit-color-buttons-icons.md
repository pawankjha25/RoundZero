# Round Zero UX audit: color, buttons, icons/images

## TL;DR

Genuinely good news on two of the three things you asked about. Color contrast isn't just "probably fine" anymore — I computed real WCAG contrast ratios for every text/background pair in both light and dark mode, and everything passes (most by a wide margin). Icons are hand-crafted, consistent, and the absence of gifs/images is a deliberate, good choice, not a gap. Buttons are where I found real (small) inconsistencies worth a decision from you — nothing broken, but two things drifted after the P0/P1 pass.

## What I actually checked

Not a visual impression this time — I pulled the exact oklch color values out of `globals.css`, converted them to sRGB, and computed real WCAG contrast ratios programmatically for light and dark mode. Then I went through every `<button>` in the codebase (28 of them) and diffed their classNames side by side. Then I opened your real, already-running app in your actual Chrome (dashboard → loop detail → report page → toggled dark mode → Practice → Interview Intel → Admin) and checked the results live, including tabbing through the report page with the keyboard to see what focus states actually look like.

## Color contrast: no problems found

| Pair | Light | Dark | WCAG floor |
|---|---|---|---|
| Body text on background | 18.1:1 | 16.8:1 | 4.5:1 |
| Muted text on background | 6.7:1 | 6.3:1 | 4.5:1 |
| Accent (links/CTAs) on background | 9.2:1 | 8.7:1 | 4.5:1 |
| Button text on accent fill | 8.8:1 | 8.8:1 | 4.5:1 |
| Border on background (non-text) | 3.1:1 | 3.2:1 | 3:1 |
| Every status badge's text on its own pill background (all 5 tones) | 4.8–5.6:1 | 4.8–6.2:1 | 4.5:1 |

Every single pair I checked clears its bar, and most clear the stricter 7:1 AAA bar too. The `StatusBadge` component also already does the right thing structurally — it always pairs color with a text label ("NO HIRE", "1/4"), never color alone, so it doesn't depend on contrast perception at all for meaning. This matches what the code's own `CONTRAST_AUDIT.md` claimed; I just verified it with real numbers instead of taking the comment's word for it. **No action needed here.**

## Icons and images/gifs: also no problems — and no gifs is the right call

There are zero image or gif files anywhere in the app (`public/` is empty of them), no `<img>`/`next/image` usage, and no icon library dependency. Every icon you see — the little glyphs next to "ML System Design," "Coding," etc. in the loop planner — is a hand-authored inline SVG in `RoundTypeIcon.tsx`: 7 icons, one per round type, all sharing the same 1.75px stroke weight and 24×24 grid, all using `currentColor` so they automatically re-theme in dark mode with zero extra code. They're genuinely well made — distinct, simple silhouettes (a fork/split for ML system design, angle brackets for coding, a hierarchy of bars for backend design) that read clearly at 18px.

The "processing" states are CSS animations, not gifs either: a three-dot bounce while waiting for the interviewer's reply, and a staged checklist with a pulsing dot for "active" step in `AIProcessState` — the code comment there explicitly says "never a giant spinner, never a faked progress percentage." That's a real UX opinion, correctly executed, and it's better than a gif would be here: gifs don't re-theme for dark mode, don't scale for retina displays, and read as cheap. **Nothing to fix; if anything this is worth knowing you already got right.**

One small, genuine inconsistency I found while in this code: `ThemeToggle.tsx`, `TypingIndicator.tsx`, and `AIProcessState.tsx` use hardcoded Tailwind grays (`neutral-300`, `neutral-400`, `neutral-950`, etc.) instead of your own `border`/`muted-foreground`/`foreground` tokens that every other component uses. It doesn't look wrong today — the raw values happen to be close to the token values — but it means these three won't move if the palette is ever retuned again (which already happened once, per the border-contrast fix noted in the CSS comments). Low priority, easy fix, flagging so it doesn't surprise you later.

## Buttons: mostly consistent, two real things to decide on

The small utility buttons (Retry, Delete, Close drawer, End Round, disconnect voice, admin row actions) are impressively consistent already: `text-xs`, `px-2`–`2.5`, `py-1`, `rounded-md`, bordered with a `hover:border-border-strong` or tone-colored hover. I didn't find a single stray one-off in that tier.

**1. The P0/P1 pass created a new two-tier split among primary buttons.** "Start interview" (Setup page) and the report page's "Retry Evaluation" got the bold treatment (`px-5 py-2.5/3`, `text-base font-semibold`, `rounded-lg`) — that was the deliberate P1 scope. But other buttons that are *also* the one primary action on their own page didn't get it: Profile's "Save profile," "Create loop," the login page's magic-link submit, and "Retry" on the end-of-interview error screen are all still the smaller `px-4 py-2 text-sm font-medium rounded-md`. Before P1 there was one consistent small size everywhere; now there are two sizes, and which button got upgraded looks a little arbitrary from a user's point of view (why is "Start interview" big and bold but "Save profile" isn't, when both are the only button on their screen?). This is a judgment call, not a bug — I can either extend the same bold treatment to that same tier of "single primary action per page" buttons, or leave it split. Want me to do the extension?

**2. No custom focus styling on any button.** Every text input gets a deliberate `focus:border-accent`, but none of the 28 `<button>` elements do — they rely entirely on the browser's default outline. I verified live by tabbing through the report page: it's not invisible (Chrome's default blue ring shows up fine on the theme toggle and the dimension cards), so nothing is actually broken for keyboard users today. But it's undesigned — that blue doesn't match your indigo accent, and default outlines aren't guaranteed to survive future CSS resets. Minor, but genuine "not quite perfect" polish if that's the bar you're going for.

Everything else I checked live — the report page in both themes, Practice, Interview Intel, Admin — held up well: labels are legible, dark mode has no washed-out or clipped text, empty states ("Not enough reports yet," "Coming soon" practice cards) look intentional rather than broken.

One unrelated, very low-priority thing I noticed while navigating: hitting a URL that doesn't exist lands on Next.js's stock 404 page (white background, unstyled, ignores dark mode). Nothing in your actual nav points there, so it's not user-facing today, but worth knowing if you ever link out to something that could 404.

## My honest read

You asked me to actually check rather than just say things are good — so: they mostly are. Color and iconography are in genuinely strong shape, backed by real measurements this time, not vibes. The only two things I'd call real findings are the primary-button size split (created by our own P1 fix, so worth closing the loop on) and the three raw-color files. Both are small, both are safe to leave alone if you'd rather not touch anything right now, and both are quick if you want them done.
