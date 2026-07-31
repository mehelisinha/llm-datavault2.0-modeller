# Research Plan and Experiment Map

> **Purpose.** A single place that connects the three research questions (see
> `RQ-Hypothesis.md`) to the concrete experiments that answer them — what has been
> run, what each experiment contributes, what is still missing, and how the three
> planned baselines map onto code that actually exists. Written to be lifted
> almost directly into the methodology and results chapters.

---

## 1. The three baselines, as built (not as imagined)

The proposal defined three comparison arms applied to the same ExampleCorp source
tables. After building the prototype, here is what each arm *actually* is in code
— an honest reconciliation, because one arm cannot do what the proposal assumed:

| Arm | Proposal definition | What exists in code | Consequence |
|---|---|---|---|
| **Manual expert** | Researcher inspects the Databricks dev schema, makes all hub/link/sat decisions, writes YAML by hand; time and correction steps recorded | The hand-authored **gold sets** (`gold_sets/*.yml`) *are* this arm's output. Time / correction counts were **not** recorded | Usable as the accuracy reference now; needs a timed manual session to get the effort numbers |
| **Deterministic-only** | Pipeline with the LLM disabled — deterministic snapshot, diff, validation, governance gate — "to isolate the AI layer's contribution over rule-based automation alone" | The deterministic pieces exist (`diff_analyzer`, `dbt_gate`, `supervisor`). **But there is no rule-based classifier** — every `modeller.py` in the lineage (including on `ai/integration`) is an LLM agent | For **drift/safety** this arm is real. For **generation (Use Case A)** it produces *nothing* unless a heuristic classifier is added — see §5, decision (b) |
| **Full multi-agent** | discovery → LLM classification + impact analysis → YAML generation/patching → deterministic validation → human governance gate | Fully present: modeller → plan-reviewer → orchestrator → `dbt_gate` → `supervisor` → approval store | Ready to evaluate end-to-end |

**Branch archaeology (for the methodology chapter).** `ai/integration` and
`ai/phase-b-agents-ui` are both **ancestors** of the current `ai/thesis-experiments`
branch (their HEADs are the merge-bases), so all of their code is already present
in evolved form. `ai/integration` is the deterministic foundation (discovery,
contracts, diff — phases 0–3, no agent classification); `ai/phase-b-agents-ui`
added the multi-agent classification and the UI/governance workflow. The
three-arm comparison does **not** require checking out old branches — the
deterministic pieces and the full pipeline coexist on the current branch and are
toggled by configuration.

---

## 2. Do the original research questions still hold?

Yes — all three are still the right questions, and the prototype matches the
architecture they assume. Only one claim bent under evidence: H1's flat "at least
as accurate as manual" became a three-axis, conditional statement (see
`RQ-Hypothesis.md`). Nothing was abandoned; the claims were sharpened.

---

## 3. What Experiments 1–4 contribute (and to which RQ)

| Exp | Title | Answers | Key result |
|---|---|---|---|
| 1 | Modeller ablation | RQ1 / H1a, H1b | Entity id at ceiling (~0.93 F1 vs the manual gold), learning-independent; naming not transferred at k=3 |
| 2 | Learning curve + LOO | RQ1 / H1c | Naming transfer is threshold-gated (0→1 at k≈10) and instance-level copying, not generalisation (leave-one-out → 0) |
| 3 | CIM cross-domain control | RQ1 / H1c (safety of corpus) | Cross-domain examples are inert on CIM; under a verified-load, leave-one-out control they give ServiceNow a significant *structural* gain (link parsimony 1.155→1.064, p=0.002) with no naming transfer and no harm (findings §2.8). A memorisation ceiling (full corpus) confirms the naming "gain" is in-domain copying, not transfer. The naming effect needs a table-vs-concept gap *and* the same entity in the corpus |
| 4 | End-to-end + taxonomy shift | RQ1 / H1d | The reviewer resolves link-FK errors but introduces surrogate-key hubs — conformance up, entity_f1 down, naming neutral, blast-radius up: a trade-off, not a scalar win |

**Honest coverage statement.** Experiments 1–4 answer **RQ1 thoroughly** (all four
sub-hypotheses have evidence) and touch the *edges* of RQ3 (conformance and
blast-radius are safety-adjacent proxies). They do **not** address **RQ2 at all**,
nor the **core empirical claims of RQ3** (safety block-rate, human-effort
comparison, audit completeness). Those are the gaps the remaining experiments fill.

---

## 4. Gap analysis → the remaining experiments

| RQ / Hypothesis | Gap | Experiment | Needs code? | Branch |
|---|---|---|---|---|
| RQ1 H1a + RQ3 H3b | No 3-arm accuracy+effort comparison | **Exp 5** — baseline comparison | Maybe (deterministic-A baseline) | see §5 |
| RQ2 H2a | Deterministic diff never tested on a labelled drift | **Exp 6a** | No (engine exists) | data only |
| RQ2 H2b | No AI impact classifier (additive/cosmetic/breaking) | **Exp 6b** | **Yes** | `ai/usecaseB-drift` |
| RQ2 H2c | Drift-review effort not measured | **Exp 6c** | No | — |
| RQ3 H3a | Safety gate never tested with unsafe inputs | **Exp 7a** | No (gates exist) | — |
| RQ3 H3c | Audit completeness — measured via Exp 7 (findings §3C) | **Exp 7b** | No (store exists) | — |

Use Case B design detail lives in `use-case-b-drift-design.md`.

---

## 5. Experiment 5 — three-arm baseline comparison (design)

**Goal.** Directly compare the three arms on the same ExampleCorp source tables to test
H1a (first-run accuracy vs manual) and H3b (human effort), for Use Case A.

**Arms and how each produces an output:**
- **Manual:** the gold mapping, plus a *timed* manual modelling session on the
  same tables to record wall-clock time and number of correction/decision steps.
- **Deterministic:** see decision (b) below — a small, transparent heuristic
  classifier, so the arm has something to score.
- **Full:** the modeller → reviewer pipeline (already the subject of Exp 4).

**Metrics (same structural grading as Exp 1–4, so results are comparable):**
`entity_f1`, `naming_adherence`, `link_ratio`, `conformance_score`,
`weighted_error_impact`; plus, for the human-effort dimension, **time-to-approved**
and **correction steps** per arm.

### Decision (b) — the deterministic arm for Use Case A: recommendation

**Recommendation: build a small, deterministic heuristic classifier as the
Use-Case-A baseline — do _not_ report a blank.**

Reasoning:
1. **It is what the proposal actually asked for.** The proposal justifies the
   deterministic arm as isolating "the AI layer's contribution over *rule-based
   automation alone*." That phrasing presupposes a rule-based classifier to
   compare against. Reporting "the deterministic arm produces nothing" answers a
   weaker question than the one posed.
2. **It is standard scientific practice.** A naïve/heuristic baseline is the
   expected control in any ML evaluation — you measure a method's lift over a
   simple rule, not over emptiness. Without it, the AI's headline accuracy has no
   floor to be judged against.
3. **It makes the three-arm comparison symmetric and quantitative.** All three
   arms then produce a mapping graded by the *same* metrics, so the table reads
   Manual vs Heuristic vs Full on one scale, and the AI's real contribution
   (entity id, naming, parsimony) becomes a measured delta rather than a
   rhetorical claim.

**Proposed heuristic (fully deterministic, no LLM, ~100 lines):** each source
table → one hub keyed on its primary/first unique-looking key; each foreign-key-
like column → one link between the two implicated tables; the remaining
descriptive columns → one satellite per hub. This is intentionally simple and
transparent so it is defensible as a "rule-based automation" floor.

**Secondary reporting (keep the honest observation too):** alongside the heuristic
scores, state plainly that *without either rules or the AI layer the pipeline
cannot classify at all* — that structural fact is itself evidence for the AI
layer's necessity and belongs in the RQ1 discussion.

> **Open question for the author (asked separately):** if you would rather not
> introduce a heuristic classifier, the fallback is to report the structural blank
> for Use Case A and lean on the deterministic arm only in Use Case B (drift),
> where it is genuinely capable. The recommendation above is the stronger option.

---

## 6. Experiment 7 — safety & governance (design sketch, for RQ3)

- **7a (safety, H3a):** construct a small suite of deliberately unsafe inputs — a
  breaking change (business-key rename / key-column type change already flagged
  HIGH by `diff_analyzer`), an invalid plan, and a plan carrying ERROR-severity
  validation issues — and assert the governance path blocks/pauses each (no
  promotion). Report block rate (target 100%) and idempotency of repeated runs on
  unchanged inputs.
- **7b (governance completeness, H3c):** over the approval runs, read the approval
  store and compute audit coverage — fraction of approved decisions carrying
  actor, timestamp, plan version, and rationale. Report approval-chain
  traceability.

Both are largely deterministic assertions over existing machinery, so 7 is low
risk and high value for RQ3.

---

## 7. Threats to validity and stronger scientific alternatives

These apply across all experiments and should appear in the thesis's limitations
section. Several are cheap upgrades that materially raise rigour:

- **Single-author gold (construct validity).** The biggest threat: the "ground
  truth" is one person's Data Vault judgement. *Partly addressed:* a documented
  codebook plus an independent-annotator panel put inter-rater agreement at κ 0.84
  (findings §2.9). The remaining upgrade is a genuinely *human* second labelling —
  a second annotator or the author's test–retest after a washout — for a human
  inter-rater figure. This is the single most valuable addition still open.
- **Means without dispersion.** Results are reported as seed means. *Upgrade:*
  report confidence intervals / effect sizes; with small n use bootstrap CIs or a
  non-parametric test (e.g. Wilcoxon signed-rank) rather than asserting a
  difference from point estimates.
- **Naming measured as exact match.** *Upgrade:* also report an edit-distance or
  an LLM-as-judge naming score, and validate the judge against human labels on a
  subset (report correlation).
- **Feedback tested via the k-proxy.** Exp 2 varied retrieved context size *k* as
  a stand-in for "corpus grows." *Upgrade:* a true longitudinal run — approve
  decisions round by round and measure the actual correction-rate drop — tests
  H1c in the hypothesis's own words.
- **One reviewer model.** Exp 4's trade-off (H1d) may be specific to gpt-5.2.
  *Upgrade:* ablate the reviewer (a weaker model, or none) to show the trade-off
  is a property of the *stage*, not one model.
- **Reviewer stochasticity.** The reviewer runs at temperature 1.0; two seeds
  bound but do not eliminate variance. *Upgrade:* more seeds on the reviewed arm.
- **Two source systems.** ServiceNow + CIM. *Upgrade:* more diverse schemas would
  strengthen external validity (this is the main MSc→PhD scaling axis).
- **For Use Case B specifically:** score impact classification with a full
  confusion matrix and per-class precision/recall, and use a **cost-weighted**
  error (a missed *breaking* change is far worse than a mislabelled *cosmetic*
  one) rather than plain accuracy.
- **Human-effort protocol.** Time-to-approved is sensitive to learning effects and
  who is doing it. *Upgrade:* several tables, fixed protocol, and acknowledge the
  single-operator limitation explicitly.

---

## 8. Recommended sequencing

1. **Exp 5 (3-arm)** — highest value: closes H1a and H3b together. Resolve
   decision (b) first (recommend: heuristic baseline).
2. **Exp 6 (Use Case B drift)** — code the impact classifier on `ai/usecaseB-drift`;
   author supplies a drifted Databricks dataset for the labelled diff.
3. **Exp 7 (safety & governance)** — cheap, deterministic, completes RQ3.
4. **Optional rigour upgrades** — second gold annotator + κ; confidence intervals;
   longitudinal feedback run. These lift the work toward a doctoral bar.
