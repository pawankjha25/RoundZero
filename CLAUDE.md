# Round Zero

AI-powered full-loop interview simulator (Staff/Principal ML/AI engineering wedge). Full PRD: `docs/PRD.md`.

## Architecture decisions to preserve

1. Modular monolith, not microservices (yet). `planner`, `interview`, `interviewers`, `evaluation`, `debrief`, `improvement` are modules inside one Python backend (`src/roundzero/`), not separate services. Keep interfaces clean so any module can be extracted into its own service later without a rewrite.
2. Prompts, rubrics, and role/level/company/loop definitions are configuration, not code. They live under `configs/`, `prompts/`, `rubrics/` as versioned YAML/Markdown, never hardcoded in route handlers or agent classes. Adding a new loop (e.g. Principal ML Infra) should mean adding a config file, not touching orchestration code.
3. `evals/` is first-class production code, not an afterthought. Every prompt/model/rubric change is regression-tested against golden interview transcripts before it ships. For an AI interview product, interviewer realism and evaluator trustworthiness are the hard problem - treat them accordingly.
4. Interviewing and evaluation are separate concerns - the interviewer agent never scores its own round (PRD section 10).
5. Build one full vertical slice before widening: Principal ML Engineer -> ML System Design round -> adaptive interview -> evidence extraction -> evaluation -> report. Once that works end-to-end, it becomes the template for the other round types.

## Layout

- `src/roundzero/` - core Python package (domain contracts, planner, interview orchestration, interviewers, evaluation, llm gateway, storage). `src/` layout to avoid `roundzero/roundzero` import ambiguity.
- `apps/api/` - FastAPI BFF exposing `src/roundzero/` over HTTP.
- `apps/web/` - Next.js candidate/admin UI.
- `configs/` - role, level, company, and loop definitions (YAML).
- `prompts/` - versioned interviewer/evaluator/planner prompts.
- `rubrics/` - versioned competency rubrics per round type.
- `evals/` - golden transcripts, interviewer/evaluator/debrief regression suites, adversarial tests.
- `specs/` - spec-driven development: one numbered folder per feature (`spec.md` = what/why, `plan.md` = technical approach, `tasks.md` = checklist). Write/agree the spec before implementing.
- `.claude/skills/` - repeatable procedures (e.g. `add-interview-round` encodes PRD Appendix C's Definition of Done).
- `docs/PRD.md` - full product/technical requirements doc.

## Working conventions

- No prompts embedded in route handlers or Python string literals inside agent code - always load from `prompts/`.
- No rubric prose inside prompts - rubrics are their own versioned YAML in `rubrics/`.
- Every agent prompt/config records: name, semantic version, owner, purpose, model constraints (PRD section 22).
- Evaluator conclusions must cite persisted evidence IDs - no unsupported scores (PRD section 21.3, section 26).
- Session events are append-only; state should be rebuildable from event history (PRD section 9).
