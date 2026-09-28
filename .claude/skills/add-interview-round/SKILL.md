---
name: add-interview-round
description: Repeatable checklist for adding a new interview round type to Round Zero (persona, rubric, prompts, evidence extraction, eval fixtures). Use when scaffolding or reviewing readiness of any round type.
---

# Add Interview Round

Source: docs/PRD.md Appendix C, "Definition of Done for an Interview Round."

## Trigger

Use this whenever adding a new round type (e.g. Coding/DSA, Backend System Design, XFN) or
reviewing whether an existing round type is actually production-ready.

## Steps (Definition of Done)

A round type is NOT done until all of the following exist:

1. Versioned interviewer persona and rubric exist (`prompts/interviewers/<round>/`, `rubrics/<round>/`)
2. At least 10 representative question/scenario seeds exist
3. Adaptive follow-up policy is defined (not a static question list)
4. Artifacts/tools required by the round are implemented (e.g. coding workspace, whiteboard/canvas)
5. Golden evaluation cases exist (`evals/golden/<round>/`)
6. Evidence extraction supports the round
7. Evaluator passes regression thresholds against the golden set
8. Candidate report renders round-specific feedback
9. Latency/cost telemetry is available for the round
10. Failure/reconnect paths are tested

## Verification

Do not mark a round type "supported" in any config or loop template until every item above
is checked. A round with a persona and rubric but no golden evals is not done - it's a demo.
