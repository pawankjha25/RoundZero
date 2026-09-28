"""
Counterfactual direction, HYPOTHETICAL: the flip rewrite (specs/005).

For the top gaps (diagnosis causes, highest leave-one-out impact first):

1. Propose - a writer model (GPT-5 mini) writes the smallest addition to ONE
   answer that meets the missed criterion (prompts/world_model/flip_rewrite/v1.md).
2. Evaluate - the extractor re-scores the edited answer blind: it sees a
   question and an answer, nothing else, and is a different vendor from the
   writer, so the two cannot collude.
3. Predict - replay the belief with only that answer's evidence swapped out,
   holding every other answer fixed.

The result is always labelled hypothetical and never used as a training label.
It deliberately projects only the final outcome - it does not invent the
follow-up turns that would have come after a different answer.
"""
from __future__ import annotations

import json
import logging
import os

from roundzero.llm.gateway import LLMGateway
from roundzero.worldmodel import belief as bl
from roundzero.worldmodel import config
from roundzero.worldmodel.diagnosis import answer_turns, probed_dims_for, question_for
from roundzero.worldmodel.extractor import Extractor
from roundzero.worldmodel.models import CompetencyDiagnosis, Evidence, FlipRewrite

logger = logging.getLogger("roundzero.worldmodel.flip")

MAX_ADDED_WORDS = 60
MAX_REWRITES = 3


class FlipWriter:
    def __init__(self, llm: LLMGateway, prompt_version: str = "v1", model_name: str = "gpt-5-mini"):
        self._llm = llm
        self._system = config.load_wm_prompt("flip_rewrite", prompt_version)
        self.version = f"{model_name}-flip-{prompt_version}"

    def write(self, *, competency: str, criterion: str, polarity: str, question: str, answer: str) -> str:
        meta = config.competency(competency)
        problem = "got it wrong" if polarity == "contradicted" else "did not address it"
        user = (
            f"Competency: {meta['label']} - {meta['measures']}\n"
            f"What separates Staff from Senior: {meta['staff_vs_senior']}\n"
            f"Missed criterion: {criterion} (the answer {problem})\n\n"
            f"Interviewer question:\n{question}\n\n"
            f"Candidate's original answer:\n{answer}\n\n"
            f"Return the JSON object described in your instructions."
        )
        raw = self._llm.complete_json(system=self._system, user_message=user, max_tokens=1500)
        added = str(json.loads(raw).get("added_text", "")).strip()
        words = added.split()
        if len(words) > MAX_ADDED_WORDS:
            added = " ".join(words[:MAX_ADDED_WORDS])
        return added


def get_flip_writer() -> FlipWriter | None:
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    from roundzero.llm.providers.openai_provider import OpenAIGateway

    return FlipWriter(OpenAIGateway())


def project(
    *,
    round_type: str,
    target_level: str | None,
    turns: list[dict],
    evidence: list[Evidence],
    turn_index: int,
    replacement: list[Evidence],
) -> tuple[dict[str, float], dict[str, int]]:
    """Final expected level and mode per competency with one answer's evidence
    replaced - shared by flip and retry."""
    comps = config.round_competencies(round_type)
    edited = [e for e in evidence if e.turn_index != turn_index] + replacement
    final = bl.final_belief(target_level, comps, answer_turns(turns), edited)
    return ({c: round(final.expected(c), 4) for c in comps}, {c: final.mode(c) for c in comps})


def generate_rewrites(
    *,
    round_type: str,
    target_level: str | None,
    turns: list[dict],
    evidence: list[Evidence],
    diagnoses: list[CompetencyDiagnosis],
    writer: FlipWriter,
    scorer: Extractor,
    max_rewrites: int = MAX_REWRITES,
) -> list[FlipRewrite]:
    comps = config.round_competencies(round_type)
    current = bl.final_belief(target_level, comps, answer_turns(turns), evidence)
    text_by_turn = {t["turn_index"]: t["text"] for t in turns}

    candidates = [(d, d.causes[0]) for d in diagnoses if not d.abstained and d.causes]
    candidates.sort(key=lambda dc: dc[1].impact, reverse=True)

    out: list[FlipRewrite] = []
    for diag, cause in candidates[:max_rewrites]:
        turn = cause.turn_index
        question = question_for(turns, turn)
        original = text_by_turn.get(turn, "")
        try:
            added = writer.write(
                competency=diag.competency,
                criterion=cause.evidence.criterion,
                polarity=cause.evidence.polarity,
                question=question,
                answer=original,
            )
        except Exception:
            logger.exception("flip writer failed for turn %s", turn)
            continue
        if not added:
            continue
        edited_answer = f"{original.rstrip()} {added}"
        rescored = scorer.extract(
            round_type=round_type,
            question=question,
            answer=edited_answer,
            turn_index=turn,
            probed_dims=probed_dims_for(turns, turn),
        )
        means, modes = project(round_type=round_type, target_level=target_level, turns=turns,
                               evidence=evidence, turn_index=turn, replacement=rescored)
        comp = diag.competency
        cur_mode = current.mode(comp)
        out.append(
            FlipRewrite(
                competency=comp,
                turn_index=turn,
                criterion=cause.evidence.criterion,
                polarity=cause.evidence.polarity,
                added_text=added,
                edited_answer=edited_answer,
                current_mean=round(current.expected(comp), 4),
                current_level=config.level_keys()[cur_mode],
                projected_mean=means[comp],
                projected_level=config.level_keys()[modes[comp]],
                flipped=modes[comp] > cur_mode,
                rescore_evidence=rescored,
                writer_version=writer.version,
                scorer_version=scorer.version,
            )
        )
    return out
