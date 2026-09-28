# prompts/

Versioned interviewer/evaluator/planner prompts. Never embed prompt text in application
code - the LLM gateway loads prompts from here by name + version (see CLAUDE.md decision 2,
docs/PRD.md section 22).

Each prompt file records: name, version, owner, purpose, model constraints.
