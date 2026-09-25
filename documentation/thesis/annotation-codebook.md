# Gold-set annotation codebook

The gold sets are hand-authored by a single annotator, which is a construct-validity
risk. This codebook makes the annotation **protocol explicit and reproducible**, so a
second rater — another person, the author after a washout, or an independent LLM — can
re-derive the same labels and the agreement can be measured (Cohen's kappa). Read it
with `dbt_builder/src/ai/evaluation/gold_sets/RUBRIC.md` (the *scoring* rubric) and
`README.md` (the gold *format*).

## The annotation item

One item per **source table** in the discovery payload. Every table is labelled,
including the ones that get no hub — silently dropping them would hide the excludes
that matter most.

## The label space (the core entity decision)

Each table gets exactly one of:

| Label | Definition | Signals |
|---|---|---|
| **hub** | The table is **one** core business entity with a stable identifying key. | A semantic business key exists (e.g. `mRID`, `iso3166_3`), or a stable surrogate/GUID (`sys_id`) uniquely identifies rows that describe one real-world concept. |
| **split** | A **single** table representing **two or more** distinct business entities. | Association / membership tables (e.g. user↔group membership) from which each side is its own entity; a table whose rows conflate two concepts. Produces ≥2 hubs. |
| **exclude** | The table gets **no hub**. | (a) telemetry / metrics / measurement tables; (b) pure junction / mapping tables whose only role is to relate other entities (they become **links**); (c) tables whose entity identity is defined in a **different schema** (out of scope). |

## Decision procedure (apply in order)

1. **Out of scope?** If the table's identity/keys live in another schema, → `exclude`.
2. **Telemetry / measurement?** If rows are time-series metrics or measurements, → `exclude`.
3. **Pure junction?** If the table exists only to relate other entities and carries no
   independent identity, → `exclude` (it becomes one or more links).
4. **Two entities in one table?** If the table yields two distinct business concepts
   (each with its own key), → `split`.
5. **Otherwise** the table is one entity with a key → `hub`.

## Business-key sub-rule (for `hub`/`split`)

Prefer a **semantic** business key; fall back to a stable **surrogate/GUID** only when
no reliable semantic key exists. Where a shop convention fixes the key, that choice is
mandatory (Tier 1 in `RUBRIC.md`); otherwise an alternative defensible key is a Tier-2
disagreement, not an error.

## Known boundary cases (documented, not hidden)

- **`terminals` (CIM)** is both a real entity (a terminal) *and* the junction between
  conducting-equipment and connectivity-node. The gold labels it `hub` (and models the
  relationship as a separate link); labelling it `exclude`/junction is a defensible
  Tier-2 alternative. This is the one item on which the independent LLM annotator
  disagreed (§2.9).
- **`task_sla` (ServiceNow)** is `exclude` as a hub: its temporal columns are modelled
  as a satellite on `hub_sla`, keyed via `task_sla.sla`, and its `task` FK points
  outside the schema.
- **`sys_user_grmember` (ServiceNow)** is `split`: it yields both `hub_user` and
  `hub_group`; there is no dedicated user/group reference table in the schema.
- **`volumemetrics` / `u_mcs_*_mapping` (ServiceNow)** are `exclude`: telemetry and a
  pure mapping table respectively.

## How reliability is measured against this codebook

`scripts/audit/interrater.py`:

- `--rater llm` — an independent LLM (a model different from the pipeline modeller,
  seeing only the schema + this codebook) labels every table; reports kappa vs gold.
- `--emit-template T` — writes the blank item list for the author to re-label after a
  washout (**intra-rater test-retest**).
- `--rater human --labels F` — scores a filled template (test-retest, or a real second
  annotator) against the gold.

Labelling-derivation and the kappa are the pure, unit-tested
`dbt_builder/src/ai/evaluation/interrater.py`.
