# Literature Review — Scope and Search Strategy

> **Purpose.** A themed map of what the literature review must cover, with
> paste-ready search strings, the target venues per theme (so you can judge
> ranking), and a small set of anchor references to verify. You search and select
> the papers manually; once you hand them to me I synthesise them into the review.

## What a literature review actually is (read this first)

A literature review is **not** a pile of paper summaries. It is an *argument*: you
survey what has been done, group it into themes, show what each theme established, and
then point at the **gap** your thesis fills. Every paper you keep is there to support
one sentence of that argument. Aim for **10–16 papers total** — depth over breadth; a
tight, well-chosen set reads better than a scattershot 40.

**The funnel — how you get from a search box to a kept paper:**

1. **Search** a theme's strings on DBLP (below). This gives you *candidates*.
2. **Screen on title + abstract** against the theme's "what to look for". Discard
   anything only loosely related. Most candidates die here — that is normal.
3. **Check the venue's rank** (mechanics below). Prefer higher-ranked venues.
4. **Read** the survivors properly (intro, method, results, conclusion — you rarely
   need every equation).
5. **Extract** one row into your tracking table (citation, venue, rank, year, the
   *one sentence* of relevance to your RQ, and which theme).

Do this theme by theme (§1–§9). You do **not** need a paper from every theme; pick the
strongest 10–16 across all of them, weighted toward the themes closest to your
contribution (§2 Data Vault, §4 agents, §8 evaluation).

## The three tools, and exactly how to use each

**1. DBLP — find the papers.** Go to <https://dblp.org/search> and paste a search
string. DBLP lists every version of a paper with its **venue**. This is where the
**"no arXiv" rule bites**: DBLP shows arXiv preprints under the venue **"CoRR"**
(e.g. *"CoRR abs/2107.03374"*). **A paper is only acceptable if DBLP shows it at a
real conference or journal** (NeurIPS, ACL, VLDB, *Decision Support Systems*, …). If
the *only* DBLP entry is CoRR, the paper is arXiv-only — **reject it**. Many famous
papers are published *both* on arXiv and at a conference; use the conference version's
citation, not the arXiv one.

**2. Scimago (SJR) — rank the journals.** Go to
<https://www.scimagojr.com/journalrank.php> and search the **journal** name. Read the
**quartile (Q1–Q4)** — Q1 is best. Use this only for *journal* papers (e.g. *MIS
Quarterly*, *VLDB Journal*, *Data & Knowledge Engineering*).

**3. CORE — rank the conferences.** Go to
<https://portal.core.edu.au/conf-ranks/> and search the **conference** name or acronym.
Read the rank: **A\* (top) > A > B > C**. Use this for *conference* papers (NeurIPS,
ACL, ICLR, VLDB, SIGMOD, ER, DaWaK, DOLAP, DESRIST…). Note a few very new venues (e.g.
**COLM**, first held 2024) are **not yet CORE-ranked** — say so rather than guessing.

**Rule of thumb:** prefer **CORE A\*/A** and **SJR Q1/Q2**. For the niche Data-Vault
theme (§2) high-ranked academic venues are scarce — a CORE **B** conference or a
practitioner book is acceptable there, and the scarcity is itself a point you make.

## The tracking table (build this as you go — it becomes the review's backbone)

| # | Theme | Citation (authors, title, **venue**, year) | Rank (CORE / SJR) | One-line relevance to your RQ |
|---|---|---|---|---|

Fill one row per kept paper. When you hand me this table (or the PDFs), I group the
papers by theme, summarise each, and position them against your contribution.

> **Integrity note.** The suggested references below are **real papers whose venue I
> verified** (against DBLP / the venue's proceedings) while preparing this list, or
> long-established works I can name with confidence. You must still **confirm every one
> on DBLP yourself** — check the author list, year, and that a non-CoRR venue exists —
> before citing. That is standard practice and it is also your arXiv filter. Where a
> sub-area moves fast I add **search strings** so you can find the current best paper
> rather than anchoring on one I name.

---

## §1 — Data Warehouse Automation (DWA) & metadata-driven generation

**Role.** Positions the whole thesis; establishes what DWA tools/approaches exist
and the automation gap the artifact addresses. (Intro + related work.)

**What to look for.** Metadata-driven / template-driven warehouse generation;
model-driven data warehousing; automated ETL/ELT code generation; dbt-style
transformation frameworks; how much of DW build is automated vs manual.

**Search strings.**
- `"data warehouse automation"`
- `"metadata-driven" ("data warehouse" OR "ETL" OR "ELT")`
- `"model-driven" "data warehouse" generation`
- `"automated ETL" OR "ETL generation" data warehouse`
- `dbt "data build tool" transformation analytics engineering`

**Target venues.** DOLAP, DaWaK, ER (conceptual modeling), *Information Systems*,
*Data & Knowledge Engineering (DKE)*, *Decision Support Systems*; VLDB/SIGMOD/ICDE
for the heavier systems work.

**Suggested papers (confirm on DBLP).**
- **Mazón & Trujillo, "An MDA approach for the development of data warehouses",
  *Decision Support Systems*, 2008** — model-driven DW generation; journal, check SJR
  (DSS is Q1).
- **Romero, Simitsis & Abelló, "GEM: Requirement-Driven Generation of ETL and
  Multidimensional Conceptual Designs", *DaWaK*, 2011** — automated ETL + design
  generation; conference (DaWaK, CORE ~B/C).
- *Books for contrast (not DBLP, cite as foundational):* Kimball & Ross, *The Data
  Warehouse Toolkit*; Inmon, *Building the Data Warehouse*.
- *Also search* `"automatic generation" "ETL" conceptual model` for Muñoz/Mazón/Trujillo
  (DOLAP 2009).

---

## §2 — Data Vault 2.0 modelling and its automation

**Role.** The target methodology the artifact generates (RQ1, RQ2). Core domain.

**What to look for.** Data Vault methodology (hub/link/satellite; business keys;
hash keys); Data Vault vs dimensional/3NF; **automation of Data Vault modelling**;
ensemble/agile modelling; generators like AutomateDV/dbtvault. **Note the gap:**
peer-reviewed academic DV literature is thin — expect to lean on books/practitioner
sources and to explicitly frame "little prior work automates DV modelling" as a
motivation.

**Search strings.**
- `"Data Vault 2.0"`
- `"Data Vault" ("hub" "link" "satellite") data warehouse modeling`
- `"Data Vault" automation OR generation OR automating`
- `"Data Vault" ("business key" OR "hash key") modeling`
- `AutomateDV OR dbtvault "Data Vault"`

**Target venues.** Books/practitioner + some academic (DaWaK, ER, *Information
Systems*). Low academic coverage is itself a finding.

**Suggested papers (confirm on DBLP).**
- **Giebler, Gröger, Hoos, Schwarz & Mitschang, "Modeling Data Lakes with Data Vault:
  Practical Experiences, Assessment, and Lessons Learned", *ER* (Conceptual Modeling),
  2019** — one of the few *peer-reviewed* Data-Vault modelling papers; ER is CORE **A**.
  This is your strongest academic DV anchor.
- **Giebler, Gröger, Hoos, Schwarz & Mitschang, "Leveraging the Data Lake: Current State
  and Challenges", *DaWaK*, 2019** — context for DV in modern lake/warehouse architecture.
- *Book (foundational, not DBLP):* Linstedt & Olschimke (2015), *Building a Scalable Data
  Warehouse with Data Vault 2.0*, Morgan Kaufmann.
- **The point to make:** peer-reviewed DV-*automation* work is essentially absent — that
  scarcity is a motivation for the thesis, not a weakness of the review.

---

## §3 — LLMs for structured / code / schema generation

**Role.** The technical core of RQ1 — can LLMs emit *valid structured artifacts*
(the YAML plan)?

**What to look for.** LLM code generation; structured/JSON/grammar-constrained
output; constrained decoding; **text-to-SQL**; DDL/schema generation from NL or
metadata; reliability of structured output.

**Search strings.**
- `"large language models" "code generation"`
- `"structured output" OR "constrained decoding" language model`
- `"text-to-SQL" ("large language model" OR "LLM")`
- `LLM ("schema generation" OR "DDL generation" OR "metadata generation")`
- `"JSON" ("grammar" OR "constrained") "language model" generation`

**Target venues.** ACL, EMNLP, NAACL, NeurIPS, ICLR (NLP/ML); ICSE, FSE/ESEC, ASE
(software); VLDB, SIGMOD (text-to-SQL/DB). All CORE A\*/A.

**Suggested papers (confirm on DBLP).**
- **Vaswani et al., "Attention Is All You Need", *NeurIPS*, 2017** — the transformer;
  foundational (A\*).
- **Brown et al., "Language Models are Few-Shot Learners" (GPT-3), *NeurIPS*, 2020** —
  few-shot capability; also anchors §5 (A\*).
- **Yu et al., "Spider: A Large-Scale Human-Labeled Dataset for … Text-to-SQL",
  *EMNLP*, 2018** — the text-to-SQL benchmark (A\*).
- **Pourreza & Rafiei, "DIN-SQL: Decomposed In-Context Learning of Text-to-SQL with
  Self-Correction", *NeurIPS*, 2023** — LLM text-to-SQL via decomposition + self-fix;
  close analogue of your structured-generation + reviewer idea (A\*).
- **Li et al., "Can LLM Already Serve as a Database Interface? A Big Bench for
  Large-Scale Database Grounded Text-to-SQLs" (BIRD), *NeurIPS* (Datasets &
  Benchmarks, Spotlight), 2023** — the modern text-to-SQL benchmark; recent, heavily
  cited (A\*).
- **Gao et al., "Text-to-SQL Empowered by Large Language Models: A Benchmark
  Evaluation" (DAIL-SQL), *PVLDB* 17(5), 2024** — prompt/example selection for
  LLM text-to-SQL; recent, DB-venue (A\*).
- *Vaswani/Brown are the seminal lineage — cite once for background; lead with the
  2023–2024 work above.* *(Optional pre-training anchor: Devlin et al., "BERT",
  NAACL 2019, A.)*
- **⚠ EXCLUDE — Chen et al. (2021), "Evaluating Large Language Models Trained on Code"
  (Codex/HumanEval).** Widely cited but **arXiv-only** (DBLP lists it *only* as
  *CoRR abs/2107.03374*) — it fails the no-arXiv rule. Cite the venue-published
  **HumanEval/pass@k** discussion via §8 instead, or use DIN-SQL above.

---

## §4 — LLM agents & multi-agent systems for data engineering

**Role.** The architecture — the "multi-agent" framing and the reviewer
sub-question (RQ1, H1d).

**What to look for.** LLM agents; **multi-agent LLM** orchestration; reasoning +
acting / tool use; agent review/critique loops (generator–critic); LLMs applied to
data integration, wrangling, cleaning, matching.

**Search strings.**
- `"LLM agents" OR "language model agents"`
- `"multi-agent" "large language models" framework`
- `"large language model" ("data integration" OR "data wrangling" OR "data cleaning")`
- `("self-refine" OR "self-critique" OR "reviewer") "language model" generation`
- `"tool use" OR "tool-augmented" language model agents`

**Target venues.** NeurIPS, ICLR, ICML, ACL, EMNLP (all A\*). *(Do not cite the arXiv
versions — find the conference version on DBLP.)*

**Suggested papers (confirm on DBLP).**
- **Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models", *ICLR*,
  2023** — reasoning + tool use (A\*).
- **Wei et al., "Chain-of-Thought Prompting Elicits Reasoning in LLMs", *NeurIPS*,
  2022** (A\*).
- **Wang et al., "Self-Consistency Improves Chain-of-Thought Reasoning in Language
  Models", *ICLR*, 2023** — directly relates to your sample-and-vote modeller (A\*).
- **Madaan et al., "Self-Refine: Iterative Refinement with Self-Feedback", *NeurIPS*,
  2023** — the generator–critic idea; anchors your reviewer sub-question H1d (A\*).
- **Shinn et al., "Reflexion: Language Agents with Verbal Reinforcement Learning",
  *NeurIPS*, 2023** — self-critique agents (A\*).
- **Hong et al., "MetaGPT: Meta Programming for a Multi-Agent Collaborative Framework",
  *ICLR*, 2024** — a multi-agent "software company" (PM/architect/engineer roles); the
  closest published analogue to your multi-agent pipeline, recent and high-impact (A\*).
- **Qian et al., "ChatDev: Communicative Agents for Software Development", *ACL*, 2024**
  — communicating agents that build software; recent, directly on your architecture (A\*).
- **Wu et al., "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation",
  *COLM*, 2024** — multi-agent framework. ⚠ COLM is a *real peer-reviewed venue* (in DBLP)
  but **new (2024) and not yet CORE-ranked** — say so; use it as a multi-agent anchor,
  not as a "high-ranked" citation.

- **Guo et al., "Large Language Model based Multi-Agents: A Survey of Progress and
  Challenges", *IJCAI*, 2024** — a recent multi-agent *survey* at a top venue (A\*);
  a survey is ideal for a related-work section and gets cited quickly.

*Lead with MetaGPT/ChatDev/Reflexion/Self-Refine (all 2023–2024). Cite ReAct/CoT once
for lineage.*

---

## §5 — Retrieval-augmented generation & in-context / few-shot learning

**Role.** The feedback-learning mechanism (RQ1, H1c — retrieval of approved
examples into the prompt).

**What to look for.** RAG; in-context learning; few-shot prompting; **demonstration
/ example selection** for in-context learning; retrieval for code; how many/which
examples matter (directly relevant to your k-threshold finding).

**Search strings.**
- `"retrieval-augmented generation"`
- `"in-context learning" "large language models"`
- `"few-shot" ("prompting" OR "learning") language model`
- `"demonstration selection" OR "example selection" in-context learning`
- `"retrieval augmented" ("code generation" OR "structured")`

**Target venues.** NeurIPS, ICLR, ACL, EMNLP, NAACL, TACL (A\*/A).

**Suggested papers (confirm on DBLP).**
- **Asai et al., "Self-RAG: Learning to Retrieve, Generate, and Critique through
  Self-Reflection", *ICLR* (Oral), 2024** — retrieval **plus a self-critique step**;
  the single closest published match to your retrieval-and-reviewer design, recent and
  high-impact (A\*). *Lead with this one.*
- **Min et al., "Rethinking the Role of Demonstrations: What Makes In-Context Learning
  Work?", *EMNLP*, 2022** — what few-shot examples actually contribute; supports your
  "instance-copying, not generalisation" finding (A\*).
- **Rubin, Herzig & Berant, "Learning to Retrieve Prompts for In-Context Learning",
  *NAACL*, 2022** — *which* examples to retrieve; on your retrieval mechanism (A).
- *Lewis et al. 2020 (NeurIPS, A\*) is the seminal RAG paper — cite once for lineage.*
- **⚠ EXCLUDE — Gao et al. (2023/24), "Retrieval-Augmented Generation for Large Language
  Models: A Survey".** Very widely cited, but **arXiv-only** (DBLP lists it only as
  *CoRR abs/2312.10997*). Do not cite it; use Self-RAG + Lewis instead.
- *For your k-threshold finding, also search* `"number of demonstrations" in-context
  learning`.

---

## §6 — Human-in-the-loop, feedback learning & active learning

**Role.** The approve→learn loop (RQ1, H1c and the longitudinal feedback claim).

**What to look for.** Human-in-the-loop ML; **active learning**; learning from human
feedback (RLHF and lighter forms); interactive ML; using approvals/edits as training
signal; feedback loops in deployed ML systems.

**Search strings.**
- `"human-in-the-loop" machine learning`
- `"active learning" survey machine learning`
- `"reinforcement learning from human feedback" OR RLHF`
- `"learning from" ("user feedback" OR "human feedback") ("data" OR "code")`
- `"interactive machine learning"`

**Target venues.** NeurIPS, ICML, ICLR; CHI, IUI, CSCW (human-in-the-loop /
interactive side).

**Suggested papers (confirm on DBLP).**
- **Christiano et al., "Deep Reinforcement Learning from Human Preferences", *NeurIPS*,
  2017** — learning from human preference signal; the conceptual parent of your
  approve→learn loop (A\*).
- **Ouyang et al., "Training Language Models to Follow Instructions with Human Feedback"
  (InstructGPT), *NeurIPS*, 2022** — human feedback as a training signal for LLMs (A\*).
- **Rafailov et al., "Direct Preference Optimization: Your Language Model is Secretly a
  Reward Model" (DPO), *NeurIPS*, 2023** — the recent, simpler alternative to RLHF for
  learning from preferences; high-impact 2023 work (A\*).
- *For active learning:* Settles, *Active Learning Literature Survey* (2009) is a
  **university technical report**, not a DBLP conference/journal entry — if you want a
  citable active-learning venue paper instead, search `"active learning" survey` and
  keep one at a ranked venue (e.g. an *IEEE TKDE* / *ACM Computing Surveys* survey).

---

## §7 — Schema matching, schema evolution & drift detection (Use Case B)

**Role.** RQ2 — deterministic drift detection + AI impact classification.

**What to look for.** Schema matching (the classic problem); **schema evolution**;
schema **change/drift detection**; data contracts; **impact analysis** of schema
change; additive/breaking change classification; LLMs applied to schema
matching/evolution.

**Search strings.**
- `"schema matching" survey`
- `"schema evolution" ("detection" OR "impact" OR "management")`
- `"schema drift" OR "schema change" detection data`
- `"data contract" schema ("breaking change" OR "compatibility")`
- `"large language model" ("schema matching" OR "schema evolution")`

**Target venues.** VLDB, SIGMOD, ICDE, EDBT (A\*/A); *VLDB Journal*, *Information
Systems*, *TKDE* (Q1).

**Suggested papers (confirm on DBLP).**
- **Rahm & Bernstein, "A Survey of Approaches to Automatic Schema Matching", *VLDB
  Journal*, 2001** — the classic schema-matching survey (Q1); frames the deterministic
  side of your drift detection.
- **Li, Li, Suhara, Doan & Tan, "Deep Entity Matching with Pre-Trained Language Models"
  (Ditto), *PVLDB* (Proc. VLDB Endowment), 2020** — language models applied to
  matching; the modern LM-for-schema bridge to your AI impact classifier (A\*).
- *Book (foundational, not DBLP):* Doan, Halevy & Ives, *Principles of Data Integration*.
- *For evolution/drift specifically, search* `"schema evolution" survey` and
  `"data contract" "breaking change" compatibility` and keep one ranked-venue paper.

---

## §8 — Evaluating LLM-generated artifacts (LLM-as-judge, benchmarking, no gold)

**Role.** Your **methodology/evaluation** chapter — how to grade quality without a
full ground truth, and how to justify the metrics used.

**What to look for.** **LLM-as-a-judge**; evaluation of generated code/text;
reference-free / reference-based evaluation; benchmarking LLMs; **inter-rater
reliability** (Cohen's κ) — directly supports your single-annotator-gold limitation
and the recommended second-annotator upgrade.

**Search strings.**
- `"LLM as a judge" OR "LLM-as-a-judge" evaluation`
- `"evaluating" "large language model" outputs benchmark`
- `"reference-free" evaluation ("code generation" OR "natural language generation")`
- `"pass@k" OR "functional correctness" code generation evaluation`
- `"inter-rater reliability" OR "Cohen's kappa" annotation agreement`

**Target venues.** ACL, EMNLP, NeurIPS Datasets & Benchmarks track, TACL.

**Suggested papers (confirm on DBLP).**
- **Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena", *NeurIPS*
  (Datasets & Benchmarks), 2023** — the LLM-as-judge reference; supports your
  independent-annotator idea (A\*).
- **Liu et al., "G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment",
  *EMNLP*, 2023** — using an LLM to score generated output; recent, directly underpins
  your evaluation methodology (A\*).
- **Ji et al., "Survey of Hallucination in Natural Language Generation", *ACM Computing
  Surveys*, 2023** — the reference survey for the failure mode your grounding metric
  measures; recent Q1 journal.
- **Cohen, "A Coefficient of Agreement for Nominal Scales", *Educational and
  Psychological Measurement*, 1960** — Cohen's κ; the basis of your inter-rater metric
  (classic journal; check SJR).
- **Landis & Koch, "The Measurement of Observer Agreement for Categorical Data",
  *Biometrics*, 1977** — the κ interpretation bands (0.81–1.00 = "almost perfect") you
  quote in findings §2.9 (Q1 journal).
- *For code-eval / pass@k without arXiv,* cite the HumanEval discussion via a
  venue-published survey — search `"code generation" evaluation survey` at a ranked
  venue. **Do not** cite Chen et al. 2021 directly (arXiv-only, see §3).

---

## §9 — Design Science Research methodology

**Role.** Foundation for the **methodology chapter** (see
`methodology-classification.md`).

**What to look for.** DSR framework and guidelines; the DSR **process model**;
artifact types; **evaluation** of design artifacts; positioning/presenting DSR.

**Search strings.**
- `"design science research" "information systems"`
- `"design science research methodology"`
- `"design science" guidelines artifact evaluation`
- `"design science research" evaluation framework`

**Target venues.** *MIS Quarterly*, *JMIS*, *EJIS*, *JAIS* (Q1); DESRIST conference.

> **Why the foundations here are (correctly) old.** DSR is a *mature methodology*, and
> you cite the paper that **defines the method you followed** — that is Hevner 2004 and
> Peffers 2007. Reviewers expect them; substituting a 2025 paper for Hevner would look
> like you don't know the field. Old ≠ outdated for a methodology foundation. Pair the
> canonical papers with **one recent** DSR reference to show currency — that is the right
> shape, not "all recent".

**Foundational (cite these — they define the method).**
- **Hevner, March, Park & Ram, "Design Science in Information Systems Research", *MIS
  Quarterly*, 2004** — the foundational DSR guidelines (Q1).
- **Peffers, Tuunanen, Rothenberger & Chatterjee, "A Design Science Research Methodology
  for Information Systems Research", *Journal of Management Information Systems*, 2007** —
  the DSRM process model your methodology chapter follows (Q1).
- **Gregor & Hevner, "Positioning and Presenting Design Science Research for Maximum
  Impact", *MIS Quarterly*, 2013** — how to frame the contribution (Q1).

**Recent (add ONE of these for currency — both verified, top venue).**
- **Tuunanen, Winter & vom Brocke, "Dealing with Complexity in Design Science Research:
  A Methodology Using Design Echelons", *MIS Quarterly* 48(2), 2024** — a genuinely
  recent DSR methodology paper at the field's top venue (Q1); use it to show the method
  is live, not frozen in 2007.
- **vom Brocke, Winter, Hevner & Maedche, "Accumulation and Evolution of Design Knowledge
  in Design Science Research: A Journey Through Time and Space", *JAIS* 21(3), 2020** —
  heavily cited; on how DSR contributions build into a body of knowledge (Q1).

**Pick 2–3 total:** Hevner 2004 + Peffers 2007 (core) **+ Tuunanen et al. 2024** (recency).
That pairing — two canonical, one 2024 — is exactly what an examiner wants to see.

---

## Suggested narrative for the written review

Once papers are selected, the review flows from broad to specific and lands on the
gap the thesis fills:

1. **Problem space** (§1, §2) — DW automation exists, but Data Vault modelling is
   largely manual and under-researched.
2. **Enabling technology** (§3, §4, §5) — LLMs can generate structured artifacts and
   act as agents; retrieval/few-shot lets them learn from examples.
3. **The learning signal** (§6) — human feedback / active learning as a training
   source; approvals as labels.
4. **The second use case** (§7) — schema evolution and drift detection.
5. **How to evaluate it honestly** (§8) — grading generated artifacts without a full
   gold standard; inter-rater reliability.
6. **How the study is framed** (§9) — Design Science Research.

**The gap statement** the review should build toward: *prior work automates parts of
data-warehouse construction and shows LLMs can generate structured/code artifacts,
but no prior work combines a multi-agent LLM pipeline with an approval-driven
feedback loop to generate and maintain Data Vault 2.0 models, nor evaluates such a
system's accuracy, learning behaviour, and human-effort trade-offs against manual
and rule-based baselines.*

## Inclusion / exclusion (keep the review defensible)

- **Include:** peer-reviewed papers that appear on **DBLP at a real conference or
  journal**; seminal books for §1/§2/§7 (cited as foundational, clearly labelled).
- **Exclude — arXiv-only papers.** If a paper's *only* DBLP entry is **CoRR**, it is an
  arXiv preprint and is **out** (per the thesis rule). If the same work also appears at a
  conference/journal, use that version. (Worked example: Chen et al. 2021 "Codex" is
  CoRR-only → excluded; DIN-SQL, NeurIPS 2023 → fine.)
- **Exclude:** vendor marketing/blogs (cite only as clearly-labelled practitioner
  context), and papers only tangentially related.
- **Record for each kept paper:** citation, venue + its rank (CORE/SJR), year, the
  one-line relevance to your RQ, and which theme — this table is the review's backbone.

## A recommended core set (≈14 papers — recency-first, hits your 10–16 target)

Every AI/ML/LLM/RAG row below is **2023–2026, at a real venue, and I verified the venue
while preparing this** (against DBLP / the proceedings). The only older entries are ones
where recency is not expected — schema-matching lineage (§7) and Design-Science
methodology (§9), whose foundational papers are *supposed* to be older. Confirm each on
DBLP, look up its rank, keep/swap to taste.

| # | Theme | Paper (verify on DBLP) | Venue / rank | Year |
|---|---|---|---|---|
| 1 | §1 DWA | Mazón & Trujillo, *An MDA approach for the development of data warehouses* | *Decision Support Systems* / Q1 | 2008 |
| 2 | §2 Data Vault | Giebler et al., *Modeling Data Lakes with Data Vault* | ER / CORE A | 2019 |
| 3 | §3 text-to-SQL | **Li et al., *BIRD: Can LLM Already Serve as a Database Interface?*** | NeurIPS D&B / A\* | **2023** |
| 4 | §3 text-to-SQL | **Pourreza & Rafiei, *DIN-SQL*** | NeurIPS / A\* | **2023** |
| 5 | §4 multi-agent | **Hong et al., *MetaGPT*** | ICLR / A\* | **2024** |
| 6 | §4 multi-agent | **Qian et al., *ChatDev*** | ACL / A\* | **2024** |
| 7 | §4 generator–critic | **Madaan et al., *Self-Refine*** | NeurIPS / A\* | **2023** |
| 8 | §5 RAG + critique | **Asai et al., *Self-RAG*** | ICLR (Oral) / A\* | **2024** |
| 9 | §5 in-context | Min et al., *Rethinking the Role of Demonstrations* | EMNLP / A\* | 2022 |
| 10 | §6 feedback | **Rafailov et al., *Direct Preference Optimization (DPO)*** | NeurIPS / A\* | **2023** |
| 11 | §7 schema/drift | Rahm & Bernstein, *…Automatic Schema Matching* | *VLDB Journal* / Q1 | 2001 |
| 12 | §8 evaluation | **Liu et al., *G-Eval: NLG Evaluation using GPT-4*** | EMNLP / A\* | **2023** |
| 13 | §8 evaluation | **Zheng et al., *Judging LLM-as-a-Judge*** | NeurIPS D&B / A\* | **2023** |
| 14 | §9 methodology | Hevner et al., *Design Science in IS Research* | *MIS Quarterly* / Q1 | 2004 |

That is 14 (10 of them **2023–2024**). Add Peffers et al. 2007 (*JMIS*, Q1) for a second
methodology anchor to reach 15, or drop one §8 row to land at 13. **Recent swap-ins for
more depth:** Gao et al. *DAIL-SQL* (§3, PVLDB 2024, A\*), Shinn et al. *Reflexion* (§4,
NeurIPS 2023, A\*), Ji et al. *Hallucination Survey* (§8, ACM Comput. Surv. 2023, Q1),
Li et al. *Ditto* (§7, PVLDB 2020, A\*).

**Cite-once-for-lineage (don't count toward the 14, mention in one sentence each):**
Vaswani et al. 2017 (transformer), Brown et al. 2020 (GPT-3 few-shot), Lewis et al. 2020
(RAG), Yao et al. 2023 (ReAct), Ouyang et al. 2022 (InstructGPT). These establish the
lineage; your body citations should be the 2023–2024 rows above.

**Coverage sanity check:** this set is heavily **CORE A\* / SJR Q1**, skews **2023–2024**, spans every RQ, and
directly mirrors your own components (structured generation, sample-voting, a
generator–critic reviewer, retrieval-based learning, schema drift, honest evaluation, and
the DSR frame). The two deliberately weaker-venue areas — §2 Data Vault (ER/DaWaK) and
§4's AutoGen (COLM, unranked) — are the niches where strong venues genuinely do not
exist, which you state as motivation rather than apologise for.

## On 2025 / 2026 papers — read before you go hunting for them

There is a real tension in "recent **and** well-cited": a 2025/2026 paper has had almost
no time to accumulate citations, and a large share of 2025/2026 work is still **arXiv-only**
(which your rule excludes). So "newest possible" and "good citation count / ranked venue"
pull against each other. The right target is **2023–2024 papers at A\*/Q1 venues** — recent
enough to be current, old enough to be peer-reviewed *and* cited. That is what the core set
above is.

Where 2025/2026 genuinely helps is **surveys** (they get cited fast and suit a related-work
section) and the **methodology currency pick** (§9's Tuunanen et al. 2024). If you want a
2025 paper for a specific concept, tell me the concept and I will hunt for one that is
**already at a 2025 venue (ICLR/ACL/NeurIPS/VLDB 2025), not CoRR** — but expect it to carry
few citations, and don't build a core argument on it. Never trade a well-cited 2024 A\* paper
for a shinier-but-uncited 2026 preprint.
