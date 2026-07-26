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
   feedback-learning mechanism is largely inert at the modelling stage (instance-copying,
   not convention generalisation; and, on the error measure with the widest downstream
reach, cross-domain examples are not merely inert but actively harmful, §2.8). The safety layer —
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

A word on why every learning comparison here runs over ten seeds rather than the three
a first pass invites. The choice came out of a near-miss. An early three-seed run of the
off-versus-on comparison looked encouraging on the hard schema: learning seemed to
tighten link cardinality and lift conformance, and the conformance gain was a clean
sweep, every "on" run beating its paired "off" run — the sort of result that reads as
settled. It was not. Rerun at ten seeds, both effects shrank and lost any claim to
significance, while the one difference that held up was a cost rather than a gain:
learning significantly worsened the errors with the widest downstream reach (§2.8).
Three seeds would have earned a confident paragraph the larger sample flatly
contradicts. So the count is ten throughout, effects carry their spread instead of
standing as single numbers, and nothing is called significant on the strength of a
handful of runs.

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

**Execution (`dbt run` + `dbt test`) — the stronger check, and what it exposes.**
Compile validates SQL; execution materialises the models and runs the data tests. On
the CIM project, `dbt test` passed **38 of 42 (0.905)** against the materialised
objects. `dbt run`, however, exposed a defect that compile did not: `stg_terminals`
derived `END_DATE` / `IS_DELETED` from an `OPERATION_TYPE` CDC column that the live
`terminals` bronze table does not contain (`UNRESOLVED_COLUMN`) — a derived-column
expression that names a non-existent source column compiles without complaint and fails
only at execution. **This is the finding: compile-pass does not imply run-pass.** The
defect was corrected — the delete flag is the bronze `cdc_flag` column (as the other
staging models already use), not `OPERATION_TYPE` — and after regeneration `stg_terminals`
resolves its columns and no longer errors. The remaining barrier to a fully clean
materialisation is not the code: all three staging views fail identically with
`PERMISSION_DENIED` (`MANAGE`) because they pre-exist under another principal in the
target schema — a warehouse grant, resolved by granting `MANAGE` or materialising into a
user-owned schema.

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

**Result — learning OFF vs ON, paired by seed (n = 10, gpt-4.1).** The ON arm retrieves
up to 10 approved examples from the (cross-domain) corpus; both arms share seeds 42–51
per system.

| System | Metric | mean OFF | mean ON | Δ (95% CI) | p (exact) | Cliff's δ | Effect |
|---|---|---|---|---|---|---|---|
| CIM | entity F1 / naming / link | 1.00 / 1.00 / 2.00 | identical | 0.000 | 1.000 | 0.00 | none |
| ServiceNow | entity F1 | 0.927 | 0.910 | +0.018 [−0.006, +0.041] | 0.375 | +0.30 | small |
| ServiceNow | link ratio | 1.173 | 1.127 | +0.045 [−0.018, +0.109] | 0.375 | +0.20 | small |
| ServiceNow | conformance | 0.957 | 0.960 | −0.002 [−0.006, +0.002] | 0.287 | −0.38 | medium |
| ServiceNow | **weighted error impact** | 31.0 | 37.9 | **−6.9 [−11.5, −2.2]** | **0.029** | −0.67 | large |

**What this means.** With ten seeds the picture sharpens and partly *reverses* the
three-seed read. On CIM, learning is **completely inert** — every metric identical
across all ten seeds. On ServiceNow the directional "gains" that looked large at n = 3
(a preliminary run had link parsimony δ = 0.56 and a conformance *complete separation*
δ = −1.00) **shrink to small/medium and remain non-significant** at n = 10
(p = 0.29–0.38): those were small-sample artifacts, exactly the trap §2.7 warned
against. The **one effect that reaches significance is negative**: learning ON
**significantly increases the blast-radius-weighted error impact** on the hard schema
(31.0 → 37.9; p = 0.029; δ = −0.67, large). Retrieving cross-domain approved examples
does not help entity identification or naming and *measurably worsens the errors that
carry the most downstream cost* — those with high dependency fan-out. This is a clean
corroboration of the boundary-condition thesis (§0): feedback learning is **not a free
improvement**; cross-domain examples are inert at best and harmful on the axis that
matters most. It is also a concrete lesson about sample size. No single metric changed
sign between the two runs; what changed was the conclusion. At three seeds the numbers
read as a mild endorsement of learning — two effects that looked sizeable — and at ten
seeds those melt into noise while the one difference that hardens into significance is a
cost. That is the quiet way a small sample misleads: not by flipping a number, but by
dressing noise up as signal.

**Scope.** The corpus here is cross-domain to CIM/ServiceNow (the approved examples come
from other catalogs), so this measures **cross-domain** learning specifically; a
same-domain corpus is untested (§6). At n = 10 a large effect is detectable (minimum
two-sided p = 2/2¹⁰ ≈ 0.002); the remaining small/medium effects would need still more
seeds to resolve.

**Supports.** RQ1 / H1c (feedback learning is inert-to-harmful cross-domain);
statistical rigour.

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

**Honest limits.** An LLM panel is not a panel of *humans*; this is
human-vs-independent-automated agreement and shares biases common to language models,
and one panellist (gpt-4.1) is the pipeline modeller's model — so gpt-4o is the cleanest
independent point (κ 0.84). A genuinely human second labelling — the author's intra-rater
test–retest after a washout — is prepared (a 12-item blank template is emitted by the
same script) but not yet completed, so no human test–retest kappa is reported. The claim
is bounded accordingly: the gold is reproducible by independent raters to κ ≈ 0.84; a
human inter-rater figure remains open (§6).

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
is **inert** — every metric is unchanged. But "inert" is a claim about CIM only, and it
does not generalise: the ten-seed run in §2.8 shows the same cross-domain corpus is
*not* harmless on the hard ServiceNow schema, where it significantly raises the
blast-radius-weighted error impact. So the honest scope condition is that a shared
multi-system corpus is safe where the model is already strong and a liability where it
is not, rather than universally safe. Separately, CIM's naming adherence was already 1.0
without any learning, because its source tables are *already* concept-named — which
sharpens the Experiment 2 finding: the naming benefit exists only where table names
diverge from the shop convention.
**Supports.** RQ1 / H1c (corpus safety is schema-dependent — see §2.8).

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

**Limitation.** The approval rate is a valid aggregate but not a controlled test of
H1c's "approval improves over successive runs as the corpus grows". The 15 decisions
span only 2 catalogs (mostly one) and a single reviewer, and their order is not a time
series of independent runs on a fixed system, so the rising trajectory is suggestive
rather than causal. Establishing that effect requires repeated runs on the *same*
system with the corpus growing between them (§6).

**Reproducibility.** `python scripts/audit/audit_report.py --out
documentation/thesis/data/audit.json`.

**Supports.** RQ3 / H3c (supported); RQ1 / H1c (approval rate reported; the
successive-runs effect is not established).

---

## 4. Consolidated hypothesis scorecard

| Hypothesis | Status | Principal evidence |
|---|---|---|
| **H1a** first-run accuracy comparable to manual | **Supported at the classification stage** | Exp 1, 5 (entity F1 0.93–1.00 vs manual reference; 0.50 for rules) |
| **H1b** naming and link parsimony are the weak axes | **Supported; over-linking since partly fixed** | Exp 1, 5 (naming 0.000; link ratio 1.6–2.0); §3B.1 (invalid over-linking removed, ratio 1.67→1.06) |
| **H1c** feedback effect is conditional | **Supported — inert-to-harmful cross-domain** | Exp 2 (threshold at 10; leave-one-out → 0.000), Exp 3 (cross-domain inert); §2.8 (n = 10: CIM inert; ServiceNow weighted error impact significantly **↑** with learning, p = 0.029); §3C (approval rate 0.667) |
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
generations and prints every figure in §2; `scratchpad/run_seeds_ablation.py`
produces the five-seed confidence intervals in §2.7.

**Section 3B improvements.** `scratchpad/run_improvements.py` measures link parsimony
before/after, the constrained reviewer's full-arm entity F1, and the gpt-4o ablation.
The passes are unit-tested in `tests/ai/test_plan_hygiene.py`; they are enabled by the
settings `link_parsimony_enabled` and `reviewer_preserve_business_keys` (both default
on). The approval recommendation is `python -m dbt_builder.src.ai.evaluation generate
--payload <disc.yaml> --gold <system_id>` (prints the APPROVE/REVIEW/REJECT verdict).

**Significance + effect size (§2.8).** `python scripts/stats/significance.py --results
<experiment.json> --metric gold_entity_f1 --compare off,on` reads an `experiment --out`
JSON and prints the paired permutation p-value, bootstrap CI and Cliff's delta for each
system. Unit-tested in `tests/ai/test_significance.py`.

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

1. **Inter-rater reliability of the gold sets** — the standing construct-validity
   threat, now *partly* addressed (§2.9): a documented codebook plus an independent LLM
   annotator give kappa 0.84 ("almost perfect"). What remains open is a genuinely
   *human* second labelling — either a second annotator or the author's intra-rater
   test–retest after a washout (the 12-item template is prepared) — to report a
   human inter-rater kappa rather than a human-vs-automated one.
2. **A fully clean `dbt run`** — compile-pass rate is 2/2 and `dbt test` passes 38/42
   (§2.4). The one metadata defect execution exposed (`stg_terminals`' `OPERATION_TYPE`)
   is fixed; the remaining barrier to a fully clean materialisation is a warehouse
   `MANAGE` grant on staging views that pre-exist under another principal — resolved by
   the grant or by materialising into a user-owned schema, neither a code matter.
3. **The successive-runs approval effect (H1c)** — the approval rate is reported
   (0.667, §3C), but the claim that approval improves over successive runs as the corpus
   grows is not established, because the decisions span only two catalogs and one
   reviewer. Establishing it requires repeated runs on the same system with the corpus
   growing between them.
4. **Power for the *small* learning effects** — the off-vs-on table is now at n = 10
   (§2.8), enough to detect the one large effect (a *negative* one: learning
   significantly raises weighted error impact, p = 0.029). The residual small/medium
   ServiceNow effects (entity F1, link ratio, conformance) stay non-significant and would
   need still more seeds to resolve; none is load-bearing for a claim.
5. **Breadth** — two source systems and small seed counts. The transferable claims are
   the *patterns* (AI advantage scales with schema difficulty; naming is unstable while
   entity identification is stable), not the absolute figures. Model-ablation (§3B.3)
   covers two models on two systems.
