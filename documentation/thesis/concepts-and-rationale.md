# DWA — Concepts & Rationale

A concept-by-concept walkthrough of the **Data Warehouse Automation (DWA)**
project: what each idea is, where it lives in the code, and *why* it was chosen.
Written for the MSc thesis and the private project write-up.

---

## Table of contents

1. [What the project is (problem statement)](#1-what-the-project-is-problem-statement)
2. [The pipeline at a glance](#2-the-pipeline-at-a-glance)
3. [Data Engineering concepts](#3-data-engineering-concepts)
4. [Data Vault 2.0 concepts](#4-data-vault-20-concepts)
5. [AI / LLM concepts](#5-ai--llm-concepts)
6. [ML / retrieval & embedding concepts](#6-ml--retrieval--embedding-concepts)
7. [Software & MLOps engineering concepts](#7-software--mlops-engineering-concepts)
8. [Consolidated "why these concepts" table](#8-consolidated-why-these-concepts-table)
9. [Glossary](#9-glossary)

---

## 1. What the project is (problem statement)

**DWA is a metadata-driven, AI-assisted generator for Data Vault 2.0 (DV2)
warehouses.** It looks at the *raw landing tables* of a source system (the
"bronze" layer in a lakehouse) and automatically proposes a complete Data Vault
2.0 model — Hubs, Links, Satellites, plus a Business Vault of PIT and Bridge
tables — emitting it as a deterministic metadata YAML that drives a dbt +
AutomateDV build.

The problem it solves: **DV2 modelling is expensive, slow, and inconsistent
when done by hand.** A senior data modeller has to inspect every source table,
decide which columns are business keys, find every foreign-key relationship,
decide how to split descriptive attributes into satellites by rate of change,
and keep the naming perfectly consistent so downstream tooling works. On a
50-table ServiceNow or CIM/IEC-61968 source that is days of repetitive,
error-prone work. DWA reduces that to a reviewable machine-generated plan
produced in minutes, with a human approving the result rather than authoring it.

**Two parallel "front ends" exist** for the same modelling knowledge:

- the **automated Python pipeline** (`dbt_builder/src/ai/**`) described in this
  document; and
- a **manual Claude-Code path** — loose agent/skill markdown files
  (`dv2-*.agent.md`, `dv-metadata-*.md`) that a human drives interactively to
  write the YAML incrementally.

The same DV2 rules live in both; the Python pipeline bakes them into prompts,
the manual path keeps them as editable skill files.

---

## 2. The pipeline at a glance

The whole system is a **linear, fail-fast pipeline** with a human approval gate
at the end. Orchestrated by `PipelineOrchestrator.run`
(`dbt_builder/src/ai/orchestration/orchestrator.py`):

```
SNAPSHOT ─► ANALYZE ─► ARCHITECT_BV ─► GENERATE ─► VALIDATE ─► (human approval)
   │           │            │             │           │
   │           │            │             │           └─ dbt compile gate
   │           │            │             └─ deterministic YAML emitter
   │           │            └─ deterministic PIT/Bridge + LLM BV satellites
   │           └─ LLM modeller: schema → DV2 plan (vote over N samples)
   └─ inspect bronze + vault, diff them → change-set
```

| Step | Module | Nature |
|------|--------|--------|
| **SNAPSHOT** | `pipeline/bronze_reader.py`, `pipeline/catalog_inspector.py`, `pipeline/diff_analyzer.py` | Deterministic data engineering |
| **ANALYZE** | `agents/schema_analyzer.py` → `agents/modeller.py` | LLM (the core AI step) |
| **ARCHITECT_BV** | `agents/bv_architect.py` (+ `bv_sat_proposer.py`) | Deterministic + LLM |
| **GENERATE** | `rendering/metadata_v3_emitter.py` | Deterministic rendering |
| **VALIDATE** | `validation/dbt_gate.py` | Deterministic verification |
| Cross-cutting | `supervision/supervisor.py` | Deterministic risk gate (human-in-the-loop) |

Key architectural decision visible in the orchestrator: **every step is wrapped
in try/except that converts any exception into a `PipelineStepResult(status=
'failed')`**, the run is updated *functionally* via `model_copy(update={…})`
(immutable state transitions), and the supervisor is consulted after SNAPSHOT,
ARCHITECT_BV and VALIDATE to optionally **pause** for human review. This keeps a
long, partly non-deterministic (LLM) pipeline auditable and recoverable.

---

## 3. Data Engineering concepts

### 3.1 The medallion / lakehouse architecture

**What.** Data flows through layers of increasing structure:
Bronze (raw CDC landing) → Staging → Raw Vault → Business Vault → (Information
mart). Documented in `README.md` and `documentation/docs/data_vault/`.

| Layer | Role |
|-------|------|
| Bronze | Append-only Delta tables; raw change-data-capture (CDC) with Insert/Update/Delete flags |
| Staging | AutomateDV `stage` macro adds hash keys, hashdiffs, derived columns |
| Raw Vault | Hubs, Links, Satellites — immutable, historised |
| Business Vault | PIT, Bridge, derived business rules |

**Why.** The medallion pattern is the lakehouse standard because it separates
*ingestion concerns* (cheap, append-only, schema-on-read) from *modelling
concerns* (curated, historised, query-optimised). DWA only ever *reads* bronze
and *writes* vault metadata — it never mutates source data, which keeps it a
safe, idempotent producer.

### 3.2 Change-Data-Capture (CDC), Delta, append-only

**What.** Bronze is an append-only Delta log with I/U/D flags; the vault is
insert-only and historised (satellites append a new version row whenever the
hashdiff changes). See the DV2 load rules in
`documentation/docs/data_vault/datavault_v2_principles.md`.

**Why.** Insert-only + hashdiff change detection is the foundation of DV2's
*full auditability* — you can reconstruct the state of any entity at any point
in time. It also makes loads idempotent and parallelisable (no update/delete
contention).

### 3.3 Snapshot → diff → idempotency (the SNAPSHOT step)

**What.** Before any AI runs, the pipeline takes two structural snapshots and
diffs them:

- `bronze_reader.read_bronze` lists + describes the bronze tables;
- `catalog_inspector.inspect_catalog` lists + describes the *existing* vault
  (or `greenfield_catalog_snapshot` for a brand-new build);
- `diff_analyzer.diff` joins them into a **ChangeSet** classifying every table
  as `NEW` / `DRIFT` / `UNCHANGED`, and every vault entity with no source as
  `ORPHANED`.

The diff is purely structural (column names + dtypes) and matches a bronze
table to a vault entity by stripping the `hub_`/`sat_`/`lnk_` prefix
(`diff_analyzer.py:_strip_vault_prefix`). High-risk changes (business-key
rename, dtype change on a key column) are flagged `ChangeRisk.HIGH`.

**Why.** This is what makes the generator **incremental and idempotent**:
re-running it on an unchanged source produces no work, and on a changed source
only the `NEW`/`DRIFT` tables are sent to the (expensive) LLM
(`schema_analyzer.py` filters to "actionable" tables). It also lets the
deterministic **supervisor** halt the run *before* spending a single token if
the change is too large or too risky — a cost-control and safety mechanism.

### 3.4 Schema discovery & empirical column profiling

**What.** `discovery/column_profiler.py` profiles a *sample* of rows
(`profile_column` / `profile_table`) and computes, per column: inferred type,
null-rate, cardinality ratio, and a few sample values. A column with a
cardinality ratio ≥ `0.99` is flagged as "likely a key"
(`_KEY_CARDINALITY_THRESHOLD`). `discovery/spark_discovery.py` adapts this to
Databricks/Spark; `discovery/system_columns.py` recognises technical/audit
columns.

**Why.** The LLM cannot reliably pick a *business key* from column names alone —
it needs empirical signal (is this column unique? is it mostly null? is it a
GUID or a human-meaningful value?). Profiling supplies exactly the features the
modelling prompt needs to choose a real business key over a surrogate, and to
detect FK relationships. Deliberately *sample-based* and DB-agnostic (input is
just `list[dict]`) so it works in tests, the PoC, and production identically.

### 3.5 dbt + AutomateDV code generation

**What.** The final artefact drives **dbt** with the **AutomateDV** package
(the de-facto open-source DV2 automation library for dbt). `dv_components/`
contains the OOP component model that renders dbt model SQL (hub/link/satellite
macros) and project YAMLs (`dbt_project.yml`, `sources.yml`, `packages.yml`).
The DV2 macro contracts (`src_pk`, `src_nk`, `src_hashdiff`, `src_payload`,
`src_ldts`, `src_source`) are documented in the principles doc.

**Why.** dbt is the industry standard for warehouse transformation (version
control, tests, lineage, environments); AutomateDV encodes the DV2 loading
patterns so DWA only has to emit *metadata*, not hand-written SQL. Generating
metadata rather than SQL keeps DWA decoupled from the warehouse dialect.

> The deterministic engine that turns the metadata YAML into the actual dbt +
> AutomateDV project (`dv_components`, `runners/dbt_builder.py`) is documented
> in depth in its own file: [`dv-components-sql-engine.md`](./dv-components-sql-engine.md).
> The metadata YAML is the seam between the AI half (this document) and that
> code-generation half.

### 3.6 Databricks, Spark, Unity Catalog

**What.** `api/databricks_uc.py`, `utils/spark.py`, `utils/databricks_sql.py`
and `databricks.yml` integrate with Databricks Unity Catalog for live catalog
inspection. `_resolve_describe_parallelism` lets table-describe calls run in
parallel against the warehouse.

**Why.** The target platform is a Databricks lakehouse; Unity Catalog is the
governed metadata source of truth for the bronze and vault schemas. Parallel
describe is a straightforward latency optimisation for wide schemas.

### 3.7 GitLab merge-request integration

**What.** `integrations/gitlab.py` / `utils/gitlab_mr.py` push approved YAML as
a merge request.

**Why.** The output must enter the team's normal review/CI/CD flow rather than
being written straight to production — the AI is a *proposer*, the MR is the
*control point*.

---

## 4. Data Vault 2.0 concepts

Data Vault 2.0 (Dan Linstedt) is the modelling methodology the whole project
automates. Full reference: `documentation/docs/data_vault/datavault_v2_principles.md`.
The modelling rules are encoded as the LLM's system prompt in
`agents/modeller.py` (`_BUILTIN_RV_RULES`) and the editable
`prompts/rv_modelling_rules.md`.

### 4.1 The three core entities

| Entity | Holds | DWA rule (from the modeller prompt) |
|--------|-------|-------------------------------------|
| **Hub** | A unique business key = the enterprise identity of a concept | Choose a *real, human-meaningful* business key; only fall back to `sys_id`/GUID when no semantic key exists |
| **Link** | A relationship between two+ hubs (the foreign keys, as hub hash keys) | **Every** FK-like column produces a link; association tables (e.g. `user`×`group`) produce one hub *per* entity plus a link |
| **Satellite** | Descriptive, changing attributes of one hub/link, historised | Payload contains *only* descriptive columns — never business keys, FK columns, or technical/CDC/audit columns |

### 4.2 Business keys vs. surrogate hash keys, and hashdiff

**What.** A hub stores the natural **business key** plus a deterministic
**hash key** `HK_<ENTITY>` (SHA-256 over the trimmed/upper-cased business key).
Satellites carry a **hashdiff** `HD_<ENTITY>` — a hash over the payload columns
— used to detect change.

**Why.** Hash keys give fixed-length, system-independent, *deterministic*
surrogate keys that can be computed in parallel across systems without lookups
(a defining DV2 advantage over sequence surrogate keys). Hashdiff turns
change-detection into a single equality check.

### 4.3 Multi-hub decomposition & link generation (the hardest part)

**What.** A single source table often yields *more than one hub*. An
association table (`sys_user_grmember` with `user` + `group`) must become
`hub_user`, `hub_group`, **and** `link_user_group`. Self-referencing columns
(`parent`, `manager`, `reports_to`) become self-links. The prompt explicitly
calls *under-modelling links and multi-hub tables* "the most common mistake".

**Why.** This is precisely where naïve automation (and junior modellers) fail —
collapsing everything into one `sys_id` hub destroys the relational structure.
Encoding it as a hard, repeated prompt rule (rules 1–4) is the single biggest
quality lever in the system.

### 4.4 Effectivity satellites

**What.** For every link, an `eff_sat_<link>` is created with a `driving_fk` and
`secondary_fk` (rule 5). This is an SCD2-style record of *when a relationship
was/was not effective*.

**Why.** Relationships change over time (a user leaves a group); the effectivity
satellite is DV2's standard way to historise relationship validity without
mutating the link.

### 4.5 Satellite split by rate of change

**What.** A hub's descriptive columns are split across satellites by how fast
they change (rule 6):

- `_details` (subgroup `details`, velocity `static`) — quasi-static specs;
- `_operational` (subgroup `operational`, velocity `dynamic`) — status/flags;
- `_measurements` (subgroup `measurements`, velocity `dynamic`) — numeric readings.

Max 3 satellites per hub (`SAT_CAP_PER_HUB`). The mapping is enforced in code
(`modeller.py:_VELOCITY_BY_SUBGROUP`) with asserts that tie it to the contract
vocabulary so it can't silently drift.

**Why.** A volatile column (status) changing should *not* force a new history
row for stable columns (serial number). Splitting by velocity keeps satellite
history compact and storage cheap — a core DV2 performance/governance practice.

### 4.6 Business Vault: PIT and Bridge tables

**What.** `bv_architect.py` builds the Business Vault. Crucially it splits
responsibility:

- **PIT (Point-In-Time)** and **Bridge** tables are produced *deterministically*
  from raw-vault topology alone (a hub with ≥2 satellites gets a PIT; a link
  touching ≥2 hubs gets a Bridge). No LLM.
- **Business-Vault satellites** (derived business rules) are *LLM-driven*
  because they encode logic that can't be inferred from structure — but only
  **pattern-gated** (see §5.9).

**Why.** PIT/Bridge are "pure mechanical constructs" — adding an LLM would add
latency, cost and non-determinism "for zero quality upside". This is a clean
example of *using the cheapest correct tool per sub-problem*: determinism where
structure suffices, the LLM only where genuine judgement is required.

### 4.7 AS_OF_DATE and PIT logic

**What.** The emitter uses an `AS_OF_DATE` snapshot column (never
`SNAPSHOT_DATE`), emits a dedicated `as_of_dates` section before `pit_tables`,
and every PIT references an `as_of_dates_table`. Defined in
`rendering/databricks_defaults.py` and `metadata_v3_emitter.py`.

**Why.** PIT tables are pre-joined snapshots "as of" a grid of dates that make
point-in-time queries fast; the `as_of_dates` grid is the spine they hang on.
Aligning the column name to the DV2 skills keeps the generated YAML consistent
with the team's hand-built conventions.

### 4.8 Deterministic emitter

**What.** `render_v3` (`rendering/metadata_v3_emitter.py`) is *fully
deterministic*: it sorts every top-level list by name and renders identical YAML
for identical input. All variability comes from the LLM *plan*, never from
rendering.

**Why.** Reproducibility: the same plan must always yield byte-identical YAML so
diffs are meaningful, reviews are stable, and the dbt compile gate tests the
real artefact. Pushing all non-determinism up into one isolated step (the
modeller) and keeping everything downstream deterministic is the central
reproducibility strategy of the whole system.

---

## 5. AI / LLM concepts

This is the research core. The LLM is used as a **structured reasoning engine
that maps a source schema to a Data Vault plan** — not as a chatbot.

### 5.1 LLM as a structured modeller (the ANALYZE step)

**What.** `ModellingAgent.propose` (`agents/modeller.py`) compacts the
discovery payload into a JSON prompt, calls Azure OpenAI, and returns a
validated `ModelingPlan` (a strict pydantic model: hubs/links/satellites with
business keys, FK columns, payloads, confidence, subgroup, velocity).

**Why.** Schema → DV2 mapping is a *judgement* task (which column is the
business key? is this an association table?) that resists pure heuristics but is
well within an LLM's pattern-matching ability when given the right empirical
signal. Framing it as "produce structured JSON conforming to a schema" (rather
than free text) is what makes the output machine-consumable and verifiable.

### 5.2 Structured output / JSON mode + strict contracts

**What.** For non-gpt-5 models the call requests
`response_format={"type":"json_object"}`; the result is validated against the
`ModelingPlan` pydantic contract (`contracts/decisions.py`) which is
`extra="forbid"`. The strict-JSON *output contract* (`_OUTPUT_CONTRACT`) is kept
in code and appended to the editable rule file so it can never be edited away.

**Why.** JSON mode guarantees syntactic validity; the pydantic contract
guarantees *shape*; together they turn an LLM into a typed function. `extra=
"forbid"` catches drift (a model inventing keys) rather than silently ignoring
it.

### 5.3 Self-consistency: majority voting over N samples (ensembling)

**What.** By default the agent draws **N=3** independent completions and
**votes**: each plan's fingerprint = `(sorted hub names, sorted link names,
sorted sat names)`; the most frequent fingerprint wins; ties break by total
confidence then lowest index (`_vote`). Invalid samples are dropped rather than
re-prompted.

**Why.** This is the **self-consistency** technique — sampling multiple
reasoning paths and taking the majority answer measurably improves correctness
on structured-reasoning tasks versus a single greedy decode. Voting on the
*structural fingerprint* (not the raw text) is the right granularity for DV2:
two plans that name the same hubs/links/sats are "the same answer" even if
payloads differ slightly. Dropping (not re-prompting) invalid samples keeps
latency and cost bounded.

### 5.4 Two-model generate → review (a stronger critic)

**What.** `agents/plan_reviewer.py` implements a second model in a
generator→reviewer flow: a fast generator drafts the plan, then a *stronger*
model is given the draft + source tables and asked to critique and patch it
(fix weak keys, add missed links, re-split satellites). It is **fail-safe by
construction** — any problem (disabled, empty/invalid reply, schema-invalid
result, or a review that catastrophically drops the model) falls back to the
original plan. The reviewer works at the *plan* (JSON) level, never the rendered
YAML, so the emitter stays deterministic.

**Why.** A cheap model for breadth + an expensive model for a single
high-quality review pass is a strong cost/quality trade-off (cf. "LLM-as-a-judge"
and refine-then-critique patterns). Making it strictly non-destructive means
review "can only improve the plan or no-op; it can never break the pipeline".

### 5.5 Agentic tool-calling loop (function calling)

**What.** `agents/tool_loop.py` is a model-agnostic engine driving the standard
OpenAI function-calling protocol (`tool_calls → execute → feed back`). The
modeller can inject `ToolSpec`s (e.g. to fetch more column detail on demand).
It knows nothing about Data Vault — pure infrastructure. Note: tool-calling is
incompatible with `response_format=json_object`, so the loop strips it.

**Why.** Tool-calling lets the model *pull* extra context only when it needs it,
rather than stuffing the entire catalogue into one prompt. Keeping the engine
domain-agnostic and stdlib-only makes it reusable and trivially testable.

### 5.6 Prompt engineering: editable rules + code-side contract

**What.** Each agent's system prompt is assembled from two parts: **rules** read
from an editable markdown file (`prompts/rv_modelling_rules.md`, overridable via
`DWA_AI_AI_PROMPTS_DIR`) **plus** a **code-side output/JSON contract** appended
in code. A byte-identical `_BUILTIN_*` fallback lives in code so the agent
degrades gracefully if the file is missing. The rules themselves are heavily
domain-specific (ServiceNow patterns, IEC-61968/CIM patterns, naming, ordering).

**Why.** Ops/modellers can tune *modelling judgement* (the rules) without a code
deploy, but the *transport contract* (strict JSON, no prose) can never be edited
away — separating "policy you may change" from "invariants you may not" is a
deliberate prompt-governance decision. The in-code fallback guarantees the agent
never sends an empty system prompt.

### 5.7 Context-window management: batching + adaptive recursive splitting

**What.** Large catalogues exceed the model's context/completion limits. Two
mechanisms handle it:

- **Batching** (`_propose_batched`): split tables into fixed-size batches, run
  each batch's completion concurrently, merge plans by name-union. Trades
  cross-batch link discovery for ~linear speedup.
- **Adaptive recursive splitting** (`_propose_voted_adaptive`): if *every*
  sample in a batch fails with *invalid JSON* (the signature of output
  truncation — the plan exceeded the completion-token budget), halve the table
  set and recurse until each piece fits (down to one table), then merge. A
  schema-invalid failure is *not* split (halving won't fix a malformed-but-
  complete plan) — it re-raises so the real cause surfaces fast.

**Why.** This makes the modeller **self-tune to any table width** without a
hand-guessed `batch_size`, and turns "the whole run failed after minutes" into
"a couple of tables got their own smaller call". The distinction between
*truncation* (split helps) and *malformed* (split wastes calls) is a precise,
cost-aware control.

### 5.8 LLM rate-limiting: RPM semaphore + TPM token bucket

**What.** Two process-global gates protect the Azure deployment
(`agents/modeller.py`):

- `_LLM_SEMAPHORE` (a `BoundedSemaphore`) bounds *simultaneous in-flight
  requests* (≈ requests-per-minute);
- `_LLM_TOKEN_BUCKET` (a thread-safe token bucket) bounds *tokens consumed per
  minute* (TPM), estimating cost from prompt-chars/4 + completion budget.

Oversized single calls are clamped to one minute's capacity and force serial
pacing with a warning.

**Why.** Azure OpenAI returns HTTP 429 when *either* RPM *or* TPM is exceeded,
and real workloads with uneven prompt sizes hit **TPM first** — so a
request-count limiter alone is insufficient. Modelling both quotas explicitly is
what keeps a fan-out (voting × batching) workload from self-DoSing the
deployment. This is essentially client-side backpressure.

### 5.9 Tolerant output coercion (robustness at the boundary)

**What.** `_coerce_plan_dict` reshapes raw LLM JSON to fit the strict contract
*without inventing data*: drop unknown keys, normalise field-name variants,
coerce scalars to lists, lowercase enums, cap satellites per hub, merge
same-named entities (union their keys), enforce cross-entity uniqueness
(hub > link > satellite precedence), and drop individually invalid satellites so
"one bad entity can't fail an otherwise-good plan". It also cleans satellite
payloads (strip own business key, FK columns, technical columns).

**Why.** More capable/verbose models (e.g. gpt-4.1) add descriptive keys the
strict contract rejects, which would fail *every* otherwise-good plan. Coercing
at the boundary lets the contract stay strict (catching real drift) while
tolerating harmless verbosity — Postel's law applied to LLM output. Critically
it *never fabricates*, only prunes/reshapes what the model produced.

### 5.10 Anti-hallucination by construction (pattern-gated BV sats)

**What.** `agents/bv_sat_proposer.py`: deterministic pattern detectors
(`bv_sat_patterns.py`) scan the accepted plan and surface candidate BV
satellites (e.g. `voltage_tier`, `manufacturer_normalised`). **If zero patterns
match, no LLM call is made at all.** When patterns do match, the LLM may only
*confirm/reject and refine* — it is "explicitly forbidden from inventing new BV
satellites". Every confirmed proposal is then structurally validated (every
column in the derivation SQL must exist in the parent hub's payload) or dropped.

**Why.** Directly answers the stated user requirement *"I don't want the LLM to
hallucinate."* Patterns are the deterministic, auditable **floor**; the LLM adds
judgement **on top** but can never manufacture an artefact no pattern justified.
This "deterministic floor + LLM ceiling" pattern recurs throughout the system
(see also §4.6) and is the project's core trust strategy.

### 5.11 Deterministic risk supervisor (human-in-the-loop)

**What.** `supervision/supervisor.py` evaluates the run after SNAPSHOT,
ARCHITECT_BV and VALIDATE. It is **purely deterministic — no LLM calls** — with
all thresholds in one `SupervisorConfig` (e.g. `max_new_tables=15`,
`drift_fraction_threshold=0.40`, `low_confidence_fraction_threshold=0.40`,
`pause_on_validation_errors=True`). When it recommends PAUSE and the operator
hasn't set `acknowledge_risks`, the run halts with `status=PAUSED` and the
assessment is attached for the UI.

**Why.** The expensive/risky decision of "should a human look at this before we
continue?" must itself be **predictable and explainable** — using an LLM to
police the LLM would add cost and another non-deterministic failure mode. Hard
thresholds give an auditable safety gate and a clean human-in-the-loop seam
("Continue anyway" after reviewing the banner).

### 5.12 Verification grounding: the dbt compile gate

**What.** `validation/dbt_gate.py` writes the generated metadata out as real dbt
model YAMLs and runs `dbt parse` → `dbt compile` (and `dbt build` when sample
data exists). Any dbt failure becomes a blocking ERROR `ValidationIssue`. The
dbt runner is injected so the gate is unit-testable without dbt-core or a
warehouse.

**Why.** This is the project's ultimate **grounding / verification** step: a
plan is only approvable if it *genuinely compiles into a buildable AutomateDV
project*. It turns "the LLM said this is valid" into "the compiler proved it
builds" — the strongest possible check against subtle structural errors.

### 5.13 Model selection rationale (gpt-4o vs gpt-5)

**What.** `settings.py`: `primary_chat_deployment` defaults to **gpt-5** (stronger
structured reasoning) but the *modeller* (`modeller_chat_deployment`) defaults to
**gpt-4o**. The modeller is the hottest TPM consumer (fans out across many large
batches); gpt-5 spends budget on invisible reasoning tokens and typically has
the lowest TPM quota, making it the dominant 429 source.

**Why.** A documented, deliberate cost/throughput/quality trade-off: use the
strong reasoning model where a single high-value judgement is made (reviewer,
other agents) and the cheaper deterministic model (temperature 0, no
reasoning-token overhead, 3–5× TPM headroom) for the high-fan-out hot path.

---

## 6. ML / retrieval & embedding concepts

### 6.1 Text embeddings with a content-addressed cache

**What.** `embeddings/embedder.py` wraps Azure OpenAI
`text-embedding-3-small` (1536-dim). Each `(text, model)` pair is hashed
(SHA-256) and the vector cached on disk, sharded into 256 sub-dirs by first hash
byte. Misses are embedded in batches (up to 2048 inputs/request); transient
errors retry with **tenacity** exponential backoff (5 attempts).

**Why.** Embeddings are deterministic for a given input, so caching makes
re-embedding the same column description free — a direct **cost and latency**
win, plus reproducibility. Batching respects the API's input limit; backoff
handles rate limits/5xx gracefully.

### 6.2 Vector store: FAISS (cosine) with a metadata sidecar

**What.** `embeddings/faiss_store.py` is an on-disk FAISS index. Vectors are
row-normalised so inner-product == cosine similarity (`_normalize`). FAISS holds
only floats, so ids + metadata live in a `<index>.meta.json` sidecar aligned to
FAISS row order. It is explicitly **single-writer** (in-memory mutate → atomic
file replace). An Azure AI Search backend (`azure_search_store.py`) implements
the same `VectorStore` interface (`vector_store.py`) for the managed,
multi-writer case.

**Why.** FAISS gives fast approximate-nearest-neighbour search locally with no
service dependency — ideal for single-process runs and tests. The shared
`VectorStore` interface (dependency inversion) means the managed Azure backend
can be swapped in without touching callers. Cosine via normalised inner product
is the standard similarity metric for text embeddings.

### 6.3 Retrieval-augmented generation → lexical reference loader (a reversal)

**What.** The pipeline originally used FAISS / Azure AI Search to retrieve
similar hub/sat/link structures as **few-shot examples** at prompt time (classic
RAG). `reference/loader.py` documents a deliberate move *away* from that: it now
loads a directory of curated, approved raw-vault YAMLs once, parses each into a
typed record, and selects the most relevant examples by **lexical overlap
score** — "pure and reproducible".

**Why.** A documented, evidence-based engineering decision worth highlighting in
a thesis: the embedding-based retrieval (a) required a running embedding
deployment, (b) was non-deterministic across cache invalidations, and (c) added
a network hop per call. For a *small, curated* example set, lexical selection is
**deterministic, dependency-free, and good enough** — a case where the simpler
non-ML method beats the ML one. The embedding/vector machinery (§6.1–6.2)
remains in the codebase for larger-scale retrieval needs.

### 6.4 Feedback learning — closing the loop (the core contribution)

**What.** `ai/feedback-learning` turns the static reference loader (§6.3) into a
**self-improving** one. On human **approval**, the plan is exploded into
per-object rows and appended to a Databricks Delta corpus
(`dwa_meta_ai.rv_examples`, `store/corpus.py` + `store/yaml_store.py`); on the
next run the modeller retrieves the most lexically-relevant approved objects
(`ReferenceLoader.from_corpus_rows` → `modeller._reference_block`) and injects
them into its prompt. The approval action is therefore **both** the quality
judgement **and** the training signal. Gated by `learning_examples_enabled` (off
= prompt byte-identical to before → the ablation control).

**Why.** This is the thesis's central claim made operational: that accumulating
human feedback measurably improves the modeller. Retrieval stays **lexical, not
vector** for the same reasons as §6.3 (tiny human-gated corpus, identifier — not
prose — queries, determinism, zero standing infra); the German/English synonymy
gap is handled by a small alias map rather than re-introducing embeddings. The
effect is measured by the evaluation package (conformance, gold P/R/F1,
blast-radius, latency) via a **learning-OFF-vs-ON ablation** and a **learning
curve** — see `experiments-and-evaluation.md`.

---

## 7. Software & MLOps engineering concepts

These are the "how it's built well" concepts — relevant to the thesis's
software-engineering contribution.

### 7.1 Typed contracts everywhere (pydantic)

**What.** Every inter-step payload is a pydantic model in `contracts/`
(`ModelingPlan`, `DiscoveryPayload`, `BvProposal`, `CatalogSnapshot`,
`ChangeSet`, `PipelineRun`, `RiskAssessment`, `ValidationIssue`, …). Strict
(`extra="forbid"`), with `Literal` enums and `min_length` constraints that the
coercion layer *reads from the model* rather than re-listing.

**Why.** The contracts are the single source of truth; deriving accepted enum
values and min-item counts *from* the contract (`_literal_str_values`,
`_field_min_items`) guarantees the tolerant-coercion layer can never drift from
the schema. This is type-driven design used to keep an LLM honest.

### 7.2 Dependency injection & testability

**What.** Catalog access, the dbt runner, `propose_fn`, the BV-sat proposer, and
the LLM client are all injected. The orchestrator takes optional
`schema_analyzer`/`bv_architect`/`yaml_generator`/`supervisor`. Modules import
step-modules directly (never the service facade) to avoid circular imports.

**Why.** Everything is unit-testable without Azure, dbt-core, Spark, or a
network — the seams (`propose_fn`, `DbtCommandRunner`) let tests pass stubs.
This is what makes a heavily-external system (LLM + warehouse + dbt) actually
testable in CI.

### 7.3 Immutable, functional pipeline state

**What.** `PipelineRun` is updated *functionally* — each step returns a new
instance via `model_copy(update={…})`; nothing is mutated in place.

**Why.** Immutable state transitions make the run history a clean audit trail
and eliminate a whole class of partial-update bugs in a multi-step pipeline.

### 7.4 Determinism & reproducibility as a first-class goal

**What.** Recurring theme: deterministic emitter (§4.8), deterministic
PIT/Bridge (§4.6), deterministic supervisor (§5.11), optional `seed` per sample
in the modeller, alphabetical ordering forced in both prompt rules and emitter,
content-addressed embedding cache. *All* non-determinism is concentrated in the
LLM sampling step and then collapsed by voting.

**Why.** For a generator whose output feeds version control + CI, reproducibility
is non-negotiable — stable diffs, repeatable reviews, and a compile gate that
tests a stable artefact. Concentrating randomness in one place and neutralising
it (voting) is the architectural expression of that goal.

### 7.5 Configuration & secrets management

**What.** `settings.py` (`AISettings`, pydantic-settings) loads all config from
env vars prefixed `DWA_AI_` and an optional `.env`, with `SecretStr` for keys.
`.env` is gitignored; settings load failures fall back to safe permissive
defaults so tests run without credentials.

**Why.** Twelve-factor config: no secrets in code, environment-overridable
behaviour, and graceful degradation in credential-less environments (CI / unit
tests).

### 7.6 Resilience: retries, backoff, graceful degradation

**What.** Tenacity exponential backoff on embeddings; empty-response and
truncated-JSON retries (with doubled, then *clamped*, token budgets) in the
modeller; per-batch failures are skipped (not fatal) so a large run still yields
a reviewable partial plan; the reviewer always falls back to the original plan.

**Why.** Every external dependency (Azure, dbt, warehouse) can fail
transiently; the system is engineered so that *partial success is still useful*
and no single transient error discards minutes of work.

### 7.7 Observability

**What.** Structured `logging` throughout (timings per step, batch sizes,
sample completion times, vote outcomes, gate config). C4 architecture diagrams
live in `documentation/c4/` (Structurizr).

**Why.** A multi-step, partly non-deterministic, fan-out pipeline is only
operable if you can see where time and tokens go and why a plan was chosen.

### 7.8 Human-in-the-loop approval & web UI

**What.** A FastAPI backend (`api/`) + Vite/React UI (`ui/`) run via `pnpm dev`.
Routers expose discovery, pipeline runs, plans, approvals and history. The
supervisor's PAUSE surfaces a risk banner; approved YAML is stored
(`store/yaml_store.py`) and can be pushed as a GitLab MR.

**Why.** The whole design treats the AI as a *proposer under human control*, not
an autonomous actor. The approval gate + MR flow are the governance backbone.

---

## 8. Consolidated "why these concepts" table

| Concept | Category | Why chosen (one line) |
|---------|----------|------------------------|
| Medallion / lakehouse | Data eng | Industry-standard separation of ingestion vs. curation; DWA only reads bronze, writes vault metadata |
| CDC + insert-only + hashdiff | Data eng / DV2 | Full auditability and idempotent, parallel loads |
| Snapshot → diff → change-set | Data eng | Incremental, idempotent generation; cost gate before any LLM call |
| Column profiling | Data eng / ML-feature | Supplies empirical key/FK signal the LLM needs; DB-agnostic and sample-based |
| dbt + AutomateDV | Data eng | Standard transformation tooling; DWA emits metadata, not dialect-specific SQL |
| Data Vault 2.0 | Modelling | Auditable, parallel-loadable, source-agnostic enterprise warehouse method |
| Hash keys / hashdiff | DV2 | Deterministic, lookup-free surrogate keys + O(1) change detection |
| Multi-hub + mandatory links | DV2 | Prevents the #1 modelling mistake (collapsed `sys_id` hubs) |
| Satellite split by velocity | DV2 | Keeps history compact; volatile columns don't rewrite stable history |
| Deterministic PIT/Bridge | DV2 + design | Mechanical constructs need no LLM — zero quality upside, real cost downside |
| LLM structured modeller | AI | Schema→DV2 mapping is judgement that resists heuristics but suits an LLM |
| JSON mode + strict pydantic | AI | Turns the LLM into a typed, verifiable function |
| Self-consistency voting | AI/ML | Majority over N samples beats single greedy decode on structured reasoning |
| Two-model generate→review | AI | Cheap breadth + expensive critique; strictly non-destructive |
| Tool-calling loop | AI | Model pulls extra context on demand instead of stuffing the prompt |
| Editable rules + code contract | AI/governance | Tune judgement without deploy; never let invariants be edited away |
| Batching + adaptive splitting | AI | Self-tunes to context limits; distinguishes truncation from malformed output |
| RPM semaphore + TPM bucket | AI/infra | Azure 429s come from TPM first; request-count limiting alone is insufficient |
| Tolerant coercion | AI/robustness | Strict contract + Postel's law; tolerate verbosity, never fabricate |
| Pattern-gated BV sats | AI/trust | "No hallucination": deterministic floor, LLM only refines on top |
| Deterministic supervisor | AI/safety | The policing layer must itself be predictable and explainable |
| dbt compile gate | AI/verification | "The compiler proved it builds" beats "the LLM said it's valid" |
| Embedding cache + FAISS | ML/retrieval | Cheap, deterministic, reproducible nearest-neighbour search |
| RAG → lexical reference loader | ML/retrieval | For a small curated set, simpler deterministic selection beats embeddings |
| Pydantic contracts + DI | SW eng | Single source of truth; fully testable without external services |
| Immutable functional state | SW eng | Clean audit trail; no partial-update bugs |
| Determinism-first | SW eng | Stable diffs/reviews and a meaningful compile gate |

---

## 9. Glossary

- **DV2 / Data Vault 2.0** — Dan Linstedt's modelling methodology (Hubs, Links,
  Satellites + Business Vault) optimised for auditability and parallel loading.
- **Hub / Link / Satellite** — the three raw-vault entity types (business keys /
  relationships / descriptive history).
- **Effectivity satellite** — SCD2 record of when a relationship was effective.
- **PIT / Bridge** — Business-Vault performance structures (point-in-time
  snapshots / pre-joined link spans).
- **AS_OF_DATE** — the snapshot-date spine PIT tables are built on.
- **Hashdiff** — hash over a satellite's payload, used to detect change.
- **Bronze / Medallion** — raw append-only landing layer in a lakehouse.
- **CDC** — Change-Data-Capture (Insert/Update/Delete event stream).
- **dbt / AutomateDV** — transformation framework / its DV2 automation package.
- **Self-consistency** — sample multiple reasoning paths, take the majority.
- **RAG** — Retrieval-Augmented Generation (inject retrieved examples into the
  prompt).
- **TPM / RPM** — tokens-per-minute / requests-per-minute API quotas.
- **Token bucket** — rate-limiting algorithm that refills capacity over time.
- **Postel's law** — "be liberal in what you accept, strict in what you emit";
  here, tolerant input coercion against a strict output contract.

---

*Generated from a reading of the DWA source tree (`dbt_builder/src/ai/**`),
the README, and `documentation/docs/data_vault/`. Cross-check any quoted
threshold/default against the current code before citing — defaults such as
sample count, satellite cap, and model deployments are env-overridable in
`settings.py`.*
