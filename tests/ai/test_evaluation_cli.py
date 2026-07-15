"""Phase 6: evaluation CLI (score command) + latency in the ablation runner."""

from __future__ import annotations

from dbt_builder.src.ai.contracts.decisions import HubDecision, ModelingPlan, SatelliteDecision
from dbt_builder.src.ai.evaluation import AblationArm, ExperimentCase, run_ablation
from dbt_builder.src.ai.evaluation.__main__ import main


def _plan() -> ModelingPlan:
    return ModelingPlan(
        system_id="cim",
        hubs=(
            HubDecision(
                name="hub_terminal", source_table="t", business_keys=("mrid",), hash_key="HK_T"
            ),
        ),
        satellites=(
            SatelliteDecision(
                name="sat_terminal_details",
                source_table="t",
                parent_hub="hub_terminal",
                hash_key="HK_T",
                hashdiff="HD_T",
                payload=("name",),
            ),
        ),
    )


def test_score_command_runs_and_reports(tmp_path, capsys):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(_plan().model_dump_json(), encoding="utf-8")

    rc = main(["score", "--plan", str(plan_path), "--gold", "IEC_CIM_001"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "conformance score" in out
    assert "entity id" in out  # structural entity P/R/F1 printed
    assert "naming adherence" in out


def test_score_command_without_gold(tmp_path, capsys):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(_plan().model_dump_json(), encoding="utf-8")
    rc = main(["score", "--plan", str(plan_path)])
    assert rc == 0
    assert "naming adherence" not in capsys.readouterr().out


def test_ablation_reports_mean_latency():
    cases = [ExperimentCase(system_id="t", source_tables=("t",))]

    def propose(arm, case):
        return _plan()

    results = run_ablation(cases, propose=propose, arms=[AblationArm("a", {})])
    assert "mean_latency_s" in results["a"]
    assert results["a"]["mean_latency_s"] >= 0.0
