---
name: planning_rules
description: Decision rules for the automated DV2 Planning Agent (Dv2PlanningAgent). Single source shared with the manual DV2 Planning skill. The output JSON schema is fixed in code (Dv2Plan) — these rules MUST NOT introduce output fields not in that schema.
---
Rules:
1. Prefer stable surrogate IDs (mrid, sys_id, uuid) over mutable codes.
2. Split satellites by rate-of-change OR semantic domain — never both. Rate-of-change groups: STATIC (serial_number, manufacturer, model), SLOW (name, address, category, owner), FREQUENT (status, state, active_flag, priority, assigned_to), CONTINUOUS (readings, measurements, counters). Never put all columns in one satellite; a single frequently-changing column (status, in_service) gets its own satellite.
3. Only propose BVs whose derivation_sql references columns visible in the payload of the named parent hub. Common BV patterns: status/state → lifecycle classification; numeric thresholds → tier classification; dates → age buckets; codes → normalised labels. Do NOT invent derivations.
4. Flag tables you cannot confidently classify under review_flags rather than guessing.
5. Classify each table HUB / LINK / REFERENCE / SKIP. HUB = clear unique business key for a real-world entity (a noun). LINK = 2+ FKs to other hubs representing a relationship. REFERENCE = small stable lookup/code table (name contains choice/code/type/status/category/lookup/ref/config/schedule) — list under reference_tables. SKIP = staging/temp/audit/denormalised with no business key.
6. Detect foreign keys by: name ending in _id/_mrid/_key/_fk/_code/_ref, name matching another entity, or high cardinality that is not the primary business key.
7. Estimate PIT volume bands (estimated_band): sm/md/lg/xl. Use conservative (higher) estimate when unsure; reference/code tables are sm, user/person md, transaction/event lg–xl, CI/asset md–lg.
8. Calibrate confidence honestly: high = obvious, no reasonable alternative; medium = reasonable but alternatives exist; low = ambiguous, needs human confirmation.
