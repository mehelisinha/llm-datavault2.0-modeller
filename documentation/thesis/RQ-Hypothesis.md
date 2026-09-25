# Research Questions and Hypotheses (reframed)

> **Purpose.** This is the single authoritative statement of the thesis's research
> questions and hypotheses, rewritten *after* building the prototype and running
> Experiments 1–4. It keeps the original intent of the proposal's RQ1–RQ3 but
> sharpens each claim into something precise and testable, folding in what the
> experiments actually revealed. Where a claim changed, the change is deliberate
> and explained — this document supersedes the wording in the original proposal.
>
> Each hypothesis is written to be **falsifiable**: it names the metric, the
> comparison, and the condition under which it holds. Sub-hypotheses are lettered
> (H1a, H1b, …) so results can be reported against them one at a time.

---

## Why the reframing was needed

The original hypotheses were written before any code existed, so they treated
"accuracy" and "improvement" as single quantities. The experiments showed that
model quality is not one number but **three independent axes**, and that the
feedback loop's benefit is real but narrow. The reframed questions make those
distinctions explicit, which turns vague claims ("the system improves the model")
into ones a reader can check ("naming adherence rises from 0 to 1 at k≈10, but
only for entities already in the corpus").

The three quality axes, used throughout:

1. **Entity & business-key identification** — did the system find the right
   business entities and key them correctly? (structural correctness)
2. **Naming-convention adherence** — did it use the shop's concept names
   (`hub_company`) rather than raw source-table names (`hub_core_company`)?
3. **Link parsimony** — did it produce the right number of links, or over-link by
   emitting one for every foreign-key-like column?

---

## RQ1 — Accuracy and iterative improvement of AI-generated Data Vault mappings (Use Case A)

**Research question.** To what extent can the multi-agent LLM system generate
accurate Data Vault mapping configurations from live ExampleCorp Databricks source
metadata — measured separately for entity/business-key identification, naming
convention, and link parsimony — and under what conditions does feeding approved
expert decisions back into the retrieval index reduce the expert correction rate
on subsequent runs?

**H1a — First-run accuracy (vs baselines).** On entity and business-key
identification, the system's first-run output matches the manual expert baseline
within measurement noise (no material accuracy lost to automation) and matches or
exceeds a deterministic rule-based baseline on the same source tables.

**H1b — Systematic weaknesses.** The raw model deviates from the expert on the
other two axes: it names hubs after source tables rather than concepts, and it
over-produces links. These are the axes where the model is weakest and therefore
where the downstream mechanisms (feedback learning; the reviewer) have room to
help.

**H1c — Feedback effect is conditional, not general.** Incorporating approved
decisions into the retrieval index improves *naming-convention adherence*, but
only when (i) the amount of retrieved context exceeds a size threshold and (ii)
the corpus already contains an approved model of the *same entity*. That is, the
naming mechanism is **instance-level transfer (copying), not convention generalisation**,
and it does **not** change entity-identification accuracy, which is already at
ceiling. A distinct, *structural* effect does generalise across domains: even with the
target system held out (leave-one-out), retrieving another domain's approved models
significantly improves **link parsimony** on the hard schema (findings §2.8) — so the
feedback loop transfers modelling *structure* across domains while *naming* stays
instance-specific.

**H1d — Reviewer stage is a trade-off, not a scalar gain (sub-question).** The
second-model (plan-reviewer) stage — the part that makes the pipeline genuinely
"multi-agent" — improves DV2 convention conformance and repairs structural
connectivity (it resolves dangling link foreign keys), but it does **not** act as
a pure quality gain. It introduces a measurable trade-off: it redistributes
errors toward higher-fan-out objects (re-keying hubs onto surrogate keys), leaves
naming unchanged, and can *lower* structural agreement with the expert gold.
End-to-end quality is therefore multi-dimensional and must be reported as a
profile, not a single "better/worse" verdict.

---

## RQ2 — Deterministic-plus-AI schema drift detection (Use Case B)

**Research question.** How completely does the deterministic diff engine detect
structural schema drift between an approved metadata contract and the live ExampleCorp
Databricks schema, and how accurately does an AI impact-classification layer label
the Data Vault semantic impact of those changes (additive / cosmetic / breaking),
compared with a rule-only baseline and with manual expert review?

**H2a — Complete deterministic recall.** The deterministic diff engine detects
100% of the structural changes (added columns, removed columns, type changes, new
tables, orphaned entities) present in a manually verified ground-truth diff — i.e.
complete recall on structural drift, with no dependence on the LLM.

**H2b — AI impact classification beats rules.** The AI impact-classification layer
labels each detected change's Data Vault impact (additive / cosmetic / breaking)
at an accuracy significantly higher than a rule-only mapping of the deterministic
diff, when scored against an expert-labelled test set of changes.

**H2c — Lower human effort than manual review.** Reaching the same set of
drift-review decisions costs less human effort (time and manual steps) with the
deterministic+AI pipeline than with unaided manual schema review of the same
changes.

---

## RQ3 — Safety, governance, and human effort

**Research question.** Does the governance layer reliably prevent unsafe metadata
operations across both use cases, and how does the human effort required by the
full multi-agent system compare with the manual and deterministic-only baselines?

**H3a — Zero unsafe promotions.** In controlled tests that deliberately feed
unsafe inputs (a breaking change, an invalid plan, a plan carrying ERROR-severity
validation issues), the governance layer blocks 100% of unsafe promotions: no
breaking change is auto-applied, no unvalidated YAML is accepted, and no
ERROR-severity plan is promoted.

**H3b — Fewer manual correction steps than the baselines.** Reaching an approvable
model of equivalent quality (the gold reference) requires **fewer manual correction
steps** with the full multi-agent system than either building the model from
scratch (the manual arm) or repairing the rule-based output (the deterministic
arm). Correction steps are counted **objectively** as the structural edits — hubs
to add/delete/rename, links and satellites to adjust — needed to bring an arm's
output up to the reference. Under a **stated practitioner time-per-table
assumption** this implies a proportional reduction in *estimated* effort; a
controlled human-timing study was **not** conducted and is recorded as future work.

*Note on scope (integrity).* The original hypothesis claimed less human *time*,
which implies a measured timing study. No such study was run (no independent
Data-Vault expert was available to time), so the claim is deliberately narrowed to
the **objective, reproducible correction-step count**, with any time figure
presented explicitly as an assumption-based *estimate* — never as a measurement.

**H3c — Complete governance trail.** Every approved decision carries a complete,
traceable audit record — actor, timestamp, plan version, and rationale — giving
full approval-chain traceability from source metadata to approved YAML.

---

## Status at a glance (detail in `research-plan-and-experiment-map.md`)

| Hypothesis | Evidence so far | Still needed |
|---|---|---|
| H1a first-run accuracy | Exp 1 (entity_f1 ≈ 0.93 vs gold) | 3-arm comparison with effort (Exp 5) |
| H1b weaknesses | Exp 1, 2 (naming 0, over-linking ~1.8×) | — (established) |
| H1c conditional feedback | Exp 2 (threshold + LOO), Exp 3 (control) | — (established) |
| H1d reviewer trade-off | Exp 4 (taxonomy shift) | more seeds / a second reviewer model (optional) |
| H2a deterministic recall | engine built | drift test on a labelled diff (Exp 6) |
| H2b AI impact accuracy | — | build classifier + expert-labelled set (Exp 6) |
| H2c drift effort | — | timed manual vs pipeline (Exp 6) |
| H3a zero unsafe promotions | gates built | controlled unsafe-input test (Exp 7) |
| H3b correction steps | Exp 5 (objective counts: full < deterministic < manual) | optional practitioner-time estimate overlay |
| H3c audit completeness | approval store built | read audit coverage from the store (Exp 7) |
