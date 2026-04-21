"""
Metadata — reads the DWA YAML configuration and produces DVComponentModel objects
ready to be handed to DBTBuilder for SQL and config generation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from src.dv_components.models.model import (
    DbtPackage,
    DVComponentModel,
    DVPackagesModel,
    DVProjectModel,
    EffSatModel,
    HubModel,
    LinkModel,
    SatelliteModel,
    StagingModel,
)

# Convention defaults — can be overridden by subclassing
_DEFAULT_LDTS = "LOAD_DATE"


class Metadata:
    """
    Reads a DWA YAML metadata file and produces typed ``DVComponentModel``
    objects for every Data Vault component defined within.

    Supported sections:  hubs · links · satellites · eff_sats

    Usage::

        meta = Metadata("path/to/iec_cim_metadata.yaml")
        all_models = meta.get_all_component_models()
        project    = meta.get_project_model()
    """

    def __init__(self, yaml_path: str | Path):
        self._path = Path(yaml_path)
        self._config: Dict[str, Any] = self._load()

    # ------------------------------------------------------------------
    # System info
    # ------------------------------------------------------------------

    @property
    def system(self) -> Dict[str, Any]:
        return self._config["system"]

    @property
    def system_name(self) -> str:
        return self.system["system_name"]

    @property
    def _record_source(self) -> str:
        return "RECORD_SOURCE"
        # return self.system.get("record_source", self.system_name)

    @property
    def packages(self) -> list[dict]:
        """Return the list of dbt package entries (package + version)."""
        return self._config.get("packages", [])

    def get_packages_model(self) -> DVPackagesModel:
        """Return a DVPackagesModel from metadata, falling back to defaults."""
        raw = self._config.get("packages")
        if raw:
            return DVPackagesModel(packages=[DbtPackage(**p) for p in raw])
        return DVPackagesModel()

    # ------------------------------------------------------------------
    # Project model
    # ------------------------------------------------------------------

    def get_project_model(self) -> DVComponentModel:
        """Return a DVComponentModel wrapping a DVProjectModel for dbt_project.yml."""
        profile = f"{self.system_name.lower()}_databricks"
        proj = DVProjectModel(
            system=self.system_name,
            profile=profile,
            model_paths=["models"],
            analysis_paths=["analyses"],
            test_paths=["tests"],
            seed_paths=["data/seeds"],
            macro_paths=["macros"],
            snapshot_paths=["snapshots"],
            target_path="target",
            clean_targets=["target", "dbt_packages"],
            vars={
                "load_date": "{{ run_started_at.strftime('%Y-%m-%d') }}",
                "record_source": self._record_source,
            },
            catalog=self.system.get("catalog"),
            stg_schema="staging",
            raw_vault_schema="raw_vault",
            business_vault_schema="business_vault",
        )
        project_name = self.system_name.lower()
        return DVComponentModel(name=project_name, meta=proj)

    # ------------------------------------------------------------------
    # Hubs
    # ------------------------------------------------------------------

    def get_hub_models(self) -> List[DVComponentModel]:
        """Return one DVComponentModel per hub definition."""
        models: List[DVComponentModel] = []
        for entry in self._config.get("hubs", []):
            self._require_keys(
                entry, {"name", "staging_model", "business_key", "hash_key"}, "hub"
            )
            hub = HubModel(
                source_model=[entry["staging_model"]],
                src_pk=entry["hash_key"],
                src_nk=entry["business_key"],
                src_ldts=_DEFAULT_LDTS,
                src_source=self._record_source,
            )
            models.append(DVComponentModel(name=entry["name"], meta=hub))
        return models

    # ------------------------------------------------------------------
    # Links
    # ------------------------------------------------------------------

    def get_link_models(self) -> List[DVComponentModel]:
        """Return one DVComponentModel per link definition."""
        models: List[DVComponentModel] = []
        for entry in self._config.get("links", []):
            self._require_keys(
                entry, {"name", "source_model", "hash_key", "fk_columns"}, "link"
            )
            link = LinkModel(
                source_model=[entry["source_model"]],
                src_pk=entry["hash_key"],
                src_fk=list(entry["fk_columns"]),
                src_ldts=_DEFAULT_LDTS,
                src_source=self._record_source,
            )
            models.append(DVComponentModel(name=entry["name"], meta=link))
        return models

    # ------------------------------------------------------------------
    # Satellites
    # ------------------------------------------------------------------

    def get_satellite_models(self) -> List[DVComponentModel]:
        """Return one DVComponentModel per satellite definition."""
        models: List[DVComponentModel] = []
        for entry in self._config.get("satellites", []):
            self._require_keys(
                entry,
                {"name", "source_model", "hash_key", "hashdiff", "payload"},
                "satellite",
            )
            sat = SatelliteModel(
                source_model=[entry["source_model"]],
                src_pk=entry["hash_key"],
                src_hashdiff=entry["hashdiff"],
                src_payload=list(entry["payload"]),
                src_eff=entry.get("effective_from"),
                src_ldts=_DEFAULT_LDTS,
                src_source=self._record_source,
            )
            models.append(DVComponentModel(name=entry["name"], meta=sat))
        return models

    # ------------------------------------------------------------------
    # Effectivity Satellites
    # ------------------------------------------------------------------

    def get_eff_sat_models(self) -> List[DVComponentModel]:
        """Return one DVComponentModel per eff_sat definition."""
        models: List[DVComponentModel] = []
        for entry in self._config.get("eff_sats", []):
            self._require_keys(
                entry,
                {
                    "name",
                    "source_model",
                    "hash_key",
                    "driving_fk",
                    "secondary_fk",
                    "effective_from",
                    "start_date",
                    "end_date",
                },
                "eff_sat",
            )
            sfk = entry["secondary_fk"]
            eff = EffSatModel(
                source_model=[entry["source_model"]],
                src_pk=entry["hash_key"],
                src_dfk=entry["driving_fk"],
                src_sfk=sfk if isinstance(sfk, list) else [sfk],
                src_eff=entry["effective_from"],
                src_end_date=entry["end_date"],
                src_start_date=entry["start_date"],
                src_ldts=_DEFAULT_LDTS,
                src_source=self._record_source,
            )
            models.append(DVComponentModel(name=entry["name"], meta=eff))
        return models

    # ------------------------------------------------------------------
    # Staging
    # ------------------------------------------------------------------

    def get_staging_models(self) -> List[DVComponentModel]:
        """Return one DVComponentModel per staging definition."""
        models: List[DVComponentModel] = []
        for entry in self._config.get("staging", []):
            self._require_keys(entry, {"name", "source_table"}, "staging")
            derived_columns = [
                {"column_name": col, "expr": expr, "order": i}
                for i, (col, expr) in enumerate(
                    entry.get("derived_columns", {}).items()
                )
            ]
            hashed_columns = []
            for col, value in entry.get("hashed_columns", {}).items():
                if isinstance(value, list):
                    hashed_columns.append(
                        {"column_name": col, "is_hashdiff": False, "columns": value}
                    )
                else:
                    hashed_columns.append(
                        {
                            "column_name": col,
                            "is_hashdiff": value.get("is_hashdiff", False),
                            "columns": value.get("columns", []),
                        }
                    )
            ranked_columns = [
                {
                    "column_name": col,
                    "partition_by": v["partition_by"],
                    "order_by": v["order_by"],
                    "dense_rank": v.get("dense_rank", False),
                }
                for col, v in entry.get("ranked_columns", {}).items()
            ]
            source = entry["source_table"]
            stg = StagingModel(
                source_model=[source] if isinstance(source, str) else source,
                source_name=self.system.get("schema"),
                derived_columns=derived_columns,
                hashed_columns=hashed_columns,
                ranked_columns=ranked_columns,
            )
            models.append(DVComponentModel(name=entry["name"], meta=stg))
        return models

    # ------------------------------------------------------------------
    # All components (in dependency order)
    # ------------------------------------------------------------------

    def get_all_component_models(self) -> List[DVComponentModel]:
        """Return all component models in dependency order: staging → hubs → links → sats → eff_sats."""
        return (
            self.get_staging_models()
            + self.get_hub_models()
            + self.get_link_models()
            + self.get_satellite_models()
            + self.get_eff_sat_models()
        )

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------

    def _load(self) -> Dict[str, Any]:
        if not self._path.exists():
            raise FileNotFoundError(f"Metadata config not found: {self._path}")
        with self._path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        self._validate_top_level(data)
        return data

    @staticmethod
    def _validate_top_level(data: Dict[str, Any]) -> None:
        required = {"system", "hubs"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(
                f"Metadata config is missing required top-level keys: {missing}"
            )

    @staticmethod
    def _require_keys(entry: Dict[str, Any], required: set, kind: str) -> None:
        missing = required - set(entry.keys())
        if missing:
            name = entry.get("name", "<unnamed>")
            raise ValueError(
                f"Metadata {kind} '{name}' is missing required keys: {missing}"
            )
