# Experiment 6 — Schema-drift detection and impact classification (Use Case B, RQ2)

**Status.** Complete. **6a (recall), 6b (impact accuracy) and 6c (review effort)**
all run on a REAL CIM drift dataset in Databricks
(`edh_unreg_silver_dev_st.cim_drifted` vs `.bronze`), and the drift is viewable in
the UI (§7). Everything lives on branch `ai/usecaseB-drift`. The earlier synthetic
proof-of-concept is kept as an appendix (§8) for contrast.

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
proof-of-concept (§8) the AI once mislabelled an *orphaned* table as cosmetic,
dropping breaking recall to 0.75. On the **real** data the AI classified the
orphaned `connectivity_nodes` correctly as breaking. So the safety regression is a
*possible* failure mode (worth the hybrid guardrail below), but it did not occur
here — reported honestly in both directions rather than cherry-picked.

**F-4: Design implication — hybrid remains the safe architecture.** Because an LLM
*can* occasionally miss a safety-critical case (§8), the recommended design is the
AI for subtle type-compatibility judgement **on top of** the rule's hard
safety-floor (orphaned / removed column / high-risk key change are always breaking).
On this dataset the hybrid would score the AI's 1.00 while *guaranteeing* the rule's
perfect breaking recall — the best of both.

### H2c — drift-review effort (objective action counts)

As in Experiment 5's H3b, effort is measured as **manual actions**, not wall-clock
time (no human drift-review session was timed, so no timing is claimed). Three
action types: **discovery** (comparisons a reviewer must make to *find* the
changes), **decisions** (assigning an impact to each change), and **corrections**
(fixing a wrong machine label).

| Arm | Discovery | Decisions | Corrections | **Total actions** |
|---|---|---|---|---|
| Manual (unaided) | 28 | 8 | — | **36** |
| Deterministic (rule-only) | 0 | 0 | 1 | **1** |
| Deterministic + AI | 0 | 0 | 0 | **0** |

Discovery = 4 table-presence checks + 24 distinct column comparisons
(conducting_equipment 13, terminals 11) — what a human must inspect by hand to
find the 8 changes. Corrections come straight from §3: the rule mislabels the one
widening, the AI mislabels nothing.

**F-5: H2c is supported — the pipeline removes the search burden entirely.** An
unaided reviewer performs ~36 actions; the pipeline reduces this to 1 (rule) or 0
(AI) corrective actions, because change *discovery* is fully automated (H2a recall
= 1.00) and classification is near-perfect. The saving is dominated by discovery
(28 of 36 actions), which is exactly the tedious, error-prone part.

*Honest qualification:* "0 corrections" is not "0 effort" — the reviewer still
**reads** the 8 machine classifications to confirm them. What is eliminated is the
28-step search and the 8 independent judgement calls; what remains is verification.
A time figure would need the practitioner-assumption overlay used in Exp 5 §5.

## 4. What is still needed

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
Real run (needs Azure + the `cim_drifted` schema): the committed drift modules under
`dbt_builder/src/ai/drift/` produce every figure. Read `bronze` and `cim_drifted` from
Databricks, diff via `pipeline.diff_analyzer.diff`, expand with `atomic_changes`,
classify with `rule_based_impact` + `get_impact_classifier()`, and score against
`fixtures/cim_drift_labels.json` with `score_impacts`; recreate the dataset from
`fixtures/cim_drift.sql`. The effort counts (H2c) come from the same two schemas via the
discovery/decision/correction action model in §3. (These were driven by a one-off
orchestration script that was not committed; the modules and labels it called are all in
the repo and unit-tested in `tests/ai/test_drift_impact.py`.)

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
4. The SNAPSHOT step shows the change-set (2 DRIFT, 1 NEW, 1 ORPHANED), and the run
   **pauses** with a risk banner because the `mrid` business-key retype is a
   breaking change.

> **Note (Experiment 7).** That pause only happens *after* the governance fix made
> in Experiment 7. As originally built the supervisor never consulted the diff's
> per-change risk, so this exact drift would have been detected, correctly
> classified as breaking — and then **not stopped** (block rate 62%). See
> `experiment-7-safety-governance.md` §2–§3.

Verified via the identical committed backend code path:
UC REST → `inspect_catalog(bronze)` + `read_bronze(cim_drifted)` → `diff` (the same
`pipeline` modules the app itself runs).

## 8. Appendix — synthetic proof-of-concept (for contrast)

Before the real dataset existed, a hand-labelled **synthetic** set (n = 10, one
`gpt-4.1` run) previewed the pipeline. It gave AI accuracy 0.90 vs rule-only 0.80,
**but** the AI once mislabelled an orphaned table as cosmetic — dropping breaking
recall to 0.75 (rule 1.00) and raising cost to 5 (rule 2). That surfaced the safety
failure mode the cost-weighted metric is built to catch, and motivated the hybrid
guardrail (§3 F-4). On the **real** CIM data that miss did not recur (§3 F-3). Both
outcomes are reported — the synthetic caution and the real clean run — rather than
keeping only the flattering one. (The synthetic preview was a one-off run and its
script was not committed; the real-data result in §3 is the one that stands, and it
is reproducible from the committed drift modules and fixtures.)
