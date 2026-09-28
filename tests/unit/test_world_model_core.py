"""
World-model core (specs/005-world-model-interviewer): the likelihood model and
belief update, the forward picker, the extractor's unsupported-claim guard,
inverse diagnosis, the two counterfactuals (flip - hypothetical, retry - real),
the simulator, gate metrics and the Gate 3 fitter. Pure functions, no DB.
"""
from __future__ import annotations

import json
import random

import pytest

from roundzero.worldmodel import belief as bl
from roundzero.worldmodel import config, learn, metrics, picker, simulator, steering
from roundzero.worldmodel.diagnosis import diagnose, node_status
from roundzero.worldmodel.extractor import Extractor, LLMExtractor, RuleBasedExtractor, validate_items
from roundzero.worldmodel.flip import FlipWriter, generate_rewrites
from roundzero.worldmodel.models import Belief, Evidence
from roundzero.worldmodel.retry import NotAnAnswerTurnError, score_retry

RT = "ml_system_design"
TRADEOFFS = "tradeoffs_judgment"


def ev(turn, polarity, strength=0.8, dimension="trade_offs", criterion="identifies the bottleneck", span="x"):
    return Evidence(
        turn_index=turn,
        dimension=dimension,
        competency=config.dimension_to_competency(RT, dimension),
        criterion=criterion,
        polarity=polarity,
        span=None if polarity == "absent" else span,
        strength=strength,
        extractor_version="test",
    )


# --- config / model ----------------------------------------------------------


def test_competencies_and_mapping_load():
    assert config.competency_keys() == [
        "problem_framing", "ml_system_design", "ml_depth",
        "tradeoffs_judgment", "production_reliability", "leadership_influence",
    ]
    assert config.dimension_to_competency(RT, "trade_offs") == TRADEOFFS
    assert config.dimension_to_competency(RT, "communication") is None  # cross-cutting
    assert "leadership_influence" in config.round_competencies("technical_leadership")


def test_every_rubric_dimension_is_mapped():
    from roundzero.evaluation.rubric_loader import load_rubric

    dim_map = config.load_competencies()["dimension_map"]
    for round_type, mapping in dim_map.items():
        keys = {d["key"] for d in load_rubric(round_type)["dimensions"]}
        assert keys == set(mapping), round_type


def test_likelihood_columns_sum_to_one_and_priors_are_distributions():
    data = config.load_likelihoods()
    for i in range(4):
        assert sum(data["default"][p][i] for p in config.POLARITIES) == pytest.approx(1.0)
    for prior in data["priors"].values():
        assert sum(prior) == pytest.approx(1.0)


def test_worked_example_contradiction_moves_mass_to_senior():
    b = Belief(probs={TRADEOFFS: [0.10, 0.40, 0.40, 0.10]})
    after = bl.apply_evidence(b, [ev(4, "contradicted", 0.8)])
    assert after.mode(TRADEOFFS) == 1  # senior
    assert after.expected(TRADEOFFS) < b.expected(TRADEOFFS)


def test_demonstrated_raises_and_zero_strength_is_a_no_op():
    b = bl.initial_belief("staff", [TRADEOFFS])
    assert bl.apply_evidence(b, [ev(1, "demonstrated")]).expected(TRADEOFFS) > b.expected(TRADEOFFS)
    assert bl.apply_evidence(b, [ev(1, "demonstrated", 0.0)]).probs == b.probs


def test_per_turn_strength_cap_limits_one_long_answer():
    b = bl.initial_belief("staff", [TRADEOFFS])
    one = bl.apply_evidence(b, [ev(1, "demonstrated", 1.0)])
    five = bl.apply_evidence(b, [ev(1, "demonstrated", 1.0) for _ in range(5)])
    assert five.probs[TRADEOFFS] == pytest.approx(one.probs[TRADEOFFS])


def test_floor_lets_a_belief_recover():
    b = bl.initial_belief("staff", [TRADEOFFS])
    for t in range(30):
        b = bl.apply_evidence(b, [ev(t, "contradicted", 1.0)])
    assert min(b.probs[TRADEOFFS]) >= 0.009
    assert bl.apply_evidence(b, [ev(99, "demonstrated", 1.0)]).expected(TRADEOFFS) > b.expected(TRADEOFFS)


def test_evidence_without_competency_is_ignored():
    b = bl.initial_belief("staff", [TRADEOFFS])
    comm = ev(1, "demonstrated", dimension="communication")
    assert comm.competency is None
    assert bl.apply_evidence(b, [comm]).probs == b.probs


# --- forward: picker + steering --------------------------------------------


def test_picker_prefers_the_most_uncertain_competency():
    b = Belief(probs={TRADEOFFS: [0.25, 0.25, 0.25, 0.25], "ml_depth": [0.01, 0.01, 0.97, 0.01]})
    d = picker.choose(b, after_turn_index=3, recent_choices=[], time_remaining_sec=1800, mode="shadow")
    assert d.chosen.competency == TRADEOFFS
    assert d.options[0].eig > d.options[1].eig
    assert sum(d.chosen.predicted.values()) == pytest.approx(1.0, abs=1e-3)


def test_picker_blocks_a_third_probe_in_a_row_and_stops_near_the_end():
    b = Belief(probs={TRADEOFFS: [0.25] * 4, "ml_depth": [0.1, 0.2, 0.6, 0.1]})
    d = picker.choose(b, after_turn_index=5, recent_choices=[TRADEOFFS, TRADEOFFS], time_remaining_sec=1800, mode="live")
    assert d.chosen.competency == "ml_depth"
    late = picker.choose(b, after_turn_index=9, recent_choices=[], time_remaining_sec=60, mode="live")
    assert late.chosen is None


def test_probe_hint_names_the_competency_and_never_a_level():
    b = Belief(probs={TRADEOFFS: [0.25] * 4})
    d = picker.choose(b, after_turn_index=1, recent_choices=[], time_remaining_sec=1800, mode="live")
    hint = steering.render_probe_hint(d.chosen)
    assert "Trade-offs and judgment" in hint
    for level_word in ("Senior", "Staff level", "Principal", "below_senior"):
        assert level_word not in hint.replace("a Staff answer", "")
    assert steering.probe_block(None) == ""


# --- perceive: extractor guard ----------------------------------------------

ANSWER = "We'd add more replicas behind the load balancer and scale out. We'd also cache common prompts."


def test_validation_drops_unsupported_and_unknown_items():
    raw = [
        {"dimension": "trade_offs", "criterion": "bottleneck", "polarity": "contradicted",
         "span": "add more replicas behind the load balancer", "strength": 0.8},
        {"dimension": "trade_offs", "criterion": "made up", "polarity": "demonstrated",
         "span": "we would shard the KV cache", "strength": 0.9},  # not in the answer
        {"dimension": "not_a_dimension", "criterion": "x", "polarity": "demonstrated",
         "span": "cache common prompts", "strength": 0.5},
        {"dimension": "reliability", "criterion": "failover", "polarity": "absent", "strength": 0.5},  # not probed
        {"dimension": "serving_scalability", "criterion": "caching", "polarity": "demonstrated",
         "span": "CACHE   common prompts", "strength": 3},  # whitespace/case tolerant, strength clipped
    ]
    items = validate_items(raw, round_type=RT, answer=ANSWER, turn_index=4,
                           probed_dims=["trade_offs", "serving_scalability"], version="t")
    assert [(i.dimension, i.polarity) for i in items] == [
        ("trade_offs", "contradicted"), ("serving_scalability", "demonstrated")]
    assert items[0].competency == TRADEOFFS and items[1].strength == 1.0


class _FakeLLM:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def complete_json(self, *, system, user_message, max_tokens=1024):
        self.calls.append(user_message)
        return json.dumps(self.payload)


def test_llm_extractor_parses_and_validates():
    llm = _FakeLLM({"evidence": [{"dimension": "trade_offs", "criterion": "bottleneck", "polarity": "contradicted",
                                  "span": "add more replicas", "strength": 0.8}]})
    items = LLMExtractor(llm, model_name="fake").extract(round_type=RT, question="What changes at 10x QPS?",
                                                           answer=ANSWER, turn_index=4, probed_dims=["trade_offs"])
    assert len(items) == 1 and items[0].extractor_version.startswith("llm-fake")
    assert "What changes at 10x QPS?" in llm.calls[0]


def test_rule_based_extractor_is_weak_and_never_contradicts():
    x = RuleBasedExtractor()
    long_answer = " ".join(["word"] * 60)
    items = x.extract(round_type=RT, question="q", answer=long_answer, turn_index=2, probed_dims=["trade_offs"])
    assert items and all(i.polarity != "contradicted" and i.strength <= 0.3 for i in items)
    assert x.extract(round_type=RT, question="q", answer=long_answer, turn_index=2, probed_dims=[]) == []


# --- inverse: diagnosis ------------------------------------------------------


def _turns():
    return [
        {"turn_index": 0, "speaker": "interviewer", "text": "Frame the problem.", "competency_tags": ["framing"]},
        {"turn_index": 1, "speaker": "candidate", "text": "Answer one", "competency_tags": []},
        {"turn_index": 2, "speaker": "interviewer", "text": "Trade-offs?", "competency_tags": ["trade_offs"]},
        {"turn_index": 3, "speaker": "candidate", "text": "Answer two", "competency_tags": []},
        {"turn_index": 4, "speaker": "interviewer", "text": "What changes at 10x QPS?", "competency_tags": ["trade_offs"]},
        {"turn_index": 5, "speaker": "candidate", "text": ANSWER, "competency_tags": []},
        {"turn_index": 6, "speaker": "interviewer", "text": "Cost?", "competency_tags": ["cost_efficiency"]},
        {"turn_index": 7, "speaker": "candidate", "text": "Answer four", "competency_tags": []},
    ]


def _evidence():
    return [
        ev(1, "demonstrated", 0.7, dimension="framing", criterion="defines success metric"),
        ev(3, "demonstrated", 0.7),
        ev(5, "contradicted", 0.9, criterion="identifies the bottleneck under load",
           span="add more replicas behind the load balancer"),
        ev(7, "absent", 0.6, dimension="cost_efficiency", criterion="cost per request"),
    ]


def test_diagnosis_finds_where_it_went_wrong_and_ranks_causes():
    diags = {d.competency: d for d in diagnose(round_type=RT, target_level="staff", turns=_turns(), evidence=_evidence())}
    t = diags[TRADEOFFS]
    assert [p.label for p in t.path] == ["A1", "A2", "A3", "A4"]
    assert t.went_wrong_turn == 5
    assert t.path[2].status == "wrong" and t.path[2].question == "What changes at 10x QPS?"
    assert t.causes[0].turn_index == 5 and t.causes[0].impact > 0
    assert all(c.impact >= t.causes[-1].impact for c in t.causes)
    assert not t.abstained and t.final_level in config.level_keys()


def test_diagnosis_abstains_without_enough_evidence():
    diags = {d.competency: d for d in diagnose(round_type=RT, target_level="staff", turns=_turns(), evidence=_evidence())}
    assert diags["production_reliability"].abstained
    assert diags["production_reliability"].final_level is None


def test_node_status():
    assert node_status([]) == "none"
    assert node_status([ev(1, "contradicted")]) == "wrong"
    assert node_status([ev(1, "demonstrated", 0.8)]) == "strong"
    assert node_status([ev(1, "demonstrated", 0.3)]) == "thin"
    assert node_status([ev(1, "absent")]) == "thin"


# --- counterfactual: flip (hypothetical) and retry (real) -----------------


class _StrongScorer(Extractor):
    """Blind re-scorer stand-in: credits any answer that mentions KV-cache."""

    version = "fake-scorer"

    def _raw_items(self, *, round_type, question, answer, probed_dims):
        if "KV-cache" in answer:
            return [{"dimension": "trade_offs", "criterion": "identifies the bottleneck under load",
                     "polarity": "demonstrated", "span": "KV-cache bound", "strength": 1.0}]
        return [{"dimension": "trade_offs", "criterion": "identifies the bottleneck under load",
                 "polarity": "contradicted", "span": "add more replicas", "strength": 0.9}]


def test_flip_rewrite_is_hypothetical_rescored_blind_and_projected():
    turns, evidence = _turns(), _evidence()
    diags = diagnose(round_type=RT, target_level="staff", turns=turns, evidence=evidence)
    writer = FlipWriter(_FakeLLM({"added_text": "Replicas alone won't hold p99 - each replica is KV-cache bound."}),
                        model_name="fake")
    rewrites = generate_rewrites(round_type=RT, target_level="staff", turns=turns, evidence=evidence,
                                 diagnoses=diags, writer=writer, scorer=_StrongScorer())
    rw = next(r for r in rewrites if r.competency == TRADEOFFS)
    assert rw.hypothetical and rw.turn_index == 5
    assert rw.edited_answer.startswith(ANSWER) and rw.edited_answer.endswith("KV-cache bound.")
    assert rw.projected_mean > rw.current_mean
    assert rw.scorer_version == "fake-scorer" and rw.writer_version.startswith("fake")


def test_flip_writer_caps_added_text_length():
    long_text = " ".join(["word"] * 200)
    writer = FlipWriter(_FakeLLM({"added_text": long_text}))
    out = writer.write(competency=TRADEOFFS, criterion="c", polarity="absent", question="q", answer="a")
    assert len(out.split()) == 60


def test_retry_swaps_only_that_answer():
    result = score_retry(round_type=RT, target_level="staff", turns=_turns(), evidence=_evidence(),
                         turn_index=5, retry_text="Each replica is KV-cache bound, so plan memory first.",
                         scorer=_StrongScorer())
    assert result.after[TRADEOFFS] > result.before[TRADEOFFS]
    assert result.after["problem_framing"] == pytest.approx(result.before["problem_framing"])
    with pytest.raises(NotAnAnswerTurnError):
        score_retry(round_type=RT, target_level="staff", turns=_turns(), evidence=_evidence(),
                    turn_index=4, retry_text="x", scorer=_StrongScorer())


# --- simulator, metrics, learning ------------------------------------------


def test_simulator_is_deterministic_and_reports_every_policy():
    comps = config.round_competencies(RT)
    a = simulator.compare_policies(comps, runs_per_persona=3, budget=6, seed=7)
    b = simulator.compare_policies(comps, runs_per_persona=3, budget=6, seed=7)
    assert a == b and set(a) == set(simulator.POLICIES)
    assert len(a["adaptive"]["accuracy_by_q"]) == 6


def test_sampled_evidence_follows_the_likelihood_column():
    rng = random.Random(0)
    n = 4000
    hits = sum(simulator.sample_evidence(TRADEOFFS, 3, rng, 0).polarity == "demonstrated" for _ in range(n))
    assert hits / n == pytest.approx(config.likelihood_row(TRADEOFFS, "demonstrated")[3], abs=0.03)


def test_metrics():
    assert metrics.quadratic_weighted_kappa([0, 1, 2, 3], [0, 1, 2, 3]) == pytest.approx(1.0)
    assert metrics.quadratic_weighted_kappa([0, 1, 2, 3], [3, 2, 1, 0]) < 0
    assert metrics.expected_calibration_error([0.9, 0.9], [True, True]) == pytest.approx(0.1)
    p, r = metrics.span_precision_recall(
        [(5, "contradicted", "add more replicas"), (5, "demonstrated", "nothing like gold")],
        [(5, "contradicted", "add more replicas behind the load balancer"), (7, "absent", None)],
    )
    assert p == 0.5 and r == 0.5


def test_fitter_recovers_a_table_and_splits_by_round():
    rng = random.Random(1)
    true = {"demonstrated": [0.1, 0.3, 0.7, 0.9], "absent": [0.5, 0.5, 0.25, 0.08],
            "contradicted": [0.4, 0.2, 0.05, 0.02]}
    transitions = []
    for r in range(200):
        lvl = r % 4
        for _ in range(10):
            pol = rng.choices(list(config.POLARITIES), weights=[true[p][lvl] for p in config.POLARITIES])[0]
            transitions.append((f"r{r}", TRADEOFFS, lvl, pol))
    fitted = learn.fit_likelihoods(transitions)
    assert fitted["default"]["demonstrated"][3] == pytest.approx(0.9, abs=0.05)
    train, test = learn.split_by_round(transitions)
    assert not ({t[0] for t in train} & {t[0] for t in test})
    report = learn.compare_on_heldout(transitions)
    assert report["fitted_wins"]  # the true table differs from v1, so fitting should win
