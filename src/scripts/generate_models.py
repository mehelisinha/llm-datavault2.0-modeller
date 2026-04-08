#!/usr/bin/env python3
"""
Script to generate Data Vault models using the DV generator classes.
"""

import os
import sys

# Add the src directory to the path so we can import dv
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dv.config_generator import DVConfigGenerator
from dv.generator import DVGenerator
from dv.hub import Hub
from dv.link import Link
from dv.satellite import Satellite


def main():
    """Main function to generate sample Data Vault models."""

    # Initialize generator
    generator = DVGenerator(base_path="models")

    # Define hubs
    hubs = [
        Hub(
            name="hub_conducting_equipment",
            source_models=["stg_conducting_equipment", "stg_terminals"],
            src_pk="HK_CONDUCTING_EQUIPMENT",
            src_nk="mrid",
        ),
        Hub(
            name="hub_connectivity_node",
            source_models=["stg_connectivity_nodes"],
            src_pk="HK_CONNECTIVITY_NODE",
            src_nk="mrid",
        ),
    ]

    # Define satellites
    satellites = [
        Satellite(
            name="sat_conducting_equipment_details",
            source_models=["stg_conducting_equipment"],
            src_pk="HK_CONDUCTING_EQUIPMENT",
            src_hashdiff="HD_CONDUCTING_EQUIPMENT_S",
            src_payload=[
                "name",
                "equipment_type",
                "base_voltage_kv",
                "in_service",
                "asset_status",
                "manufacturer",
                "model",
                "serial_number",
            ],
        ),
        Satellite(
            name="sat_connectivity_node_details",
            source_models=["stg_connectivity_nodes"],
            src_pk="HK_CONNECTIVITY_NODE",
            src_hashdiff="HD_CONNECTIVITY_NODE_S",
            src_payload=["name", "node_type", "nominal_voltage", "is_connected"],
        ),
    ]

    # Define links
    links = [
        Link(
            name="lnk_terminal_equipment_node",
            source_models=["stg_terminals"],
            src_pk="HK_TERMINAL_EQUIPMENT_NODE_L",
            src_fk=["HK_CONDUCTING_EQUIPMENT", "HK_CONNECTIVITY_NODE"],
        )
    ]

    # Generate all components
    all_components = hubs + satellites + links
    generator.generate_components(all_components, overwrite=True)

    # Generate YAML model configuration pattern metadata for each component
    config_generator = DVConfigGenerator(base_models_path="models")
    yaml_paths = config_generator.generate_all_yaml(all_components)
    print(f"Generated YAML metadata: {yaml_paths}")

    print("Data Vault models generated successfully!")


if __name__ == "__main__":
    main()
