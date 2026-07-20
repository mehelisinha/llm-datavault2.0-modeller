# Experiment 5 — Three-arm baseline comparison (Manual vs Deterministic vs Full)

**Research questions.** This is the proposal's headline comparison. It answers
**RQ1 / H1a** (is the AI system at least as accurate as the manual expert, and how
much does it add over rule-based automation?) and sets up **RQ3 / H3b** (human
effort), for Use Case A (generation).

**Arms.**
- **Manual expert** — the hand-authored gold model. Its accuracy is the reference
  (1.0 by construction); the arm's *research value* is its human effort (§5).
- **Deterministic** — the rule-based `HeuristicClassifier` (no LLM): one hub per
  table keyed by a fixed rule, links from foreign-key-like column names, one
  satellite of the remaining columns. This is the "rule-based automation alone"
  baseline the proposal defined. (See decision (b) in
  `research-plan-and-experiment-map.md` — a heuristic baseline was built rather
  than reporting a blank.)
- **Full multi-agent** — the modeller (learning on, k=10) → gpt-5.2 plan-reviewer
  pipeline. Reported in two stages because the reviewer is a genuine trade-off
  (H1d): the **classification stage** (modeller output) and the **reviewed output**
  (what the deployed pipeline actually promotes).

**Systems.** ServiceNow IT4IT (`SNOW_IT4IT_001`, a *hard* schema — prefixed table
names, telemetry/junction tables, one table holding two entities) and IEC-CIM
(`IEC_CIM_001`, an *easy* schema — unambiguous mRID-keyed tables). Same structural
grading as Experiments 1–4; the deterministic arm is seed-independent, the full
arm is averaged over 2 seeds.

## 1. Results

**ServiceNow (hard schema), means:**

| Metric | Manual (ref) | Deterministic | Full — classification | Full — reviewed |
|---|---|---|---|---|
| entity_f1 | 1.00 | **0.50** | **0.94** | 0.71 |
| naming_adherence | 1.00 | 0.00 | 0.50 † | 0.42 † |
| link_ratio (1.0 = ideal) | 1.00 | **0.00** (under) | 1.82 (over) | 1.86 (over) |
| conformance | — | 0.90 | 0.95 | 0.96 |
| hubs produced (gold = 7) | 7 | 9 | ~8 | ~8 |

**CIM (easy schema), means:**

| Metric | Manual (ref) | Deterministic | Full — classification | Full — reviewed |
|---|---|---|---|---|
| entity_f1 | 1.00 | **1.00** | 1.00 | 1.00 |
| naming_adherence | 1.00 | 0.33 | 1.00 | 1.00 |
| link_ratio | 1.00 | 0.00 (under) | 2.00 (over) | 2.00 (over) |
| conformance | — | 1.00 | 1.00 | 1.00 |

† Naming is the unstable axis — see the variance note in §4.

## 2. Analysis — entity identification (H1a)

**F-1: The AI's lift over rules is large exactly where the schema is hard, and nil
where it is easy.** On CIM the deterministic rule already scores entity_f1 = 1.0 —
the mRID keys are unambiguous, so rules and AI tie. On ServiceNow the rule
collapses to 0.50 while the modeller reaches 0.94. The gap *is* the AI's
contribution, and it is concentrated in the cases a rule cannot handle. Precisely,
the deterministic arm on ServiceNow:
- **Missed `hub_user` and `hub_group`** — both live in `sys_user_grmember`; the
  rule makes exactly one hub per table and cannot split one table into two
  entities.
- **Missed `hub_country`** — the gold keys it on `iso3166_3`, but the rule
  defaulted to the `sys_id` surrogate.
- **Produced 5 spurious hubs** — it makes a hub for *every* table, including
  telemetry (`volumemetrics`), a junction/mapping table, and `task_sla`, which the
  expert excludes or models as a link, not a hub.

The modeller, by contrast, splits `sys_user_grmember`, recognises the semantic
country key, and suppresses the telemetry table — the judgement calls that
constitute "expert-level" classification.

**F-2: H1a is supported at the classification stage but eroded by the reviewer.**
At the modeller stage the system matches the manual expert on entity
identification (0.94 ≈ 1.0 within the ~0.06 ceiling-band noise seen in Exp 1). The
**reviewer then lowers entity_f1 to 0.71** — still far above the rule baseline
(0.50) but no longer level with the manual expert. So the honest reading of H1a is
conditional: *the AI's classification stage is as accurate as the manual expert on
entity identification; the full pipeline, including the governance-oriented
reviewer, trades some of that entity fidelity for convention conformance* (the H1d
trade-off, reproduced here — the reviewer resolves link-FK errors but re-keys hubs
onto surrogates). On the easy schema (CIM) all three arms tie at 1.0, so the
trade-off only surfaces where there is difficulty to begin with.

## 3. Analysis — the other two axes

**F-3: Naming — rules are weak, AI is better but not free.** The deterministic arm
scores 0 on ServiceNow (raw `hub_core_company` names) and only 0.33 on CIM —
notably it cannot even de-pluralise (`hub_terminals` vs the gold `hub_terminal`),
which the LLM does. So even on the "easy" schema the rule loses on naming. The AI's
naming advantage is real but unstable run-to-run (§4).

**F-4: Links — the two automated arms fail in _opposite_ directions.** The
deterministic arm produces **zero** links on both systems (`link_ratio = 0`):
ServiceNow's foreign keys are named `company`/`parent`/`vendor_manager`, not
`<table>_id`, so the pattern-matcher finds nothing; it *under-links*. The AI
*over-links* (`link_ratio` 1.8–2.0), emitting a link for many FK-like columns the
gold treats as attributes. Neither matches the expert's link count, but the
failure modes are mirror images — a useful qualitative contrast: rules are
conservative and miss relationships; the LLM is liberal and invents them.

## 4. Threats to validity / honest caveats

- **Naming is the unstable axis (important).** This run measured modeller naming at
  k=10 as 0.43–0.57, whereas the Experiment 2 reproduction measured 1.0 with zero
  variance a few days earlier. The *direction* of the naming-threshold finding
  (near-0 at low k, positive at k=10) is robust, but its *magnitude at k=10 is not
  a stable point value* across sessions — most likely gpt-4.1 deployment drift or
  retrieval-order nondeterminism over calendar time. Entity identification, by
  contrast, is stable, which is why the Experiment 5 headline (F-1, F-2) rests on
  entity_f1, not naming.
- **The manual arm's accuracy is tautological.** The gold *is* the manual output,
  so its entity_f1 is 1.0 by definition; it cannot be "wrong" against itself. The
  meaningful manual measurement is effort (§5), still to be collected. The gold is
  also single-author — the standing construct-validity limitation.
- **The deterministic baseline is deliberately naïve.** A more elaborate rule
  engine (e.g. reading real PK/FK constraints from Unity Catalog) would score
  higher. The claim is not "rules cannot do this" but "the *simple* rule baseline
  the proposal defined is substantially beaten by the AI on hard schemas."
- **Two systems, two seeds.** External validity is limited; the *pattern* (AI-lift
  scales with schema difficulty) is the transferable finding.

## 5. Human effort (H3b) — protocol for the manual arm

The accuracy arms above run automatically; the **human-effort** dimension of H3b
requires a measured manual session that only the researcher can perform. Protocol
(to keep the number defensible):

1. **Same tables, cold start.** Model the same ServiceNow (and CIM) source tables
   by hand via Unity Catalog, with no AI assistance, exactly as the proposal's
   manual baseline describes.
2. **Record:** wall-clock **time-to-approved** and the **number of discrete
   decisions/corrections** (each hub/link/sat classification and each business-key
   choice counts as one).
3. **Full-arm comparison:** for the same tables, record the time to review and
   approve the pipeline's output (accept/edit/reject per object) — the corrections
   here are the pipeline's error rate made concrete.
4. **Deterministic-arm comparison:** the rule output is instantaneous to produce;
   record the time to *fix it up to approvable quality* (which, given F-1/F-4, is
   substantial on ServiceNow — missing entities and all links must be added).

The prediction (H3b) is: manual is slowest per table; the full pipeline is fastest
*to an approvable result* on the hard schema because it already found the entities;
the deterministic arm is fast to produce but slow to repair. This table is the
last piece of Experiment 5 and is filled from the researcher's timed session.

## 6. Interpretation — what Experiment 5 establishes

- **H1a (entity accuracy):** supported at the classification stage — the AI matches
  the manual expert on entity identification and **beats the rule-based baseline
  decisively on hard schemas (0.94 vs 0.50)**, while tying on easy ones. The full
  pipeline (with reviewer) trades some entity fidelity for conformance (H1d).
- **The AI's value is schema-dependent and locatable:** it is concentrated in the
  judgement calls (splitting entities, semantic keys, excluding non-business
  tables) that rules cannot make — which is a more useful claim for the thesis
  than a blanket "AI is better".
- **Both automated arms mishandle link cardinality**, in opposite directions —
  neither is a solved problem, and this is an honest limitation to carry forward.

## 7. How to reproduce

Deterministic arm (seed-independent):
```bash
python -m dbt_builder.src.ai.evaluation experiment \
  --system SNOW_IT4IT_001 --system IEC_CIM_001 \
  --condition "deterministic:producer=heuristic" --seeds 42
```
Full arm (modeller + reviewer, 2 seeds):
```bash
python -m dbt_builder.src.ai.evaluation experiment \
  --system SNOW_IT4IT_001 --system IEC_CIM_001 \
  --condition "full:k=10,review=1" --seeds 42,43
```
The manual arm is the gold model (`gold_sets/*.yml`) plus the timed session in §5.
Heuristic classifier: `dbt_builder/src/ai/evaluation/baselines.py`, unit-tested in
`tests/ai/test_baselines.py` (no network). Branch: `ai/exp5-baselines`.
