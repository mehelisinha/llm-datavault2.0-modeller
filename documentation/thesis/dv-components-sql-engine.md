# DWA — The `dv_components` SQL Generation Engine

This document covers the **deterministic code-generation half** of DWA — the
engine that turns a metadata YAML into a runnable dbt + AutomateDV project. It
complements [`concepts-and-rationale.md`](./concepts-and-rationale.md), which
covers the AI half that *produces* the metadata. Together they close the loop:

```
  AI pipeline (dbt_builder/src/ai)              dv_components engine (dbt_builder/src/dv_components)
  ──────────────────────────────────           ───────────────────────────────────────────────────
  source schema ──► ModelingPlan ──► METADATA YAML ──► typed DvModels ──► dbt .sql + .yml project
       (LLM, non-deterministic)        (the contract)     (deterministic, no AI)
```

The metadata YAML is the **clean seam** between the two halves: the AI side only
has to emit it correctly; this engine only has to compile it. Either side can be
driven by hand (the manual Claude-Code path writes the same YAML; `DBTBuilder`
can build any YAML, AI-generated or hand-authored).

Same structure as the companion doc: **what / where in code / why chosen.**

---

## Table of contents

1. [End-to-end flow](#1-end-to-end-flow)
2. [Metadata-driven generation](#2-metadata-driven-generation)
3. [Typed models & discriminated unions](#3-typed-models--discriminated-unions)
4. [The component class hierarchy](#4-the-component-class-hierarchy)
5. [Factory + manager dispatch](#5-factory--manager-dispatch)
6. [Two-level (meta) Jinja2 templating](#6-two-level-meta-jinja2-templating)
7. [AutomateDV macro wrapping](#7-automatedv-macro-wrapping)
8. [Per-entity generation: staging, hub, link, satellite, eff-sat](#8-per-entity-generation)
9. [dbt config, materialisation & tests](#9-dbt-config-materialisation--tests)
10. [Project-level artefacts & custom macros](#10-project-level-artefacts--custom-macros)
11. [Design-pattern inventory & rationale](#11-design-pattern-inventory--rationale)

---

## 1. End-to-end flow

**What.** `runners/dbt_builder.py::DBTBuilder.build()` is the entry point:

1. `Metadata(metadata_path)` (`runners/metadata.py`) parses the DWA metadata YAML
   into typed component models (`get_all_component_models()` → `dict[str,
   list[DvModels]]`).
2. `cleanup_output_location()` wipes and recreates the output dir (with a guard
   refusing to delete a filesystem root).
3. For every component model, `DVComponentManager` writes a `.sql` and/or `.yml`
   file into the correct dbt folder.

**Where.** `runners/dbt_builder.py`, `runners/metadata.py`,
`manager/dv_component_manager.py`.

**Why.** A single, dumb orchestrator (parse → iterate → write) with all the
intelligence pushed into typed models + per-component generators. The build is
**idempotent**: it cleans and fully regenerates the project every run, so the
output is a pure function of the metadata YAML — the same reproducibility
philosophy as the AI emitter (`render_v3`).

---

## 2. Metadata-driven generation

**What.** Nothing about a specific source system is hard-coded in the engine.
Every hub/link/sat/staging model, plus the column lists, hash keys, payloads and
dbt config, comes from the metadata YAML. The engine is a *pure interpreter* of
that contract. `iec_cim_metadata_v3.yaml` and `poc/metadata/iec_cim_metadata.yaml`
are reference instances of the YAML shape.

**Where.** `runners/metadata.py` (YAML → models),
`dv_components/**` (models → files).

**Why.** **Metadata-driven design** is the whole thesis of "data warehouse
automation": separating *what to build* (declarative metadata) from *how to
build it* (the engine). Adding a new source system never touches code — only the
YAML changes. It also makes the AI side's job well-defined: produce valid
metadata, nothing more.

---

## 3. Typed models & discriminated unions

**What.** Every component is a pydantic model with a `dv_type` literal
discriminator. `pydantic_model/discriminator.py` assembles them into
discriminated unions:

- `SqlModels` = Hub | Link | Satellite | EffSat | Staging | Macro
- `BvModels` = Pit | Bridge | Dim | Fact | BvSat
- `ProjectModels` = Project | Source | Profiles | Packages
- `DvModels` = the union of all of the above (`Field(discriminator="dv_type")`)

Raw-vault leaf models (`pydantic_model/sql/raw_vaul.py`):

| Model | DV-specific fields | Validation |
|-------|--------------------|------------|
| `HubModel` | `src_pk`, `src_nk`, `src_ldts` | — |
| `LinkModel` | `src_pk`, `src_fk: list[str]`, `src_ldts` | — |
| `SatelliteModel` | `src_pk`, `src_hashdiff`, `src_payload: list[str]`, `src_eff?` | exactly **one** `source_model` |
| `EffSatModel` | `src_dfk`, `src_sfk: str\|list`, `src_start_date`, `src_end_date` | exactly **one** `source_model` |

Each model also knows its own `models_path` (e.g. `RAW_VAULT/hubs`,
`RAW_VAULT/links`), so file placement is data, not code.

**Where.** `pydantic_model/sql/raw_vaul.py`, `staging.py`, `business_vault.py`,
`base.py`, `enums.py`, `discriminator.py`.

**Why.** The discriminated union is the key design choice: pydantic reads
`dv_type` and **automatically picks the right model class** during YAML parsing,
giving validated, type-safe components for free. A `SatelliteModel` *cannot* be
constructed with two source models (DV2 rule: a satellite has exactly one
parent source) — the contract enforces a modelling invariant at parse time, long
before any SQL is rendered. This mirrors the AI side's strict `ModelingPlan`
contract — **the same "make illegal states unrepresentable" discipline on both
halves**.

---

## 4. The component class hierarchy

**What.** A small abstract hierarchy (`components/base.py`):

```
DVBaseYmlGenerator (ABC)          ── owns model+logger, builds the dbt schema .yml
└── DVBaseComponentGenerator (ABC) ── adds SQL rendering pipeline (renderer, config, formatter)
    ├── DVBaseRawVaultComponent    ── config: materialized=incremental, strategy=merge, tag raw_vault
    │   ├── HubComponent
    │   ├── LinkComponent
    │   └── SatelliteBaseComponent
    │       ├── SatComponent       (regular satellite: hashdiff + payload)
    │       └── EffSatComponent    (effectivity satellite: dfk/sfk + start/end dates)
    └── DVBaseStagingComponent     ── config: materialized=view, tag staging
        └── StagingComponent
```

Each concrete subclass implements three abstract methods:
`_get_sql_config()`, `_sql_template_body` (the Jinja template), and
`_get_render_kwargs()` (the variables), plus `_cols_for_yml` for the schema YAML.

The base `generate_sql_str()` runs the fixed pipeline:
`_render(**_get_render_kwargs())` → `env.from_string(config_macro + body).render(...)`.

**Where.** `components/base.py` and the `components/sql/raw_vault/*.py` leaves.

**Why.** **Template Method pattern.** The base class fixes the *invariant
algorithm* (build config → assemble template → render) and the subclasses fill in
only the *variant parts* (which AutomateDV macro, which fields). This is why
adding a new entity type is ~30 lines (a template body + kwargs), and why every
component automatically gets consistent config-building, tagging, and YAML
generation. Raw-vault vs staging "flavour" bases centralise the
materialisation strategy so it lives in exactly one place per layer.

---

## 5. Factory + manager dispatch

**What.** Two cooperating objects:

- `DVComponentFactory.create(model)` (`components/factory/dv_component_factory.py`)
  maps `model.dv_type` → the right component class via a `_handlers` dict and
  instantiates it.
- `DVComponentManager` (`manager/dv_component_manager.py`) wraps a model +
  project path: it computes the output path from the model's own
  `models_path`/`file_name`, calls `generate_sql_str()` / `generate_yml_str()`,
  and writes each requested `file_extension` via the shared `FileManager`.

**Where.** `components/factory/dv_component_factory.py`,
`factory/dv_model_factory.py`, `manager/dv_component_manager.py`.

**Why.** **Factory pattern + registry dict** keeps dispatch open for extension
(add a handler entry) and closed for modification (no `if/elif` chains). The
manager separates *what content to generate* (the component) from *where/how to
persist it* (paths, extensions, file IO) — a clean single-responsibility split
that makes both independently testable.

> Note: there are two near-identical factories (`components/factory/` and
> `factory/dv_model_factory.py`) — the latter additionally registers
> `profiles`. This is a minor duplication worth flagging if you cite the code:
> the `components/factory` one is what `DVComponentManager` actually uses.

---

## 6. Two-level (meta) Jinja2 templating

**What.** This is the cleverest mechanism in the engine, and the one most worth
explaining in a thesis. The generator emits **dbt SQL files that are themselves
Jinja templates** (dbt compiles them later with native `{{ }}` / `{% %}`). To
write Jinja *that contains Jinja* without the two layers colliding,
`helpers/template_renderer.py` configures a Jinja2 `Environment` with **custom
delimiters**:

| Layer | Delimiters | Evaluated by | Example |
|-------|-----------|--------------|---------|
| **Generation** (DWA) | `<< >>` (vars), `<% %>` (blocks) | `TemplateRenderer` at build time | `<<src_pk>>`, `<% if src_eff %>` |
| **dbt / AutomateDV** | `{{ }}`, `{% %}` | dbt at `dbt compile` time | `{{ automate_dv.hub(...) }}` |

So a hub template body like:

```jinja
{%- set src_pk = '<<src_pk>>' -%}
{{ automate_dv.hub(src_pk=src_pk, ...) }}
```

is rendered by DWA (replacing `<<src_pk>>` with e.g. `HK_TERMINAL`) into a valid
dbt model that **still** contains the native `{{ automate_dv.hub(...) }}` call
for dbt to expand at compile time.

**Where.** `helpers/template_renderer.py` (the custom-delimiter env);
`components/base.py::_SqlConfigBuilder.config_macro` (the shared
`render_config` macro); every leaf component's `_sql_template_body`.

**Why.** Generating-templates-with-templates is genuinely hard because both use
`{{ }}` by default — naively, DWA's renderer would try to evaluate dbt's
`{{ automate_dv.hub }}` and fail. Re-mapping DWA's delimiters to `<< >>` / `<% %>`
**cleanly separates the two evaluation phases** and lets DWA inject values into a
dbt template without escaping gymnastics. It is a small, elegant solution to a
real two-stage code-generation problem.

---

## 7. AutomateDV macro wrapping

**What.** DWA does **not** generate raw DV2 SQL (the hashing, merge logic,
incremental filtering). Instead every raw-vault model is a thin wrapper that
calls the corresponding **AutomateDV** macro with the metadata-supplied params:

| Component | Emitted macro call | Key params |
|-----------|--------------------|-----------|
| Staging | `automate_dv.stage(...)` | `include_source_columns`, `derived_columns`, `hashed_columns`, `null_columns`, `ranked_columns` |
| Hub | `automate_dv.hub(...)` | `src_pk`, `src_nk`, `src_ldts`, `src_source`, `source_model` |
| Link | `automate_dv.link(...)` | `src_pk`, `src_fk`, `src_ldts`, `src_source`, `source_model` |
| Satellite | `automate_dv.sat(...)` | `src_pk`, `src_hashdiff`, `src_payload`, `src_ldts`, `src_source`, `src_eff?` |
| Eff-Sat | `automate_dv.eff_sat(...)` | `src_pk`, `src_dfk`, `src_sfk`, `src_start_date`, `src_end_date`, `src_eff` |

**Where.** Each `_sql_template_body` in `components/sql/raw_vault/*.py` and
`components/sql/staging/staging.py`.

**Why.** AutomateDV is the mature, tested open-source implementation of the DV2
loading patterns (hash computation, hashdiff change-detection, insert-only /
merge incremental loads). Re-implementing that SQL would be a large, bug-prone
undertaking for zero differentiation. DWA's value-add is **deciding the model
and wiring the parameters**, not re-coding the load mechanics — so it delegates
the mechanics and owns the metadata. This keeps DWA warehouse-portable (anything
AutomateDV supports) and tiny.

---

## 8. Per-entity generation

### 8.1 Staging (`StagingComponent`)

**What.** Materialised as a **view**. Renders `automate_dv.stage()` with the four
column-transform families:

- `derived_columns` — load metadata / constants (`RECORD_SOURCE`, `LOAD_DATE`,
  `EFFECTIVE_FROM`, `CDC_FLAG`);
- `hashed_columns` — both **hub hash keys** (`HK_*` over the business key) and
  **hashdiffs** (`is_hashdiff: true` over a payload group);
- `null_columns` — required/optional null handling;
- `ranked_columns` — window ranking (e.g. dedupe by latest `load_dts`).

When `source_name` is set it renders a dbt `{{ source('bronze', 'table') }}`
reference; otherwise a `ref()` to an upstream model. The `StagingModel` exposes
`get_dv_from_field()` which flattens the typed sub-models into the exact nested
dict AutomateDV expects.

**Why.** Staging is where **all the hashing happens** (DV2's defining step), so
the raw-vault models downstream only reference pre-computed `HK_*`/`HASHDIFF_*`
columns. Making it a view keeps it cheap and always-fresh. Typing each transform
family (`HashedColumns`, `DerivedColumn`, `RankedColumns`, `NullColumns`) with a
`computed_field dv_model` means the YAML author gets validation while AutomateDV
gets its exact dict shape — a clean adapter between human-friendly and
macro-friendly representations.

### 8.2 Hub / Link

**What.** Both are `materialized=incremental, strategy=merge` with
`unique_key=src_pk`. Hub passes a single `src_nk` (business key); Link passes
`src_fk` (the list of participating hub hash keys). Both accept a list of
`source_model`s (a hub/link can be loaded from multiple staging models).

**Why.** Incremental merge on the hash key is the DV2 insert-only pattern: a hub
row is written once per new business key, a link once per new relationship.
Allowing multiple source models supports the multi-source hubs the AI modeller
proposes (rule 8 "cross-batch awareness").

### 8.3 Satellite / Eff-Sat

**What.** `SatComponent` renders `automate_dv.sat()` with `src_hashdiff` +
`src_payload`, optionally `src_eff` (effective-from). `EffSatComponent` renders
`automate_dv.eff_sat()` with a **driving foreign key** (`src_dfk`) and
**secondary foreign key(s)** (`src_sfk`, rendered as a Jinja list for multi-FK
links or a quoted scalar for single-FK), plus `src_start_date`/`src_end_date`.
Both use a composite `unique_key=[src_pk, src_ldts]`.

**Why.** The composite `(hash_key, load_date)` unique key is exactly the DV2
satellite primary key (parent HK + load timestamp), enforcing insert-only
historisation. The dfk/sfk split is what lets the effectivity satellite track
*which side drives* a relationship's lifecycle — the structural detail the AI
modeller sets via `driving_fk`/`secondary_fk` (rule 5), carried through to SQL.

---

## 9. dbt config, materialisation & tests

**What.** `_SqlConfigBuilder` (`components/base.py`) builds the dbt `config()`
block: it starts from the flavour base (raw-vault → incremental/merge; staging →
view), **auto-adds the component class name as a tag**, and merges per-component
overrides (e.g. `unique_key`). The config is rendered through the shared
`render_config` Jinja macro. Each component also emits a schema **`.yml`** with
dbt tests: raw-vault models get `not_null, unique` on the PK and `not_null` on
the load date; satellites add `not_null` on the hashdiff; staging asserts
`not_null` on every hashed column.

**Where.** `components/base.py` (`_SqlConfigBuilder`, `DVBaseRawVaultComponent`,
`DVBaseStagingComponent`, `_default_cols_for_yml`).

**Why.** Centralising config means the materialisation/tagging policy is one
obvious place, not scattered across templates. Auto-generated tags give free
selective dbt runs (`dbt run --select tag:raw_vault`). Emitting tests alongside
the SQL means **every generated model ships with data-quality assertions** — the
generator bakes in DV2 governance (unique hash keys, non-null load dates) rather
than leaving it to the user.

---

## 10. Project-level artefacts & custom macros

**What.** Beyond per-entity SQL, the engine also generates the dbt *project
scaffolding* — `dbt_project.yml` (`ProjectComponent`), `packages.yml` (pins
AutomateDV — `PackagesComponent`), `sources.yml` (bronze source defs —
`Source(s)Component`), and `profiles.yml` (`ProfilesComponent`). It also emits
**custom dbt macros** via `MacroComponentFactory`: `generate_schema_name`
(controls target schema naming) and `drop_table` (`components/sql/macros/`).

**Where.** `components/project_level/*.py`, `components/sql/macros/*.py`,
`configs/config_generator.py`.

**Why.** The output must be a **complete, runnable dbt project**, not just model
files — so the engine emits the whole envelope (project config, dependency
pinning, sources, profile). Generating `packages.yml` guarantees the AutomateDV
version the templates target is the version installed. The custom macros encode
deployment conventions (schema naming) that the team needs but AutomateDV
doesn't provide.

---

## 11. Design-pattern inventory & rationale

A compact map of the software-engineering concepts in this engine (useful for
the SW-engineering chapter of the thesis):

| Pattern / concept | Where | Why it's there |
|-------------------|-------|----------------|
| **Metadata-driven generation** | whole engine | Separate *what* (YAML) from *how* (engine); new sources need no code |
| **Discriminated union (tagged) models** | `discriminator.py`, all `*Model`s | pydantic auto-selects the right class from `dv_type`; validation at parse time |
| **Make illegal states unrepresentable** | `SatelliteModel` single-source validator | DV2 invariants enforced by the type, before rendering |
| **Template Method** | `DVBaseComponentGenerator` | Fix the render algorithm once; subclasses fill variant parts |
| **Flavour base classes** | `DVBaseRawVaultComponent` / `DVBaseStagingComponent` | Materialisation policy in one place per layer |
| **Factory + registry dict** | `DVComponentFactory`, `MacroComponentFactory`, `SatComponentFactory` | Open/closed dispatch; no `if/elif` chains |
| **Separation of generate vs. persist** | `DVComponentManager` | Content generation is independent of file IO |
| **Two-level meta-templating** | `TemplateRenderer` custom delimiters | Generate Jinja-that-contains-Jinja without delimiter collision |
| **Delegation to a mature library** | AutomateDV macro wrapping | Own the modelling decision, not the load-SQL mechanics |
| **Adapter (typed ⇄ macro dict)** | `StagingModel.get_dv_from_field`, `computed_field dv_model` | Human-friendly validated input → exact AutomateDV dict shape |
| **Idempotent full regeneration** | `DBTBuilder.cleanup_output_location` | Output is a pure function of the metadata YAML |
| **Tests-as-code generation** | `_default_cols_for_yml` | DV2 governance (unique/not-null) ships with every model |
| **Dependency injection (logger, FileManager)** | constructors | Testable without real IO |

---

### How this connects back to the AI half

The single artefact both halves agree on is the **metadata YAML**. The AI
pipeline's deterministic emitter (`rendering/metadata_v3_emitter.py`,
`render_v3`) produces it; this engine's `Metadata` parser consumes it. The dbt
**compile gate** (`ai/validation/dbt_gate.py`) is literally this engine run
against a candidate plan, then `dbt parse`/`compile` — i.e. the verification
step in the AI pipeline *is* a dry run of the SQL engine. That is why a plan is
only approvable if this engine can turn it into a project that compiles.

---

*Generated from a reading of `dbt_builder/src/dv_components/**`,
`dbt_builder/src/runners/{dbt_builder,metadata}.py`, and the reference metadata
YAMLs. Cross-check macro signatures against the installed AutomateDV version
before citing.*
