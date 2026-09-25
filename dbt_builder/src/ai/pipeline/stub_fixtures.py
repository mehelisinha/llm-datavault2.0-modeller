"""Injectable Spark callables for stub / test discovery runs.

Shared by API stub mode and pytest so catalog inspection and bronze reads
stay identical between local dev and CI.
"""

from __future__ import annotations


def stub_list_vault_entities(_catalog: str, _schema: str) -> list[tuple[str, str]]:
    return [
        ("hub_conducting_equipment", "hub"),
        ("sat_conducting_equipment_details", "sat"),
        ("hub_terminal", "hub"),
    ]


def stub_describe_vault(_catalog: str, _schema: str, table: str) -> list[tuple[str, str, bool, str | None]]:
    if table == "hub_conducting_equipment":
        return [
            ("hk_conducting_equipment", "string", False, None),
            ("mrid", "string", False, None),
            ("load_dts", "timestamp", False, None),
        ]
    if table == "sat_conducting_equipment_details":
        return [
            ("hk_conducting_equipment", "string", False, None),
            ("hashdiff_ce_details", "string", False, None),
            ("name", "string", True, None),
            ("manufacturer", "string", True, None),
            ("load_dts", "timestamp", False, None),
        ]
    if table == "hub_terminal":
        return [
            ("hk_terminal", "string", False, None),
            ("mrid", "string", False, None),
            ("load_dts", "timestamp", False, None),
        ]
    return []


def stub_list_bronze_tables(_catalog: str, _schema: str) -> list[str]:
    return ["conducting_equipment", "terminals", "connectivity_nodes"]


def stub_describe_bronze(
    _catalog: str, _schema: str, table: str
) -> list[tuple[str, str, bool, str | None, bool]]:
    if table == "conducting_equipment":
        return [
            ("mrid", "string", False, None, False),
            ("name", "string", True, None, False),
            ("manufacturer", "string", True, None, False),
            ("voltage_level", "double", True, None, False),
        ]
    if table == "terminals":
        return [
            ("mrid", "string", False, None, False),
            ("conducting_equipment_mrid", "string", False, None, False),
            ("connectivity_node_mrid", "string", False, None, False),
        ]
    if table == "connectivity_nodes":
        return [
            ("mrid", "string", False, None, False),
            ("description", "string", True, None, False),
        ]
    return []
