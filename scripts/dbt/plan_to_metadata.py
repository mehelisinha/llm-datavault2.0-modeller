"""Turn a generated ModelingPlan into a dbt-buildable DWA metadata YAML (gap 3 bridge).

`build_projects.py` consumes a DWA *metadata* YAML, but the pipeline produces a
*ModelingPlan* JSON (from `... evaluation generate --out plan.json`). This script
bridges the two so any generated system (e.g. ServiceNow) can enter the compile /
run / test sweep, not just the hand-authored CIM metadata.

It renders the raw-vault-only view of the plan via
:func:`~dbt_builder.src.ai.rendering.metadata_v3_emitter.render_v3` with **no
business-vault proposal** (``bv=None``) — so it is fully offline (no second LLM
call) and emits exactly the sections `DBTBuilder` consumes: staging, hubs, links,
satellites, eff_sats. The source-system identity (catalog/schema/record_source)
comes from the same discovery YAML the plan was generated from.

As a built-in guard it re-reads the emitted YAML with the dbt builder's own
``Metadata`` reader and fails loudly if it does not parse — so a bad emit is caught
here, before the dbt sweep.

Example
-------
    python scripts/dbt/plan_to_metadata.py \
        --plan snow_plan.json \
        --discovery poc/metadata/servicenow_it4it_discovery.yaml \
        --out poc/metadata/servicenow_it4it_metadata.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dbt_builder.src.ai.contracts.decisions import ModelingPlan  # noqa: E402
from dbt_builder.src.ai.discovery.schema_discovery import discover_from_yaml  # noqa: E402
from dbt_builder.src.ai.rendering.metadata_v3_emitter import render_v3  # noqa: E402
from dbt_builder.src.runners.metadata import Metadata  # noqa: E402


def plan_to_metadata_yaml(plan_path: str, discovery_path: str) -> str:
    """Render the raw-vault metadata YAML for ``plan_path`` (offline, bv omitted)."""
    plan = ModelingPlan.model_validate_json(Path(plan_path).read_text(encoding="utf-8"))
    payload = discover_from_yaml(discovery_path)
    if plan.system_id != payload.system.system_id:
        raise ValueError(
            f"plan system_id {plan.system_id!r} != discovery system_id "
            f"{payload.system.system_id!r} — the plan and discovery YAML must match."
        )
    return render_v3(plan, payload.system)  # bv=None -> raw-vault-only, no LLM


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--plan", required=True, help="ModelingPlan JSON (from 'evaluation generate --out')")
    p.add_argument("--discovery", required=True, help="the discovery YAML the plan was generated from")
    p.add_argument("--out", required=True, help="path to write the DWA metadata YAML")
    args = p.parse_args(argv)

    yaml_text = plan_to_metadata_yaml(args.plan, args.discovery)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml_text, encoding="utf-8")

    # Guard: the emitted YAML must be consumable by the dbt builder. Parse it back
    # and count components, so a bad emit fails here rather than mid-sweep.
    meta = Metadata(out)
    components = meta.get_all_component_models()
    counts = {k: len(v) for k, v in components.items() if v}
    print(f"wrote {out}")
    print(f"parsed OK via Metadata — components: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
