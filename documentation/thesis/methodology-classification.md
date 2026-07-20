# Research Methodology — Classification

> **Purpose.** The agreed classification of this thesis's research type, for the
> methodology chapter. These labels are not mutually exclusive — a thesis is
> described by a *stack* across several axes (purpose, approach, design, setting).

## Headline

This is **applied Design Science Research (DSR)**: the contribution is a **built
software artifact** (a multi-agent LLM system for Data Vault automation), evaluated
through **controlled, comparative, benchmarking experiments** using predominantly
**quantitative** metrics, with a light **qualitative** interpretive layer — i.e.
**quantitative-dominant mixed methods**.

One-sentence form for the chapter:

> "Following the Design Science Research paradigm (Hevner et al., 2004; Peffers et
> al., 2007), this work designs, builds, and evaluates a software artifact that
> addresses a real data-engineering problem, using controlled experimental,
> comparative, and benchmarking evaluation."

The six project phases (problem → artifact design → build → evaluate → iterate →
communicate) map directly onto the Peffers et al. (2007) DSR process model.

## Classification across axes

| Axis | Label | Justification |
|---|---|---|
| **Paradigm / purpose** | Design Science Research; development-based; **applied** | The core deliverable is a built artifact solving ExampleCorp's real DWA problem — not basic or theoretical research |
| **Evaluation design** | **Experimental** | Independent variables (learning on/off, retrieval k, arm) are manipulated; dependent variables (entity_f1, correction steps, conformance) are measured; controls used (leave-one-out, seeds, ablation) |
| **Approach** | **Quantitative**, **empirical** | Conclusions rest on measured runs, not reasoning alone |
| **Comparison** | **Comparative**, **benchmarking** | Three-arm comparison (manual / deterministic / full) graded against a gold-standard reference |
| **Blend** | **Mixed methods** (quantitative-dominant) | Small qualitative layer: error-taxonomy analysis and the interpretive "where does the AI add value" characterisation |
| **Setting** | Case-study *flavour* | Applied to specific case systems (ServiceNow, IEC-CIM) at ExampleCorp — not a classic interpretive case study |

## What it is *not* (to pre-empt mislabels)

- **Not simulation research** — the LLM calls and system runs are real, not a
  simulated model of a system.
- **Not a systematic review / meta-analysis** — those study existing literature;
  the literature review here is a *component*, not the research type.
- **Not action / participatory / grounded-theory / purely-qualitative** — there is
  no participant co-design cycle, no qualitative theory-building as the method.

## Anchor references (verify author/year/venue before citing)

- Hevner, March, Park & Ram (2004), *Design Science in Information Systems
  Research*, MIS Quarterly.
- Peffers, Tuunanen, Rothenberger & Chatterjee (2007), *A Design Science Research
  Methodology for Information Systems Research*, JMIS.
- March & Smith (1995); Gregor & Hevner (2013) — for artifact types and positioning.

> **Caveat.** Research-type taxonomies vary by university/department. Confirm your
> program's preferred framing — some headline this as "experimental research" with
> DSR as the wrapper, others require "Design Science Research" explicitly. Both
> descriptions are defensible for this build-and-measure CS/IS thesis.
