# Use Case B — Schema Drift Detection and Impact Classification (design)

> **Purpose.** Design document for Use Case B (RQ2). It records what already
> exists in code, what must be built, the taxonomy reconciliation between the
> proposal and the implementation, the experiment design (Exp 6), and exactly what
> dataset the author needs to create in Databricks. Kept in scope per the author's
> decision. Any code arising from this goes on branch **`ai/usecaseB-drift`**;
> this document itself is the no-code deliverable.

---

## 1. What Use Case B is

Given an **approved metadata contract** (the currently accepted Data Vault model)
and the **live ExampleCorp Databricks bronze schema**, detect how the source has drifted
and classify what each change *means* for the Data Vault model, so a human can
review only what matters. Two layers:

1. **Deterministic drift detection** — a purely structural diff (column
   add/remove/type-change, new/removed tables). Must be exhaustive: it is the
   safety-critical layer, so it must miss nothing.
2. **AI impact classification** — for each detected change, label its Data Vault
   semantic impact: **additive**, **cosmetic**, or **breaking**. This is the
   judgement layer that saves human review time.

This maps to RQ2 / H2a (recall), H2b (impact accuracy), H2c (effort).

---

## 2. What already exists (deterministic layer) — H2a is buildable now

`dbt_builder/src/ai/pipeline/diff_analyzer.py` already produces a `ChangeSet`:

- Every bronze table is categorised **NEW** (no vault entity yet), **DRIFT**
  (entity exists, columns changed), **UNCHANGED**, or **ORPHANED** (vault entity
  with no bronze source).
- Each change carries per-column `ColumnDiff`s (`added` / `removed` /
  `type_changed`, with old/new dtype).
- Matching is convention-aware: bronze `conducting_equipment` matches vault
  `hub_conducting_equipment` by stripping the `hub_`/`sat_`/`link_` prefix.
- A coarse `ChangeRisk` (LOW/MEDIUM/HIGH) is already assigned; **HIGH** flags
  business-key rename and key-column type change — exactly the changes that are
  usually *breaking*.

**Implication:** the deterministic engine needed for **H2a (complete recall) is
already implemented**. Testing it needs a *labelled drift dataset*, not new code.

## 3. What is missing (AI layer) — H2b needs code

The proposal's impact taxonomy — **additive / cosmetic / breaking** — does **not**
exist anywhere in the codebase. What exists is a *different* taxonomy:
`ChangeCategory` (NEW/DRIFT/UNCHANGED/ORPHANED) describes the diff *shape*, and
`ChangeRisk` (LOW/MEDIUM/HIGH) is a coarse structural heuristic. The
`SchemaAnalyzer` uses the `ChangeSet` only to decide **which tables to skip vs
re-model** — it never assigns a Data-Vault-semantic impact.

So **H2b requires a new component**: an impact classifier that takes each detected
change and labels it additive/cosmetic/breaking. This is the code that goes on
`ai/usecaseB-drift`.

### Taxonomy reconciliation (definitions to use)

The classifier and the expert labels must share precise definitions:

| Impact | Meaning for the Data Vault | Example changes |
|---|---|---|
| **Additive** | Forward-compatible; extends the model without invalidating anything already approved | New column → new satellite payload field / new satellite; new table → new hub; a genuinely new nullable attribute |
| **Cosmetic** | No Data Vault structural consequence; no model change required | Comment change; column reorder; case/whitespace-only rename that does not change identity; a compatible type widening (e.g. `int`→`bigint`) that does not touch a key |
| **Breaking** | Invalidates the existing contract; must **not** be auto-applied | Business-key rename or removal; key-column type change; table removal (orphaned hub); removal of a column a satellite/hashdiff depends on |

The deterministic layer already flags most *breaking* candidates as `HIGH` risk —
so a useful design is: the **rule-only baseline** = map `ChangeRisk` mechanically
to impact (HIGH→breaking, else additive/cosmetic by add-vs-modify), and the **AI
layer** = an LLM that reasons over the change *in DV context* to produce the
impact label. H2b then tests whether the AI beats that rule-only mapping.

---

## 4. Experiment 6 — design

### 6a — Deterministic recall (H2a)  *[no code]*
Run `diff_analyzer` on the approved-contract vs drifted-schema pair and check that
**every** injected structural change appears in the `ChangeSet`. Metric: **recall
= detected / total injected changes** (target 1.0). Because the diff is
deterministic, this is a single exhaustive run, not a seeded average.

### 6b — AI impact classification accuracy (H2b)  *[code on `ai/usecaseB-drift`]*
For each detected change, compare three labels: **expert** (ground truth),
**rule-only** (mechanical mapping of `ChangeRisk`), and **AI** (the new
classifier). Metrics:
- Overall accuracy vs expert, AI **and** rule-only, with the AI-over-rule delta.
- **Confusion matrix** + per-class precision/recall (additive/cosmetic/breaking).
- **Cost-weighted error**: a missed *breaking* change (labelled additive/cosmetic)
  is the dangerous failure and must be weighted far higher than the reverse. Report
  this separately from plain accuracy — it is the safety-relevant number.
- Seeds: the classifier's model temperature determines whether to average over
  seeds (report variance if temperature > 0).

### 6c — Human effort (H2c)  *[no code]*
Time a manual expert drift-review of the same change-set (wall-clock + number of
decisions) and compare against the time to review the pipeline's pre-classified
output. Report effort delta and whether the review *decisions* agree.

---

## 5. What the author needs to create in Databricks (dataset)

To run Exp 6 we need a **controlled drift pair** with a known ground truth. The
author can build this; the shape required:

1. **Baseline (approved contract):** one system already in use (CIM or ServiceNow
   is ideal — a gold model already exists). This is the "before".
2. **Drifted bronze schema:** a copy of the same source with a **known, recorded
   set of injected changes** spanning all three impact classes, e.g.:
   - *Additive:* add a new nullable column to a table; add a whole new table.
   - *Cosmetic:* rename a non-key descriptive column; widen a non-key type
     (`int`→`bigint`); change a comment.
   - *Breaking:* rename or drop a **business-key** column; change a **key
     column's** type; drop an entire table.
3. **Ground-truth label sheet:** for each injected change, record (a) that it was
   injected (for recall), and (b) its expert impact label (additive/cosmetic/
   breaking) with a one-line rationale. Ten to twenty changes is enough for a
   first pass; more per class tightens the per-class precision/recall.

A single small drifted dataset (10–20 labelled changes) is sufficient to
demonstrate H2a fully and give a first, honest read on H2b/H2c. The author has
offered to add such a dataset (e.g. adding a new field to a table to confirm it is
detected) — that is exactly the input required.

> **What is blocked on the dataset:** nothing conceptual. The deterministic recall
> test (6a) can even run on a *synthetic* drifted YAML pair without touching
> Databricks, as a dry run, then be repeated on the real Databricks pair for the
> thesis result. The AI classifier (6b) can be built and unit-tested on synthetic
> changes first, then evaluated on the real labelled set.

---

## 6. Build plan for `ai/usecaseB-drift` (when the author greenlights)

1. Add an `impact` taxonomy (`additive`/`cosmetic`/`breaking`) as a typed enum and
   attach an optional `impact` field to `TableChange`/`ColumnDiff` (non-breaking,
   defaulted).
2. Implement the **rule-only** mapping (deterministic; the baseline) —
   `ChangeRisk` + add/remove/modify → impact.
3. Implement the **AI classifier** — an LLM step that takes a change in DV context
   and returns an impact label + rationale. Injectable/testable like the modeller.
4. Extend the evaluation harness (`study.py`) with a drift-scoring path:
   accuracy, confusion matrix, per-class P/R, cost-weighted error.
5. Unit tests on synthetic changes (no network), mirroring `test_study.py`.
6. Run 6a/6b/6c on the author's Databricks drift pair; write
   `experiment-6-drift.md` with results, following the Exp 1–4 template.

All of this is isolated on `ai/usecaseB-drift`; the thesis-experiments branch is
untouched until the work is reviewed.
