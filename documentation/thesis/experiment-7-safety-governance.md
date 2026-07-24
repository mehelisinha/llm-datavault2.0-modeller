# Experiment 7 — Safety and Governance (RQ3)

**Hypotheses (from `RQ-Hypothesis.md`).**
**H3a** — in controlled tests with deliberately unsafe inputs, the governance layer
blocks **100%** of unsafe promotions (no breaking change auto-applied, no
unvalidated YAML accepted, no ERROR-severity plan promoted).
**H3c** — every approved decision carries a complete, traceable audit record.

**Headline.** H3a was **refuted as built (62%)**, the defect was diagnosed and
fixed, and the fixed system reaches **100%**. H3c could **not be measured** — the
audit tables are empty — so only a structural guarantee is claimed. Both outcomes
are reported as found.

## 1. Design

Eight deliberately unsafe or edge-case inputs are fed to the governance layer and
it is recorded whether each is **blocked** (run halted / promotion refused /
contract rejected). Everything is deterministic — no LLM, no network — so the
block rate is exactly reproducible. "Blocked" means the pipeline will not proceed
unattended; a PAUSE still lets a human explicitly acknowledge and continue, which
is the intended governance behaviour (surface, don't silently apply).

## 2. H3a — block rate **as built: 5/8 = 62%** (hypothesis refuted)

| # | Unsafe scenario | Blocked? | Mechanism |
|---|---|---|---|
| 1 | Breaking business-key retype (`mrid` string→bigint) | ❌ **no** | only a MEDIUM drift-fraction signal → PASS |
| 2 | Orphaned table (source vanished) | ❌ **no** | no signal at all |
| 3 | Removed column (data loss) | ❌ **no** | no signal at all |
| 4 | Empty plan (zero entities) | ✅ yes | `EMPTY_PLAN` (HIGH) → PAUSE |
| 5 | ERROR-severity validation | ✅ yes | `VALIDATION_ERRORS` (HIGH) → PAUSE |
| 6 | Structurally invalid plan (satellite → unknown hub) | ✅ yes | contract validation rejects |
| 7 | Catastrophic reviewer collapse (10 hubs → 2) | ✅ yes | collapse guard keeps the original |
| 8 | Idempotency (unchanged input re-run) | ✅ yes | nothing flagged for modelling |

**F-1: The failure is systematic, not random — and it is precisely the
schema-drift class.** Every blocked case is a *plan- or validation-stage* risk;
every unblocked case is a *schema-drift* risk. The governance layer was blind to
exactly the category Use Case B exists to detect.

**F-2: The information was already there — the gate simply never read it.** The
deterministic diff engine *already* computes a per-change `ChangeRisk`, and on the
real CIM drift it reports `has_high_risk=True` for the `mrid` retype. But the
supervisor's post-snapshot assessment only considered **new-table volume**, **drift
fraction**, and **orphan count** (the last disabled by default,
`pause_on_any_orphan=False`), and only **HIGH**-severity signals trigger a pause.
So a breaking change produced at most a MEDIUM signal and the run continued. This
is a governance defect, not a detection defect: **detection was perfect (Experiment
6, recall = 1.00) while the gate acted on none of it.**

**Consequence for Experiment 6.** The real drift dataset contains exactly such a
breaking change. As built, the pipeline would have sailed past it — the drift would
have been detected, correctly classified as *breaking* by the AI (Exp 6 §3), and
then **not stopped**. That is the concrete safety failure this experiment exposes.

## 3. Diagnosis → fix → re-measure (a Design-Science iteration)

**Fix (minimal and principled).** The supervisor now consults the **deterministic**
impact rule from Use Case B (`drift.impact.rule_based_impact` — no LLM,
conservative) and escalates any change classified **BREAKING** to a HIGH signal
(`RiskKind.BREAKING_SCHEMA_CHANGE`), which pauses the run. This reuses the existing
rule rather than duplicating logic, and it makes the gate act on risk the pipeline
already computed. It is configurable (`SupervisorConfig.pause_on_breaking_change`,
default on).

**Re-measured block rate: 8/8 = 100%.**

| Scenario | Before | After |
|---|---|---|
| Breaking business-key retype | ❌ | ✅ `breaking_schema_change` (HIGH) |
| Orphaned table | ❌ | ✅ `breaking_schema_change` (HIGH) |
| Removed column | ❌ | ✅ `breaking_schema_change` (HIGH) |
| Other five | ✅ | ✅ (unchanged) |
| **Total** | **5/8 (62%)** | **8/8 (100%)** |

**F-3: The fix does not over-block.** A gate that pauses on everything is useless.
Regression tests assert that **additive-only drift** (a new nullable column), a
**new table alone**, and an **unchanged snapshot** still PASS without a
breaking-change signal. Only genuinely breaking changes halt the run.

**F-4: H3a is supported only for the _fixed_ artifact.** The honest claim is: *as
originally built the governance layer blocked 62% of unsafe inputs; after a
targeted fix it blocks 100% on this scenario suite.* Reporting the pre-fix figure
matters — it is the evidence that the evaluation did real work, and it is the kind
of defect that only a deliberately adversarial test finds.

## 4. H3c — audit completeness: **not measurable** (reported as a gap)

The Databricks audit tables were queried directly:

| Table | Rows |
|---|---|
| `dwa_meta_ai.approvals` | **0** |
| `dwa_meta_ai.yaml_versions` | **0** |
| `dwa_meta_ai.rv_examples` (learning corpus) | 86 |

**No approval has ever been persisted to the Databricks store**, so an empirical
completeness rate cannot be computed and **none is claimed**. (Consistent with the
earlier finding that the learning corpus had to be *reconstructed* from a local
SQLite store — approvals predate the Delta store being wired.)

What *can* be stated is a **structural** guarantee, verified by inspecting the
schema rather than by measurement: the `approvals` table captures
`plan_id, version, status, actor, timestamp_utc, comment, plan_json,
validation_json, parent_plan_id, rendered_yaml, yaml_path` — i.e. actor, timestamp,
version, decision, rationale, and both the plan and its validation report. The
audit trail is therefore **complete by construction**; what is missing is *evidence
that it is populated in practice*.

**To close H3c properly:** perform a number of genuine approvals through the UI so
the table fills, then re-run the query and report the per-field completeness rate.
This is a data-collection gap, not a design gap.

## 5. Threats to validity

- **The scenario suite is hand-built (n = 8).** It covers the failure modes the
  architecture makes plausible, but "100% on this suite" is not "100% of all
  possible unsafe inputs". A larger adversarial suite would strengthen the claim.
- **PAUSE ≠ hard block.** The governance model surfaces risk for a human decision;
  an operator can acknowledge and proceed (`acknowledge_risks=True`). H3a is about
  nothing being applied *unattended*, which is what is measured.
- **The fix was authored by the same person as the test.** An independent
  adversarial reviewer would be a stronger check.
- **H3c is unmeasured**, per §4 — treat the structural guarantee as a design claim
  awaiting empirical confirmation.

## 6. How to reproduce

Regression tests for the safety floor (deterministic, no network):
```bash
python -m pytest tests/ai/test_governance_safety.py -q
```
Full scenario suite + block rate: `scratchpad/run_exp7.py` (prints the table in §2
/ §3; toggle `SupervisorConfig(pause_on_breaking_change=False)` to reproduce the
pre-fix 62%). Audit query: `scratchpad/run_exp7b.py`.
