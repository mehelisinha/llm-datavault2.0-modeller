"""Inter-rater reliability of the gold sets — triangulation for the single-author gap.

Three legs, one script:

* ``--rater llm``   — an **independent LLM annotator** (a model *different* from the
  pipeline modeller, seeing only the source schema + the codebook, never the gold or
  the pipeline's output) labels each source table hub/split/exclude; the script then
  reports Cohen's kappa vs the gold labelling.
* ``--emit-template T`` — writes the blank item list (one row per source table) for the
  author to re-label after a washout, enabling **intra-rater test-retest**.
* ``--rater human --labels F`` — scores a filled template (or any second labelling)
  against the gold, i.e. the test-retest (or a real second annotator) kappa.

The gold labelling and the kappa are derived by the pure, unit-tested
:mod:`dbt_builder.src.ai.evaluation.interrater`. Only the LLM annotator does I/O.

Examples
--------
    python scripts/audit/interrater.py --rater llm --system IEC_CIM_001 --system SNOW_IT4IT_001 \
        --out documentation/thesis/data/interrater_llm.json
    python scripts/audit/interrater.py --emit-template documentation/thesis/data/annotation_template.csv
    python scripts/audit/interrater.py --rater human --labels my_reannotation.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dbt_builder.src.ai.evaluation.gold import load_gold_models  # noqa: E402
from dbt_builder.src.ai.evaluation.interrater import (  # noqa: E402
    ENTITY_LABELS,
    gold_entity_labels,
    kappa_and_agreement,
)

_DEFAULT_SYSTEMS = ("IEC_CIM_001", "SNOW_IT4IT_001")

# The codebook decision rules the independent annotator is held to — identical to
# documentation/thesis/annotation-codebook.md so the human and the LLM label to the
# same protocol.
CODEBOOK_RULES = """\
Label each SOURCE TABLE with exactly one of: hub, split, exclude.

- hub: the table represents ONE core business entity that has a stable identifying
  key (a semantic business key if one exists, otherwise a stable surrogate/GUID such
  as sys_id or mRID). It becomes one Data Vault hub.
- split: a SINGLE table that represents TWO OR MORE distinct business entities — for
  example an association/membership table (user-group membership) from which both a
  user entity and a group entity are derived. It becomes two or more hubs.
- exclude: the table should NOT become a hub. This covers (a) telemetry / metrics /
  measurement tables, (b) pure junction / mapping tables whose only role is to relate
  other entities (they become links, not hubs), and (c) tables whose entity identity
  is defined in a DIFFERENT schema (out of scope here).
"""


def _discover(system_id: str, gold):
    from dbt_builder.src.ai.discovery.schema_discovery import discover_from_yaml

    return discover_from_yaml(gold.discovery_payload)


def _schema_text(payload) -> str:
    lines = []
    for t in payload.tables:
        cols = ", ".join(c.name for c in t.columns)
        lines.append(f"- {t.name}: {cols}")
    return "\n".join(lines)


def _annotate_llm(payload, *, deployment: str) -> dict[str, str]:
    """Independent LLM annotator: label every table hub/split/exclude from schema only.

    Robust to model quirks: some reasoning deployments reject ``temperature=0`` or
    ``response_format``; on such an error the call is retried without those options.
    """
    from openai import AzureOpenAI

    from dbt_builder.src.ai.settings import get_settings

    s = get_settings()
    client = AzureOpenAI(
        azure_endpoint=s.azure_openai_endpoint,
        api_key=s.azure_openai_api_key.get_secret_value(),
        api_version=s.azure_openai_api_version,
    )
    tables = [t.name for t in payload.tables]
    prompt = (
        f"{CODEBOOK_RULES}\n\nSource tables and their columns:\n{_schema_text(payload)}\n\n"
        f"Return ONLY a JSON object mapping every table name to its label, e.g. "
        f'{{"{tables[0]}": "hub"}}. Tables to label: {tables}.'
    )
    messages = [
        {"role": "system", "content": "You are a Data Vault 2.0 data modeller. Follow the rules exactly. Reply with JSON only."},
        {"role": "user", "content": prompt},
    ]
    try:
        resp = client.chat.completions.create(
            model=deployment, messages=messages, temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception:
        resp = client.chat.completions.create(model=deployment, messages=messages)
    content = resp.choices[0].message.content or "{}"
    start, end = content.find("{"), content.rfind("}")
    raw = json.loads(content[start : end + 1]) if start >= 0 else {}
    labels = {t: str(raw.get(t, "exclude")).strip().lower() for t in tables}
    for t, lab in labels.items():
        if lab not in ENTITY_LABELS:
            labels[t] = "exclude"
    return labels


def _annotator_labeling(systems: list[str], deployment: str) -> dict[str, str]:
    """Run one annotator model across systems; return labels keyed ``system::table``."""
    golds = load_gold_models()
    out: dict[str, str] = {}
    for sid in systems:
        payload = _discover(sid, golds[sid])
        for t, lab in _annotate_llm(payload, deployment=deployment).items():
            out[f"{sid}::{t}"] = lab
    return out


def _majority(labelings: list[dict[str, str]]) -> dict[str, str]:
    """Per-item majority vote across annotator labelings (ties -> first-seen order)."""
    from collections import Counter

    keys = set().union(*labelings)
    out: dict[str, str] = {}
    for k in keys:
        votes = Counter(lbl[k] for lbl in labelings if k in lbl)
        out[k] = votes.most_common(1)[0][0]
    return out


def _cmd_panel(deployments: list[str], systems: list[str], gold_keyed: dict[str, str], out: str | None) -> int:
    """A panel of independent annotator models: each vs gold + model-vs-model agreement."""
    labelings = {d: _annotator_labeling(systems, d) for d in deployments}
    print(f"(panel: {deployments})\n")
    result: dict[str, object] = {"deployments": deployments, "vs_gold": {}, "model_vs_model": {}}
    print("-- each annotator vs gold --")
    for d, lab in labelings.items():
        r = kappa_and_agreement(gold_keyed, lab)
        result["vs_gold"][d] = {"kappa": r["cohens_kappa"], "agreement": r["raw_agreement"]}
        print(f"  {d:10} kappa={r['cohens_kappa']}  agreement={r['raw_agreement']}")
    print("-- annotator vs annotator (task objectivity) --")
    for i in range(len(deployments)):
        for j in range(i + 1, len(deployments)):
            di, dj = deployments[i], deployments[j]
            r = kappa_and_agreement(labelings[di], labelings[dj])
            result["model_vs_model"][f"{di} vs {dj}"] = {"kappa": r["cohens_kappa"], "agreement": r["raw_agreement"]}
            print(f"  {di} vs {dj}: kappa={r['cohens_kappa']}  agreement={r['raw_agreement']}")
    maj = _majority(list(labelings.values()))
    rm = kappa_and_agreement(gold_keyed, maj)
    result["majority_vs_gold"] = {"kappa": rm["cohens_kappa"], "agreement": rm["raw_agreement"], "disagreements": rm["disagreements"]}
    print(f"-- panel majority vs gold: kappa={rm['cohens_kappa']}  agreement={rm['raw_agreement']} --")
    for d in rm["disagreements"]:
        print(f"   {d['item']}: gold={d['rater_a']}  majority={d['rater_b']}")
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nwrote {out}")
    return 0


def _all_items(systems: list[str]) -> list[tuple[str, str, str]]:
    """Return (system_id, table, gold_label) for every source table across systems."""
    golds = load_gold_models()
    rows: list[tuple[str, str, str]] = []
    for sid in systems:
        gold = golds[sid]
        payload = _discover(sid, gold)
        tables = [t.name for t in payload.tables]
        gl = gold_entity_labels(gold, tables)
        for t in tables:
            rows.append((sid, t, gl[t]))
    return rows


def _cmd_emit_template(path: str, systems: list[str]) -> int:
    rows = _all_items(systems)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["system_id", "source_table", "label"])  # leave label blank to fill
        for sid, t, _gold in rows:
            w.writerow([sid, t, ""])
    print(f"wrote {len(rows)}-item blank template to {path}")
    print("Fill the 'label' column (hub/split/exclude) after a washout, then score with --rater human --labels <file>.")
    return 0


def _load_human_labels(path: str) -> dict[str, str]:
    keyed: dict[str, str] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            lab = (row.get("label") or "").strip().lower()
            if lab:
                keyed[f"{row['system_id']}::{row['source_table']}"] = lab
    return keyed


def _report(gold_keyed: dict[str, str], other_keyed: dict[str, str], *, rater: str, out: str | None) -> int:
    res = kappa_and_agreement(gold_keyed, other_keyed)
    print(f"================ INTER-RATER ({rater} vs gold) ================")
    print(f"items            : {res['n_items']}")
    print(f"raw agreement    : {res['raw_agreement']}")
    print(f"Cohen's kappa    : {res['cohens_kappa']}")
    print(f"gold label dist  : {res['dist_a']}")
    print(f"{rater:5} label dist : {res['dist_b']}")
    if res["disagreements"]:
        print("disagreements:")
        for d in res["disagreements"]:
            print(f"  {d['item']}: gold={d['rater_a']}  {rater}={d['rater_b']}")
    else:
        print("no disagreements.")
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps({"rater": rater, **res}, indent=2), encoding="utf-8")
        print(f"\nwrote {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--system", action="append", default=None, help="gold system_id (repeatable)")
    p.add_argument("--rater", choices=("llm", "human"), default="llm", help="second rater to score vs gold")
    p.add_argument("--labels", default=None, help="filled template CSV (with --rater human)")
    p.add_argument("--deployment", default=None, help="LLM annotator deployment (default: gpt-4o, != modeller)")
    p.add_argument("--panel", default=None, help="comma-separated deployments for a multi-annotator panel, e.g. gpt-4o,gpt-5")
    p.add_argument("--emit-template", default=None, help="write a blank annotation template CSV and exit")
    p.add_argument("--out", default=None, help="write the result JSON here")
    args = p.parse_args(argv)

    systems = args.system or list(_DEFAULT_SYSTEMS)

    if args.emit_template:
        return _cmd_emit_template(args.emit_template, systems)

    rows = _all_items(systems)
    gold_keyed = {f"{sid}::{t}": lab for sid, t, lab in rows}

    if args.panel:
        deployments = [d.strip() for d in args.panel.split(",") if d.strip()]
        return _cmd_panel(deployments, systems, gold_keyed, args.out)

    if args.rater == "human":
        if not args.labels:
            print("--rater human requires --labels <filled template CSV>")
            return 2
        other = _load_human_labels(args.labels)
        return _report(gold_keyed, other, rater="human", out=args.out)

    # LLM annotator, per system, keyed the same way.
    from dbt_builder.src.ai.settings import get_settings

    deployment = args.deployment or get_settings().chat_deployment_gpt4o
    golds = load_gold_models()
    other: dict[str, str] = {}
    for sid in systems:
        payload = _discover(sid, golds[sid])
        labels = _annotate_llm(payload, deployment=deployment)
        for t, lab in labels.items():
            other[f"{sid}::{t}"] = lab
    print(f"(independent annotator: {deployment})\n")
    return _report(gold_keyed, other, rater="llm", out=args.out)


if __name__ == "__main__":
    sys.exit(main())
