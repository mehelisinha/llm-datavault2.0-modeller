# Experiment 1 — Feedback-learning ablation on the modelling agent

**Research question.** Does injecting previously-approved Data-Vault objects as
few-shot examples measurably improve the *modelling agent's* raw output?

**Hypothesis (H1).** With relevant approved examples in context, the agent
produces models that are (a) more *correct* (right entities + keys) and (b)
closer to the shop's *naming convention*.

## 1. Design

| Element | Value |
|---|---|
| Test system | ServiceNow IT4IT (`SNOW_IT4IT_001`), 9 source tables |
| Unit under test | `ModellingAgent.propose()` — the modeller **in isolation** (no plan-reviewer, no BV), so the ablation attributes any effect to retrieval alone |
| Corpus | 86 approved objects across 4 prior systems, in Databricks `dwa_meta_ai.rv_examples` |
| Retrieval | lexical top-*k* (k=3), deterministic |
| Generator model | `gpt-4.1` (Azure OpenAI), temperature 0, seeds {42, 43, 44} |
| Repeats | 3 seeds per arm (variance control) |

**Arms (the key control against train/test leakage):**
- **OFF** — learning disabled (k=0).
- **ON-LOO** — learning ON, but the test system's own approved model
  (`edh_unreg_consumption_dev`) is **excluded** from the corpus (leave-one-out).
  Measures genuine **transfer** from *other* systems.
- **ON-full** — learning ON with the full corpus (the test system's own model is
  present). This is the **leakage upper bound** — it retrieves near-identical
  examples, so it is *not* a fair test of generalisation, only a ceiling.

**Metrics.** Entity identification is graded *structurally* — a hub is matched
to the gold by `(source_table, business_key)`, **not by name** — because the raw
modeller names hubs after the table (`hub_core_company`) while the shop
convention uses the concept (`hub_company`). This separates two things the
literature usually conflates:
- **`entity_f1`** — did it find the right entities with the right keys? (correctness)
- **`naming_adherence`** — of the entities it got right, how many use the shop's
  concept name? (convention transfer — the clean place for learning to show up)
- plus conformance (DV2 well-formedness), `link_ratio` (produced/expected links),
  latency.

## 2. Results (mean of 3 seeds)

| Arm | entity_f1 | naming_adherence | conformance | link_ratio | latency (s) |
|---|---|---|---|---|---|
| OFF | **0.933** | **0.000** | 0.943 | 1.79 | 24.2 |
| ON-LOO (transfer) | 0.914 | **0.000** | 0.932 | 1.79 | 23.6 |
| ON-full (leakage ceiling) | 0.933 | **0.000** | 0.945 | 1.64 | 26.9 |

`naming_adherence` had zero variance across all 9 runs (std = 0.0).

## 3. Analysis

**F-1: Entity identification is at ceiling and learning-independent.**
Entity recall is ~1.0 in every arm — the modeller finds *all* seven gold
entities and their business keys **without** any examples. The `entity_f1` of
0.93 reflects one spurious hub (`hub_task`, from the cross-schema
`task_sla.task` reference), not a missed entity. Feedback learning neither helps
nor hurts here: the base model already solves entity extraction for this schema.

**F-2: The naming convention is NOT transferred by few-shot retrieval — even
when the exact concept-named examples are in context.** `naming_adherence = 0`
in *all* arms, including ON-full. We verified the retrieved block does contain
concept-named examples (e.g. `hub_department` for `cmn_department`), yet the
agent still emits `hub_cmn_department`. The agent's table-based naming prior
(from its system prompt) dominates the k=3 in-context examples. **Corollary
(hypothesis):** the clean concept names in the approved corpus originate
*downstream* (the plan-reviewer step renames the modeller's output), not from the
modeller — so feeding them back to the modeller does not reproduce them.

> **⚠ Revised by Experiment 4.** This corollary was a *hypothesis*, not a
> measurement — Experiment 1 never graded the reviewer's output. Experiment 4
> grades it directly and the corollary is **false**: the gpt-5.2 plan-reviewer is
> **naming-neutral** (`naming_adherence` 0→0 with learning off, 1→1 with learning
> on — it preserves whatever names the modeller emitted). The clean concept names
> in the corpus therefore come from the **modeller's own few-shot learning** once
> *k* crosses the threshold (Experiment 2), and/or from human edits at approval
> time — **not** from the reviewer. The correct reading of F-2 is narrower: the
> modeller ignores naming examples *at k=3*, but adopts them at *k≈10* (Exp 2);
> the reviewer is not the source of the convention. See
> `experiment-4-endtoend-taxonomy.md` §4 F-A.

**F-3: Over-linking is systematic and learning-independent.** All arms produce
~1.6–1.8× the expected number of links: the modeller emits a link for every
FK-like column (e.g. `link_cmn_location_contact`, `link_cmn_department_dept_head`),
including references the gold treats as attributes. ON-full trends slightly lower
(1.64 vs 1.79) but within seed variance.

**F-4: Latency cost of learning is negligible.** ON adds ~0–3 s over OFF (larger
prompt); immaterial next to the ~24 s generation time.

## 4. Interpretation

For this system, the naive hypothesis (H1) is **not supported at the modeller
level**: correctness is already near-ceiling, and the one dimension that *does*
differ from the gold — naming — is unaffected by k=3 lexical few-shot. This is a
*negative but informative* result: it localises **where** the feedback loop can
and cannot add value.

- The loop's mechanism (retrieve relevant approved objects) works — it surfaces
  the right examples.
- But **conditioning strength matters**: three examples do not override a strong
  generative prior. This motivates Experiment 2 (does *more* context — higher
  *k* — transfer the convention?) and points to alternatives (an explicit,
  corpus-derived naming instruction, or applying the corpus at the *reviewer*
  stage). *[Revised by Experiment 4: the reviewer does **not** decide naming — it
  is naming-neutral — so the actionable lever is higher k at the modeller (Exp 2)
  or an explicit naming instruction, not the reviewer.]*

## 5. Threats to validity / limitations

- **Single system, one model.** Results may differ for schemas where entity
  extraction is *not* at ceiling (larger/ambiguous sources) or for weaker models.
- **Modeller-only.** By isolating `propose()` we exclude the reviewer — so this
  bounds the *mechanism*, not the end-to-end product (a separate end-to-end study
  is warranted). *[Experiment 4 ran that study and found the reviewer is
  naming-neutral, so — contrary to the assumption originally stated here — naming
  is **not** "normalised at the reviewer" in production; it is set at the modeller
  by learning.]*
- **Reproducibility.** LLM output is only best-effort deterministic under a fixed
  seed; we report 3 seeds, but naming_adherence's zero variance makes F-2 robust.
- **Metric scope.** Links/satellites are reported as counts, not name-F1, because
  their names are naming-confounded the same way as hubs.

## 6. Trade-offs

| | Gain | Cost |
|---|---|---|
| Learning ON (k=3) | none measurable on this system (entity at ceiling, naming unmoved) | +0–3 s latency, +prompt tokens, corpus/retrieval infra |
| Leave-one-out discipline | valid transfer measurement (no leakage) | smaller effective corpus → weaker (honest) signal |

**Take-away for the dissertation:** the contribution is not "learning always
helps" — it is a *characterisation* of when it does. Here, the feedback loop is
inert at the modeller stage because the base model is already competent on
entities and impervious to few-shot on naming. That reframes the loop's value
toward (i) harder schemas and (ii) the stages where its signal is actionable.

## 7. How to reproduce this experiment manually

1. Ensure Databricks is the backend and the corpus is populated:
   `DWA_AI_METADATA_STORE_BACKEND=delta` in `.env`; `az login` valid.
2. For each arm and seed, generate and score (the CLI runs one arm at a time):
   ```bash
   # OFF arm (learning disabled) — score against the gold:
   python -m dbt_builder.src.ai.evaluation generate \
       --payload poc/metadata/servicenow_it4it_discovery.yaml \
       --gold SNOW_IT4IT_001 --no-learning --out off.json
   # ON arm (learning enabled, full corpus):
   python -m dbt_builder.src.ai.evaluation generate \
       --payload poc/metadata/servicenow_it4it_discovery.yaml \
       --gold SNOW_IT4IT_001 --out on.json
   ```
   Read `entity id … P/R/F1`, `naming adherence`, and `links produced/expected`
   from each scorecard.
3. For the **leave-one-out** ON arm and multi-seed variance, the CLI's single
   corpus can't exclude a catalog per-run; use the harness hook: build the agent
   with `get_modelling_agent(reference_loader_override=_load_reference_corpus(cfg,
   exclude_catalogs=("edh_unreg_consumption_dev",)), reference_limit_override=3)`
   and vary `cfg.llm_seed`. (Script: `scratchpad/exp1_v2.py`.)
4. To confirm F-2, print the injected block for the ON-full agent:
   `agent._reference_block(payload)` — you will see concept-named examples
   (`hub_department`) that the output nonetheless does not adopt.
