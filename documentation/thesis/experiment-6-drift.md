# Experiment 6 — Schema-drift detection and impact classification (Use Case B, RQ2)

**Status.** The **code is built and unit-tested**; **H2a is demonstrated** on a
synthetic drift pair; **H2b has a synthetic proof-of-concept** (below). The
**thesis result for 6b/6c awaits the author's real drifted Databricks dataset**
(see `use-case-b-drift-design.md` §5). Everything here lives on branch
`ai/usecaseB-drift`.

**Hypotheses (from `RQ-Hypothesis.md`).** H2a — the deterministic diff has complete
recall on structural changes. H2b — the AI impact classifier (additive / cosmetic /
breaking) beats a rule-only baseline. H2c — the pipeline costs less human effort
than manual review.

## 1. What was built

- `dbt_builder/src/ai/drift/impact.py` — the `ChangeImpact` taxonomy
  (additive / cosmetic / breaking); `rule_based_impact` (the deterministic
  **baseline** — conservative: it cannot judge type compatibility, so any
  type-change/removed column/high-risk/orphaned table is treated as breaking); and
  `ImpactClassifier` (an LLM that reasons about the change in context, **fail-safe**
  to the rule baseline on any error).
- `dbt_builder/src/ai/drift/scoring.py` — `score_impacts` →
  `DriftImpactReport`: accuracy, a confusion matrix, per-class precision/recall,
  and an **asymmetric cost-weighted error** in which missing a *breaking* change
  costs 5× a false alarm (the safety-relevant number).
- `tests/ai/test_drift_impact.py` — 17 tests, no network.

## 2. H2a — deterministic detection recall (demonstrated on synthetic data)

The existing diff engine (`pipeline.diff_analyzer`) was run on a synthetic
before/after pair with injected changes: a new table, a table with an added *and* a
removed column, and a vault entity whose source disappeared. **Every injected
change was detected** with the correct category (NEW / DRIFT / ORPHANED) and the
correct per-column verbs (added / removed). This confirms the *mechanism* for H2a
(recall = 1.0 on the synthetic set); the thesis figure will re-run this on the real
Databricks drift pair.

## 3. H2b — AI vs rule-only impact accuracy (SYNTHETIC proof-of-concept)

> **⚠ Illustrative only.** The following uses a **hand-labelled synthetic
> change-set of n = 10**, one run of `gpt-4.1`. The expert labels were assigned by
> the author of the code, not an independent Data-Vault expert, and the changes are
> toy. **This is not the thesis result** — it demonstrates that the pipeline runs
> end-to-end and previews the *kind* of finding to expect. The real result requires
> the drifted Databricks dataset with independent expert labels.

| Metric | Rule-only baseline | AI classifier |
|---|---|---|
| Accuracy | 0.80 | **0.90** |
| Breaking-class recall (safety) | **1.00** | 0.75 |
| Cost-weighted error (lower = safer) | **2** | 5 |

**F-1: The AI is more accurate but less safe — the metrics disagree.** The AI
correctly classifies compatible type *widenings* (`int → bigint` on a non-key
column) as **cosmetic**, where the conservative rule over-calls them **breaking** —
lifting overall accuracy 0.80 → 0.90. **But** the AI made one *dangerous* error: it
labelled an **orphaned (removed) table** as cosmetic when it is **breaking**. The
rule baseline never makes that miss (orphaned → breaking is hard-coded). So the
safety-critical metrics — breaking recall (1.00 → 0.75) and cost-weighted error
(2 → 5) — **favour the conservative rule**, even though raw accuracy favours the AI.

**F-2: This is exactly why the cost-weighted metric exists.** Judging impact
classification by accuracy alone would call the AI the clear winner; the asymmetric
cost — where auto-applying a missed breaking change is far worse than a false alarm
— reveals the opposite on the safety axis. Reporting both is essential.

**F-3: Design implication — a hybrid, not a replacement.** The right architecture is
the AI for the *subtle* judgement (type compatibility, cosmetic vs additive) **on
top of** the rule's *hard safety-floor* (orphaned / removed column / high-risk key
change are always breaking, regardless of what the AI says). That keeps the AI's
accuracy gain without surrendering the rule's guaranteed breaking recall. This
mirrors the Experiment 4 reviewer finding: the AI improves one axis while
introducing a risk on another, so it belongs *inside* deterministic guardrails.

## 4. What is still needed (6b/6c on real data)

To turn the synthetic PoC into the thesis result, the author supplies a **drifted
Databricks dataset** (shape in `use-case-b-drift-design.md` §5): an approved
contract plus a drifted schema carrying 10–20 **recorded, expert-labelled** changes
spanning all three impact classes. Then:

- **6a (recall):** run the diff engine on the real pair; report detected / injected.
- **6b (impact accuracy):** run rule-only and AI on the detected changes; report the
  table above on real data, with the confusion matrix and per-class P/R.
- **6c (effort):** compare review effort (correction-style counts, as in Exp 5) for
  the pre-classified pipeline output vs unaided manual drift review.

The author has offered to add a field to a Databricks table to confirm detection —
that is exactly the input needed to begin 6a on real data.

## 5. Threats to validity

- **The §3 numbers are synthetic and single-author-labelled** — n = 10, one model
  run. They show the mechanism and a plausible trade-off, nothing more.
- **The AI's orphaned-table miss may be partly a prompt artifact.** It is reported
  as-is (not prompt-tuned away) because the honest finding — an LLM can miss a
  safety-critical case a rule guarantees — is the point, and the hybrid design (F-3)
  addresses it structurally rather than by prompt-fiddling.
- **Cost weights (5 / 1 / 1) are a stated choice**, not empirical; they encode "a
  missed breaking change is much worse than a false alarm." Sensitivity to these
  weights should be noted when the real result is reported.

## 6. How to reproduce

Unit tests (H2a synthetic recall + classifier + scoring), no network:
```bash
python -m pytest tests/ai/test_drift_impact.py -q
```
Synthetic 6b PoC (needs Azure; illustrative): `scratchpad/exp6_synthetic.py` builds
the labelled change-set, runs `rule_based_impact` and `get_impact_classifier()`, and
scores both with `score_impacts`. On the real dataset, the same two functions run
over the diff engine's `ChangeSet`; scoring is identical.
