# Experiments & Evaluation (Phases 4–6)

How the feedback-learning system is measured for the dissertation, what is
stored where, how to verify a generated model is correct, and how to run every
experiment. Companion to `concepts-and-rationale.md`.

---

## 1. The feedback loop (what "learning" means here)

```
   ┌─────────── generate ───────────┐          ┌────────── learn ──────────┐
   discovery → modeller → plan → YAML → human APPROVE → corpus → retrieved
                  ▲                                                   │
                  └──────────── injected as few-shot examples ◄───────┘
```

The modeller proposes a `ModelingPlan`; a human approves it in the web app; the
approved objects become **few-shot examples** that are retrieved and injected
into the modeller's prompt on the next run. Retrieval is lexical (token overlap
on table/object names), deterministic, and gated by
`DWA_AI_LEARNING_EXAMPLES_ENABLED` (the on/off switch for the ablation study).

---

## 2. What is stored where — and where `iec_cim_metadata_v3.yaml` fits

This is the most common point of confusion. There are **three different YAML
representations**, and they are NOT the same thing:

| Artifact | Shape | Produced by | Stored in |
|---|---|---|---|
| **`iec_cim_metadata_v3.yaml`** (the *v3 monolithic* output) | ONE document for the whole source system (system, hubs, links, sats, staging, PIT/bridge, dims/facts, bv_sats) | `render_v3(plan, system, bv)` (`metadata_v3_emitter.py`) | **`dwa_meta_ai.yaml_versions`** — one row = the entire document |
| **Per-object dbt YAMLs** (`hub_x.yml`, `sat_x.yml`, …) | ONE file per hub/link/sat | `YamlGenerator` (re-run on approve, exploding the plan) | **`dwa_meta_ai.rv_examples`** — one row per object |
| **Gold sets** (`servicenow.yml`, `cim.yml`) | Hand-authored *expected* structure (names + business keys) | You (by hand) | `dbt_builder/src/ai/evaluation/gold_sets/` (in the repo, NOT Databricks) |

So, to answer directly:

- **`iec_cim_metadata_v3.yaml` is NOT stored in `rv_examples`.** It is the
  whole-system generated document; on approval it lands in **`yaml_versions`**.
  `rv_examples` gets the *per-object* explosion of the same approved plan — those
  granular objects are what the modeller retrieves as few-shot examples.
- **The experiments do NOT read `iec_cim_metadata_v3.yaml`.** They score the
  in-memory `ModelingPlan` against the **gold sets** (`gold_sets/*.yml`). The
  gold set is your hand-authored ground truth; the v3 file is a generated output.
- If you trust a particular `iec_cim_metadata_v3.yaml` as "correct", you can
  *derive* a gold set from it (list its expected hub/link/sat names and hub
  business keys into `gold_sets/cim.yml`). That is the intended way to turn a
  known-good output into a benchmark. The generated file itself is never the
  grader input.

---

## 3. How do we verify a generated YAML is correct?

There is no single oracle, so correctness is established in **four layers**,
cheapest first:

1. **Structural validity (objective, automatic).** Does the YAML compile? The
   dbt gate (`validation/dbt_gate.py`) runs `dbt parse`/compile against
   AutomateDV. Pass/fail. Nothing is approvable with ERROR-severity issues.
2. **Convention conformance (objective, automatic, no ground truth).**
   `score_plan()` checks the DV2 conventions the modeller is told to follow
   (naming prefixes, `HK_`/`HD_`, semantic business keys, link arity, no
   key/technical leak into satellite payloads, every hub has a satellite, …) and
   returns a scalar **conformance score** plus a typed **error taxonomy**.
3. **Reference correctness (needs a gold set).** `grade_against_gold()` compares
   the plan to hand-authored truth: **precision / recall / F1** on hubs, links,
   satellites, and **business-key accuracy**. This is the only layer that says
   whether the *right* entities were found, not just well-formed ones.
4. **Human review (the final word).** The approve / reject / request-changes
   action in the web app. This is simultaneously the quality judgement AND the
   training signal — the same click that accepts a model adds it to the corpus.

For a quick single-plan check use the CLI (§6): it runs layers 2 and 3 in one
command.

---

## 4. The experiments (Phase 4–6)

All metrics are pure functions over a `ModelingPlan` in
`dbt_builder/src/ai/evaluation/`.

### 4.1 Conformance + error taxonomy — `score_plan`
- **Measures:** fraction of DV2 convention checks passed; count of each
  `IssueType` (naming, surrogate_business_key, link_fk_unresolved,
  payload_key_leak, hub_without_satellite, …).
- **Why:** ground-truth-free quality signal available on every plan.
- **Reports:** `conformance_score ∈ [0,1]`, `issues_by_type` histogram.

### 4.2 Input → output coverage — `coverage`
- **Measures:** fraction of source tables that produced ≥1 object; lists the
  uncovered (silently dropped) tables.
- **Why:** a missed table is a modelling failure invisible to conformance.

### 4.3 Blast radius — `plan_blast_radius`, `weighted_error_impact`
- **Measures:** per object, how many downstream objects depend on it (a hub's
  satellites + the links referencing it). `weighted_error_impact` sums
  `1 + blast_radius` over each conformance issue.
- **Why:** an error on a high-fan-out hub is worse than one on a leaf satellite.
  The study shows retrieval preferentially removes *high-blast-radius* errors.

### 4.4 Gold precision / recall / F1 — `grade_against_gold`
- **Measures:** per-kind P/R/F1 + business-key accuracy vs a `gold_sets/*.yml`.
- **Why:** the reference-based correctness signal. Hubs/links are the strong
  signal; satellite names are noisier (topic suffixes vary) — read sat F1
  alongside conformance, not alone.

### 4.5 Ablation study — `run_ablation`
- **Design:** identical inputs, two arms — **learning OFF** (`k=0`) vs
  **learning ON** (`k=3`) — differing ONLY in approved-example retrieval.
- **Reports:** per-arm mean conformance, gold macro-F1, business-key accuracy,
  weighted error impact, and **mean latency** (§5). Expectation: ON ≥ OFF on
  quality; the delta is the measured value of the feedback loop.

### 4.6 Learning curve — `run_ablation` with corpus-size arms
- **Design:** a series of arms, each with an increasing number of approved
  examples in the corpus (0 → 5 → 10 → 20). Plot quality vs corpus size.
- **Reports:** a rising curve *is* the headline result — the system gets better
  as it accumulates human feedback. Complement with the longitudinal signals in
  `approvals` (approval rate up, pre-approval edit distance down over time).

---

## 5. Latency — what it is and its role here

**Latency** = wall-clock time to get a result: how long from "ask the modeller"
to "plan returned". It is a *cost/performance* dimension, orthogonal to
*quality* (a more accurate model that is far slower may not be worth it).

Where latency comes from in this system, largest first:
1. **The LLM call** dominates — seconds per completion. Batching, sample-voting
   and the process-global TPM token bucket (`modeller.py`) all shape it.
2. **Feedback retrieval adds two costs when learning is ON:** (a) a one-time
   corpus load from Databricks per agent build (`load_latest()`), and (b) a
   **larger prompt** — the injected examples add input tokens, so each LLM call
   is marginally slower and costs more. This is the price of the quality gain.
3. **Databricks round-trips** — approve() writes to Delta; a cold SQL Warehouse
   adds a one-off ~20–30 s start-up. Serverless keeps idle cost ≈ 0.

**Its role in the thesis:** the ablation reports `mean_latency_s` per arm, so the
learning-ON quality improvement is reported *against* its latency/token cost — a
fair, honest comparison rather than quality in isolation. If learning ON raises
F1 by X but latency by Y%, both numbers go in the results.

---

## 6. Running it — the CLI

```
# Verify ONE generated model (conformance + gold), e.g. after an approval:
python -m dbt_builder.src.ai.evaluation score --plan plan.json --gold cim \
       --source-tables terminals,equipment

# Run the learning OFF-vs-ON ablation over a folder of discovery payloads:
python -m dbt_builder.src.ai.evaluation ablation --payloads-dir ./payloads --k 3
```

- `score` takes a JSON dump of a `ModelingPlan` (from an approval's `plan_json`,
  or `plan.model_dump_json()`), prints the conformance score, issue list, and —
  if `--gold` matches a bundled set — the P/R/F1 + business-key accuracy.
- `ablation` reads discovery payloads from `--payloads-dir`, matches each to a
  gold set by `system_id`, builds a real modelling agent per arm (needs Azure
  OpenAI creds), toggles `learning_examples_enabled`, and prints the per-arm
  table including `mean_latency_s`. A learning curve is the same runner with
  corpus-size arms.

### 6.1 Where discovery payloads come from

The web-app pipeline builds the `DiscoveryPayload` **internally** during a run
and does **not** export it as a file. So for the study, the canonical file
artifact is the **offline discovery YAML** (`system` + `tables` + `columns`),
read by `discover_from_yaml` — e.g. `poc/metadata/iec_cim_discovery.yaml`. The
`ablation` CLI's `--payloads-dir` accepts:

- `*.yaml` / `*.yml` — discovery YAMLs (recommended; what you already author), and
- `*.json` — raw `DiscoveryPayload` dumps (if you export one from a run).

So point `--payloads-dir` at a folder of discovery YAMLs, one per source system.

### 6.2 Gold sets are STARTERS — verify them by hand

`gold_sets/servicenow.yml` and `gold_sets/cim.yml` are **templates, not final**.
Before trusting the gold F1 numbers, confirm each:

1. **`system_id` must equal the discovery payload's `system_id`** or the ablation
   won't pair payload↔gold. `cim.yml` is already keyed `IEC_CIM_001` to match
   `iec_cim_discovery.yaml`; `servicenow.yml` uses a placeholder `servicenow` —
   change it to your real ServiceNow discovery `system_id`.
2. **Object names must match what YOUR modeller emits** (e.g. `link_` vs the
   legacy `lnk_`, and the satellite topic suffixes). Run the modeller once, look
   at the produced names, and reconcile the gold names. `cim.yml` is aligned with
   the authoritative hand-model in `poc/metadata/iec_cim_metadata.yaml`.
3. **Business keys** should be the semantic keys you expect (mRID for CIM,
   `number`/`user_name`/`name` for ServiceNow).

`servicenow.yml` has no authoritative reference in the repo, so it needs the most
attention. See `gold_sets/README.md` for the format.

---

## 7. Suggested end-to-end run for the dissertation

1. **Populate the corpus:** in the web app, run discovery → generate → **approve**
   real models for a few source systems. Each approval writes to `yaml_versions`,
   `rv_examples`, and `approvals` in `edh_platform_config_dev.dwa_meta_ai`.
2. **Author gold sets** for the systems you can defend (start from the ServiceNow
   / CIM templates in `gold_sets/`), keeping scope small (5–10 tables).
3. **Export discovery payloads** for those systems as JSON into a `./payloads`
   folder (one file per system).
4. **Ablation:** `python -m dbt_builder.src.ai.evaluation ablation
   --payloads-dir ./payloads` → OFF vs ON table.
5. **Learning curve:** repeat with an increasing corpus (approve more, re-run).
6. **Report:** conformance, gold F1, business-key accuracy, blast-radius-weighted
   error impact, and latency — OFF vs ON and vs corpus size. The improvement is
   the contribution; the ablation + learning curve is the evidence.
