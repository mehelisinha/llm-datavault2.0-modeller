"""Use Case B — schema-drift impact classification + scoring (RQ2).

No network: the LLM classifier is exercised with a fake client, and the
deterministic recall check runs the real diff engine on a synthetic snapshot pair.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from dbt_builder.src.ai.contracts.catalog import (
    ChangeCategory,
    ChangeRisk,
    ColumnDiff,
    TableChange,
)
from dbt_builder.src.ai.drift.impact import (
    ChangeImpact,
    ImpactClassifier,
    rule_based_impact,
)
from dbt_builder.src.ai.drift.scoring import impact_cost, score_impacts

A, C, B = ChangeImpact.ADDITIVE, ChangeImpact.COSMETIC, ChangeImpact.BREAKING


def _change(category, *, risk=ChangeRisk.LOW, diffs=()):
    return TableChange(table_name="t", category=category, risk=risk, column_diffs=diffs)


def _diff(name, verb, old=None, new=None):
    return ColumnDiff(name=name, change=verb, old_dtype=old, new_dtype=new)


# ── rule-based baseline ───────────────────────────────────────────────────────


def test_new_table_is_additive():
    assert rule_based_impact(_change(ChangeCategory.NEW, diffs=(_diff("x", "added"),))) is A


def test_added_column_is_additive():
    ch = _change(ChangeCategory.DRIFT, diffs=(_diff("phone", "added", new="string"),))
    assert rule_based_impact(ch) is A


def test_removed_column_is_breaking():
    ch = _change(ChangeCategory.DRIFT, diffs=(_diff("name", "removed", old="string"),))
    assert rule_based_impact(ch) is B


def test_type_change_is_conservatively_breaking():
    # The rule baseline cannot judge compatibility -> any type change is breaking.
    ch = _change(ChangeCategory.DRIFT, diffs=(_diff("id", "type_changed", "int", "bigint"),))
    assert rule_based_impact(ch) is B


def test_high_risk_is_breaking():
    ch = _change(ChangeCategory.DRIFT, risk=ChangeRisk.HIGH,
                 diffs=(_diff("mrid", "added", new="string"),))
    assert rule_based_impact(ch) is B


def test_orphaned_table_is_breaking():
    assert rule_based_impact(_change(ChangeCategory.ORPHANED)) is B


def test_unchanged_is_cosmetic():
    assert rule_based_impact(_change(ChangeCategory.UNCHANGED)) is C


# ── AI classifier (fake client) ───────────────────────────────────────────────


class _FakeMsg:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})


class _FakeCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return type("R", (), {"choices": [_FakeMsg(self._content)]})


class _FakeClient:
    def __init__(self, content):
        self.chat = type("C", (), {"completions": _FakeCompletions(content)})


def _clf(content):
    return ImpactClassifier(client=_FakeClient(content), deployment="gpt-4.1")


def test_ai_classifier_parses_verdict():
    v = _clf('{"impact": "cosmetic", "rationale": "int->bigint widening on a non-key"}').classify(
        _change(ChangeCategory.DRIFT, diffs=(_diff("id", "type_changed", "int", "bigint"),))
    )
    assert v.impact is C and v.source == "ai" and "widening" in v.rationale


def test_ai_beats_rule_on_compatible_widening():
    # Rule says breaking (any type change); a competent AI says cosmetic.
    ch = _change(ChangeCategory.DRIFT, diffs=(_diff("id", "type_changed", "int", "bigint"),))
    assert rule_based_impact(ch) is B
    assert _clf('{"impact": "cosmetic", "rationale": "widening"}').classify(ch).impact is C


def test_ai_classifier_falls_back_on_bad_json():
    v = _clf("not json").classify(_change(ChangeCategory.ORPHANED))
    assert v.source == "rule" and v.impact is B  # rule baseline used


def test_ai_classifier_falls_back_on_unknown_label():
    v = _clf('{"impact": "catastrophic"}').classify(_change(ChangeCategory.NEW,
             diffs=(_diff("x", "added"),)))
    assert v.source == "rule" and v.impact is A


def test_no_client_uses_rule_baseline():
    v = ImpactClassifier(client=None).classify(_change(ChangeCategory.DRIFT,
        diffs=(_diff("c", "removed"),)))
    assert v.source == "rule" and v.impact is B


# ── cost function ─────────────────────────────────────────────────────────────


def test_missing_a_breaking_change_is_the_costliest_error():
    assert impact_cost(B, A) == 5  # expert breaking, predicted additive -> dangerous
    assert impact_cost(B, C) == 5
    assert impact_cost(A, B) == 1  # false alarm -> cheap
    assert impact_cost(A, C) == 1  # minor confusion
    assert impact_cost(B, B) == 0  # correct


# ── scoring ───────────────────────────────────────────────────────────────────


def test_score_impacts_perfect():
    rep = score_impacts([A, C, B], [A, C, B])
    assert rep.accuracy == 1.0
    assert rep.total_cost == 0
    assert rep.breaking_recall == 1.0


def test_score_impacts_confusion_and_cost():
    # expert: [B, B, A]; predicted: [A, B, A] -> one missed breaking (cost 5).
    rep = score_impacts([A, B, A], [B, B, A])
    assert rep.n == 3 and rep.correct == 2
    assert rep.total_cost == 5
    assert rep.confusion["breaking"]["additive"] == 1
    assert rep.confusion["breaking"]["breaking"] == 1
    assert rep.per_class["breaking"].recall == 0.5  # 1 of 2 breaking caught


def test_score_impacts_length_mismatch_raises():
    with pytest.raises(ValueError):
        score_impacts([A], [A, B])


# ── deterministic detection recall (H2a) on a synthetic drift pair ────────────


def test_diff_engine_detects_all_injected_changes():
    from dbt_builder.src.ai.contracts.catalog import (
        BronzeColumn,
        BronzeSnapshot,
        BronzeTable,
        CatalogSnapshot,
        VaultColumn,
        VaultEntity,
    )
    from dbt_builder.src.ai.pipeline.diff_analyzer import diff

    now = datetime.now(timezone.utc)
    # Approved vault: hub_company(sys_id, name) + hub_old(k).
    catalog = CatalogSnapshot(
        catalog="c", schema_name="v", captured_at=now,
        entities=(
            VaultEntity(name="hub_company", kind="hub", columns=(
                VaultColumn(name="sys_id", raw_dtype="string"),
                VaultColumn(name="name", raw_dtype="string"),
            )),
            VaultEntity(name="hub_old", kind="hub", columns=(
                VaultColumn(name="k", raw_dtype="string"),
            )),
        ),
    )
    # Drifted bronze: company gains 'phone' (added) + name removed; new 'ticket'
    # table; hub_old has no bronze source (orphaned).
    bronze = BronzeSnapshot(
        catalog="c", schema_name="b", captured_at=now,
        tables=(
            BronzeTable(catalog="c", schema_name="b", name="company", columns=(
                BronzeColumn(name="sys_id", raw_dtype="string"),
                BronzeColumn(name="phone", raw_dtype="string"),
            )),
            BronzeTable(catalog="c", schema_name="b", name="ticket", columns=(
                BronzeColumn(name="number", raw_dtype="string"),
            )),
        ),
    )
    change_set = diff(catalog, bronze)
    by_table = {c.table_name.lower(): c for c in change_set.changes}
    # every injected change is detected:
    assert by_table["ticket"].category is ChangeCategory.NEW           # new table
    assert by_table["company"].category is ChangeCategory.DRIFT        # column changes
    assert by_table["hub_old"].category is ChangeCategory.ORPHANED     # vanished source
    company_verbs = {cd.change for cd in by_table["company"].column_diffs}
    assert "added" in company_verbs and "removed" in company_verbs
