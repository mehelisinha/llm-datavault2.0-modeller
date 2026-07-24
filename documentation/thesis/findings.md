# Findings

> **Purpose.** A single, self-contained record of every evaluation metric used in
> this thesis: what it measures, what it produced, what the result *means*, and
> which research question or hypothesis it supports. Written to be lifted directly
> into the results and discussion chapters.
>
> **Ground rules applied throughout.** Every number here was produced by code and
> is reproducible by the commands in §5. Nothing is estimated, extrapolated, or
> assumed unless explicitly labelled as such. Where a metric could **not** be
> measured, that is stated plainly rather than filled with a plausible figure.
> Where a result contradicts an earlier claim of ours, the contradiction is
> recorded rather than quietly corrected.

---

## 1. How to read this document

Metrics are given by their full names, not code identifiers. Each entry states:
**what it measures**, **the measured result**, **what the result means**, and the
**hypothesis or research question** it supports (see `RQ-Hypothesis.md`).

**Experimental conditions.** Unless stated otherwise: generator `gpt-4.1` at
temperature 0 with a fixed seed; reviewer `gpt-5.2` at temperature 1.0 (the only
value that model accepts); systems are ServiceNow IT4IT (`SNOW_IT4IT_001`, 9 source
tables, a *difficult* schema) and IEC-61968 CIM (`IEC_CIM_001`, 3 source tables, an
*easy* schema).

---

## 2. Reliability and grounding of generated models

These metrics need **no gold standard** — they can be computed on any run of any
source system, which makes them the most portable evidence in the thesis.

### 2.1 Hallucination Rate (source-grounding check)

**What it measures.** The proportion of source references in a generated plan that
**do not exist in the source system**. A *reference* is any source identifier the
model names: each object's source table, each hub's business-key column, and each
satellite's payload columns. A reference is *fabricated* when the named table is
absent from the discovery payload, or the named column is absent from that table.

This is the only metric in the suite that detects the canonical failure mode of a
language model — **inventing data that is not there**. It is distinct from the
conformance checks for unresolved link foreign keys and orphaned satellites, which
detect *internal* dangling references (plan-versus-plan consistency). Grounding is
*plan-versus-source*.

**Result.**

| System | Runs | Hallucination Rate | Fabricated references |
|---|---|---|---|
| IEC-CIM | 5 | **0.0000** | none |
| ServiceNow | 3 | **0.0015** | 1 — payload column `u_site_access_3_name` on `sat_cmn_location_details` |
| Deterministic heuristic baseline | 3 | 0.0000 | none (cannot invent by construction) |

**What this means.** Hallucination is **rare but not absent**. Across roughly 660
source references in the ServiceNow runs, exactly one was invented: the model
attached a payload column to a satellite that does not exist in the source table.
This matters more than the small number suggests, for three reasons. First, it
**refutes the comfortable assumption** — which we had made before measuring — that
the prompt instruction "never invent tables or columns" plus the plan-coercion step
made fabrication structurally impossible. It does not. Second, a fabricated payload
column would propagate into generated SQL and fail at compile or run time, so its
practical cost is disproportionate to its frequency. Third, it establishes that the
metric is **sensitive enough to catch a real case** rather than merely returning
zero because nothing is being checked.

The rate is low enough to conclude that the pipeline is *substantially* grounded,
and the deterministic baseline is grounded by construction (it can only reference
columns it read). The honest summary is: *hallucination is a real but marginal
failure mode in this system, and it requires a grounding check to catch, because no
other metric in the suite detects it.*

**Supports.** RQ1 / H1a (correctness of generated mappings) and the safety argument
of RQ3 — an ungrounded reference is an unsafe artifact.

### 2.2 Self-Consistency (output stability)

**What it measures.** How often repeated generations from the **same input, same
seed, same temperature** agree on the same set of entities. Formally, the fraction
of runs sharing the most common entity fingerprint (the sorted hub, link and
satellite names — the same fingerprint the modelling agent itself uses for majority
voting). A value of 1.0 means every run produced the same entity set.

**Result.**

| System | Runs | Self-Consistency |
|---|---|---|
| IEC-CIM (easy schema) | 5 | **0.80** |
| ServiceNow (hard schema) | 3 | **0.33** |

**What this means.** This is one of the more consequential findings in the thesis.
Even at **temperature 0 with a fixed seed**, the generator does **not** reproduce
its own output: four of five CIM runs agreed, but on the harder ServiceNow schema
**all three runs disagreed** with one another. Large language model inference is not
bit-deterministic, and the effect scales with task difficulty — the more ambiguous
the schema, the less stable the output.

This finding explains, in a single measurement, an anomaly that recurred throughout
the earlier experiments: the naming-adherence figure that read 1.0 in one session,
0.43–0.57 in another, and 1.0 again in a third (Experiment 5, §4). We had attributed
that to possible model-deployment drift over calendar time. The self-consistency
measurement shows a simpler and better-supported explanation: **the generator is
inherently unstable run-to-run**, so any single run is a sample, not a reading.

The methodological consequence is direct and should be stated in the thesis: **no
result from a single generation of this system is trustworthy.** Multiple seeds,
reported dispersion, and preference for metrics that proved stable (entity
identification) over metrics that proved unstable (naming) are not optional rigour
— they are required by the artifact's measured behaviour.

**Supports.** Validity of every other result; directly informs RQ1 (how reliable is
the multi-agent system) and the threats-to-validity discussion.

### 2.3 Idempotency Rate

**What it measures.** The fraction of repeated runs that reproduce the first run's
plan **exactly**, field for field — not merely the same entity names, but the same
business keys, payload columns and links. Stricter than self-consistency.

**Result.**

| Arm | Runs | Idempotency Rate |
|---|---|---|
| LLM generator — IEC-CIM | 5 | **0.20** |
| LLM generator — ServiceNow | 3 | **0.33** |
| Deterministic heuristic baseline | 3 | **1.00** |

**What this means.** The gap between self-consistency and idempotency is
informative. On CIM, 80% of runs agreed on *which entities* to create but only 20%
agreed on *every detail* of them. In other words the model is considerably more
stable about **what the entities are** than about **how it fills them in** — key
choices and payload composition wobble even when the entity set is settled. This is
consistent with the earlier experimental picture in which entity identification sat
at a ceiling while naming and link cardinality moved around.

The deterministic baseline scores a perfect 1.00 by construction. That contrast is
worth reporting rather than dismissing: rule-based automation buys **exact
reproducibility**, which the AI arm does not provide, and that is a genuine
engineering trade-off against the AI's substantially higher accuracy on difficult
schemas (Experiment 5). A production system that must produce byte-identical output
on unchanged inputs cannot rely on the generator alone without a caching or
approval-pinning layer.

**Supports.** RQ3 (H3a's idempotency clause — "repeated runs on unchanged inputs")
and the reliability discussion for RQ1.

### 2.4 Structural Validation Pass Rate

**What it measures.** The proportion of generated plans that render to metadata
YAML which passes the deterministic validation gate — YAML parses, internal
references resolve, and no ERROR-severity issue is raised.

**Result.** **1.00** (100%) on every run of both systems — 8 of 8 generated plans
rendered and validated cleanly.

**What this means.** Every plan the generator produced was a *structurally valid
artifact*, not merely a plausible-looking one. Combined with the near-zero
hallucination rate, this supports the claim that the pipeline's output is
well-formed by construction: the emitter is deterministic and the contract layer
rejects malformed plans before they reach it.

**Important limitation — this is not a dbt compile-pass rate.** The full dbt
compile gate is **disabled by default** and could **not** be exercised in this
environment: it requires a configured dbt profile (`~/.dbt/profiles.yml`) with live
Databricks credentials, which does not exist here — a `dbt parse` attempt failed for
exactly that reason. **No dbt compile-pass rate is claimed anywhere in this thesis.**
What is claimed is the offline structural validation rate above. Closing this gap
requires configuring a dbt profile and running `dbt deps` and `dbt parse` against a
generated project (see §5).

**Supports.** RQ1 / H1a; the "does it actually produce usable artifacts" question.

### 2.5 Token Consumption per Plan

**What it measures.** Prompt and completion tokens consumed to generate one plan,
captured directly from the model's usage reporting.

**Result.**

| System | Prompt tokens | Completion tokens | Total |
|---|---|---|---|
| IEC-CIM (3 tables) | 2,637 | 1,213 | ≈3,850 |
| ServiceNow (9 tables) | 9,873 | 4,051 | ≈13,924 |

**What this means.** Cost scales with schema size roughly proportionally — tripling
the table count multiplied total tokens by about 3.6. This is the practical
counterweight to the quality findings: the feedback-learning mechanism improves
naming only by *adding retrieved examples to the prompt* (Experiment 2), which
directly increases prompt tokens, and the reviewer stage adds a second full call.
Any recommendation to raise the retrieval count past the threshold identified in
Experiment 2 therefore carries a measurable, quantified cost, and the thesis can
state that cost rather than hand-waving about it.

**Supports.** RQ1 (cost side of the feedback mechanism) and RQ3 (practical
viability).

### 2.6 Chance-Corrected Agreement (Cohen's Kappa)

**What it measures.** Agreement between two sets of labels **after removing the
agreement expected by chance**. Plain accuracy flatters a classifier when one class
dominates; kappa does not. Applied here to the schema-drift impact labels from
Experiment 6 (n = 8 changes, classes: additive / cosmetic / breaking).

**Result.**

| Comparison | Accuracy | Cohen's Kappa |
|---|---|---|
| AI classifier vs expert labels | 1.00 | **1.000** |
| Rule-only baseline vs expert labels | 0.88 | **0.771** |

**What this means.** The chance correction changes the story in a useful way. The
rule baseline's raw accuracy of 0.88 sounds close to the AI's 1.00, but once
agreement-by-chance is removed the gap widens materially (0.771 versus 1.000) — the
rule benefits from the fact that most changes in this dataset are breaking, a class
it over-predicts by design. Kappa is therefore the fairer statistic for this
comparison and strengthens, rather than weakens, the Experiment 6 conclusion.

**A precise caveat about what this kappa is and is not.** This measures agreement
between an *automated classifier* and the expert labels. It is **not** inter-rater
reliability between two independent human annotators, which remains the standing
construct-validity limitation of this thesis: the gold sets and the drift answer key
have a **single author**. Cohen's kappa is now implemented and tested, so that
analysis can be run the moment a second annotator provides labels — but **no
inter-rater reliability figure is claimed here**, because no second annotation
exists.

**Supports.** RQ2 / H2b; and the methodology chapter's treatment of agreement.

### 2.7 Bootstrap Confidence Intervals

**What it measures.** A non-parametric 95% confidence interval for a metric's mean,
computed by resampling — appropriate for the very small samples used here, and
deterministic for a fixed seed so intervals are reproducible.

**Result.** Entity Identification F1: CIM **1.000, 95% CI [1.000, 1.000]** (n = 5);
ServiceNow **0.933, 95% CI [0.933, 0.933]** (n = 3).

**What this means.** These intervals are degenerate, and it would be misleading to
present them as evidence of precision. The interval collapses because **every run in
the sample produced an identical value** — entity identification was perfectly
stable across runs — not because the sample is large. The honest reading is: *entity
identification showed zero observed variance in these samples*, which corroborates
the stability finding in §2.2 (entity identification is the stable axis) while
saying nothing about how the metric would behave on unseen systems. Reporting the
interval, degenerate as it is, is more honest than reporting a bare mean.

**Supports.** Statistical rigour across all quantitative claims.

---

## 3. Findings from Experiments 1–7

### Experiment 1 — Feedback-learning ablation
**Metrics:** Entity Identification F1, Naming-Convention Adherence, Link Cardinality
Ratio, DV2 Convention Conformance Score, Generation Latency.
**Result.** Entity Identification F1 ≈ 0.91–0.93 across all three arms (learning off,
leave-one-out, full corpus); Naming-Convention Adherence **0.000 in every arm**;
Link Cardinality Ratio ≈ 1.6–1.9 (over-linking); latency cost of learning +0–3 s.
**What it means.** The naive hypothesis that feedback learning improves the model was
**not supported at the modelling stage**. Entity identification was already at a
ceiling the base model reaches unaided, and the one axis that did differ from the
expert — naming — was completely unmoved by three retrieved examples. This is a
negative but highly informative result: it localises where the feedback loop can and
cannot add value, and it motivated Experiment 2.
**Supports.** RQ1 / H1a, H1b.

### Experiment 2 — Learning curve and transfer probe
**Metrics:** Naming-Convention Adherence across retrieval sizes; Entity
Identification F1.
**Result.** Naming-Convention Adherence flat at 0.000 for retrieval of 0, 1, 3 and 5
examples, then **1.000 at 10**; under leave-one-out at 10 it returns to **0.000**.
**What it means.** Two distinct findings. First, the effect is **threshold-gated, not
gradual** — below a certain amount of in-context evidence the model's own naming
prior dominates completely; above it, the shop convention is adopted wholesale.
Second, and more limiting, the leave-one-out collapse shows the mechanism is
**instance-level copying, not convention generalisation**: the model reproduces
`hub_company` when an approved `hub_company` is in the corpus, but it does not infer
the abstract rule "prefer concept names over table names" from examples of *other*
entities. This bounds the contribution honestly and is a stronger claim than a
monotone learning curve would have been.
**Supports.** RQ1 / H1c.

### Experiment 3 — Cross-domain control
**Metrics:** as Experiment 1, on CIM with the CIM corpus excluded.
**Result.** Every metric identical across all conditions (all 1.000; link ratio 2.0).
**What it means.** Injecting examples from unrelated source systems is **inert, not
harmful** — a shared multi-system corpus is safe to leave enabled. Separately, CIM's
naming adherence was already 1.0 without any learning, because its source tables are
*already* concept-named. That sharpened the Experiment 2 finding into a scope
condition: the naming benefit only exists where table names diverge from the shop
convention.
**Supports.** RQ1 / H1c (corpus safety).

### Experiment 4 — End-to-end reviewer and error-taxonomy shift
**Metrics:** Error-Taxonomy Distribution, Blast-Radius-Weighted Error Impact, DV2
Convention Conformance Score, Entity Identification F1.
**Result.** The reviewer resolved all unresolved-link-foreign-key errors (14 → 0) but
introduced surrogate-business-key errors (8 → 12); conformance rose (0.93 → 0.96)
while Entity Identification F1 fell (1.00 → 0.71) and Blast-Radius-Weighted Error
Impact rose (42.5 → 50.0) **even though the raw issue count fell**.
**What it means.** The second model is a **trade-off, not a scalar improvement**. It
redistributes errors across the taxonomy rather than eliminating them: it repairs
connectivity while re-keying hubs onto surrogates. Critically, issue *count* and
blast-radius-weighted *impact* moved in opposite directions, because the errors
removed were low-fan-out (links) and those introduced sat on hubs, which everything
depends on. Judging the reviewer by counting issues would have produced the wrong
conclusion.
**Supports.** RQ1 / H1d.

### Experiment 5 — Three-arm baseline comparison
**Metrics:** Entity Identification F1, Naming-Convention Adherence, Link Cardinality
Ratio, Manual Correction-Step Count.
**Result (ServiceNow, hard schema).** Entity Identification F1: manual reference 1.00,
deterministic rules **0.50**, AI classification stage **0.94**, after reviewer 0.71.
Manual Correction-Step Count: build-from-scratch 29, repair rules 25, repair AI
**9.5**. On CIM (easy schema) all arms tied at 1.00.
**What it means.** The AI's value is **schema-dependent and locatable**. On an easy
schema, rules match it exactly — the AI adds nothing. On a hard schema the AI nearly
doubles the rule baseline's accuracy, and the gap is entirely made of judgement calls
rules cannot make: splitting one table into two business entities, recognising a
semantic key (`iso3166_3`) over a surrogate, and excluding telemetry and junction
tables. Both automated arms mishandle link cardinality, but in *opposite* directions
— rules under-link (ratio 0.0, finding no relationships), the model over-links (1.8).
**Supports.** RQ1 / H1a; RQ3 / H3b.

### Experiment 6 — Schema drift detection and impact classification
**Metrics:** Drift Detection Recall, Change-Impact Classification Accuracy,
Breaking-Change Recall, Cost-Weighted Misclassification Error, drift-review action
counts.
**Result (real drifted Databricks dataset, 8 labelled changes).** Drift Detection
Recall **1.00**. Impact accuracy: AI **1.00** versus rule-only **0.88**;
Breaking-Change Recall **1.00 for both**; Cost-Weighted Error 0 (AI) versus 1 (rule).
Review effort: 36 manual actions unaided, 1 with rules, **0** with AI.
**What it means.** Deterministic detection is exhaustive — the engine missed nothing,
which is the property a safety-critical layer must have. The AI's advantage over the
rule baseline is precisely the judgement the rule cannot make: recognising that a
`bigint → decimal(38,0)` widening is *cosmetic* rather than breaking. Both classifiers
caught every breaking change, so the AI's accuracy gain came at **no safety cost** on
this dataset. On effort, the pipeline eliminates the entire 28-step discovery burden
of manually comparing two schemas.
**Honest limits.** The cosmetic class has **n = 1**, so the AI's entire advantage
rests on a single case — directional, not statistically established. Separately, an
earlier synthetic proof-of-concept saw the AI mislabel an orphaned table as cosmetic
(dropping breaking-change recall to 0.75); that failure did **not** recur on real
data, and both outcomes are reported rather than only the favourable one.
**Supports.** RQ2 / H2a, H2b, H2c.

### Experiment 7 — Safety and governance
**Metrics:** Governance Block Rate, Audit-Trail Completeness.
**Result.** Block Rate **5/8 = 62% as built**, rising to **8/8 = 100%** after a
targeted fix. Audit-Trail Completeness: **not measurable**.
**What it means.** This is the most consequential finding of the evaluation and a
complete Design-Science iteration. The governance layer blocked every *plan-stage*
risk (empty plan, validation errors, structurally invalid plan, catastrophic reviewer
collapse) but was **blind to schema-drift risk**: a breaking business-key retype, a
dropped column and a vanished source table all passed the gate. The cause was
specific and instructive — the diff engine **already computed** per-change risk, but
the supervisor never consulted it, weighing only table volume, drift fraction and
orphan count. Detection was perfect while enforcement was absent.
Verified on production data: the real CIM drift returned *proceed* before the fix and
*pause* after it. The fix escalates any change the deterministic impact rule calls
breaking, and regression tests confirm it does **not** over-block benign additive
drift.
**Audit-Trail Completeness could not be measured**: the approvals and YAML-version
tables contain **zero rows**, because no approval has ever been persisted to the
Delta store. Only a structural guarantee is claimed — the schema captures actor,
timestamp, version, decision and rationale — and no completeness percentage is
reported.
**Supports.** RQ3 / H3a (refuted as built, supported after remediation); H3c
(unmeasured).

---

## 4. Consolidated hypothesis scorecard

| Hypothesis | Status | Principal evidence |
|---|---|---|
| **H1a** first-run accuracy comparable to manual | **Supported at the classification stage** | Exp 1, 5 (entity F1 0.93–1.00 vs manual reference; 0.50 for rules) |
| **H1b** naming and link parsimony are the weak axes | **Supported** | Exp 1, 5 (naming 0.000; link ratio 1.6–2.0) |
| **H1c** feedback effect is conditional | **Supported, with limits** | Exp 2 (threshold at 10; leave-one-out → 0.000), Exp 3 (cross-domain inert) |
| **H1d** reviewer is a trade-off | **Supported** | Exp 4 (conformance ↑, entity F1 ↓, weighted impact ↑) |
| **H2a** complete deterministic drift recall | **Supported** | Exp 6 (recall 1.00 on real data) |
| **H2b** AI impact classification beats rules | **Supported, directionally** | Exp 6 (1.00 vs 0.88; kappa 1.000 vs 0.771) — cosmetic n = 1 |
| **H2c** lower drift-review effort | **Supported** | Exp 6c (36 → 1 → 0 actions) |
| **H3a** zero unsafe promotions | **Refuted as built (62%); supported after fix (100%)** | Exp 7 |
| **H3b** fewer manual correction steps | **Supported** | Exp 5 (29 / 25 / 9.5) |
| **H3c** complete audit trail | **Not measurable** | Exp 7 (audit tables empty) |

---

## 5. Reproducing every result

All commands run from the repository root with `PYTHONPATH` set to it and a valid
`az login` for anything touching Databricks.

**Unit tests for every metric implementation (no network):**
```bash
python -m pytest tests/ai/test_grounding_and_stats.py tests/ai/test_gold_grading.py \
                 tests/ai/test_drift_impact.py tests/ai/test_governance_safety.py \
                 tests/ai/test_baselines.py tests/ai/test_study.py -q
```

**Experiments 1–5 (one declarative runner):**
```bash
# Exp 1 — ablation
python -m dbt_builder.src.ai.evaluation experiment --system SNOW_IT4IT_001 \
  --condition off --condition "loo:k=3,exclude=edh_unreg_consumption_dev" \
  --condition "on:k=3" --seeds 42,43,44

# Exp 2 — learning curve + transfer probe
python -m dbt_builder.src.ai.evaluation experiment --system SNOW_IT4IT_001 \
  --condition off --condition k1:k=1 --condition k3:k=3 --condition k5:k=5 \
  --condition k10:k=10 --condition "loo_k10:k=10,exclude=edh_unreg_consumption_dev" --seeds 42,43

# Exp 3 — cross-domain control
python -m dbt_builder.src.ai.evaluation experiment --system IEC_CIM_001 \
  --condition off --condition "loo_k3:k=3,exclude=iec_cim+edh_unreg_silver_dev_st" \
  --condition full_k10:k=10 \
  --condition "loo_k10:k=10,exclude=iec_cim+edh_unreg_silver_dev_st" --seeds 42,43

# Exp 4 — end-to-end reviewer + taxonomy shift
python -m dbt_builder.src.ai.evaluation experiment --system SNOW_IT4IT_001 --system IEC_CIM_001 \
  --condition "e2e_off:k=0,review=1" --condition "e2e_on:k=10,review=1" --seeds 42,43

# Exp 5 — three-arm baseline (deterministic arm is seed-independent)
python -m dbt_builder.src.ai.evaluation experiment --system SNOW_IT4IT_001 --system IEC_CIM_001 \
  --condition "deterministic:producer=heuristic" --seeds 42
python -m dbt_builder.src.ai.evaluation experiment --system SNOW_IT4IT_001 --system IEC_CIM_001 \
  --condition "full:k=10,review=1" --seeds 42,43
```
Each command prints entity F1, naming adherence, link ratio, conformance, the error
taxonomy and the correction-step count.

**Experiment 6 (drift).** Recreate the dataset from
`dbt_builder/src/ai/drift/fixtures/cim_drift.sql`; the answer key is
`cim_drift_labels.json`. Then run `scratchpad/run_exp6.py` (recall + impact accuracy)
and `scratchpad/run_exp6c.py` (review effort). To view the drift in the UI: `pnpm dev`,
then run the pipeline with catalog `edh_unreg_silver_dev_st`, vault schema `bronze`,
bronze schema `cim_drifted`.

**Experiment 7 (governance).** `scratchpad/run_exp7.py` prints the block-rate table
(set `SupervisorConfig(pause_on_breaking_change=False)` to reproduce the pre-fix 62%);
`scratchpad/run_exp7b.py` queries the audit tables; `scratchpad/verify_exp7_real.py`
shows the pre-/post-fix decision on the real drift.

**Section 2 metrics (hallucination, consistency, idempotency, tokens, validation,
kappa, confidence intervals).** `scratchpad/run_metrics.py` performs the repeated
generations and prints every figure in §2.

**Not reproducible here — and not claimed.** The dbt compile-pass rate requires a
dbt profile at `~/.dbt/profiles.yml` with Databricks credentials plus `dbt deps`;
Audit-Trail Completeness requires real approvals to exist in the Delta store;
inter-rater reliability requires a second human annotator.

---

## 6. What is still not measured

1. **Inter-rater reliability of the gold sets** — the single largest threat to
   construct validity. The kappa function is implemented and tested; it needs a
   second annotator, not more code.
2. **dbt compile-pass rate** — needs a configured dbt profile (§2.4).
3. **Audit-Trail Completeness** — needs approvals to be performed (§3, Experiment 7).
4. **Approval rate over time** — the most direct test of H1c's "successive runs"
   wording; blocked by the same empty approval store.
5. **Model-ablation robustness** — repeating key experiments with a weaker generator
   would show whether the findings are properties of the *mechanism* or of `gpt-4.1`.
6. **Breadth** — two source systems and small seed counts. The transferable claims
   are the *patterns* (AI advantage scales with schema difficulty; naming is unstable
   while entity identification is stable), not the absolute figures.
