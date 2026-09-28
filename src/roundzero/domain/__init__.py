"""
Core domain objects / contracts shared across the whole system:
TargetRole, LoopPlan, RoundDefinition, SessionEvent, Rubric, EvidenceItem,
RoundEvaluation, DebriefReport. See docs/PRD.md section 37, ticket 1.

Milestone 1 implements: TargetRole, ConversationState, InterviewerInput/Output
(roundzero.domain.interview) and shared enums (roundzero.domain.enums). The rest
(SessionEvent, Rubric, EvidenceItem, RoundEvaluation, DebriefReport) land with
Milestone 2 onward.
"""
