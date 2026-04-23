"""
IEC61968 CIM Dummy Data Generator
Simulates a grid asset SWAP scenario (Insert → Update → Delete)
Entities: Terminal, ConnectivityNode, ConductingEquipment
"""

import argparse
from datetime import datetime, timedelta
from typing import Any

import pyspark.sql.functions as F

# from faker import Faker
from dbt_builder.src.utils.spark import spark

# fake = Faker()

# # ── Seed for reproducibility ──────────────────────────────────────────────────
# Faker.seed(42)
BASE_DATE = datetime(2024, 1, 15, 8, 0, 0)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────
def ts(offset_minutes: int) -> str:
    return (BASE_DATE + timedelta(minutes=offset_minutes)).isoformat()


def record_source() -> str:
    return "IEC61968_CIM_v2.0"


# ─────────────────────────────────────────────────────────────────────────────
# CONNECTIVITY NODES  (network graph nodes)
# ─────────────────────────────────────────────────────────────────────────────
connectivity_nodes = [
    # Initial load (INSERT)
    {
        "mrid": "CN-001",
        "name": "BusBar_A",
        "description": "Primary 11kV busbar at substation Alpha",
        "load_dts": ts(0),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    {
        "mrid": "CN-002",
        "name": "BusBar_B",
        "description": "Secondary 11kV busbar at substation Alpha",
        "load_dts": ts(0),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    {
        "mrid": "CN-003",
        "name": "BusBar_C",
        "description": "11kV busbar at substation Beta",
        "load_dts": ts(0),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    {
        "mrid": "CN-004",
        "name": "JunctionPoint_1",
        "description": "Junction point on feeder circuit 7",
        "load_dts": ts(0),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    # Update during repair (UPDATE)
    {
        "mrid": "CN-001",
        "name": "BusBar_A",
        "description": "Primary 11kV busbar at substation Alpha — isolated for maintenance",
        "load_dts": ts(90),
        "record_source": record_source(),
        "cdc_flag": "U",
    },
    # Post-repair restore (UPDATE)
    {
        "mrid": "CN-001",
        "name": "BusBar_A",
        "description": "Primary 11kV busbar at substation Alpha — restored",
        "load_dts": ts(240),
        "record_source": record_source(),
        "cdc_flag": "U",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# CONDUCTING EQUIPMENT  (lines, switches, etc.)
# ─────────────────────────────────────────────────────────────────────────────
conducting_equipment = [
    # Original switch — INSERT
    {
        "mrid": "CE-SW-001",
        "name": "Switch_Alpha_Feeder7",
        "equipment_type": "LoadBreakSwitch",
        "base_voltage_kv": 11.0,
        "in_service": True,
        "asset_status": "InService",
        "manufacturer": "ABB",
        "model": "OVB-12",
        "serial_number": "ABB-2018-00441",
        "load_dts": ts(0),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    # Existing cable — INSERT
    {
        "mrid": "CE-LN-001",
        "name": "Cable_Alpha_to_Beta",
        "equipment_type": "ACLineSegment",
        "base_voltage_kv": 11.0,
        "in_service": True,
        "asset_status": "InService",
        "manufacturer": "Nexans",
        "model": "XLPE-185",
        "serial_number": "NX-2015-88821",
        "load_dts": ts(0),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    {
        "mrid": "CE-LN-002",
        "name": "Cable_Beta_to_JP1",
        "equipment_type": "ACLineSegment",
        "base_voltage_kv": 11.0,
        "in_service": True,
        "asset_status": "InService",
        "manufacturer": "Prysmian",
        "model": "XLPE-240",
        "serial_number": "PR-2019-33210",
        "load_dts": ts(0),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    # Transformer — INSERT
    {
        "mrid": "CE-TX-001",
        "name": "Transformer_Alpha_Main",
        "equipment_type": "PowerTransformer",
        "base_voltage_kv": 33.0,
        "in_service": True,
        "asset_status": "InService",
        "manufacturer": "Siemens",
        "model": "3AT3",
        "serial_number": "SI-2010-00123",
        "load_dts": ts(0),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    # ── REPAIR SCENARIO: swap Switch_Alpha_Feeder7 ──────────────────────────
    # Step 1: Original switch goes out of service (UPDATE)
    {
        "mrid": "CE-SW-001",
        "name": "Switch_Alpha_Feeder7",
        "equipment_type": "LoadBreakSwitch",
        "base_voltage_kv": 11.0,
        "in_service": False,
        "asset_status": "OutOfService",
        "manufacturer": "ABB",
        "model": "OVB-12",
        "serial_number": "ABB-2018-00441",
        "load_dts": ts(90),
        "record_source": record_source(),
        "cdc_flag": "U",
    },
    # Step 2: Replacement switch arrives and is installed (INSERT)
    {
        "mrid": "CE-SW-002",
        "name": "Switch_Alpha_Feeder7_New",
        "equipment_type": "LoadBreakSwitch",
        "base_voltage_kv": 11.0,
        "in_service": False,
        "asset_status": "Commissioned",
        "manufacturer": "Schneider",
        "model": "Flusarc-M",
        "serial_number": "SE-2024-00887",
        "load_dts": ts(120),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    # Step 3: Old switch physically removed (DELETE)
    {
        "mrid": "CE-SW-001",
        "name": "Switch_Alpha_Feeder7",
        "equipment_type": "LoadBreakSwitch",
        "base_voltage_kv": 11.0,
        "in_service": False,
        "asset_status": "Retired",
        "manufacturer": "ABB",
        "model": "OVB-12",
        "serial_number": "ABB-2018-00441",
        "load_dts": ts(150),
        "record_source": record_source(),
        "cdc_flag": "D",
    },
    # Step 4: New switch put in service (UPDATE)
    {
        "mrid": "CE-SW-002",
        "name": "Switch_Alpha_Feeder7_New",
        "equipment_type": "LoadBreakSwitch",
        "base_voltage_kv": 11.0,
        "in_service": True,
        "asset_status": "InService",
        "manufacturer": "Schneider",
        "model": "Flusarc-M",
        "serial_number": "SE-2024-00887",
        "load_dts": ts(180),
        "record_source": record_source(),
        "cdc_flag": "U",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# TERMINALS  (connect ConductingEquipment to ConnectivityNodes)
# ─────────────────────────────────────────────────────────────────────────────
terminals = [
    # Initial wiring: Switch CE-SW-001 connects CN-001 ↔ CN-002
    {
        "mrid": "TM-001",
        "name": "T1_SW001",
        "conducting_equipment_mrid": "CE-SW-001",
        "connectivity_node_mrid": "CN-001",
        "sequence_number": 1,
        "phases": "ABC",
        "connected": True,
        "load_dts": ts(0),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    {
        "mrid": "TM-002",
        "name": "T2_SW001",
        "conducting_equipment_mrid": "CE-SW-001",
        "connectivity_node_mrid": "CN-002",
        "sequence_number": 2,
        "phases": "ABC",
        "connected": True,
        "load_dts": ts(0),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    # Cable CE-LN-001: CN-002 → CN-003
    {
        "mrid": "TM-003",
        "name": "T1_LN001",
        "conducting_equipment_mrid": "CE-LN-001",
        "connectivity_node_mrid": "CN-002",
        "sequence_number": 1,
        "phases": "ABC",
        "connected": True,
        "load_dts": ts(0),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    {
        "mrid": "TM-004",
        "name": "T2_LN001",
        "conducting_equipment_mrid": "CE-LN-001",
        "connectivity_node_mrid": "CN-003",
        "sequence_number": 2,
        "phases": "ABC",
        "connected": True,
        "load_dts": ts(0),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    # Cable CE-LN-002: CN-003 → CN-004
    {
        "mrid": "TM-005",
        "name": "T1_LN002",
        "conducting_equipment_mrid": "CE-LN-002",
        "connectivity_node_mrid": "CN-003",
        "sequence_number": 1,
        "phases": "ABC",
        "connected": True,
        "load_dts": ts(0),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    {
        "mrid": "TM-006",
        "name": "T2_LN002",
        "conducting_equipment_mrid": "CE-LN-002",
        "connectivity_node_mrid": "CN-004",
        "sequence_number": 2,
        "phases": "ABC",
        "connected": True,
        "load_dts": ts(0),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    # Transformer CE-TX-001: CN-001
    {
        "mrid": "TM-007",
        "name": "T1_TX001",
        "conducting_equipment_mrid": "CE-TX-001",
        "connectivity_node_mrid": "CN-001",
        "sequence_number": 1,
        "phases": "ABC",
        "connected": True,
        "load_dts": ts(0),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    # ── REPAIR: Disconnect old switch terminals (UPDATE connected=False) ──
    {
        "mrid": "TM-001",
        "name": "T1_SW001",
        "conducting_equipment_mrid": "CE-SW-001",
        "connectivity_node_mrid": "CN-001",
        "sequence_number": 1,
        "phases": "ABC",
        "connected": False,
        "load_dts": ts(90),
        "record_source": record_source(),
        "cdc_flag": "U",
    },
    {
        "mrid": "TM-002",
        "name": "T2_SW001",
        "conducting_equipment_mrid": "CE-SW-001",
        "connectivity_node_mrid": "CN-002",
        "sequence_number": 2,
        "phases": "ABC",
        "connected": False,
        "load_dts": ts(90),
        "record_source": record_source(),
        "cdc_flag": "U",
    },
    # New switch terminals connected to same nodes (INSERT)
    {
        "mrid": "TM-008",
        "name": "T1_SW002",
        "conducting_equipment_mrid": "CE-SW-002",
        "connectivity_node_mrid": "CN-001",
        "sequence_number": 1,
        "phases": "ABC",
        "connected": True,
        "load_dts": ts(120),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    {
        "mrid": "TM-009",
        "name": "T2_SW002",
        "conducting_equipment_mrid": "CE-SW-002",
        "connectivity_node_mrid": "CN-002",
        "sequence_number": 2,
        "phases": "ABC",
        "connected": True,
        "load_dts": ts(120),
        "record_source": record_source(),
        "cdc_flag": "I",
    },
    # Delete old terminals when switch is retired (DELETE)
    {
        "mrid": "TM-001",
        "name": "T1_SW001",
        "conducting_equipment_mrid": "CE-SW-001",
        "connectivity_node_mrid": "CN-001",
        "sequence_number": 1,
        "phases": "ABC",
        "connected": False,
        "load_dts": ts(150),
        "record_source": record_source(),
        "cdc_flag": "D",
    },
    {
        "mrid": "TM-002",
        "name": "T2_SW001",
        "conducting_equipment_mrid": "CE-SW-001",
        "connectivity_node_mrid": "CN-002",
        "sequence_number": 2,
        "phases": "ABC",
        "connected": False,
        "load_dts": ts(150),
        "record_source": record_source(),
        "cdc_flag": "D",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# WRITE TO CSV (Bronze landing files)
# ─────────────────────────────────────────────────────────────────────────────
datasets = {
    "connectivity_nodes": connectivity_nodes,
    "conducting_equipment": conducting_equipment,
    "terminals": terminals,
}
catalog = "edh_unreg_silver_dev_st"
bronze_db = "bronze"


class DummyDataGenerator:
    """Generate and insert dummy bronze data for initial load and eff_sat updates."""

    def __init__(self, catalog: str = catalog, bronze_db: str = bronze_db):
        self.catalog = catalog
        self.bronze_db = bronze_db
        self.datasets: dict[str, list[dict[str, Any]]] = datasets

    def create_schema(self, name: str | None = None) -> None:
        schema_name = name or self.bronze_db
        spark.sql(f"use catalog {self.catalog};")
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {self.catalog}.{schema_name};")
        print(f"✅ Schema {self.catalog}.{schema_name} created or already exists.")

    def insert_initial_data_for_table(self, table_name: str) -> None:
        """Overwrite one bronze table with its initial dummy dataset."""
        if table_name not in self.datasets:
            available = ", ".join(sorted(self.datasets.keys()))
            raise ValueError(
                f"Unknown table '{table_name}'. Available tables: {available}"
            )

        self.create_schema()
        data = self.datasets[table_name]
        target_table = f"{self.catalog}.{self.bronze_db}.{table_name}"
        df = spark.createDataFrame(data).withColumn("load_dts", F.current_timestamp())
        df.write.mode("overwrite").format("delta").saveAsTable(target_table)
        print(
            f"✅ Written dataset '{table_name}' to {target_table} with {len(data)} records."
        )

    def insert_initial_data_all_tables(self) -> None:
        """Overwrite all bronze source tables with initial dummy datasets."""
        for table_name in self.datasets:
            self.insert_initial_data_for_table(table_name)

    @staticmethod
    def build_eff_sat_terminal_update_events(offset_minutes: int = 300) -> list[dict]:
        """Create update events that trigger a new effective-satellite state.

        We keep the same terminal business key (mrid) and change relationship keys
        (conducting_equipment_mrid/connectivity_node_mrid) so
        `eff_sat_terminal_equipment_node` can close the previous state and open a new one.
        """
        return [
            {
                "mrid": "TM-008",
                "name": "T1_SW002",
                "conducting_equipment_mrid": "CE-SW-002",
                "connectivity_node_mrid": "CN-004",
                "sequence_number": 1,
                "phases": "ABC",
                "connected": True,
                "load_dts": ts(offset_minutes),
                "record_source": record_source(),
                "cdc_flag": "U",
            },
            {
                "mrid": "TM-009",
                "name": "T2_SW002",
                "conducting_equipment_mrid": "CE-SW-002",
                "connectivity_node_mrid": "CN-003",
                "sequence_number": 2,
                "phases": "ABC",
                "connected": True,
                "load_dts": ts(offset_minutes),
                "record_source": record_source(),
                "cdc_flag": "U",
            },
        ]

    def insert_eff_sat_updates(self, offset_minutes: int = 300) -> None:
        """Append effective-satellite update rows into the bronze terminals table."""
        self.create_schema()
        update_events = self.build_eff_sat_terminal_update_events(
            offset_minutes=offset_minutes
        )
        table_name = f"{self.catalog}.{self.bronze_db}.terminals"

        df = spark.createDataFrame(update_events).withColumn(
            "load_dts", F.current_timestamp()
        )
        df.write.mode("append").format("delta").saveAsTable(table_name)
        print(
            f"✅ Appended {len(update_events)} effective-satellite update rows to {table_name}."
        )
        print("➡️ Next step: run dbt for staging and effective satellite models.")
        print(
            "   Example: dbt run --profiles-dir . --select stg_terminals eff_sat_terminal_equipment_node"
        )


def create_schema(name: str, catalog: str):
    """Backward-compatible wrapper for existing callers."""
    DummyDataGenerator(catalog=catalog, bronze_db=name).create_schema(name=name)


def create_datasets(datasets: dict, catalog: str, bronze_db: str):
    """Backward-compatible wrapper for existing callers."""
    generator = DummyDataGenerator(catalog=catalog, bronze_db=bronze_db)
    generator.datasets = datasets
    generator.insert_initial_data_all_tables()


def build_eff_sat_terminal_update_events(offset_minutes: int = 300) -> list[dict]:
    """Backward-compatible wrapper for existing callers."""
    return DummyDataGenerator.build_eff_sat_terminal_update_events(
        offset_minutes=offset_minutes
    )


def insert_eff_sat_updates(
    catalog: str, bronze_db: str, offset_minutes: int = 300
) -> None:
    """Backward-compatible wrapper for existing callers."""
    DummyDataGenerator(catalog=catalog, bronze_db=bronze_db).insert_eff_sat_updates(
        offset_minutes=offset_minutes
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate initial bronze dummy data or append effective-sat updates."
    )
    parser.add_argument(
        "--mode",
        choices=["init", "eff-sat-update"],
        default="init",
        help="init: overwrite all bronze datasets, eff-sat-update: append update rows to terminals",
    )
    parser.add_argument("--catalog", default=catalog, help="Databricks catalog name")
    parser.add_argument("--bronze-db", default=bronze_db, help="Bronze schema name")
    parser.add_argument(
        "--offset-minutes",
        type=int,
        default=300,
        help="Event timestamp offset from BASE_DATE for update events",
    )
    args = parser.parse_args()
    generator = DummyDataGenerator(catalog=args.catalog, bronze_db=args.bronze_db)

    if args.mode == "init":
        generator.insert_initial_data_all_tables()
    else:
        generator.insert_eff_sat_updates(offset_minutes=args.offset_minutes)
