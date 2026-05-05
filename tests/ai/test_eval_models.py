"""Opt-in evaluation: run the modelling agent across multiple source systems.

Each fixture is just a YAML file under ``poc/metadata/`` in the Phase-1
discovery shape (``system + tables + columns``). The test loads it via
``discover_from_yaml`` — the same code path production uses — so the test
itself contains *no* schema data. To add a new source system: drop a new
discovery YAML and append an :class:`EvalCase` row.

Sanity floors are intentionally weak (each expected hub source table must
yield >=1 hub) so the run is informative without becoming flaky over LLM
variation. The detailed report is printed when run with ``-s``.

Run with::

    .venv\\Scripts\\python.exe -m pytest tests/ai/test_eval_models.py --live -s
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

pytestmark = [pytest.mark.ai, pytest.mark.live]

from dbt_builder.src.ai.agents import get_modelling_agent  # noqa: E402
from dbt_builder.src.ai.contracts.decisions import ModelingPlan  # noqa: E402
from dbt_builder.src.ai.discovery import discover_from_yaml  # noqa: E402
from dbt_builder.src.ai.settings import get_settings  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
METADATA_DIR = REPO_ROOT / "poc" / "metadata"


@dataclass(frozen=True)
class EvalCase:
    """One source system to evaluate the modelling agent against."""

    name: str
    yaml: str
    expected_hub_tables: frozenset[str]
    expected_link_table: str | None = None
    min_satellites_per_table: dict[str, int] = field(default_factory=dict)
    # Optional per-fixture token budget. ``None`` defers to AISettings, which
    # picks a per-deployment default (gpt-5 gets a larger budget to absorb its
    # invisible reasoning-token overhead). Override only when a payload is so
    # large that even the configured default is too tight.
    max_tokens: int | None = None


CASES: tuple[EvalCase, ...] = (
    EvalCase(
        name="iec_cim",
        yaml="iec_cim_discovery.yaml",
        expected_hub_tables=frozenset({"conducting_equipment", "connectivity_nodes", "terminals"}),
        expected_link_table="terminals",
        min_satellites_per_table={
            "conducting_equipment": 1,
            "connectivity_nodes": 1,
            "terminals": 1,
        },
    ),
    EvalCase(
        name="servicenow_it4it",
        yaml="servicenow_it4it_discovery.yaml",
        # Master-data / business entities — exclude link tables (sys_user_grmember,
        # task_sla, u_mcs_company_and_approval_group_mapping) and operational logs
        # (volumemetrics) which the modeller is expected to treat as links / non-hubs.
        expected_hub_tables=frozenset(
            {"cmn_department", "cmn_location", "core_company", "core_country", "contract_sla"}
        ),
        # No hand-modelled gold yet — leave link expectation open.
        expected_link_table=None,
        min_satellites_per_table={
            "cmn_department": 1,
            "cmn_location": 1,
            "core_company": 1,
            "core_country": 1,
            "contract_sla": 1,
        },
    ),
)


# ─────────────────────────────────────────────────────────────────────── scoring


@dataclass
class Score:
    """How well one ModelingPlan matches a case's sanity floors."""

    hub_table_coverage: int
    expected_hub_tables: int
    satellite_table_coverage: int
    expected_satellite_tables: int
    has_expected_link: bool | None  # None when the case has no link expectation
    total_entities: int


def _bare_table(qualified: str) -> str:
    """Strip catalog/schema prefix (``a.b.c`` -> ``c``) for tolerant matching."""
    return qualified.rsplit(".", 1)[-1].lower()


def _score(plan: ModelingPlan, case: EvalCase) -> Score:
    expected = {t.lower() for t in case.expected_hub_tables}
    hub_tables = {_bare_table(h.source_table) for h in plan.hubs}
    hub_coverage = len(expected & hub_tables)

    sat_table_hits = 0
    for table, minimum in case.min_satellites_per_table.items():
        target = table.lower()
        sats = [s for s in plan.satellites if _bare_table(s.source_table) == target]
        if len(sats) >= minimum:
            sat_table_hits += 1

    link_ok: bool | None
    if case.expected_link_table is None:
        link_ok = None
    else:
        target_link = case.expected_link_table.lower()
        link_ok = any(
            len(ln.fk_columns) >= 3 and _bare_table(ln.source_table) == target_link
            for ln in plan.links
        )

    return Score(
        hub_table_coverage=hub_coverage,
        expected_hub_tables=len(case.expected_hub_tables),
        satellite_table_coverage=sat_table_hits,
        expected_satellite_tables=len(case.min_satellites_per_table),
        has_expected_link=link_ok,
        total_entities=plan.entity_count,
    )


# ────────────────────────────────────────────────────────────────────────── test


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
@pytest.mark.parametrize(
    "model_picker",
    [
        pytest.param(lambda c: c.primary_chat_deployment, id="primary"),
        pytest.param(lambda c: c.chat_deployment_gpt4o, id="gpt-4o"),
    ],
)
def test_eval_one_model_against_fixture(case: EvalCase, model_picker, capsys) -> None:
    cfg = get_settings()
    deployment = model_picker(cfg)
    payload = discover_from_yaml(METADATA_DIR / case.yaml)

    agent = get_modelling_agent(
        settings=cfg,
        deployment=deployment,
        samples=1,  # Single-sample to keep cost predictable.
        max_tokens=case.max_tokens,  # None -> AISettings.modeller_max_tokens_for(deployment)
    )
    effective_max_tokens = case.max_tokens or cfg.modeller_max_tokens_for(deployment)
    plan = agent.propose(payload)
    s = _score(plan, case)

    # Printed report for the eval write-up (visible with `-s`).
    with capsys.disabled():
        print(
            f"\n[eval] case={case.name} deployment={deployment} max_tokens={effective_max_tokens}"
        )
        print(f"  hub_table_coverage      = {s.hub_table_coverage} / {s.expected_hub_tables}")
        print(
            f"  satellite_table_coverage= {s.satellite_table_coverage} "
            f"/ {s.expected_satellite_tables}"
        )
        print(f"  has_expected_link       = {s.has_expected_link}")
        print(f"  total_entities          = {s.total_entities}")
        print(f"  hubs                    = {[h.name for h in plan.hubs]}")
        print(f"  hub.source_table        = {[h.source_table for h in plan.hubs]}")
        print(f"  links                   = {[ln.name for ln in plan.links]}")
        print(f"  link.source_table       = {[ln.source_table for ln in plan.links]}")
        print(f"  satellites              = {[st.name for st in plan.satellites]}")

    # Sanity floor: every expected hub source table must be covered.
    assert s.hub_table_coverage == s.expected_hub_tables, (
        f"{deployment} on {case.name}: missed at least one expected hub source table; "
        f"got hubs={[h.source_table for h in plan.hubs]}"
    )
