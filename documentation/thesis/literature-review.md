# Literature Review — Directions, Scope, and Selected Papers

> **What this file is.** A complete starter kit for the literature review: (1) how to
> actually do one, (2) the concepts your review must cover, (3) a ready shortlist of
> **20 verified papers** (pick your ≥18) with venue, rank, and — crucially — which of
> your **research questions / hypotheses / evaluation metrics** each one supports, and
> (4) what to exclude and how to write it up. Companion file: `literature-review-scope.md`
> (the paste-ready search strings per theme).
>
> **Sourcing rules honoured throughout:** papers come from **DBLP** (real
> conference/journal venues only — **no arXiv/CoRR**), AI/ML/LLM/RAG papers are
> **2023–2026**, and every citation below was **venue-verified while preparing this
> list**. You must still confirm each on DBLP yourself before citing.

---

## Part 1 — How to do a literature review (start here)

A literature review is **an argument, not a pile of summaries.** You survey the field,
group papers into themes, say what each theme established, and build toward the **gap
your thesis fills**. Every paper you keep earns its place by supporting one sentence of
that argument.

**The funnel — repeat per theme:**

1. **Search** the theme's strings (from `literature-review-scope.md`) on DBLP. You get
   candidates.
2. **Screen** on *title + abstract* against the theme's question. Most candidates die
   here — that's normal.
3. **Rank-check** the venue (mechanics below).
4. **Read** the survivors (intro, method, results, conclusion — rarely every equation).
5. **Extract** one row into your tracking table.

**The three tools — exactly how to use each:**

- **DBLP** (`dblp.org/search`) — *find the paper.* DBLP shows every version with its
  **venue**. **This is your arXiv filter:** arXiv preprints appear under the venue
  **"CoRR"** (e.g. *"CoRR abs/2312.10997"*). **If the only DBLP entry is CoRR, reject
  the paper.** If it *also* appears at a conference/journal, cite that version.
- **Scimago** (`scimagojr.com/journalrank.php`) — *rank a journal.* Search the journal
  name, read the **quartile Q1–Q4** (Q1 best). Journals only.
- **CORE** (`portal.core.edu.au/conf-ranks/`) — *rank a conference.* Search the acronym,
  read **A\* > A > B > C**. Conferences only. (A few new venues, e.g. COLM, are not yet
  ranked — say so, don't guess.)

**Target:** prefer **CORE A\*/A** and **SJR Q1/Q2**. For the niche Data-Vault theme
(§B) strong academic venues barely exist — a B conference or a book is acceptable there,
and the scarcity is a point you *make* (motivation), not one you apologise for.

**The tracking table (build it as you read — it becomes the review's skeleton):**

| # | Theme | Citation (authors, title, **venue**, year) | Rank (CORE/SJR) | One-line relevance to your RQ |
|---|---|---|---|---|

---

## Part 2 — Scope: the concepts your review must cover

Seven themes, mapped to your research questions. You do not need equal depth in each —
weight toward the ones closest to your contribution (B Data Vault, C agents, F
evaluation).

| Theme | Covers | Supports |
|---|---|---|
| **A. Data-Warehouse Automation** | metadata/model-driven DW & ETL generation; where automation stops | Intro / motivation |
| **B. Data Vault 2.0 modelling** | hub/link/satellite; DV automation; the under-researched gap | RQ1 (the target methodology) |
| **C. LLM structured generation & multi-agent systems** | LLMs emitting valid structured/DB artifacts; agents; generator–critic loops | RQ1, H1a, H1d |
| **D. Retrieval-augmented & in-context / feedback learning** | RAG; example selection; learning from human/approval signal | RQ1, H1c |
| **E. Schema matching, evolution & drift** | schema change detection; impact classification | RQ2, H2a–H2c |
| **F. Evaluating LLM output (no gold, LLM-as-judge, agreement)** | reference-free eval; hallucination; inter-rater reliability | Evaluation chapter; §2.1, §2.6, §2.9 |
| **G. Design Science Research methodology** | DSR process, artifact evaluation | Methodology chapter; whole-thesis frame |

---

## Part 3 — Recommended papers (20 verified — pick your ≥18)

**How to read the table.** Every AI/ML/LLM/RAG row is **2023–2024, at a real venue,
verified.** The older rows are the ones where recency is *not* expected — schema-matching
lineage, inter-rater statistics, and DSR methodology, whose foundations are supposed to
be older. The **"Directly links to"** column ties each paper to your own RQs, hypotheses,
and evaluation metrics; **★★ = maps onto a specific mechanism of your system**, **★ = a
core theme anchor**.

| # | Theme | Paper (verify on DBLP) | Venue / Rank | Year | Directly links to |
|---|---|---|---|---|---|
| 1 | A DWA | Mazón & Trujillo, *An MDA approach for the development of data warehouses* | *Decision Support Systems* / **Q1** | 2008 | Motivation: DW automation exists, DV modelling barely automated |
| 2 | B Data Vault | Giebler, Gröger, Hoos, Schwarz & Mitschang, *Modeling Data Lakes with Data Vault* | ER / **CORE A** | 2019 | **★ RQ1** — the DV2 methodology your system generates |
| 3 | C structured gen | Pourreza & Rafiei, *DIN-SQL: Decomposed In-Context Learning of Text-to-SQL with Self-Correction* | NeurIPS / **A\*** | 2023 | **★ RQ1 / H1a** — LLM emits valid DB artifacts + a self-correction step |
| 4 | C structured gen | Li et al., *BIRD: Can LLM Already Serve as a Database Interface?* | NeurIPS D&B / **A\*** | 2023 | RQ1 — LLMs on real database-grounded generation |
| 5 | D example selection | Gao et al., *Text-to-SQL Empowered by LLMs: A Benchmark Evaluation* (DAIL-SQL) | *PVLDB* / **A\*** | 2024 | **H1c** — which retrieved examples help generation |
| 6 | C multi-agent | Hong et al., *MetaGPT: Meta Programming for a Multi-Agent Collaborative Framework* | ICLR / **A\*** | 2024 | **★ RQ1** — the multi-agent pipeline architecture |
| 7 | C multi-agent | Qian et al., *ChatDev: Communicative Agents for Software Development* | ACL / **A\*** | 2024 | RQ1 — communicating agents produce software artifacts |
| 8 | C generator–critic | Madaan et al., *Self-Refine: Iterative Refinement with Self-Feedback* | NeurIPS / **A\*** | 2023 | **★★ H1d** — the plan-reviewer / generator–critic stage |
| 9 | C self-critique | Shinn et al., *Reflexion: Language Agents with Verbal Reinforcement Learning* | NeurIPS / **A\*** | 2023 | **H1d** — self-critique / verbal correction |
| 10 | C multi-agent | Guo et al., *LLM based Multi-Agents: A Survey of Progress and Challenges* | IJCAI / **A\*** | 2024 | RQ1 — related-work framing for the multi-agent design |
| 11 | D RAG + critique | Asai et al., *Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection* | ICLR (Oral) / **A\*** | 2024 | **★★ RQ1 / H1c+H1d** — retrieval **and** a self-critique step = your exact design |
| 12 | C sample voting | Wang et al., *Self-Consistency Improves Chain-of-Thought Reasoning* | ICLR / **A\*** | 2023 | **★ H1a + Self-Consistency metric (§2.2)** — your modeller's sample-and-vote |
| 13 | D feedback learning | Rafailov et al., *Direct Preference Optimization* (DPO) | NeurIPS / **A\*** | 2023 | **H1c** — learning from approved/preferred decisions |
| 14 | F evaluation | Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena* | NeurIPS D&B / **A\*** | 2023 | **★★ Evaluation** — the independent-annotator idea (§2.9) |
| 15 | F evaluation | Liu et al., *G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment* | EMNLP / **A\*** | 2023 | **★ Evaluation methodology** — LLM-based scoring of output |
| 16 | F hallucination | Ji et al., *Survey of Hallucination in Natural Language Generation* | *ACM Computing Surveys* / **Q1** | 2023 | **★ Grounding / hallucination metric (§2.1)** |
| 17 | E schema/drift | Rahm & Bernstein, *A Survey of Approaches to Automatic Schema Matching* | *VLDB Journal* / **Q1** | 2001 | **★ RQ2** — the deterministic matching/drift foundation |
| 18 | F inter-rater | Cohen, *A Coefficient of Agreement for Nominal Scales* | *Educ. & Psych. Measurement* / **Q1** | 1960 | **★ Cohen's κ metric (§2.6, §2.9)** |
| 19 | G methodology | Hevner, March, Park & Ram, *Design Science in Information Systems Research* | *MIS Quarterly* / **Q1** | 2004 | **★ Whole-thesis methodology frame** |
| 20 | G methodology | Peffers et al., *A Design Science Research Methodology for IS* | *JMIS* / **Q1** | 2007 | Methodology — the DSRM process you followed |

**That is 20 — already ≥18.** All are peer-reviewed at real venues and heavily cited.

**Swap-ins / extras (all verified) if you want to reach 22–24 or rebalance:**
- **Li et al., *Ditto: Deep Entity Matching with Pre-Trained Language Models*, *PVLDB* 2020 (A\*)** — **H2b** (language models classifying structural matches; note: 2020, a data-management theme, not a "recent LLM" paper).
- **Tuunanen, Winter & vom Brocke, *Design Echelons*, *MIS Quarterly* 2024 (Q1)** — a **recent** DSR methodology anchor (pairs with Hevner/Peffers for currency).
- **Romero, Simitsis & Abelló, *GEM: Requirement-Driven Generation of ETL…*, DaWaK 2011** — Theme A depth.
- **Landis & Koch, *…Observer Agreement for Categorical Data*, *Biometrics* 1977 (Q1)** — the κ interpretation bands (0.81–1.00 = "almost perfect") you quote in §2.9.

---

## Part 4 — Papers to EXCLUDE (common arXiv-only traps)

These are famous and tempting, but **DBLP lists them only as CoRR (arXiv)** → they fail
your rule. Verified during preparation:

- **Chen et al. (2021), *Evaluating LLMs Trained on Code* (Codex/HumanEval)** — CoRR-only.
  Use **DIN-SQL / BIRD** for the code/DB-generation angle instead.
- **Gao et al. (2023/24), *Retrieval-Augmented Generation for LLMs: A Survey*** —
  CoRR-only (*abs/2312.10997*). Use **Self-RAG** for the RAG anchor instead.

Also **cite-once-for-lineage only** (do not count toward the 18; one sentence each, then
move to the 2023–2024 work): Vaswani et al. 2017 (transformer), Brown et al. 2020
(GPT-3), Lewis et al. 2020 (RAG origin), Yao et al. 2023 (ReAct), Ouyang et al. 2022
(InstructGPT).

---

## Part 5 — How to write it up

Flow broad → specific → gap:

1. **Problem space** (A, B) — DW automation exists, but Data Vault modelling is largely
   manual and under-researched *(papers 1, 2)*.
2. **Enabling technology** (C, D) — LLMs generate valid structured artifacts, act as
   multi-agent systems with generator–critic loops, and learn from retrieved examples
   *(papers 3–13)*.
3. **The second use case** (E) — schema matching / drift detection *(paper 17)*.
4. **Evaluating it honestly** (F) — grading generated artifacts without a full gold
   standard; LLM-as-judge; hallucination; inter-rater reliability *(papers 14–16, 18)*.
5. **How the study is framed** (G) — Design Science Research *(papers 19–20)*.

**Gap statement to build toward:** *prior work automates parts of data-warehouse
construction and shows LLMs can generate structured artifacts and act as multi-agent,
retrieval-augmented, self-critiquing systems — but no prior work combines a multi-agent
LLM pipeline with an approval-driven feedback loop to generate and maintain Data Vault
2.0 models, nor evaluates such a system's accuracy, learning behaviour, drift handling,
and human-effort trade-offs against manual and rule-based baselines.*

---

## Part 6 — Verify-yourself checklist (do this for every paper before citing)

- [ ] It appears on **DBLP at a conference/journal** (not only "CoRR").
- [ ] Authors, title, year, venue copied from DBLP (not from memory or this file).
- [ ] Venue rank looked up: **CORE** (conference) or **Scimago** (journal).
- [ ] AI/ML/LLM/RAG paper is **2023–2026** (Theme C/D/F LLM rows); older is fine only for
      E-matching lineage, F-statistics (Cohen), and G-methodology.
- [ ] One sentence written linking it to a specific **RQ / hypothesis / metric**.

> **Integrity note.** Every citation in Part 3/4 was venue-checked against DBLP or the
> official proceedings while this file was prepared, and none is an arXiv-only paper. But
> confirm each yourself — that is standard practice and your final guard against any
> transcription slip. When your final set is chosen, hand it back and I will synthesise
> the papers into the written review, grouped by theme and positioned against your
> contribution.

---

## Part 7 — Dissertation-ready reference table (paste this)

*RQ/hypothesis labels are the **reframed** ones (`RQ-Hypothesis.md`): RQ1 = accuracy +
feedback (H1a–H1d), RQ2 = drift detection + impact (H2a–H2c), RQ3 = safety + governance +
effort (H3a–H3c). Confirm each venue/rank on DBLP + CORE/Scimago before submitting.*

| Theme | Paper | First author | Venue | Year | Rank | Supports | Reason for inclusion |
|---|---|---|---|---|---|---|---|
| Data-warehouse automation | An MDA Approach for the Development of Data Warehouses | Mazón | Decision Support Systems | 2008 | SJR Q1 | RQ1 (context) | Shows warehouse/ETL design can be model-driven and automated, but through fixed rules — the baseline the thesis extends to Data Vault with LLMs. |
| Data Vault modelling | Modeling Data Lakes with Data Vault | Giebler | ER (Conceptual Modeling) | 2019 | CORE A | RQ1 | A rare peer-reviewed Data Vault paper; grounds the target methodology and evidences that DV *automation* is essentially unstudied. |
| LLM structured generation | DIN-SQL: Decomposed In-Context Learning of Text-to-SQL with Self-Correction | Pourreza | NeurIPS | 2023 | CORE A\* | RQ1 / H1a | An LLM producing valid structured database artifacts with a self-correction step — the technical basis for generating and checking DV YAML. |
| LLM structured generation | Can LLM Already Serve as a Database Interface? (BIRD) | Li | NeurIPS (D&B) | 2023 | CORE A\* | RQ1 | Benchmarks LLMs on large, real database-grounded generation, motivating schema-grounded rather than free-text generation. |
| In-context example selection | Text-to-SQL Empowered by LLMs (DAIL-SQL) | Gao | PVLDB | 2024 | CORE A\* | RQ1 / H1c | Shows which retrieved examples most help LLM generation — directly relevant to the approved-decisions feedback index. |
| Multi-agent systems | MetaGPT: Meta Programming for a Multi-Agent Collaborative Framework | Hong | ICLR | 2024 | CORE A\* | RQ1 | Role-specialised multi-agent "software company" — the closest published analogue of the thesis's multi-agent pipeline. |
| Multi-agent systems | ChatDev: Communicative Agents for Software Development | Qian | ACL | 2024 | CORE A\* | RQ1 | Communicating agents build software artifacts through structured roles, supporting the agent-collaboration design. |
| Generator–critic | Self-Refine: Iterative Refinement with Self-Feedback | Madaan | NeurIPS | 2023 | CORE A\* | RQ1 / H1d | The generate-then-critique pattern the plan-reviewer implements; frames H1d (reviewer as refinement, not a scalar gain). |
| Self-critique agents | Reflexion: Language Agents with Verbal Reinforcement Learning | Shinn | NeurIPS | 2023 | CORE A\* | RQ1 / H1d | Agents that verbally critique and correct their own output — support for the reviewer / self-correction step. |
| Multi-agent survey | LLM based Multi-Agents: A Survey of Progress and Challenges | Guo | IJCAI | 2024 | CORE A\* | RQ1 | Recent survey mapping multi-agent LLM progress and open challenges — anchors the related-work framing. |
| RAG + self-critique | Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection | Asai | ICLR (Oral) | 2024 | CORE A\* | RQ1 / H1c, H1d | Retrieval combined with a self-critique step — the single closest match to the thesis's retrieve–generate–review design. |
| Sampling and voting | Self-Consistency Improves Chain-of-Thought Reasoning | Wang | ICLR | 2023 | CORE A\* | RQ1 / H1a | Sample-many-then-vote — the mechanism behind the modeller's majority vote and the self-consistency reliability metric. |
| Learning from feedback | Direct Preference Optimization (DPO) | Rafailov | NeurIPS | 2023 | CORE A\* | RQ1 / H1c | Learning from human-preferred outputs — the conceptual parent of treating approved decisions as a learning signal. |
| Evaluating LLM output | Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena | Zheng | NeurIPS (D&B) | 2023 | CORE A\* | Evaluation (all RQs) | Establishes using an independent LLM to assess generated output — basis for the thesis's independent-annotator evaluation. |
| Evaluating LLM output | G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment | Liu | EMNLP | 2023 | CORE A\* | Evaluation | LLM-based scoring of generated text — supports the reference-free (no full gold) evaluation methodology. |
| Hallucination / grounding | Survey of Hallucination in Natural Language Generation | Ji | ACM Computing Surveys | 2023 | SJR Q1 | Evaluation / RQ3 | The reference survey on the failure mode the grounding metric measures and the guardrails prevent. |
| Schema matching / drift | A Survey of Approaches to Automatic Schema Matching | Rahm | VLDB Journal | 2001 | SJR Q1 | RQ2 / H2a | The classic foundation for deterministic schema comparison — grounds the drift-detection engine. |
| Inter-rater reliability | A Coefficient of Agreement for Nominal Scales | Cohen | Educational and Psychological Measurement | 1960 | SJR Q1 | Evaluation | Defines Cohen's κ, the agreement statistic used for gold-set reliability and impact-label agreement. |
| Research methodology | Design Science in Information Systems Research | Hevner | MIS Quarterly | 2004 | SJR Q1 | Methodology (all RQs) | The foundational Design Science Research guidelines the thesis's method follows. |
| Research methodology | A Design Science Research Methodology for Information Systems Research | Peffers | Journal of Management Information Systems | 2007 | SJR Q1 | Methodology | The DSRM process model that structures the build-and-evaluate cycle. |

**Count: 20 papers** — all peer-reviewed, non-arXiv, and (for the AI/ML/LLM/RAG rows)
2023–2024. Optional depth swap-ins (also verified): Ditto (Li, PVLDB 2020 — H2b),
Design Echelons (Tuunanen, MIS Quarterly 2024 — recent methodology), Landis & Koch
(Biometrics 1977 — the κ interpretation bands).

---

## Part 8 — The research gap this thesis fills (paste-ready)

*Written as continuous prose for direct use in the dissertation.*

Research on automating the data warehouse is not new. Model-driven and metadata-driven
approaches have long been able to generate parts of a warehouse — ETL routines,
multidimensional designs, and staging logic — from higher-level models rather than by
hand (Mazón and Trujillo, 2008). These approaches, however, are rule- and template-based:
they follow fixed transformations and do not reason about ambiguous or messy source
schemas the way a human modeller does. When we narrow the focus to Data Vault 2.0, the
methodology this thesis targets, the picture is thinner still. The peer-reviewed
literature treats Data Vault mainly as a modelling and architecture question (Giebler et
al., 2019); there is almost no academic work on *automatically generating* Data Vault
metadata, and none that does so from a live, operational warehouse schema. This is the
first part of the gap: automation stops short of Data Vault, and what little exists is
not driven by the kind of flexible reasoning that real source systems demand.

At the same time, large language models have shown that they can produce valid,
structured artifacts directly from a schema or a natural-language request. Recent work on
text-to-SQL demonstrates LLMs generating correct, executable database queries, including
approaches that decompose the task and correct their own mistakes (Pourreza and Rafiei,
2023) and that are benchmarked on large, realistic databases (Li et al., 2023). A
parallel line of work shows that several LLM agents can collaborate — taking on
specialised roles such as analyst, engineer, and reviewer — to build software artifacts
together (Hong et al., 2024; Qian et al., 2024; Guo et al., 2024), and that a model can
improve its own output by critiquing and refining it, sometimes while also retrieving
supporting examples (Madaan et al., 2023; Shinn et al., 2023; Asai et al., 2024). These
results are the technical foundation the thesis builds on. But they were developed for a
different job: generating ad-hoc queries or greenfield code, not producing and
maintaining a *governed, versioned metadata contract* that a production pipeline depends
on. Their notion of "learning" is also internal to the model — self-critique, or tuning
on preference data (Rafailov et al., 2023) — rather than learning from the concrete
approvals of a human expert. The mechanism of feeding *approved* decisions back into a
retrieval index so that later runs imitate them, and the question of *when* that actually
helps, is left open. In-context learning research tells us which examples are useful in
general (Gao et al., 2024), but not how an approval-driven corpus behaves for
data-model generation specifically.

The second use case — keeping the generated metadata correct as source schemas change —
sits on a similarly split literature. Detecting structural differences between two
schemas is a mature, well-understood, and deterministic problem (Rahm and Bernstein,
2001). Judging the *meaning* of a change — whether adding, renaming, or retyping a column
is harmless or will break a downstream Data Vault model — is exactly the kind of semantic
judgement LLMs are now good at. Yet the two have not been brought together in a way that
keeps the safety guarantees a production system needs: a design in which detection stays
fully deterministic (so nothing is missed), an LLM only *explains and classifies* the
impact, and a breaking change is never applied automatically regardless of how confident
the model or the reviewer is. Existing multi-agent and refactoring systems change
artifacts autonomously; they do not enforce this "detect deterministically, reason with
AI, but never auto-apply a breaking change" boundary.

Finally, there is the problem of *evaluating* a system like this honestly. Methods now
exist to use an LLM as a judge of generated output (Zheng et al., 2023; Liu et al.,
2023), to reason about the fabrication or "hallucination" failure mode (Ji et al., 2023),
and to measure agreement between annotators (Cohen, 1960). But there is no established,
reference-free way to grade LLM-generated *data-model metadata* when no full gold standard
exists — one that separates entity identification from naming and from over-linking,
checks that every generated reference is grounded in the real source, and reports its
numbers with proper measures of stability and agreement rather than a single flattering
score. Without such an evaluation, claims about accuracy and about the value of a feedback
loop cannot be trusted.

Taken together, these strands leave a specific gap that this thesis fills. No prior work
combines, in one governed system: (1) a multi-agent LLM pipeline that generates Data
Vault 2.0 metadata grounded in a live warehouse schema, so the model cannot invent tables
or columns that do not exist; (2) an approval-driven feedback loop in which human expert
approvals become the retrieval corpus that shapes future generations, together with an
honest account of the narrow conditions under which that loop actually improves quality;
(3) a schema-evolution workflow that pairs fully deterministic drift detection with an LLM
impact classifier under a hard rule that breaking changes are surfaced for human decision
and never auto-applied; and (4) a reproducible, gold-free evaluation of the whole system's
accuracy, learning behaviour, drift handling, safety, and human-effort trade-offs against
manual and rule-based baselines. Each individual ingredient exists in the literature; what
is missing — and what this thesis contributes — is their combination into a single,
grounded, auditable metadata-lifecycle system, and a careful, honest measurement of where
that combination genuinely helps and where it does not.
