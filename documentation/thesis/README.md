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
| [`concepts-and-rationale.md`](./concepts-and-rationale.md) | The **AI half** + cross-cutting concepts: the LLM pipeline (modelling, voting, review, RAG/embeddings), Data Vault 2.0 theory, data engineering, and MLOps — every concept, where it lives, and why. |
| [`dv-components-sql-engine.md`](./dv-components-sql-engine.md) | The **deterministic code-generation half**: the `dv_components` engine that compiles the metadata YAML into a runnable dbt + AutomateDV project (typed models, factories, meta-templating, AutomateDV wrapping, design patterns). |
| [`performance-evolution.md`](./performance-evolution.md) | **Methodology evolution**: how YAML generation went from slow (`ai/phase-b-agents-ui`) to fast (`ai/plan-review-modelling`) — the slow baseline, the commit table, and the detailed reason each optimisation was adopted. |
| [`experiments-and-evaluation.md`](./experiments-and-evaluation.md) | **Feedback learning + evaluation** (`ai/feedback-learning`): how approved YAML is stored in Databricks and fed back as few-shot examples, what is stored where, how to verify a generated model, and every Phase 4–6 experiment (conformance, coverage, blast-radius, gold P/R/F1, ablation, learning curve) with the CLI to run them. |
| [`experiment-1-modeller-ablation.md`](./experiment-1-modeller-ablation.md) | **Experiment 1 — ablation** (OFF vs leave-one-out vs full-corpus). Finding: entity identification is at ceiling and learning-independent; the naming convention is *not* transferred by k=3 few-shot (the corpus's clean names come from the downstream reviewer). Structural, naming-independent metrics; 3 seeds/arm. |
| [`experiment-2-learning-curve.md`](./experiment-2-learning-curve.md) | **Experiment 2 — learning curve** (k=0…10) + leave-one-out transfer probe. Finding: naming transfer is **threshold-gated** (0→1.0 at k≈10) and is **instance-level copying, not convention generalisation** (LOO at k=10 stays 0). Corrects the thesis claim into a precise, conditional one. |
| [`experiment-3-cross-domain-control.md`](./experiment-3-cross-domain-control.md) | **Experiment 3 — CIM cross-domain control.** Findings: cross-domain examples are **inert, not harmful** (safe in a shared corpus); the naming effect is **invisible on CIM because its tables are already concept-named** → the effect's scope condition is a *table-vs-concept naming gap* (e.g. ServiceNow prefixes). Consolidated 1–3 map of where feedback helps / is inert / is safe. |

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
