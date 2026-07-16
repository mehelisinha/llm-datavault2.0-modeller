# Experiment 4 — End-to-end (reviewer) effect and the error-taxonomy shift

**Research questions.**
1. **Product vs mechanism:** does the *end-to-end* pipeline (modeller → gpt-5.2
   plan reviewer) produce a better model than the modeller alone — and on which
   axes?
2. **Where do the errors go:** treated as an error-processing stage, *which
   categories* of defect does the reviewer resolve, introduce, and leave — and
   does fixing them reduce the *blast-radius-weighted* cost, not just the count?

This experiment answers the dimensions requested for the thesis: **input→output,
error type, added-deliberation stage, blast radius, resolution, taxonomy shift,
and resolution analysis.**

## 1. Design

- Systems: **ServiceNow** (`SNOW_IT4IT_001`, 8 source tables) and **CIM**
  (`IEC_CIM_001`, control). Each trial captures the **raw** modeller plan *and*
  the **reviewed** plan, graded identically.
- Learning conditions: **e2e_off** (modeller learning k=0) and **e2e_on**
  (k=10 full corpus). Reviewer = **gpt-5.2**, one pass (chunked for large plans).
- 2 seeds each. The reviewer runs at **temperature 1.0** (gpt-5 family) → it is
  genuinely stochastic, so seeds measure real reviewer variance, not noise.
- Fully reproducible via one command (§6) — no bespoke script, no hardcoded paths.

## 2. Results (mean of 2 seeds; raw → reviewed)

**ServiceNow** (CIM is at ceiling in every cell — see §4):

| Condition | entity_f1 | naming | conformance | issue_count | weighted_impact | link_ratio |
|---|---|---|---|---|---|---|
| e2e_off | 0.933 → **0.750** | 0.00 → 0.00 | 0.934 → **0.946** | 11.0 → 9.5 | 46.5 → **52.0** | 1.73 → 1.86 |
| e2e_on  | 1.000 → **0.706** | 1.00 → 1.00 | 0.928 → **0.962** | 12.0 → 7.5 | 42.5 → **50.0** | 1.82 → 1.86 |

**Error-taxonomy shift** (ServiceNow, issue counts summed over 2 seeds):

| Condition | resolved (raw→rev) | introduced (raw→rev) | net_resolved |
|---|---|---|---|
| e2e_off | `link_fk_unresolved` 10→3 (**−7**) | `surrogate_business_key` 8→12 (**+4**) | +3 |
| e2e_on  | `link_fk_unresolved` 14→0 (**−14**) | `surrogate_business_key` 8→12 (**+4**), `hub_without_satellite` 2→3 (+1) | +9 |

## 3. Analysis — mapped to the requested dimensions

**Input → output.** Both systems are fully covered (every source table yields at
least a hub); the reviewer does not drop coverage (the collapse-guard in
`plan_reviewer.py` prevents that by construction). What changes is *structure*,
not *completeness*.

**Error type (raw).** ServiceNow's defect profile is dominated by three
categories: `link_fk_unresolved` (a link's FK hash-key matches no hub),
`surrogate_business_key` (a hub keyed only on a surrogate like `sys_id`), and
`hub_without_satellite`. CIM has *none* — it is clean at the raw stage.

**Added-deliberation stage.** The reviewer is a second, stronger model given the
draft plan to critique. *It uses no external tools* — the lever here is added
model capability and a dedicated critique pass, not tool access. (Framing it
honestly: this pipeline has no tool-using agent; "thinking" = the extra pass.)

**Resolution / solution.** The reviewer has a clear specialty: it **resolves
dangling link foreign keys** — `link_fk_unresolved` falls 10→3 (off) and is
**eliminated** 14→0 (on). Connectivity repair is what it reliably does.

**Error-taxonomy shift (the key result).** The reviewer does not merely reduce
errors — it **redistributes them**. As it fixes link FKs it **re-keys hubs onto
surrogate keys**, so `surrogate_business_key` *rises* 8→12. Total conformance
improves (fewer, cleaner issues: 0.934→0.946, 0.928→0.962), but the *mix* moves
from connectivity errors to key-quality errors.

**Blast radius — the count/impact divergence.** Despite resolving more issues
than it introduces (`net_resolved` +3 / +9), the **blast-radius-weighted impact
goes _up_** (46.5→52.0, 42.5→50.0). The reason: the errors it *removes* are
low-fan-out (a link relates two hubs), while the errors it *adds* sit on **hubs**,
which have the highest downstream fan-out (every satellite and link depends on
them). **Issue count and weighted impact move in opposite directions** — you
cannot judge the reviewer by counting issues.

**Resolution analysis.** Net-of-taxonomy, the reviewer is a *conformance-and-
connectivity fixer, not a correctness oracle*: it trades many link-FK errors for
fewer, heavier surrogate-key errors, lifting convention conformance while
**lowering entity_f1 vs the gold** (0.93→0.75, 1.00→0.71) and leaving **naming
untouched** (0→0, 1→1).

## 4. Two findings that revise earlier experiments

**F-A: The reviewer does _not_ supply the clean naming — the modeller's learning
does.** Experiment 1 hypothesised (F-3) that the corpus's concept-names came from
the downstream reviewer. Experiment 4 falsifies that: with learning **off** the
reviewer leaves naming at 0 (it keeps table-based names), and with learning
**on** the modeller already achieves 1.0 and the reviewer preserves it. Naming
adherence is set upstream, by few-shot learning, **not** by review. (The reviewer
prompt explicitly says "keep correct entities and their names unchanged".)

**F-B: "End-to-end quality" is not a scalar improvement.** The stronger second
model *improves DV2 conformance* and *repairs link connectivity* but *reduces
structural agreement with the gold* and *raises high-fan-out key errors*. The
honest headline is a **trade-off**, visible only through the multi-metric +
taxonomy lens — a monotone "reviewer makes it better" claim would be false.

**CIM control.** Every CIM cell is 1.0 raw and 1.0 reviewed (one seed nudged
`link_ratio` 2→3, a single spurious link). With no raw defects to fix, the
reviewer is correctly inert — it does not damage an already-correct plan.

## 5. Threats to validity / limitations

- **The entity_f1 drop is measured against a single-author gold.** Some reviewer
  re-keyings (e.g. hub on `sys_id`) may be *defensible* modelling choices rather
  than errors — the ServiceNow gold itself keys several reference hubs on
  `sys_id`. So the entity_f1 fall is partly "reviewer disagrees with *this* gold".
  The `surrogate_business_key` *rise*, by contrast, is an objective conformance
  regression (independent of the gold). Both are reported; neither is overstated.
- **Reviewer stochasticity.** At temperature 1.0 the reviewer varies across
  seeds (e.g. weighted impact 47 vs 57 at off); 2 seeds bound but do not
  eliminate this. More seeds would tighten the estimate.
- **One reviewer model, two systems.** The direction (conformance up, entity_f1
  down, naming neutral) is consistent across conditions, but the magnitudes are
  system- and model-specific.
- **Conformance ≠ correctness.** Conformance rewards convention adherence; a plan
  can be more conformant *and* less faithful to the source — which is exactly the
  divergence this experiment surfaces.

## 6. How to reproduce this experiment

The four experiments now share **one declarative, reproducible runner** — no
scratchpad scripts, no hardcoded paths. A system is named by its gold
`system_id` (the discovery-payload path is read from the gold file itself), and
a condition is a parsed spec (`off`, `on:k=10`, `loo:k=10,exclude=a+b`,
`e2e:k=10,review=1`). This exact experiment is:

```bash
python -m dbt_builder.src.ai.evaluation experiment \
    --system SNOW_IT4IT_001 --system IEC_CIM_001 \
    --condition "e2e_off:k=0,review=1" \
    --condition "e2e_on:k=10,review=1" \
    --seeds 42,43 \
    --out exp4_results.json
```

The runner prints the per-trial raw→reviewed line, the per-cell means, and the
resolved/introduced/`net_resolved` taxonomy shift, and writes the full records +
summary to `--out`. The wiring lives in `dbt_builder/src/ai/evaluation/study.py`
(`run_study` / `run_condition` / `taxonomy_shift`), unit-tested with injected
fakes in `tests/ai/test_study.py` (no network). The same command reproduces
Experiments 1–3 by changing `--condition`/`--system` (see their docs).
