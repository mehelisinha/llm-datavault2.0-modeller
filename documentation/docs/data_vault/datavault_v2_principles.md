# Data Vault 2.0 Principles (Quick Reference)

This document describes the core concepts and modeling rules for Data Vault 2.0 using dbt/automateDV.

## Table of Contents

- [Vault Types](#vault-types)
- [1. Hub](#1-hub)
- [2. Link](#2-link)
- [3. Satellite](#3-satellite)
- [4. Vault load rules](#4-vault-load-rules)
- [5. Hash key naming](#5-hash-key-naming)
- [6. Good vs bad satellite split](#6-good-vs-bad-satellite-split)
- [7. dbt + automateDV patterns](#7-dbt--automatedv-patterns)
- [8. Example: source rows → hub/link/satellite](#8-example-source-rows--hublinksatellite)
- [9. extra governance tips](#9-extra-governance-tips)

## Vault Types

Data Vault architecture consists of three main layers:

- **Raw Vault**: Immutable, historized storage of source data. Contains Hubs, Links, and Satellites. Stores raw business keys and attributes with full audit trail. No transformations or business logic applied.
- **Business Vault**: Derived and computed data from Raw Vault. Includes Point-in-Time (PIT) tables, Bridge tables, and business rules. Optimized for performance and analytics.
- **Informational Vault**: Presentation layer with dimensional models, aggregates, and reporting views. Designed for end-user consumption and BI tools.

## 1. Hub

- **Purpose:** Unique business keys repository; enterprise identity of a business concept (e.g., Customer, Product, Equipment).
- **Contains:**
  - `H{BIZ}` (surrogate hash key) - hash over the business key (( natural key))
    A good candidate for hashing is:
    - it is meaningful
    - stable over time
    - shared across systems (or at least stable within a domain)

  - Business key natural hash (e.g., `HK_CUSTOMER`)
  - `RECORD_SOURCE`, `LOAD_DATE`, `LOAD_END_DTS` (in some implementations), metadata columns (e.g., `ROW_INS_TS`)
- **Does NOT contain:** 
  - descriptive attributes (that belong to satellites), 
  - transactional measures, 
  - direct references to other hubs.
  - Surrogate keys (pks from original systems)
- **Key rule:
    - ** Business key(s) are normalized at source and should be stable.
    - ** LOAD_DATE ** represents the first time the model first recorded the data
    - ** Insert only ** data is always inserted, nut updated, not deleted
- **Hash key:** Use hash algorithm (e.g., SHA256) over business key to generate fixed-length surrogate key.
- **Model name examples:** `hub_customer`, `hub_product`, `hub_conducting_equipment`.

## 2. Link

- **Purpose:** Capture many-to-many or relationship between hubs; holds association keys over time.
- **Contains:**
  - Reference hash keys to associated hubs (`HK_CUSTOMER`, `HK_ORDER`, etc.)
  - Link hash key (e.g., `HK_ORDER_CUSTOMER_LINK`), `LOAD_DATE`, `RECORD_SOURCE`, metadata. This is made by hashing the hub business key. ! do not concatenate the Bubs Hashes. EX: hash( full_name, '||', product)
- **Does NOT contain:** 
  - descriptive fields or attributes of the entities (satellites hold these). 
  - Also avoid storing raw business payload directly.
  - business keys
  - start or end dates ( tis belong to satellite)
- **Key rule:** Link should not reference non-hub data; all foreign keys are hub business keys.
- **Hash key:** computed hash of all hub keys that participate in relationship (deterministic, stable).
- **Model name examples:** `lnk_order_customer`, `lnk_terminal_equipment_node`

### Link Types
- 1. Standard Link
- 2. SAL - Same as Link
 When SAL is used
 - MDM matching
 - Golden record creation
 - Multiple CRM systems
 - Mergers & acquisitions
 - Key mapping tables
 - Fuzzy matching outputs
 ex we receive customer info from 2 system and have 2 sets of business keys for the same entity. The SAL will contain a mapping between the 2 systems
- 3. Exploration Link

## 3. Satellite

- **Purpose:** Hold descriptive and changing attributes for a hub or link, with historisation.
- **Contains:**
  - `HK_{PARENT}` (reference hub/link key), 
  - `HASHDIFF` (change detect hash) - used to identify when o change in record has occurred,
  - attribute columns, 
  - `LOAD_DATE`, 
  - `RECORD_SOURCE`, 
  - optionally `EFFECTIVE_FROM`/`EFFECTIVE_TO`.
  - Optional `RECORD_HASH` and/or `RECORD_END_DTS` for soft delete semantics.
- **Does NOT contain:** business key uniquely identifying entity (except via hub/link key); do not repeat in multiple satellites unless needed by business context.
- **Key rule (separation):**
  1. **Context**: split rules: place columns in satellite based on same change rate (slow/fast), same source, same business meaning, data types
  2. **Avoid wide satellite**: split into multiple satellites when attribute groups have different change frequency, high cardinality, or security/PII boundaries.
  3. **Add only raw attributes**; computed fields can be in business vault or staging.
  4. **Has 1 Parent only**: a satellite can have only 1 parent ( 1 link or 1 hub)
  5. **Has no children**
  6. satellite pk is the parent **HK + load_date**
  7. No FK except for the parent HK
  8. **Append only** ( no updates or deletes are performed)
- **Hash key:** `HASHDIFF` computed from satellite payload attributes (excluding technical columns).
- **Model name examples:** `sat_customer_address`, `sat_product_price`, `sat_conducting_equipment_details`.

Satellite types:
- 1. Historical
- 2. Multi Active
- 3. Status tracking (CDC)
- 4. Record Tracking ( last load date, is_active)
- 5. Effective Satellite (SCD2) - this is the most important

## 4. Vault load rules

- Use staging layer to generate clear source columns: business keys, hash keys, hashdiff, load metadata.
- For every source record process:
  - `HK` declared in hub (business key hash). If new, insert.
  - Link target based on existing hub keys -> insert relationship.
  - Satellite insert if `HASHDIFF` changed or new reference key appears.
- Do not put non-historized, derived-only values in raw vault; those belong to business vault / reporting layer.

## 5. Hash key 
### 5.1 Naming

| Element | Common Column | Purpose |
|---|---|---|
| Hub key | `HK_{ENTITY}` | primary business key hash
| Link key | `HK_{HUB1}_{HUB2}[_...]` | combined key hash
| Satellite hashdiff | `HD_{ENTITY}_S` (`S`=sat) | detect attribute changes
| Load source | `RECORD_SOURCE` | system of record origin
| Load timestamp | `LOAD_DATE` | when ingested

### 5.2 Calculate
Use a proper hashing function
Before doing the HASH:
- do trim
- capitalize
- when concatenation multiple columns:
  - cast to string
  - handle null
  - concatenate with '||' as separator


## 6. Good vs bad satellite split

- Keep attributes with similar volatility together.
- Split by security/PII if some columns require tighter controls.
- Use one satellite for core stability, others for fast-moving fields (e.g., `sat_customer_contact`, `sat_customer_financial`).
- Example:
  - `sat_conducting_equipment_details` -> static device specs
  - `sat_conducting_equipment_status` -> status, lifecycle flags.

## 7. dbt + automateDV patterns

- `hub(...)` macro: declare `src_pk`, `src_nk`, `src_ldts`, `src_source`, `source_model`.
- `link(...)` macro: `src_pk`, `src_fk`, `src_ldts`, `src_source`, `source_model`.
- `sat(...)` macro: `src_pk`, `src_hashdiff`, `src_payload`, `src_ldts`, `src_source`, `source_model`.

## 8. Example: source rows → hub/link/satellite

### Source (bronze/staging normalized raw data)
| order_nk | customer_nk | product_nk | qty | price | status    | updated_at           |
|----------|-------------|------------|-----|-------|-----------|----------------------|
| ORD-001  | Mikey Mouse | bag        | 2   | 100.0 | NEW       | 2026-03-24 10:00:00  |
| ORD-001  | Donal Duck  | wallet     | 3   | 100.0 | CONFIRMED | 2026-03-24 12:00:00  |

> Note: `*_nk` fields are natural business keys, not surrogate hash keys.

### Hub key hash rule (business key hash - always based on natural key)
- `HK_CUSTOMER = hash('Mikey Mouse')` from `customer_nk`
- `HK_PRODUCT = hash('bag')` from `product_nk`
- `HK_ORDER = hash('ORD-001')` from `order_nk`

### Hub rows
- `hub_customer`:
  - `HK_CUSTOMER`, `customer_nk`, `RECORD_SOURCE`, `LOAD_DATE`
- `hub_product`:
  - `HK_PRODUCT`, `product_nk`, `RECORD_SOURCE`, `LOAD_DATE`
- `hub_order`:
  - `HK_ORDER`, `order_nk`, `RECORD_SOURCE`, `LOAD_DATE`

### Link rows (relationship only, no descriptive fields)
- `lnk_order_customer`:
  - `HK_ORDER_CUSTOMER_LINK = hash('order_nk' || 'customer_nk')` or equivalent from component hub keys
  - reference `HK_ORDER`, `HK_CUSTOMER`, `RECORD_SOURCE`, `LOAD_DATE`
- `lnk_order_product`:
  - `HK_ORDER_PRODUCT_LINK = hash('order_nk' || 'product_nk')`

### Satellite rows (changed attributes and history)
- `sat_order_status` (order lifecycle state):
  - `HK_ORDER`, `HASHDIFF = hash('status')`, `status`, `LOAD_DATE`, `RECORD_SOURCE`
  - row1: `NEW`, row2: `CONFIRMED`
- `sat_order_details` (quantity/price):
  - `HK_ORDER`, `HASHDIFF = hash('qty|price')`, `qty`, `price`, `LOAD_DATE`, `RECORD_SOURCE`
  - row1: `qty=2, price=100.0`, row2: `qty=3, price=100.0`


### Rule summary for this example
- Hubs store only the business natural key (`*_nk`) and its hashed surrogate `HK_*`.
- Links only store references to `HK_*` values (not natural attributes), plus load metadata.
- Satellites store descriptive/change state attributes; they refer by `HK_*` and use `HASHDIFF` to determine change rows.

## 9. extra governance tips

- Document each model with clear description in `.yml` metadata.
- Add tests/constraints for uniqueness and no-null on hub business keys.
- Keep raw vault models pure by restricting transformation to logic required for history maintenance.
