# Experiment 7 — Safety and Governance (RQ3)

**Hypotheses (from `RQ-Hypothesis.md`).**
**H3a** — in controlled tests with deliberately unsafe inputs, the governance layer
blocks **100%** of unsafe promotions (no breaking change auto-applied, no
unvalidated YAML accepted, no ERROR-severity plan promoted).
**H3c** — every approved decision carries a complete, traceable audit record.

**Headline.** H3a was **refuted as built (62%)**, the defect was diagnosed and
fixed, and the fixed system reaches **100%**. H3c is **supported**: with the approval
store since populated (35 records), audit-trail completeness is 1.00 and the approval
rate 0.667 (§4). Both the refutation and the fix are reported as found.

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

**Verified on the real dataset, not just synthetic scenarios.** Running the actual
`bronze` vs `cim_drifted` change-set (Experiment 6) through the supervisor:

```
as built (pre-fix)   -> PASS   max=medium   [high_drift_fraction(medium)]
fixed                -> PAUSE  max=high     [high_drift_fraction(medium),
                                             breaking_schema_change(high)]
```

This is the finding in its sharpest form: on **production data**, a breaking
business-key retype was detected, correctly classified as breaking — and the
as-built gate still said *proceed*. The fixed gate halts it.

**F-3: The fix does not over-block.** A gate that pauses on everything is useless.
Regression tests assert that **additive-only drift** (a new nullable column), a
**new table alone**, and an **unchanged snapshot** still PASS without a
breaking-change signal. Only genuinely breaking changes halt the run.

**F-4: H3a is supported only for the _fixed_ artifact.** The honest claim is: *as
originally built the governance layer blocked 62% of unsafe inputs; after a
targeted fix it blocks 100% on this scenario suite.* Reporting the pre-fix figure
matters — it is the evidence that the evaluation did real work, and it is the kind
of defect that only a deliberately adversarial test finds.

## 4. H3c — audit completeness: measured on a populated store

The store has since been filled with real review decisions taken through the UI, so
H3c moves from a gap to a reported result (findings §3C). Read back through the app's
own store factory, it holds **35 records — 10 approved, 5 rejected, 19 draft, 1
changes-requested** — across two source catalogs and one reviewer.

**Audit-trail completeness is 1.00.** Every record carries the full mandated
provenance — `plan_id, version, status, actor, timestamp_utc, comment, plan_json,
validation_json, parent_plan_id, rendered_yaml, yaml_path` — that is, who acted, when,
on which version, the decision, the rationale, and both the plan and its validation
report. The record schema makes those fields non-null and the store is insert-only, so
the review history of any plan is fully reconstructable; the completeness is 1.00 by
construction and now confirmed on real rows. Rationale coverage is 1.00 on rejections
(each one records why) and 0.33 across all decisions — an approval's reason is simply
its passing checks. Over the 15 terminal decisions the approval rate is 0.667.

The earlier state of this experiment — zero approval rows, completeness "not
measurable" — was true when the Delta store had not yet been wired and approvals lived
only in a local SQLite cache. That is no longer the case; the history is kept in git.

## 5. Threats to validity

- **The scenario suite is hand-built (n = 8).** It covers the failure modes the
  architecture makes plausible, but "100% on this suite" is not "100% of all
  possible unsafe inputs". A larger adversarial suite would strengthen the claim.
- **PAUSE ≠ hard block.** The governance model surfaces risk for a human decision;
  an operator can acknowledge and proceed (`acknowledge_risks=True`). H3a is about
  nothing being applied *unattended*, which is what is measured.
- **The fix was authored by the same person as the test.** An independent
  adversarial reviewer would be a stronger check.
- **H3c is now measured** on a populated store (§4): audit-trail completeness 1.00,
  approval rate 0.667. The earlier "structural guarantee only" caveat is superseded,
  though the store is still one reviewer over two catalogs (findings §6).

## 6. How to close this experiment

**H3a is closed** for the scenario suite (100%, verified on real data). Two optional
hardening steps would strengthen it:
- **Widen the adversarial suite** beyond n = 8 (e.g. a renamed business key, a
  table renamed rather than dropped, a type narrowing, simultaneous multi-table
  breaking drift).
- **Independent adversarial design** — have someone other than the fix's author
  invent the unsafe cases, removing the "same person wrote the fix and the test"
  limitation.

**H3c is now closed empirically** (§4) — it was closed by data, not code:

1. Real approvals were performed through the UI (`pnpm dev` → generate → review →
   approve), ≥10 decisions including rejects, so the audit trail populated.
2. The store was read back and completeness computed: **1.00 structural**, with every
   rejection carrying a rationale (findings §3C). That number closes H3c.
3. The same records yield the **approval rate** over the decisions taken (0.667). The
   controlled test of H1c's "across successive runs" wording — repeated runs on a single
   system with the corpus growing between them — is now provided *separately* by the
   corpus-growth curve (findings §3C): as ServiceNow's own corpus grows 0→125, naming
   adherence rises 0→~0.8+ and entity F1 ultimately reaches 0.978, with an early
   partial-corpus valley. This ad-hoc two-catalog review supplies the observational rate;
   the growth curve supplies the causal trend.

To refresh the numbers after further approvals: `python scripts/audit/audit_report.py`.

## 7. How to reproduce

Regression tests for the safety floor (deterministic, no network):
```bash
python -m pytest tests/ai/test_governance_safety.py -q
```
The block-rate table (§2/§3) is produced by running the committed supervisor
(`dbt_builder/src/ai/supervision/supervisor.py`) over the scenario suite; toggle
`SupervisorConfig(pause_on_breaking_change=False)` to reproduce the pre-fix 62%. The
scenarios and the escalation are covered by `tests/ai/test_governance_safety.py`. Audit
trail + approval rate: `python scripts/audit/audit_report.py`.
