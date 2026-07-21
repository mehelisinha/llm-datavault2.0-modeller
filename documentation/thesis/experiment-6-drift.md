# Experiment 6 — Schema-drift detection and impact classification (Use Case B, RQ2)

**Status.** Code built and unit-tested; **6a (recall) and 6b (impact accuracy) run
on a REAL CIM drift dataset** in Databricks (`edh_unreg_silver_dev_st.cim_drifted`
vs `.bronze`). **6c (human effort)** is outstanding. Everything lives on branch
`ai/usecaseB-drift`. The synthetic proof-of-concept (§7) is kept for contrast.

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
- `dbt_builder/src/ai/drift/changeset.py` — `atomic_changes`, which flattens a
  table-grouped `ChangeSet` into per-change units (each column diff scored
  individually; key removal/retype flagged HIGH).
- `tests/ai/test_drift_impact.py` — 19 tests, no network.

## 2. The real dataset

`edh_unreg_silver_dev_st.cim_drifted` — a controlled drift of the CIM bronze schema
(empty tables; drift detection is schema-only). Eight recorded, labelled changes
across the taxonomy (DDL: `drift/fixtures/cim_drift.sql`; answer key:
`drift/fixtures/cim_drift_labels.json`):

| # | Change | Expert impact |
|---|---|---|
| 1 | conducting_equipment: `+owner` | additive |
| 2 | conducting_equipment: `−serial_number` | breaking |
| 3 | conducting_equipment: `mrid` string→bigint (key) | breaking |
| 4 | terminals: `sequence_number` bigint→decimal(38,0) | **cosmetic** |
| 5 | terminals: `+phase_code` | additive |
| 6 | terminals: `phases` string→int (incompatible) | breaking |
| 7 | connectivity_nodes: absent (orphaned) | breaking |
| 8 | cim_measurements: new table | additive |

Class counts: additive 3, cosmetic 1, breaking 4. The **bronze-vs-drifted** diff
reuses the existing `pipeline.diff_analyzer.diff` by wrapping the original bronze as
the "before" snapshot — no new diff logic.

## 3. Results (real CIM drift)

**H2a — deterministic detection recall = 1.00.** All 8 injected changes were
detected with the correct category and per-column verb (3 DRIFT column changes ×2
tables, 1 NEW, 1 ORPHANED). The deterministic engine misses nothing — H2a supported
on real data.

**H2b — AI vs rule-only impact accuracy:**

| Metric | Rule-only baseline | AI classifier |
|---|---|---|
| Accuracy | 0.88 (7/8) | **1.00 (8/8)** |
| Breaking-class recall (safety) | 1.00 | 1.00 |
| Cost-weighted error (lower = safer) | 1 | **0** |

**F-1: The AI is strictly better here, with no safety cost.** The AI classified all
eight changes correctly. The rule's single error was the one it is *designed* to
get wrong: the `sequence_number` **bigint→decimal(38,0)** widening, which the rule
conservatively calls breaking but is a lossless, non-key, **cosmetic** change — the
AI correctly identifies it. Crucially, **both classifiers caught 100% of the
breaking changes** (breaking recall 1.00), so the AI's accuracy gain came at no
safety cost on this set: cost-weighted error 1 → 0.

**F-2: The AI's advantage rests on the single cosmetic case — an honest limit.**
The entire 0.88 → 1.00 accuracy gap *is* that one type-widening. With cosmetic
n = 1 in this dataset (CIM's source types offer few clean widenings), the finding is
**directional, not statistically strong**: it shows the AI *can* make the
compatibility judgement the rule cannot, on a real change, but confirming it needs
more cosmetic examples (a richer schema, or ServiceNow).

**F-3: The synthetic safety worry did _not_ reproduce.** In the earlier synthetic
proof-of-concept (§7) the AI once mislabelled an *orphaned* table as cosmetic,
dropping breaking recall to 0.75. On the **real** data the AI classified the
orphaned `connectivity_nodes` correctly as breaking. So the safety regression is a
*possible* failure mode (worth the hybrid guardrail below), but it did not occur
here — reported honestly in both directions rather than cherry-picked.

**F-4: Design implication — hybrid remains the safe architecture.** Because an LLM
*can* occasionally miss a safety-critical case (§7), the recommended design is the
AI for subtle type-compatibility judgement **on top of** the rule's hard
safety-floor (orphaned / removed column / high-risk key change are always breaking).
On this dataset the hybrid would score the AI's 1.00 while *guaranteeing* the rule's
perfect breaking recall — the best of both.

## 4. What is still needed

- **6c (human effort):** compare drift-review effort — correction-style counts (as
  in Exp 5) for reviewing the pre-classified pipeline output vs an unaided manual
  drift review. Can reuse the Experiment 5 correction-step approach.
- **More cosmetic cases / a second system:** to move F-2 from directional to
  statistically supported (drift ServiceNow, or add numeric columns that permit
  clean widenings).

## 5. Threats to validity

- **Small, single-system, single-author-labelled, single run.** n = 8 changes on
  CIM only; labels assigned by the code author, not an independent Data-Vault
  expert; `gpt-4.1` at temperature 0, one run. The result is real but not
  statistically strong.
- **Cosmetic n = 1.** The AI-over-rule advantage rests on one type-widening (F-2).
  Directional, not conclusive — needs more cosmetic examples.
- **The AI's safety failure mode is real even though it didn't fire here.** The
  synthetic run (§7) shows an LLM *can* miss a breaking case a rule guarantees;
  F-4's hybrid guardrail is the response, kept regardless of this run's clean score.
- **Cost weights (5 / 1 / 1) are a stated choice**, not empirical; they encode "a
  missed breaking change is much worse than a false alarm." Report sensitivity to
  them.

## 6. How to reproduce

Unit tests (recall on a synthetic pair + classifier + scoring + atomic expansion),
no network:
```bash
python -m pytest tests/ai/test_drift_impact.py -q
```
Real run (needs Azure + the `cim_drifted` schema): `scratchpad/run_exp6.py` reads
`bronze` and `cim_drifted` from Databricks, diffs via `pipeline.diff_analyzer.diff`,
expands with `atomic_changes`, classifies with `rule_based_impact` +
`get_impact_classifier()`, and scores against `fixtures/cim_drift_labels.json` with
`score_impacts`. Recreate the dataset from `fixtures/cim_drift.sql`.

## 7. Viewing the drift in the UI

The drift is visible in the DWA app with **no code change** — the pipeline's
SNAPSHOT step already diffs a vault schema against a bronze schema, so pointing the
"vault" (before) at `bronze` and the "bronze" (after) at `cim_drifted` yields the
drift. Prerequisites are already in `.env`: `DWA_API_DISCOVERY_MODE=databricks`,
`DWA_API_DATABRICKS_HOST`, `DWA_API_DATABRICKS_AUTH_TYPE=azure-cli`.

1. Ensure `az login` is valid.
2. Start the app: `pnpm dev`.
3. Trigger a pipeline run with:
   - catalog: `edh_unreg_silver_dev_st`
   - **vault_schema: `bronze`** (the approved "before")
   - **bronze_schema: `cim_drifted`** (the drifted "after")
   - system_id: `IEC_CIM_001`, system_name: `IEC CIM`, source_type: `delta`
   (Equivalently `POST /api/pipeline/run` with that JSON body.)
4. The SNAPSHOT step shows the change-set (2 DRIFT, 1 NEW, 1 ORPHANED). Because the
   `mrid` business-key type change is flagged **HIGH risk**, the supervisor **pauses**
   the run — the UI shows the drift plus a risk banner (exactly the governance
   behaviour RQ3 predicts).

Verified via the identical backend code path (`scratchpad/verify_ui_drift.py`):
UC REST → `inspect_catalog(bronze)` + `read_bronze(cim_drifted)` → `diff`.

## 8. Appendix — synthetic proof-of-concept (for contrast)

Before the real dataset existed, a hand-labelled **synthetic** set (n = 10, one
`gpt-4.1` run) previewed the pipeline. It gave AI accuracy 0.90 vs rule-only 0.80,
**but** the AI once mislabelled an orphaned table as cosmetic — dropping breaking
recall to 0.75 (rule 1.00) and raising cost to 5 (rule 2). That surfaced the safety
failure mode the cost-weighted metric is built to catch, and motivated the hybrid
guardrail (§3 F-4). On the **real** CIM data that miss did not recur (§3 F-3). Both
outcomes are reported — the synthetic caution and the real clean run — rather than
keeping only the flattering one. Script: `scratchpad/exp6_synthetic.py`.
