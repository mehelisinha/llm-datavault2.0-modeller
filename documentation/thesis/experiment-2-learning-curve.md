# Experiment 2 — Learning curve and the nature of convention transfer

**Research question.** How does the feedback effect vary with the amount of
retrieved context *k*, and — when it appears — is it genuine *convention
generalisation* or *instance-level* name copying?

**Motivation.** Experiment 1 found the feedback loop inert at k=3. This
experiment sweeps *k* to test whether the effect is simply *threshold-gated*, and
then isolates whether any effect transfers across systems (leave-one-out).

## 1. Design

- Same test system, model, metrics, and structural (naming-independent) grading
  as Experiment 1 (ServiceNow `SNOW_IT4IT_001`, `gpt-4.1`, temperature 0).
- **Curve:** k ∈ {0, 1, 3, 5, 10} over the **full** corpus (the condition most
  favourable to transfer — the test system's own approved model is present).
  2 seeds per k.
- **Transfer probe:** k=10 under **leave-one-out** (test system's own catalog
  excluded), 2 seeds — retrieval still returns 8 examples, but from *other*
  systems.

## 2. Results

**Learning curve (full corpus, mean of 2 seeds):**

| k | entity_f1 | naming_adherence | conformance | link_ratio |
|---|---|---|---|---|
| 0 | 0.933 | 0.000 | 0.958 | 1.82 |
| 1 | 0.933 | 0.000 | 0.911 | 1.91 |
| 3 | 0.933 | 0.000 | 0.944 | 1.73 |
| 5 | 0.933 | 0.000 | 0.941 | 1.82 |
| **10** | 0.933 | **1.000** | 0.930 | 1.82 |

**Transfer probe (k=10):**

| Condition | retrieved examples | entity_f1 | naming_adherence |
|---|---|---|---|
| full corpus (same system present) | 10 (incl. same-entity) | 0.933 | **1.000** |
| leave-one-out (other systems only) | 8 (other entities) | 0.875 | **0.000** |

Both seeds agreed within each cell (naming_adherence variance = 0).

## 3. Analysis

**F-1: The naming effect is threshold-gated, not gradual.** `naming_adherence`
is flat at 0 for k ≤ 5 and jumps to 1.0 at k = 10. Below the threshold, the
agent's table-based naming prior dominates the few in-context examples; once
enough concept-named exemplars are present (here ~one per hub, k≈10), the
in-context pattern overrides the prior and the agent adopts the shop convention
for *every* hub. This is a phase-transition-like dynamic, not a smooth curve — a
notable and reportable property of few-shot convention transfer.

**F-2: The transfer is instance-level name *copying*, not convention
*generalisation*.** Under leave-one-out at k=10 the model still receives 8
retrieved examples, but for *different* entities (e.g. `hub_activity` from a
different ITSM schema). `naming_adherence` stays at 0: the model does **not**
infer the abstract rule "prefer concept names over table names" from those
examples. It only produces `hub_company` when the corpus contains an approved
`hub_company` for `core_company` — i.e. it copies the *specific* name of the
*same* entity. This sharply bounds the mechanism's generality.

**F-3: Correctness and structure are invariant to k.** `entity_f1` (~0.88–0.93),
conformance (~0.91–0.96), and `link_ratio` (~1.6–1.9) show no monotone trend in
k — consistent with Experiment 1's finding that these are set by the base model,
not by retrieval. (The small entity_f1 dip to 0.875 under LOO is one extra
spurious hub, not a missed entity.)

## 4. Interpretation — the corrected thesis claim

Combining Experiments 1 and 2, the honest, defensible claim is **not** "feedback
learning improves the model." It is precise and conditional:

> Lexical few-shot feedback transfers the shop's **naming convention** to the
> modelling agent, but only when (a) the retrieved context is large enough to
> overcome the base model's prior (a **threshold** in k), and (b) the corpus
> contains an approved model of the **same entity** (transfer is
> *instance-level copying*, not convention *generalisation*). It does not change
> the model's **entity-identification** ability (already at ceiling) or its
> **over-linking** tendency.

This is a stronger dissertation contribution than a monotone "learning curve
goes up," because it characterises the *mechanism and its limits*, and it
explains the earlier null result (k=3 was sub-threshold).

## 5. Threats to validity / limitations

- **The k=10 transfer is a leakage (within-system) condition** — it is an upper
  bound on the retrieval mechanism, not a generalisation claim (F-2 makes this
  explicit via the LOO probe).
- **One system / one model / 2 seeds per point.** The *threshold value* (k≈10)
  is schema- and model-specific; the *shape* (threshold, not gradual) and the
  *instance-vs-convention* distinction are the transferable findings.
- **Retrieval is lexical.** A semantic retriever might surface same-entity
  examples at lower k (shifting the threshold) but would not, by itself, turn
  copying into generalisation.

## 6. Trade-offs

| Choice | Gain | Cost |
|---|---|---|
| Raise k to cross the threshold | naming convention adopted (0→1) | more prompt tokens per call; risk of context dilution on larger schemas |
| Rely on cross-system transfer (LOO) | no corpus curation per system | naming not transferred — mechanism is instance-level |
| Keep k low (k≤5) | cheapest | no naming benefit (sub-threshold) |

**Design implication:** to get convention *generalisation* (not just copying),
the naming signal should be delivered as an explicit, corpus-derived instruction
(a naming policy distilled from approved objects) rather than hoping the model
infers it from few-shot — or applied at the plan-reviewer stage, where naming is
already normalised in production.

> **⚠ Revised by Experiment 4.** The second alternative above ("applied at the
> plan-reviewer stage, where naming is already normalised") rests on an assumption
> that Experiment 4 **falsified**: the gpt-5.2 reviewer is *naming-neutral* — it
> preserves the modeller's names (`naming_adherence` 0→0 off, 1→1 on) and does
> **not** normalise them. So the reviewer is **not** a viable place to inject the
> naming convention. The two remaining levers are the ones this experiment
> established at the *modeller*: (a) raise *k* past the threshold (instance-level
> copying), or (b) distil an explicit corpus-derived naming instruction (the only
> route to true *generalisation*). See `experiment-4-endtoend-taxonomy.md` §4 F-A.

## 7. How to reproduce this experiment manually

1. Backend on Databricks with the corpus populated (see Experiment 1, step 1).
2. **Curve** — for each k, build the agent with the full corpus and that limit,
   generate, and score:
   ```python
   from dbt_builder.src.ai.agents.modeller import _load_reference_corpus, get_modelling_agent
   from dbt_builder.src.ai.discovery.schema_discovery import discover_from_yaml
   from dbt_builder.src.ai.evaluation import evaluate_plan, load_gold_models
   from dbt_builder.src.ai.settings import get_settings
   p = discover_from_yaml("poc/metadata/servicenow_it4it_discovery.yaml")
   cfg = get_settings().model_copy(update={"llm_seed": 42})
   loader = _load_reference_corpus(cfg)                     # full corpus
   agent = get_modelling_agent(settings=cfg, samples=1,
             reference_loader_override=loader, reference_limit_override=10)  # vary k here
   m = evaluate_plan(agent.propose(p),
             source_tables=tuple(t.name for t in p.tables),
             gold=load_gold_models()["SNOW_IT4IT_001"],
             technical_columns=cfg.technical_payload_column_set())
   print(m.gold_entity_f1, m.gold_naming_adherence)
   ```
   (Full script: `scratchpad/exp2_curve.py`.)
3. **Transfer probe** — repeat at k=10 with
   `_load_reference_corpus(cfg, exclude_catalogs=("edh_unreg_consumption_dev",))`
   and observe `naming_adherence` drop back to 0. Inspect the injected examples
   with `agent._reference_block(p)` to confirm they are *other-entity* examples.
   (Script: `scratchpad/exp2_loo.py`.)

The steps above are the *original* (scratchpad) procedure. The whole curve plus
the transfer probe is now reproducible in **one command**:

```bash
python -m dbt_builder.src.ai.evaluation experiment --system SNOW_IT4IT_001 \
  --condition off --condition k1:k=1 --condition k3:k=3 --condition k5:k=5 \
  --condition k10:k=10 --condition "loo_k10:k=10,exclude=edh_unreg_consumption_dev" \
  --seeds 42,43
```

Note each arm needs a **distinct label** (`k1`, `k3`, …): results are grouped by
label, so reusing one label across arms would merge them. The harness rejects
duplicate labels rather than silently averaging distinct conditions together.

## 8. Reproduction check (re-run through the unified harness)

The original run used bespoke scripts; the harness was built afterwards. The
curve and the transfer probe were **re-run** to verify the final tooling
reproduces the published result.

| k | naming_adherence (published → re-run) | entity_f1 (published → re-run) |
|---|---|---|
| 0 | 0.000 → **0.000** | 0.933 → 0.933 |
| 1 | 0.000 → **0.000** | 0.933 → 0.933 |
| 3 | 0.000 → **0.000** | 0.933 → 0.933 |
| 5 | 0.000 → **0.000** | 0.933 → 0.875 |
| **10** | **1.000 → 1.000** | 0.933 → 1.000 |
| **LOO k=10** | **0.000 → 0.000** | 0.875 → 0.933 |

**Both headline findings reproduce exactly, with zero seed variance:**
- **F-1 (threshold, not gradual):** `naming_adherence` is flat at 0 for k ≤ 5 and
  jumps to **1.0 at k = 10** — the phase-transition shape replicates precisely.
- **F-2 (instance-level copying, not generalisation):** leave-one-out at k=10
  returns `naming_adherence` to **0.0** — the model still receives 8 examples, but
  for *other* entities, and does not infer the convention. This is the claim that
  bounds the mechanism's generality, and it replicates exactly.

**Honest note on the wobble.** `entity_f1` moves ±0.06 within its ceiling band
across arms (e.g. k=5 0.933→0.875, k=10 0.933→1.000) — one spurious/extra hub
shifting across seeds under non-bit-exact temperature-0 inference. F-3
(correctness invariant to k) is unaffected: there is still no monotone trend in k,
and no claim depends on these sub-0.1 differences. Naming — the metric carrying
the findings — shows **zero** variance in every cell, which is why the conclusions
are robust.

*Provenance:* the k=0/1/3 arms and the k=5/10/LOO arms were run in two separate
invocations of the command above (an interrupted session), then combined. Arms are
independent by construction, so this does not affect the comparison.
