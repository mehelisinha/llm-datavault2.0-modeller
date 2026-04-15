"""
IEC61968 CIM Dummy Data Generator
Simulates a grid asset SWAP scenario (Insert → Update → Delete)
Entities: Terminal, ConnectivityNode, ConductingEquipment
"""

from datetime import datetime, timedelta

import pyspark.sql.functions as F

# from faker import Faker
from src.utils.spark import spark

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


def create_schema(name: str, catalog: str):
    spark.sql(f"use catalog {catalog};")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{name};")
    print(f"✅ Schema {catalog}.{name} created or already exists.")


def create_datasets(datasets: dict, catalog: str, bronze_db: str):
    create_schema(bronze_db, catalog)
    for name, data in datasets.items():
        df = spark.createDataFrame(data).withColumn("load_dts", F.current_timestamp())
        df.write.mode("overwrite").format("delta").saveAsTable(f"{catalog}.{bronze_db}.{name}")

        print(
            f"✅ Written dataset '{name}' to {catalog}.{bronze_db}.{name} with {len(data)} records."
        )
