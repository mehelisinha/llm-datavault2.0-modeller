# DWA — Concepts & Rationale (Thesis Working Notes)

> **Status:** Local-only. This folder lives under `documentation/thesis/` and is
> excluded from git via `.gitignore` (`documentation/thesis/`). Nothing here is
> committed or pushed. It is a personal reference for the MSc thesis and the
> private project write-up.

## Purpose

This folder documents **every concept** the DWA project applies — Data
Engineering, Data Vault 2.0, AI/LLM orchestration, and the ML-adjacent
retrieval/embedding machinery — and, just as importantly, **why each concept
was chosen** over the alternatives. It is written from a reading of the actual
source code (`dbt_builder/src/ai/**`), not from the marketing description.

## Files

| File | What it covers |
|------|----------------|
| [`RQ-Hypothesis.md`](./RQ-Hypothesis.md) | **The reframed research questions and hypotheses** (RQ1–RQ3, sub-hypotheses H1a–H1d, H2a–H2c, H3a–H3c), rewritten after building the prototype and running Experiments 1–4. The authoritative, human-readable statement of what the thesis claims and tests. Supersedes the proposal wording. |
| [`research-plan-and-experiment-map.md`](./research-plan-and-experiment-map.md) | **RQ → experiment map**: the three baselines as actually built, what Experiments 1–4 contribute and to which RQ, the gap analysis, the Experiment 5 (three-arm) design incl. the decision-(b) recommendation, the Experiment 7 (safety/governance) sketch, threats to validity + stronger scientific alternatives, and recommended sequencing. |
| [`use-case-b-drift-design.md`](./use-case-b-drift-design.md) | **Use Case B (RQ2) design**: deterministic drift engine (exists) vs AI impact classifier (to build on `ai/usecaseB-drift`), the additive/cosmetic/breaking taxonomy reconciliation, Experiment 6 design (recall / impact accuracy / effort), and exactly what drifted Databricks dataset the author must create. |
| [`concepts-and-rationale.md`](./concepts-and-rationale.md) | The **AI half** + cross-cutting concepts: the LLM pipeline (modelling, voting, review, RAG/embeddings), Data Vault 2.0 theory, data engineering, and MLOps — every concept, where it lives, and why. |
| [`dv-components-sql-engine.md`](./dv-components-sql-engine.md) | The **deterministic code-generation half**: the `dv_components` engine that compiles the metadata YAML into a runnable dbt + AutomateDV project (typed models, factories, meta-templating, AutomateDV wrapping, design patterns). |
| [`performance-evolution.md`](./performance-evolution.md) | **Methodology evolution**: how YAML generation went from slow (`ai/phase-b-agents-ui`) to fast (`ai/plan-review-modelling`) — the slow baseline, the commit table, and the detailed reason each optimisation was adopted. |
| [`experiments-and-evaluation.md`](./experiments-and-evaluation.md) | **Feedback learning + evaluation** (`ai/feedback-learning`): how approved YAML is stored in Databricks and fed back as few-shot examples, what is stored where, how to verify a generated model, and every Phase 4–6 experiment (conformance, coverage, blast-radius, gold P/R/F1, ablation, learning curve) with the CLI to run them. |
| [`experiment-1-modeller-ablation.md`](./experiment-1-modeller-ablation.md) | **Experiment 1 — ablation** (OFF vs leave-one-out vs full-corpus). Finding: entity identification is at ceiling and learning-independent; the naming convention is *not* transferred by k=3 few-shot (the corpus's clean names come from the downstream reviewer). Structural, naming-independent metrics; 3 seeds/arm. |
| [`experiment-2-learning-curve.md`](./experiment-2-learning-curve.md) | **Experiment 2 — learning curve** (k=0…10) + leave-one-out transfer probe. Finding: naming transfer is **threshold-gated** (0→1.0 at k≈10) and is **instance-level copying, not convention generalisation** (LOO at k=10 stays 0). Corrects the thesis claim into a precise, conditional one. |
| [`experiment-3-cross-domain-control.md`](./experiment-3-cross-domain-control.md) | **Experiment 3 — CIM cross-domain control.** Findings: cross-domain examples are **inert, not harmful** (safe in a shared corpus); the naming effect is **invisible on CIM because its tables are already concept-named** → the effect's scope condition is a *table-vs-concept naming gap* (e.g. ServiceNow prefixes). Consolidated 1–3 map of where feedback helps / is inert / is safe. |
| [`experiment-4-endtoend-taxonomy.md`](./experiment-4-endtoend-taxonomy.md) | **Experiment 4 — end-to-end reviewer + error-taxonomy shift.** Findings: the gpt-5.2 reviewer **resolves dangling link FKs** but **introduces surrogate-key hubs** → conformance up, entity_f1 (vs gold) down, naming neutral, and **blast-radius-weighted impact rises even as issue count falls**. Revises Exp 1: clean naming comes from the *modeller's learning*, not the reviewer. End-to-end quality is a **trade-off**, not a scalar win. |
| [`experiment-5-baseline-comparison.md`](./experiment-5-baseline-comparison.md) | **Experiment 5 — three-arm comparison (Manual vs Deterministic vs Full).** Answers RQ1/H1a. Findings: the AI's lift over the rule-based baseline is **large on hard schemas** (ServiceNow entity_f1 0.94 vs 0.50) and **nil on easy ones** (CIM both 1.0); the AI's value is the judgement calls rules can't make (splitting one table into two entities, semantic keys, excluding telemetry tables). The reviewer trades entity fidelity for conformance (H1d). Both automated arms mishandle link count in **opposite** directions (rules under-link, LLM over-links). Human-effort protocol (H3b) documented for the researcher's timed session. |

### Reproducible runner (all four experiments, one command)

Experiments 1–4 are the same operation under different knobs, run through one
declarative CLI — **no scratchpad scripts, no hardcoded paths**. A system is
named by its gold `system_id` (its discovery-payload path is read from the gold
file); a condition is a parsed spec (`off`, `on:k=10`,
`loo:k=10,exclude=cat_a+cat_b`, `e2e:k=10,review=1`). Wiring lives in
`dbt_builder/src/ai/evaluation/study.py`; pure logic is unit-tested with injected
fakes in `tests/ai/test_study.py` (no network). Reproduce each experiment with:

```bash
# Exp 1 — ablation (ServiceNow: OFF vs leave-one-out vs full corpus)
python -m dbt_builder.src.ai.evaluation experiment --system SNOW_IT4IT_001 \
  --condition off --condition "loo:k=3,exclude=edh_unreg_consumption_dev" --condition "on:k=3" --seeds 42,43,44

# Exp 2 — learning curve + transfer probe
python -m dbt_builder.src.ai.evaluation experiment --system SNOW_IT4IT_001 \
  --condition off --condition on:k=1 --condition on:k=3 --condition on:k=5 --condition on:k=10 \
  --condition "loo:k=10,exclude=edh_unreg_consumption_dev" --seeds 42,43

# Exp 3 — CIM cross-domain control
python -m dbt_builder.src.ai.evaluation experiment --system IEC_CIM_001 \
  --condition off --condition "loo:k=3,exclude=iec_cim+edh_unreg_silver_dev_st" \
  --condition on:k=10 --condition "loo:k=10,exclude=iec_cim+edh_unreg_silver_dev_st" --seeds 42,43

# Exp 4 — end-to-end reviewer + taxonomy shift
python -m dbt_builder.src.ai.evaluation experiment --system SNOW_IT4IT_001 --system IEC_CIM_001 \
  --condition "e2e_off:k=0,review=1" --condition "e2e_on:k=10,review=1" --seeds 42,43
```

> The two halves meet at the **metadata YAML**: the AI side emits it, the
> `dv_components` engine compiles it. Read `concepts-and-rationale.md` first for
> the overall pipeline, then `dv-components-sql-engine.md` for the SQL builder.

## How to cite this in the thesis

Each section in `concepts-and-rationale.md` is structured as:

1. **What it is** — the concept, in plain terms.
2. **Where it lives** — the file(s) implementing it (`path:symbol`).
3. **Why it was chosen** — the trade-off / decision rationale.

You can lift the "what" and "why" almost verbatim into the thesis body and use
the "where" as the implementation evidence appendix.
