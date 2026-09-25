# Gold sets — hand-modelled DV2 references for benchmarking

Each `*.yml` here is a **gold standard**: the DV2 objects a correct model
*should* produce for one public, documented source system. They are the
reference for `grade_against_gold` (precision / recall / F1 + business-key
accuracy), the ground-truth-based half of the thesis evaluation.

## Format (`GoldModel`)

```yaml
system_id: servicenow          # matches ModelingPlan.system_id
hubs:                          # expected hub -> its expected business-key set
  hub_user: [user_name]
  hub_incident: [number]
links:                         # expected link names
  - link_user_group
satellites:                    # expected satellite names
  - sat_user_details
```

## How grading works

* Objects are matched by **normalised name** (lower-cased). A renamed object
  (`hub_user` vs `hub_users`) counts as a miss — deliberate, so the benchmark is
  reproducible and strict.
* **Business-key accuracy** is computed only over hubs the plan got right, and
  requires the produced business-key *set* to equal the gold set exactly.
* Hubs and links are the strong structural signal. Satellite names carry a
  rate-of-change topic suffix (`_details` / `_operational` / `_measurements`)
  that legitimately varies, so satellite F1 is a noisier signal — read it
  alongside conformance, not on its own.

## Adding a gold set

Author against a source system whose "correct" model you can defend (public
docs or an expert). Keep the scope small (5–10 tables) and reproducible. Drop
the file here; `load_gold_models()` picks it up automatically by `system_id`.
