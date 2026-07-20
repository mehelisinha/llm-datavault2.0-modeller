# Literature Review — Scope and Search Strategy

> **Purpose.** A themed map of what the literature review must cover, with
> paste-ready search strings, the target venues per theme (so you can judge
> ranking), and a small set of anchor references to verify. You search and select
> the papers manually; once you hand them to me I synthesise them into the review.

## How to use this document

1. Work theme by theme (§1–§9). Each theme states its **role** (which RQ/chapter it
   supports), **what to look for** (the specific gap/question the papers must
   speak to), **search strings**, **target venues**, and **anchor references**.
2. Run the search strings in the databases below; screen by title/abstract against
   "what to look for"; keep what fits.
3. **Check ranking** with: **CORE Rankings** (conferences: A\*/A/B/C) and **Scimago
   Journal Rank (SJR)** or **JCR quartiles** (journals: Q1–Q4). Prefer A\*/A and
   Q1/Q2 where possible; for the niche Data-Vault theme, high-ranked venues are
   scarce — practitioner/book sources are acceptable there (noted in §2).
4. Hand me the selected papers (PDFs or full citations). I group them by theme,
   summarise each, and position them against your contribution.

**Databases to search:** Google Scholar, Scopus, Web of Science, IEEE Xplore, ACM
Digital Library, SpringerLink, arXiv (categories cs.CL, cs.DB, cs.AI, cs.SE), and
DBLP (useful for browsing a venue's proceedings directly).

**Search-string notes:** strings use quotes for exact phrases and `OR`/`AND` (works
in Google Scholar and, with minor syntax changes, in Scopus/IEEE). Add a year
filter where noted — LLM themes should skew **2020–present**; foundational themes
(schema matching, DSR, data-warehouse theory) include seminal older work.

> **Integrity note on the anchors.** The "anchor references" are limited to
> **well-established works I can name with confidence** — but you must still
> **verify every author/year/venue** before citing (standard practice, and it
> guards against any transcription error). For newer or niche sub-areas I give
> **search strings instead of specific citations**, deliberately, to avoid
> pointing you at a paper that might be mis-remembered.

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

**Anchor references (verify).** Kimball & Ross, *The Data Warehouse Toolkit*
(dimensional modelling — for contrast); Inmon, *Building the Data Warehouse*.

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

**Anchor references (verify).** Linstedt & Olschimke (2015), *Building a Scalable
Data Warehouse with Data Vault 2.0*, Morgan Kaufmann.

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
(software); VLDB, SIGMOD (text-to-SQL/DB).

**Anchor references (verify).** Vaswani et al. (2017), *Attention Is All You Need*;
Brown et al. (2020), *Language Models are Few-Shot Learners* (GPT-3); Chen et al.
(2021), *Evaluating Large Language Models Trained on Code* (Codex/HumanEval); Yu et
al. (2018), *Spider* (text-to-SQL benchmark).

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

**Target venues.** NeurIPS, ICLR, ICML, ACL, EMNLP; recent arXiv (cs.AI, cs.CL).

**Anchor references (verify).** Yao et al. (2023), *ReAct: Synergizing Reasoning
and Acting in Language Models*; Wei et al. (2022), *Chain-of-Thought Prompting*;
Wang et al. (2022), *Self-Consistency Improves Chain-of-Thought Reasoning* (relates
to your sample-voting); Wu et al. (2023), *AutoGen* (multi-agent framework). For the
generator–critic idea, also search `"self-refine" language model`.

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

**Target venues.** NeurIPS, ICLR, ACL, EMNLP, TACL.

**Anchor references (verify).** Lewis et al. (2020), *Retrieval-Augmented Generation
for Knowledge-Intensive NLP Tasks*; Brown et al. (2020) (few-shot, as above); Liu et
al. (2022), *What Makes Good In-Context Examples for GPT-3?* For "how many examples"
search `"number of demonstrations" in-context learning`.

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

**Anchor references (verify).** Settles (2009), *Active Learning Literature Survey*;
Christiano et al. (2017), *Deep Reinforcement Learning from Human Preferences*;
Ouyang et al. (2022), *Training Language Models to Follow Instructions with Human
Feedback* (InstructGPT).

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

**Target venues.** VLDB, SIGMOD, ICDE, EDBT; *VLDB Journal*, *Information Systems*,
*TKDE*.

**Anchor references (verify).** Rahm & Bernstein (2001), *A Survey of Approaches to
Automatic Schema Matching*, VLDB Journal; Doan, Halevy & Ives, *Principles of Data
Integration* (book). For evolution specifically, search `"schema evolution survey"`.

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

**Anchor references (verify).** Zheng et al. (2023), *Judging LLM-as-a-Judge with
MT-Bench and Chatbot Arena*; Chen et al. (2021) (HumanEval/pass@k, as in §3); Cohen
(1960), *A Coefficient of Agreement for Nominal Scales* (κ).

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

**Target venues.** *MIS Quarterly*, *JMIS*, *EJIS*, *JAIS*; DESRIST conference.

**Anchor references (verify).** Hevner, March, Park & Ram (2004); Peffers et al.
(2007); March & Smith (1995); Gregor & Hevner (2013), *Positioning and Presenting
Design Science Research for Maximum Impact*, MIS Quarterly.

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

- **Include:** peer-reviewed papers and reputable pre-prints (arXiv) directly on a
  theme; seminal books for §1/§2/§7; recent (2020+) work for the LLM themes.
- **Exclude:** vendor marketing/blogs (cite only as practitioner context, clearly
  labelled), and papers only tangentially related.
- **Record for each kept paper:** citation, venue + its rank (CORE/SJR), year, the
  one-line relevance to your RQ, and which theme it belongs to — this table becomes
  the backbone of the written review.
