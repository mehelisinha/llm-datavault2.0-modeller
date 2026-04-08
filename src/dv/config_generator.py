"""
Data Vault YAML configuration generator.

Generates dbt model metadata files for hub/link/satellite from Data Vault components.
"""

import os
from typing import Any, Dict, List, Optional

import yaml

from .hub import Hub
from .link import Link
from .satellite import Satellite


class DVConfigGenerator:
    """Generate YAML model metadata for Data Vault objects."""

    def __init__(self, base_models_path: str = "models"):
        self.base_models_path = base_models_path

    @staticmethod
    def _dump_yaml(data: Dict[str, Any]) -> str:
        return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)

    def _prepare_hub_metadata(self, hub: Hub, description: Optional[str] = None) -> Dict[str, Any]:
        return {
            "version": 2,
            "models": [
                {
                    "name": hub.name,
                    "description": description or f"Data Vault hub for {hub.name}",
                    "meta": {
                        "dv_type": "hub",
                        "source_models": hub.source_models,
                        "src_pk": hub.src_pk,
                        "src_nk": hub.src_nk,
                        "src_ldts": hub.src_ldts,
                        "src_source": hub.src_source,
                    },
                }
            ],
        }

    def _prepare_link_metadata(
        self, link: Link, description: Optional[str] = None
    ) -> Dict[str, Any]:
        return {
            "version": 2,
            "models": [
                {
                    "name": link.name,
                    "description": description or f"Data Vault link for {link.name}",
                    "meta": {
                        "dv_type": "link",
                        "source_models": link.source_models,
                        "src_pk": link.src_pk,
                        "src_fk": link.src_fk,
                        "src_ldts": link.src_ldts,
                        "src_source": link.src_source,
                    },
                }
            ],
        }

    def _prepare_sat_metadata(
        self, sat: Satellite, description: Optional[str] = None
    ) -> Dict[str, Any]:
        meta = {
            "dv_type": "satellite",
            "source_models": sat.source_models,
            "src_pk": sat.src_pk,
            "src_hashdiff": sat.src_hashdiff,
            "src_payload": sat.src_payload,
            "src_ldts": sat.src_ldts,
            "src_source": sat.src_source,
        }

        if sat.src_eff:
            meta["src_eff"] = sat.src_eff

        return {
            "version": 2,
            "models": [
                {
                    "name": sat.name,
                    "description": description or f"Data Vault satellite for {sat.name}",
                    "meta": meta,
                }
            ],
        }

    def _write_yaml(self, path: str, payload: Dict[str, Any]):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self._dump_yaml(payload))

    def generate_hub_yaml(
        self, hub: Hub, output_dir: Optional[str] = None, description: Optional[str] = None
    ) -> str:
        output_dir = output_dir or os.path.join(self.base_models_path, "raw_vault", "hubs")
        out_path = os.path.join(output_dir, f"{hub.name}.yml")
        payload = self._prepare_hub_metadata(hub, description)
        self._write_yaml(out_path, payload)
        return out_path

    def generate_link_yaml(
        self, link: Link, output_dir: Optional[str] = None, description: Optional[str] = None
    ) -> str:
        output_dir = output_dir or os.path.join(self.base_models_path, "raw_vault", "links")
        out_path = os.path.join(output_dir, f"{link.name}.yml")
        payload = self._prepare_link_metadata(link, description)
        self._write_yaml(out_path, payload)
        return out_path

    def generate_satellite_yaml(
        self, sat: Satellite, output_dir: Optional[str] = None, description: Optional[str] = None
    ) -> str:
        output_dir = output_dir or os.path.join(self.base_models_path, "raw_vault", "satellites")
        out_path = os.path.join(output_dir, f"{sat.name}.yml")
        payload = self._prepare_sat_metadata(sat, description)
        self._write_yaml(out_path, payload)
        return out_path

    def generate_all_yaml(
        self, components: List[Any], output_dir: Optional[str] = None
    ) -> List[str]:
        paths: List[str] = []

        for c in components:
            if isinstance(c, Hub):
                paths.append(self.generate_hub_yaml(c, output_dir))
            elif isinstance(c, Link):
                paths.append(self.generate_link_yaml(c, output_dir))
            elif isinstance(c, Satellite):
                paths.append(self.generate_satellite_yaml(c, output_dir))
            else:
                raise TypeError(f"Unsupported component type: {type(c)}")

        return paths
