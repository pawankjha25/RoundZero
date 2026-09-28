"""
Perceive: candidate answer -> span-cited evidence items (specs/005).

LLMExtractor (Gemini; Flash-Lite intended via ROUNDZERO_EXTRACTOR_MODEL) is the
real path. RuleBasedExtractor is the honest no-key fallback: it only knows which
dimensions the interviewer was probing (the previous interviewer turn's
competency_tags) and how substantive the answer was, so it emits low-strength
items and the belief barely moves - it never pretends to judge content.

Both run the same validation (the unsupported-claim guard): unknown dimensions
are dropped, `demonstrated`/`contradicted` items must quote a verbatim span from
the answer, and `absent` is only allowed for dimensions the question probed.
The extractor never sees whether an answer is original, a flip rewrite, or a
retry - which is what makes it usable as the blind re-scorer too.
"""
from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod

from roundzero.evaluation.rubric_loader import load_rubric
from roundzero.llm.gateway import LLMGateway
from roundzero.worldmodel import config
from roundzero.worldmodel.models import Evidence

logger = logging.getLogger("roundzero.worldmodel.extractor")

EXTRACTOR_MODEL_ENV_VAR = "ROUNDZERO_EXTRACTOR_MODEL"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def span_in_answer(span: str | None, answer: str) -> bool:
    return bool(span) and _norm(span) in _norm(answer)


class Extractor(ABC):
    version: str = "base"

    @abstractmethod
    def _raw_items(self, *, round_type: str, question: str, answer: str, probed_dims: list[str]) -> list[dict]:
        raise NotImplementedError

    def extract(
        self,
        *,
        round_type: str,
        question: str,
        answer: str,
        turn_index: int,
        probed_dims: list[str] | None = None,
    ) -> list[Evidence]:
        probed = list(probed_dims or [])
        raw = self._raw_items(round_type=round_type, question=question, answer=answer, probed_dims=probed)
        return validate_items(raw, round_type=round_type, answer=answer, turn_index=turn_index,
                              probed_dims=probed, version=self.version)


def validate_items(
    raw: list[dict],
    *,
    round_type: str,
    answer: str,
    turn_index: int,
    probed_dims: list[str],
    version: str,
) -> list[Evidence]:
    valid_dims = {d["key"] for d in load_rubric(round_type)["dimensions"]}
    out: list[Evidence] = []
    dropped = 0
    for item in raw:
        try:
            dim = item["dimension"]
            polarity = item["polarity"]
            span = item.get("span")
            strength = max(0.0, min(1.0, float(item.get("strength", 0.5))))
            criterion = str(item.get("criterion") or dim).strip()[:120]
        except (KeyError, TypeError, ValueError):
            dropped += 1
            continue
        if dim not in valid_dims or polarity not in config.POLARITIES:
            dropped += 1
            continue
        if polarity == "absent":
            if probed_dims and dim not in probed_dims:
                dropped += 1
                continue
            span = None
        elif not span_in_answer(span, answer):
            dropped += 1  # unsupported claim: no verbatim span
            continue
        out.append(
            Evidence(
                turn_index=turn_index,
                dimension=dim,
                competency=config.dimension_to_competency(round_type, dim),
                criterion=criterion,
                polarity=polarity,
                span=span,
                strength=strength,
                extractor_version=version,
            )
        )
    if dropped:
        logger.info("extractor %s dropped %d invalid/unsupported item(s) for turn %d", version, dropped, turn_index)
    return out


class RuleBasedExtractor(Extractor):
    """No-LLM fallback. Credits the probed dimensions with weak evidence scaled
    by how substantive the answer is; never emits `contradicted` (it cannot
    judge correctness)."""

    version = "rule-v1"

    def _raw_items(self, *, round_type: str, question: str, answer: str, probed_dims: list[str]) -> list[dict]:
        words = len(answer.split())
        if not probed_dims or words < 3:
            return []
        items: list[dict] = []
        for dim in probed_dims:
            if words >= 40:
                span = " ".join(answer.split()[:12])
                items.append({"dimension": dim, "criterion": f"substantive answer on {dim}",
                              "polarity": "demonstrated", "span": span, "strength": 0.3})
            elif words < 15:
                items.append({"dimension": dim, "criterion": f"brief answer on {dim}",
                              "polarity": "absent", "span": None, "strength": 0.2})
        return items


class LLMExtractor(Extractor):
    def __init__(self, llm: LLMGateway, prompt_version: str = "v1", model_name: str = "llm"):
        self._llm = llm
        self._system = config.load_wm_prompt("extractor", prompt_version)
        self.version = f"llm-{model_name}-extractor-{prompt_version}"

    def _raw_items(self, *, round_type: str, question: str, answer: str, probed_dims: list[str]) -> list[dict]:
        rubric = load_rubric(round_type)
        dims = "\n".join(f"- {d['key']}: {d['label']}" for d in rubric["dimensions"])
        user = (
            f"Round type: {round_type}\n\n"
            f"Rubric dimensions:\n{dims}\n\n"
            f"Dimensions this question was probing: {', '.join(probed_dims) or 'unknown'}\n\n"
            f"Interviewer question:\n{question}\n\n"
            f"Candidate answer:\n{answer}\n\n"
            f"Return the JSON object described in your instructions."
        )
        raw = self._llm.complete_json(system=self._system, user_message=user, max_tokens=1024)
        parsed = json.loads(raw)
        items = parsed.get("evidence", []) if isinstance(parsed, dict) else []
        return [i for i in items if isinstance(i, dict)]


def get_extractor() -> Extractor:
    """Gemini when GEMINI_API_KEY is set (Flash-Lite intended: set
    ROUNDZERO_EXTRACTOR_MODEL to the Flash-Lite model name available to your
    key; unset, it uses the interviewer's default Gemini model). Otherwise the
    rule-based fallback."""
    if os.environ.get("GEMINI_API_KEY"):
        from roundzero.llm.providers.gemini_provider import GeminiGateway

        model = os.environ.get(EXTRACTOR_MODEL_ENV_VAR) or None
        gateway = GeminiGateway(model=model)
        return LLMExtractor(gateway, model_name=model or "gemini")
    return RuleBasedExtractor()
