# Gold-set label rationale — why each source table got its entity label

This documents the **core entity decision** (`hub` / `split` / `exclude`) for every
source table in the two gold sets, and *why*. It is the reasoning behind `cim.yml` and
`servicenow.yml`, written so the decision is reproducible and defensible (e.g. in a viva)
rather than taking the gold on trust.

Read alongside:
- `RUBRIC.md` — how a gold set is turned into a scoring instrument (Tier 1/2/3).
- `../../../../documentation/thesis/annotation-codebook.md` — the labelling protocol the
  independent annotator also used (reliability check, κ = 0.84).

> **Scope note.** The gold sets were hand-authored **from the source schema**, *not* from
> the pipeline's output — otherwise the ablation would be circular. Every label below is a
> judgement about the *source table*, made before looking at any generated model.

---

## The decision framework (three questions, in order)

For each source table, ask:

1. **Is it even a business "thing"?**
   - Telemetry / metrics / measurements → **exclude**
   - A pure junction / mapping table (its only job is to relate other things → it becomes a
     *link*, not a hub) → **exclude**
   - Its identifying key lives in a **different schema** (out of scope) → **exclude**
2. **Is it secretly *two* things?** One table that conflates two real entities (a
   membership/association of A-to-B where A and B are both real) → **split** (yields ≥2 hubs).
3. **Otherwise it is one real entity with a stable key** → **hub**.

Mnemonic: **hub = a noun with its own ID; exclude = not a noun; split = two nouns hiding in
one table.**

---

## IEC_CIM_001 (electrical-grid schema) — 3 tables

| Source table | Label | Business key | Why |
|---|---|---|---|
| `conducting_equipment` | **hub** | `mrid` | A physical grid asset (transformer, breaker, line). Has its own stable identity (`mRID`) → one real entity → `hub_conducting_equipment`. |
| `connectivity_nodes` | **hub** | `mrid` | An electrical node where equipment connects. Own `mRID` identity → `hub_connectivity_node`. |
| `terminals` | **hub** | `mrid` | ⚠️ **The one genuinely ambiguous item.** A terminal is where a piece of equipment attaches to a node — so it is *both* a real object (it has its own `mRID`) *and* the junction between equipment and node. The gold treats it as a **hub** (it has independent identity) and models the equipment↔node relationship as a **separate link** (`link_terminal_equipment_node`). Labelling it `exclude`-as-junction is a **defensible Tier-2 alternative** (RUBRIC.md). Its impact is quantified: under the alternative labelling CIM entity-F1 moves 1.00 → 0.80, so no headline conclusion depends on the call (findings §2.9). |

CIM is deliberately the *easy* control: three unambiguous `mRID`-keyed entities, all `hub`.

---

## SNOW_IT4IT_001 (IT-service-management schema) — 9 tables

Business-key convention for this gold (a **fixed** convention, so Tier 1 — see RUBRIC.md §1):
`company` / `department` / `location` / `sla` are keyed on the stable `sys_id` GUID because
their `name` fields are non-unique display strings; `country` uses `iso3166_3`; `user` /
`group` use their membership columns.

### The 5 hubs

| Source table | Label | Business key | Why |
|---|---|---|---|
| `core_company` | **hub** | `sys_id` | A company — a core business entity. No reliable semantic key, so keyed on the stable `sys_id` GUID → `hub_company`. |
| `core_country` | **hub** | `iso3166_3` | A country — a real entity with a genuine semantic key (ISO-3166 code) → `hub_country`. |
| `cmn_department` | **hub** | `sys_id` | An organisational unit → `hub_department`. |
| `cmn_location` | **hub** | `sys_id` | A physical site/location → `hub_location`. |
| `contract_sla` | **hub** | `sys_id` | The **SLA contract itself** — an agreement that exists as its own entity with its own identity → `hub_sla`. **(Contrast with `task_sla` below — this pair is the classic trap.)** |

### The 1 split

| Source table | Label | Yields | Why |
|---|---|---|---|
| `sys_user_grmember` | **split** | `hub_user` (key `user`) + `hub_group` (key `group`) | A **membership** table ("user X is in group Y"). It conflates two real entities, and this schema has **no dedicated `sys_user` or `sys_user_group` reference table**, so this single association table is the only source of *both* entities → it splits into two hubs. This is the correct DV2 pattern but atypical; a model that flags it as unusual is not penalised (RUBRIC.md §2). |

### The 3 excludes

| Source table | Label | Why |
|---|---|---|
| `volumemetrics` | **exclude** | Pure **telemetry** — load/row counts and timings (`records_landing`, `records_inserted`, `time_taken_*`). Measurements, not a business entity. The easiest, least-contestable exclude. |
| `u_mcs_company_and_approval_group_mapping` | **exclude** | A **junction / mapping** table whose only role is to relate companies to approval groups. A pure connector → it becomes **links** (`link_u_mcs_company_approval_group`, `link_u_mcs_company_department`), not a hub. |
| `task_sla` | **exclude** | Not a new entity — it represents an **SLA's timing applied to a task**. Its `sla` FK → `contract_sla` (the SLA hub); its `task` FK references a **table outside this schema**, so there is no `hub_task` and therefore no valid 2-hub link here. Its temporal/measurement columns are modelled as a **satellite on `hub_sla`** (`sat_task_sla_measurements`), which **must** be keyed via `task_sla.sla` (→ the SLA's `sys_id`), *not* `task_sla.sys_id` (keying it on the row id produces an orphaned satellite — a Tier-3 error the dbt gate catches; RUBRIC.md §1). |

---

## Viva defence — the two questions you will be asked

1. **"Why is `contract_sla` a hub but `task_sla` excluded?"**
   > *"`contract_sla` is the SLA agreement itself — an entity with its own identity, so it's
   > a hub. `task_sla` is that agreement's measured behaviour on a task — a
   > relationship/measurement, not a new entity — so its columns become a satellite on
   > `hub_sla`, and it gets no hub of its own."*

2. **"Isn't `terminals` really just a junction — why is it a hub?"**
   > *"It has its own `mRID` identity, so it is a legitimate hub, and the relationship it
   > also expresses is modelled separately as a link. It's the one genuinely ambiguous call
   > in either gold; I treat `exclude`-as-junction as a defensible alternative and quantify
   > it — CIM entity-F1 moves only 1.00 → 0.80, so the headline holds either way."*

Everything else follows the three-question framework mechanically: telemetry and pure
mapping tables are excluded, the membership table splits, and every remaining stably-keyed
business object is a hub.

---

## Summary table (all 12)

| System | Source table | Label |
|---|---|---|
| CIM | conducting_equipment | hub |
| CIM | connectivity_nodes | hub |
| CIM | terminals | hub *(Tier-2 ambiguous)* |
| ServiceNow | core_company | hub |
| ServiceNow | core_country | hub |
| ServiceNow | cmn_department | hub |
| ServiceNow | cmn_location | hub |
| ServiceNow | contract_sla | hub |
| ServiceNow | sys_user_grmember | split → user + group |
| ServiceNow | task_sla | exclude |
| ServiceNow | u_mcs_company_and_approval_group_mapping | exclude |
| ServiceNow | volumemetrics | exclude |
