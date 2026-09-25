# DWA — YAML-Generation Performance Evolution

How the metadata-YAML generation went from **slow (often failing after minutes)**
on branch `ai/phase-b-agents-ui` to **fast** on `ai/plan-review-modelling`, and
the detailed reasoning behind every change.

This is methodology-evolution material for the thesis: it documents a concrete
before/after, the exact commits responsible, and *why* each optimisation was
adopted (the problem it solved, not just what it did).

---

## Table of contents

1. [How this was traced](#1-how-this-was-traced)
2. [The slow baseline (phase-b)](#2-the-slow-baseline-phase-b)
3. [Commit table — what changed](#3-commit-table--what-changed)
4. [Each optimisation, and why it was adopted](#4-each-optimisation-and-why-it-was-adopted)
5. [The unstable interim: `ai/agent-optimisation` before the idempotency-fix merge](#5-the-unstable-interim-aiagent-optimisation-before-the-idempotency-fix-merge)
6. [Deep dive: the voting trade-off (3 votes vs 1) and YAML quality](#6-deep-dive-the-voting-trade-off-3-votes-vs-1-and-yaml-quality)
7. [Before/after wall-time model](#7-beforeafter-wall-time-model)
8. [Evidence: lever → commit map](#8-evidence-lever--commit-map)
9. [Honest caveats](#9-honest-caveats)

---

## 1. How this was traced

`ai/phase-b-agents-ui` is a **direct ancestor** of the current branch. The merge
base equals the phase-b tip (`44dd597`), and:

```
git rev-list --left-right --count ai/phase-b-agents-ui...ai/plan-review-modelling
0    50
```

So the fast branch is exactly **50 commits ahead** of the slow one — every
relevant change lives in those 50 commits. Each performance lever below was
attributed to its commit with pickaxe search (`git log -S "<identifier>"`),
which finds the commit that introduced (or removed) a given symbol.

The modeller file itself tells the story at a glance:

| | `dbt_builder/src/ai/agents/modeller.py` |
|--|--|
| phase-b (slow) | **358 lines** |
| current (fast) | **1484 lines** |

Most of that growth is the concurrency, batching, rate-limiting and recovery
machinery described here.

---

## 2. The slow baseline (phase-b)

In `ai/phase-b-agents-ui` the modeller's `propose()` did the naïve thing — the
**entire catalogue in one prompt**, **samples drawn sequentially**:

```python
# ai/phase-b-agents-ui : modeller.py  (the slow path)
def propose(self, payload: DiscoveryPayload) -> ModelingPlan:
    user_prompt = _build_user_prompt(payload)      # ALL tables in ONE giant prompt
    candidates, errors = [], []
    for sample_idx in range(self._samples):        # 3 samples, ONE AFTER ANOTHER
        raw = self._one_completion(user_prompt)    # one blocking network call each
        ...
    return _vote(candidates)
```

Combined with the surrounding configuration, a ~50-table run meant:

1. **One enormous prompt** describing all 50 tables → the model had to emit one
   massive JSON plan covering every entity at once.
2. **Three completions in series** (plain `for` loop, no threads).
3. **On gpt-5** — `primary_chat_deployment = "gpt-5"`, with *no* dedicated
   modeller deployment, so it paid gpt-5's invisible reasoning-token overhead and
   its low TPM quota.
4. **Serial catalog describe** in SNAPSHOT — `catalog_inspector.inspect_catalog`
   had no parallelism; each table was described one at a time.
5. **No batching, no adaptive split, no token bucket, no budget clamp.** The
   single huge completion routinely hit `max_tokens`, returned **truncated
   JSON**, failed validation, and — because all three samples shared the same
   over-budget prompt — could fail *all three*, raising `ModellingAgentError`
   after minutes of waiting. The slow path's worst case was *slow **and** then a
   total failure*.

---

## 3. Commit table — what changed

The decisive commit is `13d2e59`; the others remove the remaining serial points
and the slow failure/retry paths.

| Commit | Title | What it contributed to speed |
|--------|-------|------------------------------|
| **`13d2e59`** | feat: AI model robustness, token limits, and LLM drift protections | **The core.** Introduced concurrent sampling (`sample_parallelism`, `_draw_samples_parallel`), parallel batching (`_propose_batched`, `batch_parallelism`, `batch_size`), the `large_catalog_threshold` single-completion mode, the `_TokenBucket` (TPM) + `BoundedSemaphore` (RPM) gates, and the dedicated `modeller_chat_deployment` (gpt-4o) |
| `fa72397` | feat(ai): approved-YAML storage layer … (+ catalog plumbing) | Added `catalog_describe_parallelism` / `describe_parallelism` — SNAPSHOT describe goes from serial to N-way parallel |
| `45a4d29` | Split overflowing batches adaptively and skip unrecoverable ones | `_propose_voted_adaptive`: a truncated batch is halved and retried (and a hopeless batch skipped) instead of failing the whole run |
| `dfe4b66` | Balance modeller batches to avoid fragile single-table batches | Even batch sizing → fewer wasted calls and fewer truncation failures |
| `17b2d7c` | Add configurable completion-token ceiling for the modeller | `max_completion_tokens` ceiling so budgets/retries never trigger Azure `max_tokens too large` (HTTP 400) |
| `6bac641` | Clamp completion budget and load modeller rules from a file | Budget clamp on the doubling retries → no wasted over-ceiling calls |
| `f111de2` | ai(reviewer): two-model plan reviewer with collapse guard and parallel chunked review | The added review step is itself **parallel + chunked**, so quality was raised without re-serialising the pipeline |

---

## 4. Each optimisation, and why it was adopted

For each lever: **the problem it solved**, then **why this was the right fix**.

### 4.1 Switch the modeller to gpt-4o (`modeller_chat_deployment="gpt-4o"`)

**Problem.** The modeller is the hottest call in the pipeline — it fans out
across many large prompts. Running it on gpt-5 meant (a) every call burned a
large, *invisible* share of the token budget on reasoning tokens before emitting
any JSON, inflating latency and cost; and (b) gpt-5 typically has the **lowest
TPM quota** of any deployment in the region, so the modeller was the dominant
source of HTTP 429 (rate-limit) errors — and every 429 turns into a backoff-and-
retry, i.e. *more wall time*.

**Why this fix.** gpt-4o has no reasoning-token overhead, returns deterministic
output at `temperature=0`, and usually has **3–5× the TPM headroom** of gpt-5 in
the same region. Crucially the change is *scoped*: only the modeller moves to
gpt-4o (`modeller_chat_deployment`); `primary_chat_deployment` stays gpt-5 for the
agents where a single high-value judgement benefits from stronger reasoning (e.g.
the plan reviewer). This is the single most impactful change because it speeds up
every call **unconditionally** — independent of any concurrency setting — and
removes the main 429 source.

### 4.2 Batch the catalogue (`_propose_batched`, `batch_size=25`)

**Problem.** One prompt for all 50 tables forced one completion to emit a JSON
plan for all 50 entities. That output frequently exceeded the model's
completion-token ceiling → **truncated, unparseable JSON** → the sample is
dropped. When every sample truncates, the whole run fails after minutes.

**Why this fix.** Splitting the tables into fixed-size batches (default 25)
bounds each completion's required *output* size, so each call comfortably fits
its token budget and actually returns valid JSON. The cost is losing links
between tables that land in different batches — but the table-naming convention
plus name-union merging recovers most of those, and a *reviewable partial plan*
beats a *failed full run*. Batching converts a single fragile mega-call into many
robust small calls.

### 4.3 Run batches concurrently (`batch_parallelism`)

**Problem.** Many small batches run **one after another** is still O(number of
batches) in wall time.

**Why this fix.** Batches are independent (each is a self-contained
`DiscoveryPayload` sharing the same `system_id`), so they can run on a
`ThreadPoolExecutor`. With `batch_parallelism=0` meaning "as many workers as
batches", the total wall clock collapses toward **one batch's round-trip** rather
than the sum — i.e. latency stays roughly *constant* as the catalogue grows,
instead of linear. (Actual overlap is bounded by the RPM/TPM gates in §4.6 — see
the caveat in §7.)

### 4.4 Concurrent sampling within a batch (`sample_parallelism`)

**Problem.** Self-consistency voting needs N samples (default 3). Drawing them in
a `for` loop triples the wall time of every batch.

**Why this fix.** The N samples are independent draws of the same prompt, so they
parallelise cleanly (`_draw_samples_parallel`). The production factory expands the
`sample_parallelism=0` sentinel to `samples`, so all 3 fire at once and the voting
step collapses from ~3× to ~1× round-trip. Order is preserved so the vote
tie-break (`candidates.index`) stays reproducible.

### 4.5 Single completion for large catalogues (`large_catalog_threshold=15`)

**Problem.** Voting (3 samples) is valuable for quality on small/ambiguous
inputs, but on a large catalogue it triples the number of expensive calls for
diminishing returns — and large catalogues are exactly where cost/latency hurt
most.

**Why this fix.** Above the threshold (15 tables), sampling drops to **one**
completion (no vote). This is a direct **3× reduction in the number of LLM
calls** on the big runs, applied where it matters and skipped where voting still
earns its keep. It is independent of concurrency, so it helps even when the
RPM/TPM gates are tight.

### 4.6 Rate-limit gates: TPM token bucket + RPM semaphore

**Problem.** Once you fan out (batches × samples), you can *overwhelm your own
Azure deployment*. Azure returns 429 when **either** requests-per-minute **or**
tokens-per-minute is exceeded, and real workloads with uneven prompt sizes hit
**TPM first** (e.g. 4 × 80k-token calls = 320k tokens/min against a 60k/min
deployment). A naïve fan-out would 429-storm, and every 429 → backoff → retry →
*slower than serial*.

**Why this fix.** Two coordinated, process-global gates make the fan-out
*self-throttling* instead of self-defeating:

- `_TokenBucket` paces by **TPM** — `acquire(estimated_tokens)` blocks until the
  bucket has refilled enough, estimating cost from `prompt_chars/4 + completion
  budget`.
- `BoundedSemaphore` bounds **simultaneous in-flight requests** (RPM).

The two-stage order matters: reserve TPM *first*, then take an RPM permit — so
workers queue at the token bucket rather than holding an RPM permit while waiting
for tokens (which would deadlock at low concurrency). This is client-side
backpressure: it lets you push concurrency right up to the deployment's real
quota without crossing it. The point isn't to *add* speed directly — it's to make
the parallelism in §4.3–4.4 *safe to use* so it doesn't collapse into a retry
storm.

### 4.7 Budget clamp + completion-token ceiling (`6bac641`, `17b2d7c`)

**Problem.** The empty-response / truncated-JSON recovery doubles the token
budget on retry. Without a ceiling, a 16 384 budget becomes 32 768 and Azure
rejects the request with `max_tokens is too large` (HTTP 400) — failing the whole
run. And retrying when the budget is already at the model ceiling just
re-truncates identically, wasting a call and TPM.

**Why this fix.** `_clamp_budget` caps every budget (including doubled retries) at
the model's hard ceiling, and `_has_retry_headroom` skips the retry when doubling
wouldn't actually raise the cap. Together they remove two slow dead-ends: the
400-failure path and the pointless-retry path. Pure waste elimination.

### 4.8 Adaptive recursive splitting (`_propose_voted_adaptive`, `45a4d29`)

**Problem.** Even with a fixed `batch_size`, a batch of unusually *wide* tables
can still overflow the completion budget and truncate. Hand-guessing a smaller
global `batch_size` would slow down every normal run to protect against the rare
wide one.

**Why this fix.** When *every* sample in a batch fails specifically with *invalid
JSON* (the signature of output truncation), halve the table set and recurse until
each piece fits (down to a single table), then merge by name-union. Critically it
**only splits on truncation** — a schema-invalid failure (a complete but
malformed plan) is re-raised immediately, because halving wouldn't fix it and
would just waste calls. This makes the modeller **self-tune to any table width**
without a conservative global batch size, so normal runs stay fast and only the
pathological batch pays the split cost.

### 4.9 Balanced batches (`dfe4b66`)

**Problem.** Naïve chunking can leave a final fragile single-table batch (or
wildly uneven batches), wasting calls and increasing truncation risk on the
oversized ones.

**Why this fix.** Balancing batch sizes (respecting `max_prompt_tokens`) keeps
each call's prompt well under the per-request TPM allowance and avoids
degenerate batches — fewer calls, fewer failures, smoother pacing.

### 4.10 Parallel catalog describe (`catalog_describe_parallelism=8`, `fa72397`)

**Problem.** Before any LLM runs, SNAPSHOT has to *describe* every bronze and
vault table (schema + dtypes) via the catalog. Phase-b did this **serially**, so
SNAPSHOT alone scaled linearly with table count.

**Why this fix.** Describe calls are independent catalog (Unity Catalog / REST)
lookups — **not LLM calls**, so they are *not* gated by the RPM/TPM limiter and
parallelise freely. `inspect_catalog` now runs them through
`ordered_parallel_map(max_workers=describe_parallelism)` (default 8), cutting the
SNAPSHOT step's wall time by up to ~8×. This is a clean, unconditional win with
no quota interaction.

### 4.11 Parallel chunked review (`f111de2`)

**Problem.** The new two-model generate→review step *adds* an LLM pass, which
could re-introduce a serial bottleneck and undo the gains above.

**Why this fix.** The reviewer chunks the plan and reviews chunks in parallel
(`ThreadPoolExecutor`), and is fail-safe (any problem falls back to the original
plan). So quality went up without putting a new serial call on the critical path.

---

## 5. The unstable interim: `ai/agent-optimisation` before the idempotency-fix merge

The branch history reveals an important intermediate stage that explains *why the
work felt slow **and** unstable for a while*. The fast machinery did **not** all
land together — the **fan-out shipped first, the guardrails shipped later**, and
in between (`ai/agent-optimisation`) the pipeline had the throughput levers but
none of the safety net.

### 5.1 What the branch graph shows

The merge `06be3d7` ("Merge branch 'ai/idempotency-fix' into
'ai/agent-optimisation'") has two parents:

- **agent-optimisation tip** `c86c2c9` (2026-06-05)
- **idempotency-fix tip** `f81c759` (2026-06-17)

and the **merge-base of the two sides is `c86c2c9` itself**. In other words,
`ai/agent-optimisation` was a *direct ancestor* of `ai/idempotency-fix`:
agent-optimisation contributed **zero** commits beyond the base, and **all 22
stabilisation commits were developed on `ai/idempotency-fix`** and pulled in by
the merge.

Verified with:

```
git merge-base c86c2c9 f81c759            # → c86c2c9  (agent-optimisation is the base)
git log --oneline c86c2c9..c86c2c9        # → (empty)  nothing unique on agent-optimisation
git log --oneline c86c2c9..f81c759        # → 22 commits  all the guardrails + determinism
```

### 5.2 What agent-optimisation already had (so it *looked* fast-capable)

`ai/agent-optimisation` (at `c86c2c9`) already contained the throughput core:

| Already present pre-merge | Commit |
|---------------------------|--------|
| Concurrent sampling, parallel batching, `_TokenBucket`+semaphore, `large_catalog_threshold`, **gpt-4o** modeller deployment | `13d2e59` |
| Parallel catalog describe | `fa72397` |

So on a clean, well-sized catalogue it *could* be fast. The problem was
everything that happens when a call doesn't go perfectly.

### 5.3 What was MISSING pre-merge — and why that made it slow & unstable

Every recovery/determinism guardrail was **absent** on agent-optimisation and
arrived only via the idempotency-fix merge (confirmed with
`git merge-base --is-ancestor <commit> c86c2c9` returning false for each):

| Missing guardrail | Commit (came via merge) | Failure it left open |
|-------------------|-------------------------|----------------------|
| Completion-budget **clamp** | `6bac641` | The truncated-JSON retry **doubles** the token budget; with no clamp it could exceed the model ceiling → Azure `max_tokens is too large` **HTTP 400** → whole run fails |
| Configurable completion-token **ceiling** | `17b2d7c` | No ceiling existed to clamp *to* — the clamp above is meaningless without it |
| **Adaptive batch split** + skip unrecoverable | `45a4d29` | When a batch's output overflowed, *every* sample truncated and the run **failed entirely** instead of halving the batch and recovering |
| **Batch balancing** | `dfe4b66` | Naïve chunking produced fragile single-table batches and over-large batches that truncated — wasted calls, more failures |
| **Deterministic seeding** of samples | `851a3a7` | Samples were non-reproducible → unstable, non-repeatable output run-to-run |
| **Deterministic emitter ordering** + modeller rule files | `0af1a3b` | YAML **drifted** between identical runs (lists in different orders) → "unstable" diffs, un-reviewable |
| **Tests** for clamp / adaptive split / balancing | `9e25514` | The safety net wasn't even verified, so regressions were invisible |
| AS_OF_DATE / `as_of_dates` correctness | `1c1413d`, `1caa488`, `487aa8a` | PIT/idempotency correctness gaps (re-runs not stable) |

### 5.4 Why "fan-out without guardrails" is specifically slow *and* unstable

This interim state is the textbook failure mode of adding parallelism before
adding resilience, and it's worth stating plainly for the thesis:

1. **Unstable — total-failure tail.** Fanning out (batches × samples) multiplies
   the chance that *some* call overflows its completion budget. Pre-merge there
   was no adaptive split and no budget clamp, so an overflow didn't degrade
   gracefully — it **failed the whole run** (truncated JSON on every sample, or an
   HTTP 400 from the doubled retry). More parallelism therefore meant *more
   opportunities to fail*, not just more speed.

2. **Slow — you pay full cost, then fail.** Without recovery, an overflowing
   large run does all its expensive fan-out work and *then* errors out after
   minutes, forcing a manual re-run. Effective throughput is worse than serial
   because the failure tail dominates. Unbalanced batches added more wasted calls
   on top.

3. **Unstable — non-deterministic output.** Without seed plumbing and
   deterministic emitter ordering, two identical runs produced different YAML.
   That is the "unstable" the developer *sees*: not just crashes, but
   un-reproducible, drifting output that can't be diffed or trusted — the exact
   thing the `idempotency-fix` branch name targets.

The `ai/idempotency-fix` merge added precisely the missing layer: **make every
overflow recoverable (clamp + ceiling + adaptive split + balancing) and every run
reproducible (seeding + deterministic ordering + AS_OF_DATE correctness).** Only
*after* that merge did the throughput already present on agent-optimisation turn
into reliably-fast generation. The lesson: **the parallelism made it
fast-capable; the idempotency-fix guardrails made that speed actually realisable
by removing the failure/retry/drift tail.**

---

## 6. Deep dive: the voting trade-off (3 votes vs 1) and YAML quality

This expands on §4.5. The modeller draws **3 samples and votes** for catalogues
of ≤ 15 tables, but drops to **1 sample (no vote)** above
`large_catalog_threshold = 15`. A natural question for the thesis: if one sample
already produces a complete plan, why vote three times at all — and what does
turning voting off do to YAML quality?

### 6.1 What "voting" actually is

An LLM is **not deterministic**: ask it the same question twice and you can get
slightly different answers — one run nails every link, another misses one or
picks a weaker business key. Voting (the technical name is **self-consistency**)
is simply: *draw 3 independent samples, then keep the answer the majority agree
on.* In this codebase the agreement is measured on the **structural fingerprint**
`(sorted hub names, sorted link names, sorted sat names)`; the plan whose
fingerprint occurs most often wins (ties broken by total confidence, then lowest
index — see `_vote` in `modeller.py`).

So voting does **not** make a single answer better. It is an **error-correction
safety net**: it filters out the occasional random slip by trusting the
structure that two or more independent runs agree on.

### 6.2 Why vote at all (why 1 isn't enough on small catalogues)

Because *producing a plan* and *producing the right plan* are different things. A
single run always returns **a** plan — but you have no way to know whether *this*
run was the good one or the unlucky one. With three runs the disagreement itself
is the signal: the majority structure is trustworthy, the outlier is caught and
discarded. One run gives you an answer with no second opinion; three give you a
self-checking answer. On small or ambiguous catalogues — where a single missed
link or wrong business key is both likely and costly — that insurance is cheap
and worth buying.

### 6.3 Why drop to 1 above 15 tables

Three reasons, all pointing the same way:

1. **The cost of the safety net explodes exactly when the catalogue is big.**
   3 votes = 3× the LLM calls and 3× the tokens. A large catalogue is *already*
   split into several batches (§4.2); voting 3× on *every* batch multiplies into a
   large fan-out that overruns the Azure TPM/RPM quota (429s), slows the run, and
   inflates cost. The insurance premium grows fastest precisely where you can
   least afford it.

2. **The benefit mostly disappears anyway.** The modeller runs on **gpt-4o at
   temperature 0** (§4.1), which is *near-deterministic* — the three samples tend
   to come back almost identical, so the vote frequently has nothing to choose
   between. You would pay 3× for little or no error correction.

3. **Other guardrails already cover large runs.** Tolerant coercion repairs
   malformed output, adaptive splitting recovers truncated batches (§4.8), the
   emitter is deterministic, and a separate **plan-reviewer** (a second, stronger
   model) critiques and patches the plan. A single-sample large run is therefore
   not unprotected — voting is the *one* layer that is dropped, not all of them.

### 6.4 The actual impact on YAML quality

| Catalogue size | Voting | Quality effect |
|----------------|--------|----------------|
| ≤ 15 tables | **3 + vote** | Slightly higher accuracy and run-to-run consistency: random one-off mistakes (a missed link, a weak business key) get out-voted. Cheap to afford here. |
| > 15 tables | **1, no vote** | Slightly more *per-table variance*: a single bad sample on one table is no longer caught by a majority. The risk is small in practice — gpt-4o at temp 0 is near-deterministic, and coercion + the reviewer + adaptive split absorb most problems. |

So turning voting off does **not** make the YAML structurally wrong — it removes
one statistical safety margin. The expected outcome is "almost always the same as
with voting", with a slightly higher chance that an individual table on a very
large catalogue carries a sub-optimal modelling choice that a majority vote would
otherwise have corrected.

### 6.5 One-line summary

Three votes buy insurance against the LLM's randomness — worth it while it's cheap
(small catalogues). On large catalogues the premium explodes (3× the already-large
fan-out), the payout shrinks (temp-0 gpt-4o barely varies), and other guardrails
already cover the risk — so voting is traded away for speed and stability,
accepting a small, well-covered increase in per-table variance. This is the
quality side of the same speed/stability/cost trade-off that drives every other
lever in this document.

---

## 7. Before/after wall-time model

A rough mental model for a ~50-table catalogue (illustrative, not benchmarked):

**phase-b (slow):**

```
wall ≈ serial_describe(50 tables)
     + 3 × RTT( gpt-5, ONE 50-table prompt → huge JSON )
     + (high probability) total failure on truncation → wasted minutes
```

Linear in tables for describe, 3× for sequential voting, on the slowest model,
with a large failure tail.

**current (fast):**

```
wall ≈ parallel_describe(50 tables, 8-way)
     + ~1 × RTT( gpt-4o, ONE 25-table batch )      # batches run concurrently,
                                                    # large catalog ⇒ 1 sample
     + near-zero failure tail                       # token bucket + clamp +
                                                    # adaptive split recover instead of failing
```

The dominant term drops from `3 × RTT(gpt-5, all-50)` to roughly
`1 × RTT(gpt-4o, 25)`, the describe term shrinks ~8×, and the failure tail (the
worst part of the old experience) is largely removed.

**Which levers help regardless of quota** (the robust core of the speedup):
gpt-4o (§4.1), batching avoiding truncation failures (§4.2), single-sample for
large catalogues = 3× fewer calls (§4.5), budget clamp + adaptive recovery
removing the slow failure/retry paths (§4.7–4.8), and parallel describe (§4.10).
**Which levers add more when the deployment quota allows:** concurrent batches
and samples (§4.3–4.4), unlocked safely by the rate-limit gates (§4.6).

---

## 8. Evidence: lever → commit map

Produced with `git log -S "<symbol>" ai/phase-b-agents-ui..ai/plan-review-modelling -- dbt_builder`:

| Symbol / identifier | Introduced by |
|---------------------|---------------|
| `sample_parallelism` | `13d2e59` |
| `batch_parallelism` | `13d2e59` |
| `_propose_batched` | `13d2e59` |
| `_TokenBucket` | `13d2e59` |
| `large_catalog_threshold` | `13d2e59` |
| `catalog_describe_parallelism` / `describe_parallelism` | `fa72397`, `13d2e59` |
| `ThreadPoolExecutor` (modeller/reviewer/catalog) | `13d2e59`, `fa72397`, `f111de2` |
| `_propose_voted_adaptive` | `45a4d29` |
| `modeller_chat_deployment` (gpt-4o) | `13d2e59` |
| `max_completion_tokens` ceiling / budget clamp | `17b2d7c`, `6bac641` |

Phase-b versions confirmed absent: `catalog_inspector.py` in phase-b contained no
`ThreadPoolExecutor`/`parallelism` (serial describe), and `modeller.py` in
phase-b had the sequential `for sample_idx in range(self._samples)` loop with a
single whole-catalogue prompt.

---

## 9. Honest caveats

- **Concurrency is quota-bounded.** The fan-out in §4.3–4.4 only delivers its
  full speedup up to the RPM semaphore (`max_concurrent_llm_calls`) and TPM
  bucket (`llm_tokens_per_minute`). The **code defaults are conservative**
  (`max_concurrent_llm_calls=1`, `llm_tokens_per_minute=30_000`) and are meant to
  be raised per deployment via `DWA_AI_*` env vars to match the real quota; the
  in-code fallback when settings can't load is 16 permits, signalling the intended
  operating point is higher. With the conservative default semaphore, the *robust
  core* levers (§5) still make it significantly faster; the concurrency levers add
  the rest once the quota is opened up.
- **Numbers here are a model, not a benchmark.** The before/after wall-time
  expressions illustrate the asymptotics (serial→parallel, 3×→1×, all-in-one→
  batched); they are not measured timings. If the thesis needs hard figures, run
  both branches against the same catalogue with identical `DWA_AI_*` settings and
  record `PipelineStepResult.duration_ms` (the orchestrator already logs per-step
  seconds).
- **Cross-batch links.** Batching can miss links between tables in different
  batches; this is mitigated by name-union merging and the table-naming
  convention, and is a deliberate latency/completeness trade-off.

---

*Traced from the git history between `ai/phase-b-agents-ui` and
`ai/plan-review-modelling` (50 commits). Commit attributions via `git log -S`
pickaxe. See also [`concepts-and-rationale.md`](./concepts-and-rationale.md) §5.3,
§5.7, §5.8, §5.13 for the conceptual treatment of these mechanisms.*
