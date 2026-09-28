"""
World-model interviewer (specs/005-world-model-interviewer).

One explicit belief about the candidate's level per competency, updated after
every answer from span-cited evidence, used three ways:

- forward (picker.py): which follow-up would teach us the most next;
- inverse (diagnosis.py): which answer caused the outcome, and why;
- counterfactual (flip.py hypothetical, retry.py real): what one changed answer
  would have done to the outcome.

The model itself is P(polarity | level, competency) - see
rubrics/competencies/likelihoods_v1.yaml and belief.py. Everything in this
package is DB-agnostic (CLAUDE.md decision 1); persistence lives in
apps/api/worldmodel_service.py.
"""
