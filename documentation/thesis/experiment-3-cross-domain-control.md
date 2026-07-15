# Experiment 3 — Cross-domain control and the scope of the naming effect

**Research questions.**
1. **Safety:** does injecting examples from *unrelated* source systems **degrade**
   modelling of a target system? (A learning mechanism that helps within-domain
   but harms out-of-domain would be unusable in a shared corpus.)
2. **Replication/scope:** does the naming-transfer threshold from Experiment 2
   generalise to a second, independent system?

## 1. Design

- Test system: **IEC-61968 CIM** (`IEC_CIM_001`), 3 source tables
  (`conducting_equipment`, `connectivity_nodes`, `terminals`). Same model
  (`gpt-4.1`), structural grading, and leave-one-out discipline as Experiments 1–2.
- The corpus contains two CIM catalogs (`iec_cim`, `edh_unreg_silver_dev_st`) and
  two non-CIM ones (ServiceNow `edh_unreg_consumption_dev`, ITSM
  `edh_unreg_bronze_dev`). **Leave-one-out for CIM excludes both CIM catalogs**,
  so the ON-LOO corpus is *purely cross-domain* (ServiceNow + ITSM only).
- Conditions (2 seeds each): **OFF**; **ON-LOO k=3** (cross-domain); **ON-full
  k=10** (within-system); **ON-LOO k=10** (cross-domain at the Exp-2 threshold).

## 2. Results (mean of 2 seeds; zero variance across all cells)

| Condition | entity_f1 | naming_adherence | conformance | link_ratio |
|---|---|---|---|---|
| OFF | 1.000 | 1.000 | 1.000 | 2.00 |
| ON-LOO k=3 (cross-domain) | 1.000 | 1.000 | 1.000 | 2.00 |
| ON-full k=10 (within-system) | 1.000 | 1.000 | 1.000 | 2.00 |
| ON-LOO k=10 (cross-domain) | 1.000 | 1.000 | 1.000 | 2.00 |

## 3. Analysis

**F-1: Cross-domain learning is inert, not harmful (safety control passed).**
Feeding the CIM modeller purely non-CIM examples (ServiceNow + ITSM) — at k=3 and
k=10 — left every metric at its OFF value. Retrieval on CIM source tables
(`conducting_equipment`, `terminals`) finds little lexically-relevant material in
the ServiceNow/ITSM corpus, so the injected context does not perturb the output.
This is the key robustness result: **a shared, multi-system corpus does not
degrade an unrelated target** — learning is safe to leave enabled.

**F-2: Entity identification is at a perfect ceiling here.** CIM's three
mRID-keyed entities are unambiguous; `entity_f1 = 1.0` in every condition, with
no spurious hubs (unlike ServiceNow's cross-schema `hub_task`). Consistent with
Experiments 1–2: correctness is set by the base model, not by retrieval.

**F-3: The naming effect is invisible on CIM — because there is no naming gap to
close.** `naming_adherence = 1.0` even for OFF. CIM's *source tables are already
the concept names* (`conducting_equipment` → `hub_conducting_equipment`), so the
modeller's table-based naming coincides with the shop convention. (The model even
de-pluralises `terminals` → `hub_terminal`.) There is therefore no room for
feedback learning to improve naming. This **sharpens Experiment 2's finding into
a precise scope condition:**

> The feedback loop's naming benefit is realised **only when the source schema's
> table names diverge from the shop's concept convention** — e.g. ServiceNow's
> `core_`/`cmn_`/`sys_` prefixes. Where tables are already concept-named (CIM),
> the modeller is correct by default and there is nothing to transfer.

**F-4: Over-linking replicates** (`link_ratio = 2.0`: the model emits the correct
3-hub link plus one extra), independent of learning — as in Experiments 1–2.

## 4. Interpretation — consolidated across Experiments 1–3

The three experiments together give a defensible, non-trivial characterisation of
the feedback loop's value at the modelling stage:

| Dimension | Effect of feedback learning | Condition |
|---|---|---|
| Entity + key identification | none (at ceiling) | base model already competent |
| Naming convention | 0 → 1.0 **transfer** | requires (a) k above a threshold, (b) *same entity* in corpus, and (c) a *table-vs-concept naming gap* (else nothing to transfer) |
| Over-linking | none | structural, model-intrinsic |
| Cross-domain interference | none (inert, not harmful) | safe in a shared corpus |
| Latency | +0–3 s | negligible |

The contribution is a **map of where retrieval-based feedback helps, is inert,
and is safe** — more useful for a dissertation than a single up-and-to-the-right
learning curve, because it is falsifiable and it explains its own boundary cases.

## 5. Threats to validity / limitations

- **Ceiling effects.** CIM is small and unambiguous; its perfect scores limit
  what it can reveal (by design — it is the *control*, not the *treatment*).
- **Lexical retrieval.** F-1's inertness partly reflects that lexical retrieval
  finds little cross-domain material; a semantic retriever might surface
  (spurious) cross-domain neighbours and change the interference picture — worth
  testing.
- **Two seeds.** Justified by the zero observed variance, but a larger seed
  budget would tighten confidence intervals on any future non-ceiling system.

## 6. How to reproduce this experiment manually

1. Databricks backend + populated corpus (Experiment 1, step 1).
2. Cross-domain control — build the CIM agent with the **CIM catalogs excluded**
   so only non-CIM examples remain, then generate and score:
   ```python
   from dbt_builder.src.ai.agents.modeller import _load_reference_corpus, get_modelling_agent
   from dbt_builder.src.ai.discovery.schema_discovery import discover_from_yaml
   from dbt_builder.src.ai.evaluation import evaluate_plan, load_gold_models
   from dbt_builder.src.ai.settings import get_settings
   p = discover_from_yaml("poc/metadata/iec_cim_discovery.yaml")
   cfg = get_settings().model_copy(update={"llm_seed": 42})
   loo = _load_reference_corpus(cfg, exclude_catalogs=("iec_cim", "edh_unreg_silver_dev_st"))
   agent = get_modelling_agent(settings=cfg, samples=1,
             reference_loader_override=loo, reference_limit_override=10)
   m = evaluate_plan(agent.propose(p),
             source_tables=tuple(t.name for t in p.tables),
             gold=load_gold_models()["IEC_CIM_001"],
             technical_columns=cfg.technical_payload_column_set())
   print(m.gold_entity_f1, m.gold_naming_adherence)   # -> 1.0, 1.0 (inert + no gap)
   ```
   Compare to the OFF baseline (`reference_limit_override=0`) — identical.
   (Full script: `scratchpad/exp3_cim.py`.)
