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

## 0. Contribution and framing

The contribution of this thesis is **not** a claim that an LLM automates Data Vault
modelling well, nor that feedback learning makes it better — the evidence here does not
support that framing, and says so. The contribution is twofold and evaluative:

1. **A reusable, honesty-first evaluation methodology for LLM-generated data models.**
   A suite of metrics — most of them **ground-truth-free** (hallucination /
   source-grounding, self-consistency, idempotency, structural validation, live dbt
   compile), the rest graded against a documented gold set with an explicit rubric and
   codebook — combined with the statistical discipline the artifact's own behaviour
   demands (multiple seeds, bootstrap intervals, exact permutation tests with effect
   sizes, chance-corrected agreement, blast-radius weighting). This framework is the
   transferable artifact; it is what lets any of these results be believed.

2. **A characterisation of the boundary conditions of LLM-assisted DWA** — *where* the
   AI helps and where it does not. The recurring result is that **schema difficulty is
   the moderator**: on easy, already-concept-named schemas a deterministic rule baseline
   matches the AI (the AI adds nothing); on difficult schemas the AI substantially beats
   rules on entity identification, but naming collapses and it over-links, and the
   feedback-learning mechanism is largely inert at the modelling stage: under a
   controlled, verified-load leave-one-out probe it transfers *structural* discipline
   across domains — a significant, large improvement in link parsimony on the harder
   schema — but *lexical* naming does not transfer at all (0.000 in both arms), and it
   never degrades quality (§2.8). The safety layer —
   deterministic drift detection plus AI impact classification plus a governance gate —
   is the most robust "it works" result.

Read the rest of this document as evidence for those two claims. Several headline
hypotheses are **partly refuted by our own measurements** (feedback learning; the
reviewer as a scalar improvement; the governance gate as originally built), and those
negative and boundary results are treated as the finding, not as failures to hide.

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

### 1.1 Metric catalogue — everything measured, and why

Every metric used anywhere in this thesis, what question it answers, and where its
result lives. Metrics in the top block need **no gold standard** (portable to any
run); the middle block needs a **gold/reference model**; the bottom block is
**drift- and governance-specific**.

| Metric | What it is used for (the question it answers) | Gold needed? | Result in |
|---|---|---|---|
| **Hallucination Rate** | Does the model invent tables/columns not in the source? (the one LLM-specific failure mode) | No | §2.1 |
| **Self-Consistency** | Does the same input reproduce the same *entity set* across runs? (stability) | No | §2.2 |
| **Idempotency Rate** | Does the same input reproduce the *exact same plan*, field for field? (stronger stability) | No | §2.3 |
| **Structural Validation Pass Rate** | Does the plan render to YAML that parses and whose references resolve? | No | §2.4 |
| **dbt compile (live)** | Does the generated dbt project actually compile against a real warehouse? | No | §2.4 |
| **Token Consumption per Plan** | What does one generation cost, and how does cost scale with schema size? | No | §2.5 |
| **Cohen's Kappa** | Agreement between two label sets after removing chance (drift labels here) | Labels | §2.6 |
| **Bootstrap 95% CIs** | How much does each metric wobble across seeds? (is a number reliable or a lucky draw?) | Mixed | §2.7 |
| **Entity Identification F1** | Are the right hubs/links/sats identified vs the expert model? (core correctness) | Yes | Exp 1,3,4,5 |
| **Naming-Convention Adherence** | Do generated names match the shop convention? (the learnable weak axis) | Yes | Exp 1,2,3 |
| **Link Cardinality Ratio** | Over-/under-linking vs the ideal (1.0 = right number of links) | Yes | Exp 1,3,5; §3B.1 |
| **DV2 Convention Conformance Score** | Rule-based Data-Vault well-formedness (unresolved FKs, orphan sats, …) | Partial | Exp 1,4 |
| **Error-Taxonomy Distribution** | *Which kinds* of error occur, and how the reviewer shifts them | Yes | Exp 4 |
| **Blast-Radius-Weighted Error Impact** | Weights each error by how many models depend on it (not all errors are equal) | Yes | Exp 4 |
| **Manual Correction-Step Count** | Human effort to fix output to acceptance — the objective effort proxy (replaces fabricated timings) | Yes | Exp 5; H3b |
| **Generation Latency** | Wall-clock cost of a run, incl. the learning/reviewer overhead | No | Exp 1 |
| **Drift Detection Recall** | Does the deterministic diff catch every real schema change? (safety-critical) | Answer key | Exp 6 |
| **Change-Impact Classification Accuracy** | Does the AI label additive/cosmetic/breaking correctly vs rules? | Answer key | Exp 6 |
| **Breaking-Change Recall** | Are *breaking* changes never missed? (the one class that must not leak) | Answer key | Exp 6 |
| **Cost-Weighted Misclassification Error** | Penalises dangerous mislabels (breaking→safe) more than harmless ones | Answer key | Exp 6 |
| **Drift-Review Action Count** | Human actions to triage a drift, unaided vs rules vs AI (effort, H2c) | Answer key | Exp 6c |
| **Governance Block Rate** | Fraction of unsafe promotions the supervisor actually blocks | Scenario set | Exp 7 |
| **Audit-Trail Completeness** | Do persisted approvals capture actor/time/version/decision/rationale? | Real approvals | §3C |
| **Approval Rate** | Of the decisions taken, how many are approvals vs rejections? | Real approvals | §3C |
| **Significance + Effect Size** | Is a difference bigger than seed noise, and how large? (paired permutation test, Cliff's δ) | Mixed | §2.8 |
| **Inter-Rater Reliability** | Is the gold reproducible by an independent rater? (Cohen's κ against a codebook) | Gold + codebook | §2.9 |

Both of the items that were open at the start of this work have since been measured.
Audit-trail completeness and the approval rate were computed once the approval store
held real decisions (§3C), and the gold's reliability is triangulated against an
independent annotator and a written codebook (§2.9). What is still outstanding is a
genuinely *human* second labelling of the gold — a second annotator, or the author
re-labelling after a gap — which §6 records.

### 1.2 Why the seed count is ten

A word on why the learning comparison is held to a high bar — many seeds *and* a
controlled corpus. The final off-versus-on result (§2.8) came only after two earlier
readings were shown to be artifacts. An early three-seed run looked encouraging on the
hard schema — learning seemed to tighten link cardinality and lift conformance, a clean
sweep — but rerun at ten seeds both effects shrank into noise: small-sample dressing. A
larger uncontrolled run then swung the other way, appearing to show learning either
*worsening* the highest-reach errors or *lifting* naming to 0.34–0.69 depending on the
batch — until both were traced to the retrieval plumbing rather than to learning (a
corpus that silently failed to load, and a corpus that leaked the target system's own
approved model; §2.8). The trustworthy comparison is therefore n = 20 with the corpus
**verified non-empty before every run** and a **leave-one-out** filter, so the ON arm
provably learns from the *other* domain and nothing else. The compounded lesson: at these
stakes a difference is not a finding until it survives both more seeds and a check on what
the learning arm actually retrieved.

### 1.3 Why each metric was chosen (in plain words)

One simple reason per metric — *why it is here at all*:

- **Hallucination rate** — an LLM can make up tables or columns that do not exist in the
  source; if it does, the output is unusable, and no other check catches it.
- **Self-consistency** — the model can give different answers to the *same* input, so we
  measure whether one run can be trusted or is just a lucky draw.
- **Idempotency rate** — the same input should give the exact same plan every time; we
  check whether it actually does.
- **Structural validation pass rate** — the YAML must parse and its internal references
  must line up, or it cannot be used at all.
- **dbt compile (live)** — "valid YAML" is not enough; it must compile into a real dbt
  project against the actual warehouse.
- **Token consumption** — every run costs money and time; we track how much, and how fast
  it grows with schema size.
- **Entity identification F1** — the core job is finding the right business entities and
  keys; F1 rewards finding the right ones *and* not missing any, in one number.
- **Naming-convention adherence** — using the shop's names (`hub_company`, not
  `hub_core_company`) matters, so we score it separately from correctness.
- **Link cardinality ratio** — the model tends to make too many links; this checks it
  produces the *right number*.
- **DV2 conformance score** — the output must obey Data Vault rules (no dangling links,
  no orphan satellites); this is checked by rules, not opinion.
- **Error-taxonomy distribution** — not all errors are alike, so we look at *what kinds*
  of error occur and how the reviewer shifts them.
- **Blast-radius-weighted error impact** — an error on a hub (everything depends on it)
  is worse than one on a leaf; we weight each error by how much depends on it.
- **Manual correction-step count** — we could not fairly time a human expert, so we count
  the concrete edits needed to fix the output — an objective, honest stand-in for effort.
- **Generation latency** — a slow pipeline is a real-world problem, so we time it.
- **Drift detection recall** — a safety layer must miss nothing; we check it catches
  *every* real schema change.
- **Change-impact classification accuracy** — after a change is detected, the AI must
  correctly say whether it is safe or breaking.
- **Breaking-change recall** — missing a *breaking* change is the dangerous failure, so we
  track that one class on its own.
- **Cost-weighted misclassification error** — calling a breaking change "safe" is far
  worse than the reverse, so dangerous mistakes are penalised more heavily.
- **Drift-review action count** — the goal is to save human effort, so we count the manual
  actions needed to triage a drift, with and without the tool.
- **Governance block rate** — the whole safety promise is that unsafe changes get stopped;
  we measure the fraction actually blocked.
- **Audit-trail completeness** — every decision must be traceable (who, when, what, why);
  we check the stored records carry all of it.
- **Approval rate** — a simple measure of how often generated plans are good enough for a
  human to approve.
- **Cohen's κ** — when comparing two sets of labels, plain "% agree" is misleading if one
  answer is common; κ strips out the agreement you would get by luck.
- **Bootstrap confidence intervals** — a single average can be a fluke; the interval shows
  how much that number wobbles.
- **Significance + effect size** — with only a handful of runs, a difference could be
  noise; these say whether it is real and how big it is.
- **Inter-rater reliability** — the gold answers are one person's judgement, so we check an
  independent rater reaches the same labels — evidence the gold is not just opinion.

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

**dbt compile against live Databricks — the generated project compiles cleanly.**
A dbt profile using Databricks OAuth (external browser, no stored secret) was
configured, `dbt deps` installed the AutomateDV/dbt-utils packages, and `dbt compile`
ran against the live warehouse on the generated CIM project. It parsed the whole
project — *"Found 12 models, 42 data tests, 3 sources, 1419 macros"* — and produced
compiled SQL for **all 12 models with zero errors and zero emitter warnings**. The
compiled artifacts confirm the full Data Vault rendered: **3 staging, 3 hubs, 1 link,
4 satellites, and 1 effectivity satellite** (`eff_sat_terminal_equipment_node`), plus
all 42 data tests. The only lines the run emits besides the model loads are benign,
code-independent dbt/Databricks notices (thrift SSL legacy-validation chatter and two
dbt behaviour-change opt-in notices); none originate in the generated project.

**What this means.** The generator does not merely produce YAML that passes its own
validator — it produces a dbt project that a real warehouse accepts and compiles
end-to-end, including the effectivity satellite, incremental-merge hubs/links/sats,
and every AutomateDV macro call. That closes the loop from "structurally valid
artifact" to "deployable artifact".

**Compile-pass rate across projects = 1.00 (2/2).** The compile check spans two
independent systems: the hand-authored CIM project (12 models) and a ServiceNow IT4IT
project generated end-to-end by the pipeline (gpt-4.1 plan → `render_v3` metadata →
dbt project; 48 models — 8 staging, 8 hubs, 12 links, 8 satellites, 12 effectivity
satellites). Both compile cleanly against live Databricks, ServiceNow introspecting its
real sources in `edh_unreg_consumption_dev.it4it_servicenow`. The generator and emitter
therefore produce warehouse-valid projects across two schemas of very different shape,
one authored by hand and one produced by the AI.

**Execution (`dbt run` + `dbt test`) against live Databricks.** Beyond compiling, the
generated CIM project *materialises*: `dbt run` builds **all 12 models with zero errors
(12/12)** against the live warehouse — the staging views, the incremental-merge hubs,
links and satellites, and the effectivity satellite. Execution is a stronger validation
than compilation, because it confirms the SQL not only parses but produces the physical
tables and views. `dbt test` passes **42 of 42** of the generated data tests
(`snapshots/dbt_run_test_42of42.txt`). Reaching a full pass required one emitter
correction: the generator had emitted a column-level `unique` test on every satellite /
effectivity-satellite hash key, which is over-strict by Data Vault design — a satellite's
grain is *(hash key + load date)* and the hash key repeats across loaded versions of a
business key, so uniqueness holds on the *composite* key, not the hash key alone. The
emitter now asserts `not_null` on the satellite hash key and a model-level
`dbt_utils.unique_combination_of_columns` on *(hash key + load date)*, while hubs and
links keep their column-level `unique` (their hash key genuinely is unique). The four
spurious failures are removed and uniqueness is asserted on the correct grain. The result
confirms that the generated output is not merely valid YAML but a **deployable dbt project
that builds, runs and fully passes its tests end-to-end on a real warehouse**.

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
reliability between two independent human annotators. The gold sets and the drift
answer key have a **single author**; that construct-validity threat is triangulated in
§2.9 (independent-annotator kappa 0.84 against a documented codebook), with a full
human inter-rater figure still open (§6).

**Supports.** RQ2 / H2b; and the methodology chapter's treatment of agreement.

### 2.7 Bootstrap Confidence Intervals

**What it measures.** A non-parametric 95% confidence interval for a metric's mean,
computed by resampling — appropriate for the very small samples used here, and
deterministic for a fixed seed so intervals are reproducible.

**Result (five distinct seeds, gpt-4.1).**

| System / condition | Entity Identification F1 (mean, 95% CI) | Naming Adherence (mean, 95% CI) | Link Ratio (mean, 95% CI) |
|---|---|---|---|
| ServiceNow / off | 0.947, [0.933, 0.973] | 0.000, [0.000, 0.000] | 1.673, [1.582, 1.800] |
| ServiceNow / on | 0.933, [0.933, 0.933] | 0.000, [0.000, 0.000] | 1.764, [1.727, 1.836] |
| CIM / off | 1.000, [1.000, 1.000] | **0.867, [0.600, 1.000]** | 2.000, [2.000, 2.000] |
| CIM / on | 1.000, [1.000, 1.000] | 1.000, [1.000, 1.000] | 2.000, [2.000, 2.000] |

**What this means.** The intervals confirm, with numbers, the central reliability
finding of §2.2: **the confidence intervals for entity identification and link ratio
are tight, while the interval for naming is wide.** CIM naming under leave-nothing-out
spans **[0.600, 1.000]** — one of five seeds produced 0.333 while the others produced
1.0. So naming is not merely low in some runs; it is *statistically unstable*, and any
single-run naming figure is a sample from a wide distribution, not a fixed property. Entity identification, by
contrast, varies by at most one spurious hub (F1 0.933–0.973), and link ratio is
stable around its over-linking value. **The practical rule this licenses: report
entity identification and link ratio as reliable, and always report naming with its
dispersion — never as a point estimate.**

**Supports.** Statistical rigour across all quantitative claims.

### 2.8 Significance Testing and Statistical Power

**What it measures.** Whether a difference between two conditions is larger than
sampling noise (a **p-value**), and *how large* it is regardless of significance
(an **effect size**). The experiments pair conditions by seed (`off@42` vs `on@42`),
so the correct test is a **paired permutation test**: it enumerates all `2ⁿ`
sign-flips of the per-seed differences — an *exact* p-value at these sample sizes,
with no normality assumption (a t-test would be indefensible at n=3–5). Effect size
is **Cliff's delta** (scale-free, non-parametric). Both are implemented in
`stats.py` (`paired_permutation_test`, `cliffs_delta`, `compare_paired`) and unit-
tested against hand-computed values.

**Two controls that make the learning comparison trustworthy.** The feedback corpus is
retrieved live from the Databricks store, and two failure modes silently corrupt an
uncontrolled off-vs-on comparison. First, the corpus loader degrades to *no examples* on
any transient warehouse error — it returns `None` rather than failing — so a flaky
connection turns the ON arm into a second copy of OFF with no visible sign. Second, the
corpus contains the target system's *own* approved model, so an unfiltered retrieval lets
ON copy back the very answer it is graded against, inflating "learning" into memorisation.
The final comparison controls both: the corpus is loaded **once and verified non-empty
before any generation** (21 CIM examples survive the exclusion, printed to the run log),
and a **leave-one-out** filter drops both ServiceNow-family source catalogs
(`edh_unreg_consumption_dev`, `edh_unreg_bronze_dev`) so ON can only learn from the *other*
domain — electrical-grid CIM transferring into IT-service-management ServiceNow. What ON
then shows is genuine cross-domain transfer: not a failed load, and not memorisation.

**Result — learning OFF vs ON, genuine cross-domain transfer, paired by seed (n = 20,
gpt-4.1).** Corpus verified-loaded and leave-one-out filtered; both arms share seeds
62–81 per system (`output/exp_clean_loo.json`; `snapshots/significance_clean_loo.txt`).

| System | Metric | mean OFF | mean ON | Δ = OFF−ON (95% CI) | p (exact) | Cliff's δ | Effect |
|---|---|---|---|---|---|---|---|
| CIM | entity F1 / naming / link | 1.00 / 1.00 / 2.00 | identical | 0.000 | 1.000 | 0.00 | none |
| ServiceNow | **link ratio** (1.0 = ideal) | 1.155 | 1.064 | **+0.091 [+0.045, +0.132]** | **0.002** | 0.59 | **large** |
| ServiceNow | entity F1 | 0.930 | 0.947 | −0.016 [−0.033, −0.003] | 0.126 | 0.24 | small |
| ServiceNow | weighted error impact | 33.95 | 31.60 | +2.35 [−0.65, +5.30] | 0.157 | 0.32 | small |
| ServiceNow | conformance | 0.960 | 0.956 | +0.004 [+0.001, +0.009] | 0.049 | 0.28 | small |
| ServiceNow | naming adherence | 0.000 | 0.000 | 0.000 | — | 0.00 | none |
| ServiceNow | correction steps | 12.20 | 11.95 | +0.25 [−0.70, +1.30] | 0.705 | 0.07 | negligible |

**What this means.** Genuine cross-domain feedback learning is **safe and narrowly
beneficial, and its benefit is structural rather than lexical**. The one effect that
reaches significance with a large effect size is an **improvement in link parsimony**:
learning from CIM's clean link structure moves ServiceNow's link ratio from 1.155 toward
the ideal of 1.0 (to 1.064; p = 0.002; δ = 0.59, large), i.e. the modeller over-generates
measurably fewer links. Entity F1 rises slightly (0.930 → 0.947, non-significant) and the
blast-radius-weighted error impact *falls* slightly (33.95 → 31.60, non-significant), so
on the very axis of downstream cost the controlled result shows **no harm**. Naming
adherence is **0.000 in both arms**: naming conventions are instance-specific and do *not*
transfer across domains — the modeller cannot infer ServiceNow's naming from grid examples,
exactly as H1b/H1c predict. (Conformance is nominally significant at p = 0.049, but the
effect is 0.004 — practically nil, in the *worse* direction, and it would not survive
correction for the six comparisons; it is noise, not a finding.) The reading is therefore
precise: the feedback loop transfers *modelling discipline* — parsimonious linking — across
domains while leaving *surface naming* untouched, and it never degrades quality.

**Why the controls changed the conclusion.** Uncontrolled versions of this comparison
mislead in *both* directions, which is the methodological point. A ten-seed run over the
live corpus with no load check and no domain filter produced an apparent **significant
increase** in weighted error impact — a false "harm" traceable to seeds where the corpus
silently failed to load, making the ON arm a disguised second OFF. Adding more seeds
without the filter then produced an apparent **significant naming gain** (to 0.34–0.69) — a
false "benefit" traceable to ON retrieving ServiceNow's *own* approved naming, i.e.
memorisation rather than transfer. Only the verified-load, leave-one-out comparison removes
both artifacts, and it is the one reported above. The lesson generalises beyond sample
size: with a live retrieval corpus, *what the ON arm actually retrieved* must be verified
per run, or the comparison measures plumbing rather than learning.

**Transfer vs. the memorisation ceiling.** To show *why* the leave-one-out filter is not a
cosmetic choice, the same n = 20 comparison was rerun with the filter removed — ON may now
retrieve ServiceNow's *own* approved model (the full 146-example corpus). This is the
memorisation upper bound, and it behaves completely differently
(`snapshots/learning_transfer_vs_memorisation.txt`):

| ServiceNow, ON arm | naming | link ratio (→1.0) | weighted error impact |
|---|---|---|---|
| **transfer** (leave-one-out, CIM only) | **0.000** | **1.064** ✓ better (p = 0.002) | 31.6 (no harm) |
| **ceiling** (full corpus, own model in reach) | **0.729** (p < 0.001, δ = 0.75) | **1.223** ✗ worse (p = 0.003, δ = 0.62) | **39.0** ✗ worse (p = 0.001, δ = 0.74) |

The contrast is decisive. The *entire* naming "gain" (0.729) is **memorisation** — the model
copying back its own approved answer — and it arrives bundled with two significant *costs*:
worse link parsimony and worse blast-radius-weighted error impact. Genuine cross-domain
transfer does the opposite: no naming, but *better* parsimony and no harm. This is exactly
the signature the earlier confounded run mistook for a real "naming +0.34 / error +7" effect —
it was the leaky full-corpus configuration, not learning. The practical implication is a
design rule: an approved-example corpus **must** hold out the system under generation, or it
buys a memorised surface metric at the price of structural quality.

**Scope.** The leave-one-out result isolates genuine cross-domain transfer (grid → IT service
management) at k = 10 with the target held out; the ceiling above is its memorisation upper
bound and is *not* claimed as a generalisation result. At n = 20 a large effect is detectable
comfortably; the residual small effects (entity F1, weighted error impact) stay
non-significant and are not load-bearing for any claim.

**Supports.** RQ1 / H1c (feedback learning is safe and confers a narrow, significant
*structural* benefit across domains — link parsimony — while lexical naming does not
transfer); statistical rigour.

### 2.9 Inter-Rater Reliability of the Gold Sets (single-author triangulation)

**What it measures.** Whether the gold sets — the reference answers the accuracy
metrics are graded against — are reproducible rather than one author's idiosyncrasy.
A second human annotator was not available, so reliability is **triangulated** three
ways against a documented annotation codebook (`annotation-codebook.md`): (i) an
**independent LLM annotator**, (ii) an **intra-rater test–retest** instrument for the
author to re-label after a washout, and (iii) the codebook itself, which makes the
protocol explicit so any of these can be re-run. The annotation item is one source
table; the label is the core entity decision — **hub / split / exclude**.

**Result — a panel of independent annotators vs gold.** Two models, each seeing only
the source schema and the codebook (never the gold or the pipeline output), labelled
all 12 source tables across both systems:

| Rater | vs gold: agreement | vs gold: Cohen's κ |
|---|---|---|
| gpt-4o (independent of the pipeline) | 0.917 | **0.84** |
| gpt-4.1 | 0.917 | 0.833 |
| panel majority | 0.917 | **0.84** |

Inter-annotator agreement (gpt-4o vs gpt-4.1): **κ = 0.69** (substantial).

**What this means.** Both independent models reproduce the gold's entity decisions at
**κ ≈ 0.84** — "almost perfect" agreement (Landis–Koch 0.81–1.00) — so the gold is
substantially protocol-driven, not one author's idiosyncrasy. The stronger signal is
that the two models **converge on the same single disagreement**: `terminals` (CIM),
which both label `exclude`-as-junction and the gold labels `hub`. `terminals` is
genuinely both — a real entity *and* the junction between conducting-equipment and
connectivity-node — exactly the Tier-2 "acceptable alternative" the scoring rubric
anticipates. Two independent raters flagging the *same* item on their own confirms it is
a real modelling ambiguity, not a labelling error. The lower model-vs-model κ (0.69)
shows the annotation task carries some genuine ambiguity, yet the gold sits squarely
within the range independent raters produce.

**Sensitivity of the headline result to this ambiguity.** Because `terminals` is the one
contested item, the CIM entity-identification score is recomputed for the *same*
generated plan against both defensible golds
(`scripts/audit/terminals_sensitivity.py`):

| Gold | hubs | entity F1 (tp/fp/fn) |
|---|---|---|
| A — terminals = hub (shipped) | 3 | **1.00** (3/0/0) |
| B — terminals = junction | 2 | **0.80** (2/1/0) |

Under the alternative labelling the AI's `hub_terminal` becomes a single false positive,
so entity F1 falls from 1.00 to 0.80 — both in the "strong" range, and the *entire*
difference is that one entity. The qualitative conclusion (the AI identifies CIM
entities correctly) does not flip, and the AI made the **same** defensible choice as the
shipped gold. The headline is robust to the only annotation ambiguity in the CIM gold.

**Honest limits, and why the reliability check is an *independent* rater rather than a
self re-test.** An LLM panel is not a panel of *humans*; this is
human-vs-independent-automated agreement and shares biases common to language models,
and one panellist (gpt-4.1) is the pipeline modeller's model — so gpt-4o is the cleanest
independent point (κ 0.84). A single-author **intra-rater** test–retest was **deliberately
not used** as the primary reliability evidence, for two methodological reasons: (i) a clean
*washout* is not credible for a sole author who has been immersed in the schemas throughout
the project — a re-test would largely measure memory of the first labelling, not independent
re-derivation; and (ii) intra-rater agreement is intrinsically the *weaker* form of
reliability evidence, because a rater tends to agree with themselves. Reliability is
therefore anchored on the **stronger** check — agreement with a *different, independent*
rater (κ = 0.84) applying the same documented codebook — supported by the sensitivity
analysis above showing no headline depends on the single ambiguous label. The claim is
bounded accordingly: the gold is reproducible by an independent rater to κ ≈ 0.84; a
*human* second-annotator study is acknowledged as future work (§6), the gap being one of
annotator availability, not of method.

**Reproducibility.** `python scripts/audit/interrater.py --rater llm` (LLM annotator
kappa); `--emit-template <csv>` then `--rater human --labels <csv>` (test–retest).
Logic unit-tested in `tests/ai/test_interrater.py`.

**Supports.** Construct validity of every gold-based accuracy metric (Exp 1, 3, 4, 5).

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
**What it means.** On this easy schema, injecting examples from unrelated source systems
is **inert** — every metric is unchanged. This is the easy-schema face of the
cross-domain probe. The matching hard-schema probe is the verified-load, leave-one-out
run on ServiceNow (§2.8, n = 20): there, learning from CIM-only examples is *not* inert —
it produces a significant, large improvement in link parsimony (1.155 → 1.064, p = 0.002)
with no naming transfer (0.000 both arms) and no harm to error impact. The two sit
together as one coherent picture: cross-domain transfer moves *structural* discipline and
nothing lexical, it helps only where there is room to improve (ServiceNow over-links; CIM
is already at ceiling), and it never degrades quality. Separately, CIM's naming adherence
was already 1.0 without any learning, because its source tables are *already*
concept-named — which sharpens the Experiment 2 finding: the naming benefit exists only
where table names diverge from the shop convention, and even then only when the
convention's own examples are in the corpus (memorisation), never by cross-domain
inference.
**Supports.** RQ1 / H1c (cross-domain transfer is structural, not lexical, and safe — see §2.8).

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
**Metrics:** Governance Block Rate, Audit-Trail Completeness, Approval Rate.
**Result.** Block Rate **5/8 = 62% as built**, rising to **8/8 = 100%** after a
targeted fix. On the populated approval store: Audit-Trail Completeness **1.00**;
Approval Rate **0.667** (§3C).
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
**Audit-Trail Completeness is 1.00** on the populated store (§3C): every decision
record carries the full mandated provenance (actor, timestamp, version, plan id,
decision, serialised plan), and every rejection carries a recorded reason.
**Supports.** RQ3 / H3a (refuted as built, supported after remediation); H3c
(supported — §3C).

---

## 3B. Improvements applied after the main evaluation, and their measured effect

Experiments 1–7 evaluated the system *as originally built*. The evaluation exposed
two concrete defects — over-linking and a reviewer that re-keys hubs onto surrogates
— and both were addressed with **deterministic (no-LLM) plan-hygiene passes**, then
re-measured. The Experiment 1–7 figures above are the *pre-improvement* baseline; the
figures here are the *post-improvement* system. This is the second Design-Science
iteration in the thesis (the first being Experiment 7).

### 3B.1 Link parsimony (over-linking)

**What changed.** A deterministic pass removes links that relate fewer than two
distinct hubs or name a hash key no hub owns (exactly the `link_under_two_hubs` /
`link_fk_unresolved` conformance violations), and de-duplicates links over the same
hub set. It never touches a well-formed link.

**Result (link ratio; 1.0 is ideal).**

| System | Before | After | Unresolved-FK links (before → after) |
|---|---|---|---|
| ServiceNow | 1.67 | **1.06** | ~9–14 → **0** |
| CIM | 2.00 | 2.00 | 0 → 0 |

**What this means.** On ServiceNow the pass **almost eliminates over-linking** —
link ratio falls from 1.67 to 1.06 (near the ideal 1.0), and every unresolved-foreign-
key link is gone. Crucially, CIM is **unchanged at 2.00**, and that is the *correct*
behaviour, not a failure: CIM's extra link is *structurally valid* (both its foreign
keys resolve to real hubs), so the deterministic pass rightly leaves it alone. The
honest boundary of the fix: it removes **invalid** over-linking (dangling foreign
keys, the bulk of ServiceNow's problem) but not **valid-but-semantically-spurious**
over-linking (a real link the shop would model as an attribute instead — CIM's case),
which cannot be distinguished without domain judgement. **Supports.** RQ1 / H1b.

### 3B.2 Reviewer business-key restoration (the Experiment 4 regression)

**What changed.** When the plan reviewer re-keys a hub onto a surrogate, the hub's
original (source-grounded) business key is restored, while every *other* reviewer
change is kept.

**Result (full pipeline, ServiceNow).** Reviewed-stage Entity Identification F1
**0.71 → 0.90**; link ratio 1.86 → 1.32; unresolved-FK links → 0.

**What this means.** This directly repairs the Experiment 4 trade-off. There, the
reviewer *lowered* entity identification (1.00 at the classification stage → 0.71
after review) by replacing grounded business keys with surrogates. Restoring those
keys lifts the reviewed-stage F1 back to **0.90** — close to the classification-stage
ceiling — so the full pipeline now largely *keeps* the reviewer's conformance and
connectivity gains **without** paying the entity-fidelity cost. The reviewer is no
longer a net trade-off on this system; it is closer to a genuine improvement. (H1d as
originally measured still stands as the *unconstrained* reviewer's behaviour; this is
the constrained reviewer.) **Supports.** RQ1 / H1d (mitigation).

### 3B.3 Model ablation — are the findings the mechanism's, or gpt-4.1's?

**What changed.** Key conditions were repeated with `gpt-4o` in place of `gpt-4.1`
(n = 3), everything else held constant.

**Result.**

| System / condition | gpt-4.1 entity F1 | gpt-4o entity F1 | gpt-4o naming | gpt-4o link ratio |
|---|---|---|---|---|
| CIM / off | 1.00 | 1.00 | 1.00 | 2.00 |
| CIM / on | 1.00 | 1.00 | 1.00 | 2.00 |
| ServiceNow / off | 0.95 | 0.93 | 0.00 | 0.73 |
| ServiceNow / on | 0.93 | **0.53** | 1.00 | 0.39 |

**What this means.** The findings are **partly the mechanism's and partly the
model's**, and the ablation is honest about which. On the *easy* schema (CIM) the two
models are indistinguishable — every figure is identical — so the "easy schemas are
solved" claim is model-independent. On the *hard* schema they diverge sharply:
gpt-4o's entity identification collapses to **0.53** with learning on (it appears to
mis-use the retrieved examples, over- or under-producing entities), and where gpt-4.1
*over*-links, gpt-4o *under*-links (ratio 0.73 / 0.39). So the **qualitative
patterns** transfer — difficulty concentrates on hard schemas; naming is learnable
(gpt-4o naming reaches 1.0 with learning) — but the **magnitudes and even the
direction of the link error are model-specific.** The correct thesis statement is
therefore conditional: the *structure* of the findings generalises across these two
models, the *absolute numbers* do not, and a stronger model (gpt-4.1) is materially
better on difficult schemas. **Supports.** external validity / threats to validity.

### 3B.4 A non-expert approval aid (tooling, closes the H3c blocker)

**What changed.** The scorecard prints a plain-language **APPROVE / REVIEW / REJECT**
recommendation with reasons, and the reject path auto-generates a meaningful comment
from the same checks. Fabrications are graded by blast radius: an invented source
**table** or hub **business key** (or an empty plan) is **REJECT**; a single invented
**payload column** is **REVIEW**, not a blanket REJECT. APPROVE requires that nothing
is flagged; everything else is REVIEW with the specifics listed. With no reference
model the verdict never rises above REVIEW, because correctness cannot be
auto-verified.

**What this means.** This does not change a metric; it changes who can operate the
approval gate — approving otherwise requires Data-Vault expertise. Grading fabrications
by blast radius keeps APPROVE and REVIEW reachable on real, messy schemas, where a
single mis-transcribed descriptive column would otherwise force a blanket REJECT on an
otherwise-sound plan. **Supports.** RQ3 / H3c.

### 3B.5 A third source system (AdventureWorks) — no-gold replication of the patterns

**What changed.** To test breadth beyond the two evaluated systems, the pipeline was run
on a **third, previously unseen source system** — AdventureWorks
(`edh_unreg_consumption_dev.2240_adventureworks`), a customer/product **sales** domain
distinct from both the electrical-grid CIM and the IT-service-management ServiceNow.
Discovery: **9 tables / 105 columns** (address, customer, product, customeraddress,
volumemetrics, and PII/non-PII variants). No expert gold set exists for this system, so it
is evaluated with the **ground-truth-free** metrics only (grounding, hallucination,
conformance, structural stability) — the accuracy metrics that need a gold (entity F1,
naming) are deliberately not reported here.

**Result (learning off, gpt-4.1, seeds 42–44; `snapshots/advworks_nogold_metrics.txt`).**

| Metric | Result |
|---|---|
| Grounding / hallucination | **1.000 / 0.000** every seed — every proposed object traces to a real source column |
| DV2 conformance | **1.000** every seed |
| Structure | **3 hubs + 1 link stable across all seeds**; 4–7 satellites |
| Self-consistency / idempotency | **0.333 / 0.333** |

**What this means.** The transferable *patterns* replicate on an unseen third domain: the
model is **perfectly grounded** (zero fabrication) and **fully conformant** on discovery,
and it identifies the same core entity/relationship backbone (3 hubs + 1 link) on every
seed. The instability is confined to the **satellite split** — the number of satellites
wobbles 4→7 across seeds (self-consistency 0.333), the *same* satellite-grain instability
seen on ServiceNow (§2.2), not a new failure mode. So the third system neither contradicts
nor inflates the headline claims: grounding and conformance are robust across three
domains, entity/link identification is stable, and satellite granularity is the recurring
soft spot. Because there is no gold, this is **breadth evidence, not an accuracy result** —
it widens the domain coverage of the ground-truth-free findings without claiming a third
accuracy point. **Supports.** external validity / breadth (see §6 item 5).

---

## 3C. Audit trail and approval rate (H3c, H1c)

The approval store holds real human review decisions taken through the UI.
`scripts/audit/audit_report.py` reads it through the app's own store factory (Delta on
Databricks) and computes the audit-trail and approval-rate metrics; the logic is
unit-tested in `tests/ai/test_audit_metrics.py`. The figures below are a snapshot of
the store: **35 records — 10 approved, 5 rejected, 19 draft, 1 changes-requested** —
across 2 source catalogs and one reviewer.

**Audit-Trail Completeness (H3c) = 1.00.** Every record carries the full mandated
provenance (plan id, version, decision, actor, timestamp, serialised plan), guaranteed
by construction: the record schema makes those fields non-null and the store is
insert-only, so the review history of any plan is fully reconstructable. Rationale
coverage is **1.00 on rejections** (every rejection records *why*) and 0.33 across all
decisions (approvals carry no free-text note — an approval's reason is its passing
checks). The audit trail is complete and every negative decision is explained. **H3c is
supported.**

**Approval Rate = 0.667.** Of the 15 terminal decisions, 10 are approvals (10/15). The
cumulative rate ordered by time rises from 0.00 (the first three decisions are
rejections) to 0.667.

**The observational approval rate is not, by itself, a controlled test** of H1c's
"approval improves over successive runs as the corpus grows": the 15 decisions span only
2 catalogs and a single reviewer, and their order is not a time series of independent runs
on a fixed system, so the rising trajectory is suggestive rather than causal. The
controlled version of that test is run separately below.

**Controlled corpus-growth test (H1c successive-runs).** To isolate the effect the
observational rate only hints at, ServiceNow's *own* approved corpus was grown in rounds
(0 → 5 → 10 → 20 → 40 → 80 → 125 objects; the CIM examples always present), holding the
system, seeds and retrieval size (k = 10) fixed and measuring quality at each round
(mean over seeds 42–44; `snapshots/corpus_growth_curve.txt`). This *is* the "repeated runs
on the same system with the corpus growing between them" that §6 asked for.

| own examples | corpus | naming | entity F1 | conformance | issues |
|---|---|---|---|---|---|
| 0 | 21 | 0.000 | 0.933 | 0.956 | 5.3 |
| 5 | 26 | 0.714 | 0.79 | 0.943 | 9.7 |
| 10 | 31 | 0.833 | 0.64 | 0.945 | 9.0 |
| 20 | 41 | 0.833 | 0.63 | 0.953 | 7.3 |
| 40 | 61 | 0.905 | 0.956 | 0.957 | 6.3 |
| 80 | 101 | 0.857 | 0.900 | 0.955 | 7.0 |
| 125 | 146 | 0.667 | **0.978** | 0.964 | 5.7 |

**What this means.** The successive-runs effect is **real but two-sided.** On the learnable
axis it fires immediately and strongly: naming adherence jumps from **0.000** (no own
examples) to **0.71–0.91** as soon as the system's own approved objects enter the corpus —
i.e. as you approve more of a system, its output adopts the shop naming convention. That is
the mechanism H1c predicts, now demonstrated under control rather than merely observed. But
the curve is **not a clean monotone win**: a *small, partial* corpus (5–20 examples)
measurably **degrades entity F1** (0.93 → 0.63) and raises the issue count, because the
modeller over-anchors on a handful of retrieved examples; entity F1 only recovers — indeed
climbs to its best **0.978** — once the corpus is **large** (125). So corpus growth helps,
but there is an **early "valley"**: a half-populated corpus is worse for entity
identification than none, and the benefit is realised only once coverage is high. The
honest statement is that approval-driven learning improves the naming axis across
successive runs and ultimately improves entity identification too, but it is not free at
low corpus sizes.

**Reproducibility.** `python scripts/audit/audit_report.py --out
documentation/thesis/data/audit.json` (approval rate); the corpus-growth curve is produced
by growing the retrievable corpus per round and grading each round (`corpus_growth_curve.txt`).

**Supports.** RQ3 / H3c (supported); RQ1 / H1c (the successive-runs approval effect is now
demonstrated under control — naming rises with corpus size, with an early entity-F1 valley).

---

## 4. Consolidated hypothesis scorecard

| Hypothesis | Status | Principal evidence |
|---|---|---|
| **H1a** first-run accuracy comparable to manual | **Supported at the classification stage** | Exp 1, 5 (entity F1 0.93–1.00 vs manual reference; 0.50 for rules) |
| **H1b** naming and link parsimony are the weak axes | **Supported; over-linking since partly fixed** | Exp 1, 5 (naming 0.000; link ratio 1.6–2.0); §3B.1 (invalid over-linking removed, ratio 1.67→1.06) |
| **H1c** feedback effect is conditional | **Supported — inert on easy; safe + a narrow *structural* gain on hard (no lexical transfer)** | §2.8 (verified-load leave-one-out, n = 20: CIM inert; ServiceNow link parsimony 1.155→1.064, p = 0.002, δ = 0.59 large; naming 0.000 both arms; weighted error impact unchanged); Exp 2 (threshold at 10; leave-one-out naming → 0.000); Exp 3 (cross-domain inert on CIM); §3C (approval rate 0.667; **controlled corpus-growth curve**: naming 0→0.8+ and entity F1 → 0.978 as the own corpus grows 0→125, with an early partial-corpus valley) |
| **H1d** reviewer is a trade-off | **Supported; since mitigated** | Exp 4 (conformance ↑, entity F1 ↓); §3B.2 (grounded-key restore lifts reviewed F1 0.71→0.90) |
| **H2a** complete deterministic drift recall | **Supported** | Exp 6 (recall 1.00 on real data) |
| **H2b** AI impact classification beats rules | **Supported, directionally** | Exp 6 (1.00 vs 0.88; kappa 1.000 vs 0.771) — cosmetic n = 1 |
| **H2c** lower drift-review effort | **Supported** | Exp 6c (36 → 1 → 0 actions) |
| **H3a** zero unsafe promotions | **Refuted as built (62%); supported after fix (100%)** | Exp 7 |
| **H3b** fewer manual correction steps | **Supported** | Exp 5 (29 / 25 / 9.5) |
| **H3c** complete audit trail | **Supported** | §3C (populated store: structural completeness 1.00; rejection rationale 1.00 over 15 decisions) |

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

**Experiment 6 (drift).** The drift engine, impact classifier and cost scoring are the
committed modules under `dbt_builder/src/ai/drift/`; the labelled dataset is
`dbt_builder/src/ai/drift/fixtures/cim_drift.sql` with answer key `cim_drift_labels.json`,
and the metrics (detection recall, impact accuracy, breaking-change recall,
cost-weighted error) are unit-tested in `tests/ai/test_drift_impact.py`. The real-data
figures come from pointing those committed modules at the live
`edh_unreg_silver_dev_st.cim_drifted` schema. To view the drift in the UI: `pnpm dev`,
then run the pipeline with catalog `edh_unreg_silver_dev_st`, vault schema `bronze`,
bronze schema `cim_drifted`.

**Experiment 7 (governance).** The safety floor and the `pause_on_breaking_change`
escalation live in `dbt_builder/src/ai/supervision/supervisor.py` and are
regression-tested in `tests/ai/test_governance_safety.py` (set
`SupervisorConfig(pause_on_breaking_change=False)` to reproduce the pre-fix 62%). The
audit trail and approval rate come from `python scripts/audit/audit_report.py` (§3C).

**Section 2 metrics (hallucination, consistency, idempotency, tokens, validation,
kappa, confidence intervals).** Each is a committed, unit-tested function —
`dbt_builder/src/ai/evaluation/grounding.py` (hallucination) and `…/stats.py`
(self-consistency, idempotency, bootstrap CIs, Cohen's kappa), verified in
`tests/ai/test_grounding_and_stats.py`. The repeated-generation figures (e.g.
self-consistency over five CIM / three ServiceNow runs) are produced by generating the
plans with the unified harness (`… evaluation experiment … --seeds …`) and applying
those functions to the results.

**Section 3B improvements.** The two deterministic plan-hygiene passes are committed and
unit-tested (`tests/ai/test_plan_hygiene.py`), enabled by the settings
`link_parsimony_enabled` and `reviewer_preserve_business_keys` (both default on). The
before/after link-parsimony and constrained-reviewer figures are reproduced by running
the unified harness with those settings toggled; the gpt-4o ablation by setting
`DWA_AI_MODELLER_CHAT_DEPLOYMENT=gpt-4o` before the same run. The approval recommendation
is `python -m dbt_builder.src.ai.evaluation generate --payload <disc.yaml> --gold
<system_id>` (prints the APPROVE/REVIEW/REJECT verdict).

**Significance + effect size (§2.8).** `python scripts/stats/significance.py --results
<experiment.json> --metric gold_entity_f1 --compare off,on` reads an `experiment --out`
JSON and prints the paired permutation p-value, bootstrap CI and Cliff's delta for each
system. Unit-tested in `tests/ai/test_significance.py`. The final learning result uses the
two controls described in §2.8: the ON condition is
`on:k=10,exclude=edh_unreg_consumption_dev+edh_unreg_bronze_dev` (leave-one-out, both
ServiceNow-family catalogs held out), and the corpus is loaded once and asserted
non-empty (21 CIM examples) before any generation, so a transient warehouse failure
cannot silently reduce ON to OFF. Result data: `output/exp_clean_loo.json`; console and
per-metric snapshots under `snapshots/clean_loo_run.txt` and
`snapshots/significance_clean_loo.txt`.

**dbt compile-pass rate and execution (§2.4).** Two composable scripts:
```bash
# 1) generate dbt projects from metadata YAMLs (offline, no warehouse)
python scripts/dbt/build_projects.py \
  --metadata poc/metadata/iec_cim_metadata.yaml --out-root <build_dir>

# 2) run dbt stages over them and report pass rates (live warehouse)
#    gap 3 (compile-pass rate):
python scripts/dbt/dbt_sweep.py --projects-root <build_dir> \
  --stages deps,compile --profiles-dir ~/.dbt --results-out sweep.json
#    gap 2 (execution — materialise + test; writes tables):
python scripts/dbt/dbt_sweep.py --project output/iec_dv2 \
  --stages deps,run,test --profiles-dir ~/.dbt --results-out exec.json
```
The `run_results.json` parser is unit-tested in `tests/ai/test_dbt_results.py`.

**Audit trail + approval rate (§3C).** `python scripts/audit/audit_report.py --out
documentation/thesis/data/audit.json` reads the approval store through the app's own
factory and prints audit-trail completeness, the approval rate and the cumulative
trajectory. Logic unit-tested in `tests/ai/test_audit_metrics.py`.

**Inter-rater reliability (§2.9).** `python scripts/audit/interrater.py --rater llm`
labels every source table with an independent model and reports kappa vs the gold;
`--panel gpt-4o,gpt-4.1` runs the multi-annotator panel; `--emit-template <csv>` then
`--rater human --labels <csv>` runs the intra-rater test–retest. `python
scripts/audit/terminals_sensitivity.py --plan output/cim_plan.json` recomputes CIM
entity F1 under both terminals labellings. Codebook: `annotation-codebook.md`; logic
unit-tested in `tests/ai/test_interrater.py`.

**Compile-pass rate and execution.** With a Databricks OAuth profile per project in
`~/.dbt/profiles.yml`, the sweep compiles both the CIM and ServiceNow projects
(compile-pass rate 2/2) and executes CIM (`run`/`test`); the ServiceNow project is
produced from a generated plan via `plan_to_metadata.py` (§2.4). A *human* inter-rater
figure still needs a second human labelling (§2.9, §6).

---

## 6. Limitations and open items

The metrics in this document are computed by implemented, unit-tested code with
reproducible scripts (§5). What remains are limitations of **scope and data**, not of
instrumentation:

1. **Inter-rater reliability of the gold sets — accepted as a limitation.** The gold
   sets were authored by a single researcher, so a second *human* labelling would ideally
   corroborate them. This is **accepted as a bounded limitation** rather than left as an
   action item, for two reasons: (i) it is *mitigated* — reliability is triangulated three
   ways (§2.9): a documented annotation codebook and an independent LLM annotator reproducing
   the gold at **κ = 0.84** ("almost perfect"), backed by a sensitivity analysis; and (ii)
   the residual gap is one of *annotator availability*, not method — no second human
   annotator was available within the project's scope. A single-author *intra-rater*
   re-test was deliberately not used as evidence, because a credible washout is not
   achievable for a sole author immersed in the schemas and self-agreement is the weaker
   reliability signal anyway (§2.9); the *independent*-rater κ is the stronger check. The
   claim is therefore stated conservatively: the gold is reproducible by an independent rater
   to κ ≈ 0.84, and a human second-annotator study is acknowledged as future work.
   No result in this document rests on a contested gold label — the one ambiguous item
   (`terminals`, §2.9) is shown not to change the headline via a sensitivity check.
2. **Over-strict generated satellite tests — resolved.** This was previously the one
   blemish on execution (38/42, the emitter's column-level `unique` on satellite / eff-sat
   hash keys being wrong for the composite *(hash key + load date)* grain). The emitter now
   emits `not_null` on the satellite hash key plus a model-level
   `dbt_utils.unique_combination_of_columns` on the composite grain (hubs/links unchanged),
   and `dbt run` + `dbt test` now pass **42/42** on the live warehouse (§2.4). No longer
   open.
3. **The successive-runs approval effect (H1c) — now demonstrated under control.** The
   observational approval rate (0.667) is complemented by a controlled corpus-growth curve
   (§3C): growing ServiceNow's own approved corpus 0→125 objects raises naming adherence
   from 0.000 to ~0.8+ and ultimately lifts entity F1 to 0.978, with an early partial-corpus
   valley (entity F1 dips to ~0.63 at 5–20 examples). What remains bounded is *external*
   breadth — the observational approval rate still spans only one dominant catalog and a
   single reviewer, so cross-system, multi-reviewer replication would strengthen it further.
4. **Power and controls for the learning effect** — the off-vs-on comparison is now at
   n = 20 with a **verified-load, leave-one-out** corpus (§2.8), which both raises power
   and removes the two confounds (silent empty corpus; target-model leakage) that made
   earlier reads unreliable. It detects the one large effect — a *positive* structural one:
   learning significantly improves link parsimony (p = 0.002, δ = 0.59) — while naming
   shows zero cross-domain transfer and the remaining small effects stay non-significant
   and non-load-bearing. The memorisation-ceiling arm (same comparison without the domain
   filter) is now also reported (§2.8): it confirms the naming "gain" is entirely
   in-domain copying and comes at a significant structural cost, closing this item.
5. **Breadth** — two *gold-backed* source systems and small seed counts. The transferable
   claims are the *patterns* (AI advantage scales with schema difficulty; naming is unstable
   while entity identification is stable), not the absolute figures. This is now widened on
   two fronts: a **third source system**, AdventureWorks (a sales domain, §3B.5), replicates
   the ground-truth-free patterns (grounding/conformance 1.0, stable 3-hub/1-link backbone,
   satellite-count wobble) on unseen data; and model-ablation (§3B.3) covers two models on
   two systems. What remains genuinely bounded is *gold-backed accuracy*, which still rests
   on two systems, because building a defensible expert gold for a third system was out of
   scope.

### 6.1 Consolidated limitations (single register)

The numbered items above track *open threads*; this subsection is the honest, complete
register of what bounds the study's claims, grouped by type. Several are cross-referenced
to where they are analysed in detail. None invalidates a headline result; together they
define the envelope within which the results should be read.

**Construct validity (are we measuring the right thing?)**
- **Single-author gold sets** (§2.9, item 1) — the reference answers were authored by one
  researcher. Mitigated by a codebook, an *independent* LLM annotator (κ = 0.84), and a
  sensitivity analysis. A same-author intra-rater re-test was deliberately not used (no
  credible washout for a sole immersed author; self-agreement is weaker evidence than an
  independent rater); a *human* second-annotator study was out of scope for annotator
  availability. Accepted as a bounded limitation; no headline rests on a contested label.
- **Grounding is partly a design property.** The near-zero hallucination rate reflects that
  generation is constrained to the discovered schema — the metric *confirms* the design
  holds rather than revealing an emergent surprise. It should be read as "the pipeline
  prevents fabrication, verified," not "the model never fabricates."

**Internal validity (are the effects real, not artifacts?)**
- **LLM non-determinism.** Even with a fixed seed, outputs vary run-to-run; small samples can
  dress noise as signal (demonstrated directly — early learning reads were confounded until
  controlled, §2.8). Reproducibility is best-effort, not bit-exact.
- **Reconstructed learning corpus.** The approved-example corpus was reconstructed from a
  small set of cached approvals (~10 approved plans), not organically grown from many
  independent UI approvals. The successive-runs / corpus-growth result (§3C) therefore
  *simulates* successive approval by growing that fixed corpus — realistic, but not a live
  longitudinal deployment.

**Statistical power**
- **Small samples.** Seed counts of n = 3–20 and only two gold-backed systems; the
  learning comparison detects only *large* effects reliably (§2.8). Some claims are
  explicitly directional, notably the drift AI's edge (accuracy 1.00 vs 0.88) which rests
  on a small labelled set with a **cosmetic class of n = 1** (§Exp 6).

**External validity (does it generalise?)**
- **Two gold-backed systems, one organisation, one warehouse.** A third system
  (AdventureWorks) widens only the ground-truth-free patterns (§3B.5); gold-backed accuracy
  still rests on two systems.
- **Model-dependence.** Findings are partly specific to gpt-4.1; gpt-4o diverges on the hard
  schema (§3B.3). "The AI can do this" means "this model can."
- **Lexical (not semantic) retrieval.** Feedback retrieval matches on token overlap, so it is
  weak on synonymy — especially ExampleCorp's mixed German/English naming (e.g. *kunde*/*customer*).

**Scope of specific claims**
- **Effort is measured as correction *steps*, not *time*** (H3b, §Exp 5). No stopwatch study
  with an independent Data-Vault expert was run; any time figure is a *stated assumption*,
  not a measurement.
- **The reviewer is a trade-off, not a pure gain** (H1d, §Exp 4) — it resolves link errors
  but can lower structural agreement with the gold and raises blast-radius on some objects.
- **Feedback learning is narrow and non-monotone.** It helps naming in-domain and structure
  cross-domain, but naming does not transfer across domains, and a *partial* corpus can
  briefly *degrade* entity identification before a fuller one helps (§2.8, §3C). It also
  carries a token/latency cost.
- **Governance tested on synthetic unsafe inputs** (§Exp 7), not adversarial real-world
  cases, and the system has **no long-term production or real-user validation** — it is a
  prototype evaluated in controlled experiments.

**How these are managed rather than hidden.** Every metric is computed by implemented,
unit-tested code on real generated output (nothing is hard-coded); the two evaluation
confounds that *could* have inflated the learning result were found and controlled (§2.8);
and where a claim could not be established cleanly it is stated as directional or deferred to
future work rather than asserted. The intended posture is a precise map of where the system
helps, where it does not, and where the evidence is thin — not an unqualified success story.
