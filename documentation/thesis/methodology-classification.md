# Research Methodology — Classification

> **Purpose.** The agreed classification of this thesis's research type, for the
> methodology chapter. These labels are not mutually exclusive — a thesis is
> described by a *stack* across several axes (purpose, approach, design, setting).

## Headline

This is **applied Design Science Research (DSR)**: the contribution is a **built
software artifact** (a multi-agent LLM system for Data Vault automation), evaluated
through **controlled, comparative, benchmarking experiments** using predominantly
**quantitative** metrics, with a light **qualitative** interpretive layer — i.e.
**quantitative-dominant mixed methods**.

One-sentence form for the chapter:

> "Following the Design Science Research paradigm (Hevner et al., 2004; Peffers et
> al., 2007), this work designs, builds, and evaluates a software artifact that
> addresses a real data-engineering problem, using controlled experimental,
> comparative, and benchmarking evaluation."

The six project phases (problem → artifact design → build → evaluate → iterate →
communicate) map directly onto the Peffers et al. (2007) DSR process model.

## Classification across axes

| Axis | Label | Justification |
|---|---|---|
| **Paradigm / purpose** | Design Science Research; development-based; **applied** | The core deliverable is a built artifact solving ExampleCorp's real DWA problem — not basic or theoretical research |
| **Evaluation design** | **Experimental** | Independent variables (learning on/off, retrieval k, arm) are manipulated; dependent variables (entity_f1, correction steps, conformance) are measured; controls used (leave-one-out, seeds, ablation) |
| **Approach** | **Quantitative**, **empirical** | Conclusions rest on measured runs, not reasoning alone |
| **Comparison** | **Comparative**, **benchmarking** | Three-arm comparison (manual / deterministic / full) graded against a gold-standard reference |
| **Blend** | **Mixed methods** (quantitative-dominant) | Small qualitative layer: error-taxonomy analysis and the interpretive "where does the AI add value" characterisation |
| **Setting** | Case-study *flavour* | Applied to specific case systems (ServiceNow, IEC-CIM) at ExampleCorp — not a classic interpretive case study |

## What it is *not* (to pre-empt mislabels)

- **Not simulation research** — the LLM calls and system runs are real, not a
  simulated model of a system.
- **Not a systematic review / meta-analysis** — those study existing literature;
  the literature review here is a *component*, not the research type.
- **Not action / participatory / grounded-theory / purely-qualitative** — there is
  no participant co-design cycle, no qualitative theory-building as the method.

## Anchor references (verify author/year/venue before citing)

- Hevner, March, Park & Ram (2004), *Design Science in Information Systems
  Research*, MIS Quarterly.
- Peffers, Tuunanen, Rothenberger & Chatterjee (2007), *A Design Science Research
  Methodology for Information Systems Research*, JMIS.
- March & Smith (1995); Gregor & Hevner (2013) — for artifact types and positioning.

> **Caveat.** Research-type taxonomies vary by university/department. Confirm your
> program's preferred framing — some headline this as "experimental research" with
> DSR as the wrapper, others require "Design Science Research" explicitly. Both
> descriptions are defensible for this build-and-measure CS/IS thesis.

## Evidence that this is genuinely DSR (not just "we built a thing")

Experiment 7 is a complete, documented **design → evaluate → improve → re-evaluate**
cycle, which is the defining move of Design Science Research: the evaluation
measured the governance layer at a **62% block rate**, diagnosed the defect (the
gate never consulted the per-change risk the diff engine already computed), a
minimal fix was applied, and re-measurement gave **100%** — verified on the real
drifted dataset (pre-fix PASS → post-fix PAUSE). Cite this as the DSR iteration
rather than presenting the artifact as if it were correct first time.

---

# Evaluation metrics — full catalogue

Every metric used across Experiments 1–7, what it *means*, where it is implemented,
and which hypothesis it serves. All are computed by code in
`dbt_builder/src/ai/evaluation/` and `dbt_builder/src/ai/drift/`; none are
hand-assigned.

## A. Model quality against the expert reference (gold)

| Metric | What it means | Where | Hypothesis |
|---|---|---|---|
| **entity_f1** (+ precision, recall) | Did the system find the **right business entities with the right keys**? Hubs are matched to the gold by `(source_table, business_keys)` — deliberately **naming-independent**, so "found the right thing" is separated from "named it right". | `gold.py` | H1a, H1b |
| **naming_adherence** | Of the entities it got *right*, the fraction that use the shop's **concept name** (`hub_company`) rather than a raw table name (`hub_core_company`). The clean place for feedback learning to show an effect. | `gold.py` | H1b, H1c |
| **link_ratio** | Produced ÷ expected links. **>1 = over-linking** (inventing relationships), **<1 = under-linking** (missing them). 1.0 is ideal. | `gold.py` | H1b |
| **correction_steps** (+ breakdown) | **Objective human-effort proxy**: the structural edits (hub add/delete/rename, link/satellite count deltas) needed to bring a produced plan up to the gold. Replaces an un-runnable timing study. | `gold.py` | H3b |
| **build_from_scratch_steps** | The manual arm's baseline effort — every gold object created from nothing. | `gold.py` | H3b |

## B. Convention conformance (needs **no** ground truth)

| Metric | What it means | Where | Hypothesis |
|---|---|---|---|
| **conformance_score** | Fraction of mechanical **DV2 convention checks** passed (naming prefixes, `HK_`/`HD_` conventions, link ≥2 hubs, satellite has a parent + payload, no key leakage into payload…). Measures *well-formedness*, not semantic correctness. | `conformance.py` | H1d |
| **issue_count / issues_by_type** | The **error taxonomy** — a typed histogram over 10 `IssueType`s (`naming`, `surrogate_business_key`, `link_fk_unresolved`, `satellite_orphan`, `payload_key_leak`, `hub_without_satellite`, …). Turns "quality" into a diagnosable profile. | `conformance.py` | H1d |
| **TaxonomyShift** (resolved / introduced / persisted, `net_resolved`) | How the error profile **changes between two stages** (modeller → reviewer): which categories a stage fixes, which it *causes*. This is what revealed the reviewer trade-off. | `study.py` | H1d |

## C. Severity weighting (blast radius)

| Metric | What it means | Where | Hypothesis |
|---|---|---|---|
| **max_blast_radius** | The largest downstream dependency fan-out of any object (a hub with many satellites/links has a big radius). | `blast_radius.py` | H1d |
| **weighted_error_impact** | Issues **weighted by fan-out** — an error on a high-dependency hub costs more than one on a leaf. Crucial because it can move *opposite* to raw issue count (Exp 4). | `blast_radius.py` | H1d |

## D. Input→output completeness

| Metric | What it means | Where | Hypothesis |
|---|---|---|---|
| **coverage_ratio / uncovered_count** | Fraction of source tables that produced at least one vault object — i.e. did anything get silently dropped? | `coverage.py` | H1a |

## E. Schema drift (Use Case B)

| Metric | What it means | Where | Hypothesis |
|---|---|---|---|
| **detection recall** | Detected ÷ injected changes. The safety-critical *deterministic* number — the engine must miss nothing. | Exp 6 runner | **H2a** |
| **impact accuracy** | Fraction of changes whose **additive/cosmetic/breaking** label matches the expert answer key. | `scoring.py` | **H2b** |
| **confusion matrix** + **per-class precision/recall** | Where the classifier confuses which classes — far more informative than a single accuracy figure. | `scoring.py` | H2b |
| **breaking_recall** | Recall on the **breaking** class alone: the fraction of genuinely breaking changes caught. The single most safety-relevant number. | `scoring.py` | H2b |
| **cost-weighted error** | **Asymmetric** cost: missing a breaking change costs **5**, a false alarm costs **1**. Encodes that auto-applying a breaking change is far worse than being over-cautious. Deliberately allowed to disagree with accuracy — and it did (Exp 6 §8). | `scoring.py` | H2b |
| **drift-review action counts** (discovery / decisions / corrections) | Objective effort: how many manual actions to reach the same review decisions. | Exp 6c runner | **H2c** |

## F. Governance and safety

| Metric | What it means | Where | Hypothesis |
|---|---|---|---|
| **block rate** | Fraction of deliberately unsafe inputs the governance layer refuses to apply unattended (pause / reject). | Exp 7 suite | **H3a** |
| **audit completeness** | Fraction of decision records carrying actor, timestamp, version, decision and rationale. **Measured = 1.00** on the populated store (findings §3C). | `approval_store` | **H3c** |

## G. Operational

| Metric | What it means | Where | Hypothesis |
|---|---|---|---|
| **latency** (`t_model_s`, `t_review_s`) | Wall-clock cost per stage — the price paid for any quality gain. | `study.py` | H1c/H1d (cost side) |
| **seed / session variance** | Spread of a metric across seeds and across sessions. Used to separate signal from noise (it showed naming is unstable while entity_f1 is stable). | all runners | validity |

---

# Experiment → hypothesis coverage

| Experiment | Hypotheses tested | Verdict |
|---|---|---|
| **1 — modeller ablation** | H1a, H1b | Entity id at ceiling & learning-independent; naming/link parsimony are the weak axes |
| **2 — learning curve + LOO** | H1c | Supported *conditionally*: threshold-gated, instance-level copying, not generalisation |
| **3 — CIM cross-domain control** | H1c (corpus safety) | Cross-domain examples inert on CIM; on ServiceNow (verified-load, leave-one-out, §2.8) they give a significant *structural* gain (link parsimony) with no naming transfer and no harm |
| **4 — end-to-end + taxonomy shift** | H1d | Reviewer is a **trade-off**, not a scalar gain |
| **5 — three-arm baseline** | H1a, H3b | AI ≫ rules on hard schemas, ties on easy; fewest correction steps |
| **6 — drift** | H2a, H2b, H2c | Recall 1.00; AI 1.00 vs rule 0.88; effort 36 → 0 actions |
| **7 — safety & governance** | H3a, H3c | H3a **refuted as built (62%) → fixed (100%)**; H3c **supported** (audit completeness 1.00, findings §3C) |

Every hypothesis now has evidence, including H3c.

---

# Hallucination and the other late-added metrics

## Are we measuring hallucination? **Yes — it was the biggest gap, now closed.**

In an earlier draft this was the most conspicuous hole: nothing verified that the
tables and columns the model references actually **exist in the source**. It is now
measured directly (findings §2.1); the definition below is what the metric computes,
and the reason the pre-existing proxies do not stand in for it. Those proxies capture
something adjacent but different:

- `link_fk_unresolved` — a link points at a hash key matching no hub in the plan;
- `satellite_orphan` — a satellite's parent hub is not in the plan;
  *(both are **internal** dangling references — plan-vs-plan consistency, not
  plan-vs-source grounding)*
- `entity_precision` — penalises hubs absent from the gold, but a "spurious" hub may
  be a defensible modelling alternative rather than a fabrication;
- `coverage_ratio` — detects **omission**, which is the opposite failure.

**The metric — grounding / hallucination rate.** Define a *reference* as any source
identifier the plan names: each object's `source_table`, each hub's `business_keys`,
and each satellite's `payload` columns. Then

> **hallucination_rate = fabricated references ÷ total references**, where a
> reference is *fabricated* if the named table is absent from the discovery payload,
> or the named column is absent from that table's column list.

This is pure, cheap, deterministic (plan + payload in, rate out) and needs no gold
set. It matters because hallucination is *the* canonical LLM failure mode; leaving it
unmeasured would have been a conspicuous hole in an LLM thesis, which is why it was
the first of the late additions to be built.

**The caveat, now tested rather than assumed:** the modeller's prompt forbids
inventing tables/columns, and `_coerce_plan_dict` strips unknown payload columns.
Measuring it did **not** return a flat zero — ServiceNow scored **0.0015** (one
fabricated payload column across ~660 references), CIM 0.0000. So the guardrail is
*substantially* but not *perfectly* effective; that is a stronger finding than the
assumed zero would have been. See `findings.md §2.1`.

## Metrics status — all of the below are now implemented, tested, and reported

Everything on the earlier "worth adding" list has since been built and measured; this
table is the audit trail. Full results and interpretation live in `findings.md`.

| Metric | Status | Where measured |
|---|---|---|
| Grounding / hallucination rate | **Done** — 0.0015 SNOW, 0.0000 CIM | findings §2.1 |
| dbt compile (live warehouse) | **Done** — 12 models compile clean, zero warnings | findings §2.4 |
| Self-consistency / output stability | **Done** — 0.80 CIM, 0.33 SNOW | findings §2.2 |
| Statistical rigour (bootstrap CIs) | **Done** — 95% CIs over five seeds | findings §2.7 |
| Inter-rater reliability (Cohen's κ) | **Done (proxy)** — independent-annotator κ 0.84; human test–retest still open | findings §2.9, §6 |
| Token / cost per plan | **Done** — ≈3.9k CIM, ≈13.9k SNOW tokens | findings §2.5 |
| Idempotency rate | **Done** — 0.20 CIM, 0.33 SNOW, 1.00 rules | findings §2.3 |
| Model-ablation robustness | **Done** — gpt-4o vs gpt-4.1 | findings §3B.3 |
| Significance + effect size | **Done** — off-vs-on at n=10 (findings §2.8) | findings §2.8 |
| Approval rate | **Done** — 0.667 over 15 decisions | findings §3C |
| Audit-trail completeness | **Done** — 1.00 on a populated store | findings §3C |

The two items that were blocked on data collection have since been resolved: the
approval-rate and audit-trail metrics were computed once real approvals existed
(§3C), and the gold's reliability is triangulated by an independent-annotator kappa of
0.84 against a documented codebook (§2.9). The one piece still genuinely open is a
*human* second labelling of the gold — a second annotator, or the author's test–retest
after a washout — for a human inter-rater figure rather than a human-vs-automated one.

> **Metric set is deliberately final.** The evaluation suite above is treated as complete
> for the thesis's claims; no further metrics are added, to keep scope disciplined and
> avoid late re-runs — additions such as weighted/ordinal κ or confidence calibration
> would only refine at the margins, not change any finding. Two choices to defend if
> asked: (1) **unweighted** Cohen's κ is used because the impact decision is a
> categorical modelling judgement (which action to take), not a magnitude; (2) the
> **κ = 1.0 on n = 8** result is reported as *directional, not statistically established*
> (cosmetic class n = 1), which the text states plainly rather than overclaiming.
