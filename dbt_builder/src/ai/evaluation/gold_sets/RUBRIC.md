# Gold-set scoring rubric

A gold set is a *reference answer*; this rubric turns it into a *scoring
instrument* by declaring which elements are **mandatory matches**, which are
**acceptable alternatives**, and which are **penalized errors**. Read it
alongside `README.md` (format) and the per-system caveats at the bottom.

## The three tiers

### Tier 1 — MANDATORY (must match; drives `core_f1` + `business_key_accuracy`)
These are the structural decisions a correct model *must* get right.

| Element | Scored by | Pass condition |
|---|---|---|
| **Hubs** — the right business entities | `hubs` P/R/F1, `core_f1` | every gold hub present, no extra hubs |
| **Business keys** — the semantic key per hub | `business_key_accuracy` | produced BK set == gold BK set (exact) |
| **Links** — clear, resolvable FK relationships | `links` P/R/F1, `core_f1` | every gold link present, FKs resolve to hubs |

`core_f1 = mean(hub_f1, link_f1)`. A model that scores `core_f1 == 1.0` **and**
`business_key_accuracy == 1.0` got the entities and relationships right — the
headline result for the study.

### Tier 2 — ACCEPTABLE ALTERNATIVES (do NOT hard-fail; report, don't penalize)
Defensible modelling can legitimately differ here. Grade **softly** — prefer
parent-hub coverage over exact-name match, and treat a reasonable variant as
correct in qualitative review even if the name differs.

- **Satellite splits.** `details` vs `operational` vs `measurements` is a
  rate-of-change judgement. A different split (e.g. one combined sat, or an
  extra split) that covers the same payload is acceptable. This is why
  satellites sit in `macro_f1`/`sat_f1`, **not** in `core_f1`.
- **Effectivity satellites.** Proposing an eff-sat for a link, or for a
  temporal table, is acceptable — never a false positive. (The `GoldModel`
  format does not enumerate eff-sats, so they are not name-graded at all.)
- **Alternative-but-valid business keys.** If a hub has two defensible keys
  (e.g. `sys_id` vs a semantic `name`), a model choosing the other one is a
  Tier-2 disagreement to note, not a Tier-1 failure — provided the shop has not
  fixed a convention. Fix the convention in the gold to make it Tier 1.

### Tier 3 — PENALIZED ERRORS (count against the model)
Caught by the **conformance** scorer (`IssueType`) and/or Tier-1 misses:

- missing hub / relationship (Tier-1 recall miss)
- extra / hallucinated object (Tier-1 precision miss)
- **wrong business key** (surrogate where a semantic key exists, or vice-versa
  against a fixed convention)
- **unresolved link FK** — a link hash key that matches no hub (also a common
  *silent* bug: a hash key derived from a column the source table does not have,
  or from the wrong id — name-matching will NOT catch this, conformance +
  the dbt gate will)
- key / technical column leaked into a satellite payload
- satellite hung off the wrong parent (e.g. a *link* attribute placed on a hub)

## How to run the scoring

1. `python -m dbt_builder.src.ai.evaluation score --plan p.json --gold <system_id>`
   → prints `core_f1` (Tier 1), `macro_f1` (Tier 1+2), `business_key_accuracy`,
   and the conformance issue list (Tier 3).
2. Read **Tier 1 as pass/fail**, **Tier 2 as informational**, **Tier 3 as the
   error taxonomy**. Report all three; only Tier 1 + Tier 3 penalize.

---

## Per-system caveats

### it4it_servicenow (`edh_unreg_consumption_dev`)

1. **`task_sla` is a boundary case.** `task_sla.sla` → `contract_sla` is a real
   FK, but `task_sla.task` references a **task table outside this schema**, so
   there is no `hub_task` and therefore **no valid 2-hub link** here. The gold
   models the temporal/measurement columns as `sat_task_sla_measurements` on
   `hub_sla`, which must be keyed via `task_sla.sla` (→ the SLA's `sys_id`),
   **not** `task_sla.sys_id` (the task_sla row id). A model that keys it on
   `sys_id` produces an orphaned satellite — a Tier-3 error the dbt gate catches.
2. **Hub-derivation asymmetry.** `hub_user` and `hub_group` derive from the
   association table `sys_user_grmember` (there is no dedicated `sys_user` /
   `sys_user_group` reference table in this schema). This is the correct DV2
   pattern but atypical — a model that flags it as unusual is **not** penalized.
3. **Business keys = `sys_id`** for `company`/`department`/`location`/`sla`
   (no reliable semantic key; `name`/`u_short_name` are non-unique display
   fields). This is a **fixed convention for this gold** → Tier 1. Change the
   gold if your shop keys these on a semantic column.
4. **Cross-schema references are OUT OF SCOPE.** Any FK pointing at a table not
   in `it4it_servicenow` (e.g. `task_sla.task`) is not modellable and is neither
   required nor penalized.
5. **`link_company_vendor_manager` is Tier-2.** The association is real, but
   `core_company.vendor_manager` is a user `sys_id` while `hub_user` is keyed on
   the `user` login — the FK may not resolve. Omitting it is acceptable.

### IEC_CIM_001

- Every CIM hub is keyed on `mRID` (Tier 1, unambiguous). The link name
  (`link_terminal_equipment_node`) uses the modern `link_` convention; the poc
  reference uses the legacy `lnk_` — reconcile the name after a first run.
