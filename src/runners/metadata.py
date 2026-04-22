"""
Metadata — reads the DWA YAML configuration and produces DVComponentModel objects
ready to be handed to DBTBuilder for SQL and config generation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, TypeVar

import yaml

from src.dv_components.pydantic_model.discriminator import DvModels
from src.dv_components.pydantic_model.proj_level.dv_yml import (
    DbtPackage,
    DVPackagesModel,
    DVProfileOutputModel,
    DvProfilesModel,
    DVProjectModel,
    DvSourceModel,
    TableConfig,
)
from src.dv_components.pydantic_model.sql.macro import MacroModel
from src.dv_components.pydantic_model.sql.raw_vaul import (
    EffSatModel,
    HubModel,
    LinkModel,
    SatelliteModel,
)
from src.dv_components.pydantic_model.sql.staging import (
    DerivedColumnInternal,
    HashedColumns,
    RankedColumns,
    StagingModel,
)
from src.utils.dv_schemas import DvSchemaNames
from src.utils.system_name import SystemNameCleaner

T = TypeVar("T")


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

    def __init__(self, yaml_path: str | Path) -> None:
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
    def _clean_name(self) -> str:
        """System name sanitised for use in identifiers (lowercase, no special chars)."""
        return SystemNameCleaner.clean(self.system_name)

    @property
    def _schema_names(self) -> DvSchemaNames:
        """Schema name generator for this system following ``{clean_name}_{layer}``."""
        return DvSchemaNames(self.system_name)

    @property
    def _record_source_col(self) -> str:
        """Staging column name that carries the record-source value (for ``src_source``)."""
        return self.system.get("record_source_column", "RECORD_SOURCE")

    @property
    def _record_source_value(self) -> str:
        """Actual record-source identifier stamped into rows (used in dbt project vars)."""
        return self.system.get("record_source", self.system_name)

    @property
    def _default_ldts(self) -> str:
        """Load-date-timestamp column name, read from YAML with fallback to 'LOAD_DATE'."""
        return self.system.get("default_ldts", "LOAD_DATE")

    @property
    def packages(self) -> list[dict[str, Any]]:
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

    def get_project_model(self) -> DVProjectModel:
        """Return a DVProjectModel for dbt_project.yml."""
        schemas = self._schema_names
        return DVProjectModel(
            name=self._clean_name,
            profile=f"{self._clean_name}_databricks",
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
                "record_source": self._record_source_value,
            },
            catalog=self.system["catalog"],
            stg_schema=schemas.staging,
            raw_vault_schema=schemas.raw_vault,
            business_vault_schema=schemas.business_vault,
        )

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def get_sources_model(self) -> DvSourceModel:
        """Return a DvSourceModel for sources.yml, based on staging entries."""
        system = self.system
        return DvSourceModel(
            name=system.get("schema"),
            database=system["catalog"],
            schema=system.get("schema"),
            tables=[
                TableConfig(name=entry["source_table"])
                for entry in self._config.get("staging", [])
                if "source_table" in entry
            ],
        )

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    def get_profiles_model(self) -> DvProfilesModel:
        """Return a DvProfilesModel for profiles.yml."""
        return DvProfilesModel(
            name=f"{self._clean_name}_databricks",
            target="dev",
            outputs={
                "dev": DVProfileOutputModel(
                    type="databricks",
                    catalog=self.system["catalog"],
                    schema=self._schema_names.raw_vault,
                )
            },
        )

    # ------------------------------------------------------------------
    # Hubs
    # ------------------------------------------------------------------

    def get_hub_models(self) -> List[HubModel]:
        """Return all data vault HubModel per hub definition."""
        return self._build_models(
            section="hubs",
            required_keys={"name", "staging_model", "business_key", "hash_key"},
            kind="hub",
            builder=lambda e: HubModel(
                name=e["name"],
                source_model=[e["staging_model"]],
                src_pk=e["hash_key"],
                src_nk=e["business_key"],
                src_ldts=self._default_ldts,
                src_source=self._record_source_col,
            ),
        )

    # ------------------------------------------------------------------
    # Links
    # ------------------------------------------------------------------

    def get_link_models(self) -> List[LinkModel]:
        """Return all data vault LinkModel per link definition."""
        return self._build_models(
            section="links",
            required_keys={"name", "source_model", "hash_key", "fk_columns"},
            kind="link",
            builder=lambda e: LinkModel(
                name=e["name"],
                source_model=[e["source_model"]],
                src_pk=e["hash_key"],
                src_fk=list(e["fk_columns"]),
                src_ldts=self._default_ldts,
                src_source=self._record_source_col,
            ),
        )

    # ------------------------------------------------------------------
    # Satellites
    # ------------------------------------------------------------------

    def get_satellite_models(self) -> List[SatelliteModel]:
        """Return all data vault SatelliteModel per satellite definition."""
        return self._build_models(
            section="satellites",
            required_keys={"name", "source_model", "hash_key", "hashdiff", "payload"},
            kind="satellite",
            builder=lambda e: SatelliteModel(
                name=e["name"],
                source_model=[e["source_model"]],
                src_pk=e["hash_key"],
                src_hashdiff=e["hashdiff"],
                src_payload=list(e["payload"]),
                src_eff=e.get("effective_from"),
                src_ldts=self._default_ldts,
                src_source=self._record_source_col,
            ),
        )

    # ------------------------------------------------------------------
    # Effectivity Satellites
    # ------------------------------------------------------------------

    def get_eff_sat_models(self) -> List[EffSatModel]:
        """Return all data vault EffSatModel per eff_sat definition."""
        return self._build_models(
            section="eff_sats",
            required_keys={
                "name",
                "source_model",
                "hash_key",
                "driving_fk",
                "secondary_fk",
                "effective_from",
                "start_date",
                "end_date",
            },
            kind="eff_sat",
            builder=self._build_eff_sat,
        )

    def _build_eff_sat(self, entry: Dict[str, Any]) -> EffSatModel:
        sfk = entry["secondary_fk"]
        return EffSatModel(
            name=entry["name"],
            source_model=[entry["source_model"]],
            src_pk=entry["hash_key"],
            src_dfk=entry["driving_fk"],
            src_sfk=sfk if isinstance(sfk, list) else [sfk],
            src_eff=entry["effective_from"],
            src_end_date=entry["end_date"],
            src_start_date=entry["start_date"],
            src_ldts=self._default_ldts,
            src_source=self._record_source_col,
        )

    # ------------------------------------------------------------------
    # Macros
    # ------------------------------------------------------------------
    def get_macro_models(self) -> List[MacroModel]:
        """Return all data vault MacroModel per macro definition."""
        return self._build_models(
            section="macros",
            required_keys={"name"},
            kind="macro",
            builder=self._build_macro,
        )

    def _build_macro(self, entry: Dict[str, Any]) -> MacroModel:
        return MacroModel(
            name=entry["name"],
            description=entry.get("description", f"Macro {entry['name']}"),
        )

    # ------------------------------------------------------------------
    # Staging
    # ------------------------------------------------------------------

    def get_staging_models(self) -> List[StagingModel]:
        """Return all data vault StagingModel per staging definition."""
        return self._build_models(
            section="staging",
            required_keys={"name", "source_table"},
            kind="staging",
            builder=self._build_staging,
        )

    def _build_staging(self, entry: Dict[str, Any]) -> StagingModel:
        derived_columns = [
            DerivedColumnInternal(column_name=col, expr=expr, order=i)
            for i, (col, expr) in enumerate(entry.get("derived_columns", {}).items())
        ]
        hashed_columns = [
            HashedColumns(**self._parse_hashed_column(col, value))
            for col, value in entry.get("hashed_columns", {}).items()
        ]
        ranked_columns = [
            RankedColumns(
                column_name=col,
                partition_by=v["partition_by"],
                order_by=v["order_by"],
                dense_rank=v.get("dense_rank", False),
            )
            for col, v in entry.get("ranked_columns", {}).items()
        ]
        source = entry["source_table"]
        return StagingModel(
            name=entry["name"],
            source_model=[source] if isinstance(source, str) else source,
            source_name=self.system.get("schema"),
            derived_columns=derived_columns,
            hashed_columns=hashed_columns,
            ranked_columns=ranked_columns,
        )

    @staticmethod
    def _parse_hashed_column(
        col: str, value: list[str] | dict[str, Any]
    ) -> dict[str, Any]:
        """Normalise a ``hashed_columns`` entry into a flat dict for ``HashedColumns``."""
        if isinstance(value, list):
            return {"column_name": col, "is_hashdiff": False, "columns": value}
        return {
            "column_name": col,
            "is_hashdiff": value.get("is_hashdiff", False),
            "columns": value.get("columns", []),
        }

    # ------------------------------------------------------------------
    # All components (in dependency order)
    # ------------------------------------------------------------------

    def get_all_component_models(self) -> dict[str, list[DvModels]]:
        """Return all component models in dependency order: staging → hubs → links → sats → eff_sats."""
        return {
            "MCR": self.get_macro_models(),
            "STG": self.get_staging_models(),
            "HUB": self.get_hub_models(),
            "LNK": self.get_link_models(),
            "SAT": self.get_satellite_models(),
            "EFF": self.get_eff_sat_models(),
            "PRJ": [
                self.get_project_model(),
                self.get_packages_model(),
                self.get_sources_model(),
                self.get_profiles_model(),
            ],
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_models(
        self,
        section: str,
        required_keys: set[str],
        kind: str,
        builder: Callable[[Dict[str, Any]], T],
    ) -> List[T]:
        """Iterate a YAML *section*, validate required keys, and build typed models.

        Args:
            section:       Top-level YAML key (e.g. ``"hubs"``).
            required_keys: Keys that every entry in the section must contain.
            kind:          Human-readable label used in error messages.
            builder:       Callable that converts a raw ``dict`` entry into a typed model.

        Returns:
            List of typed model objects produced by *builder*.
        """
        models: List[T] = []
        for entry in self._config.get(section, []):
            self._require_keys(entry, required_keys, kind)
            models.append(builder(entry))
        return models

    def _load(self) -> Dict[str, Any]:
        if not self._path.exists():
            raise FileNotFoundError(f"Metadata config not found: {self._path}")
        with self._path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        self._validate_top_level(data)
        self._validate_system_keys(data["system"])
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
    def _validate_system_keys(system: Dict[str, Any]) -> None:
        """Fail early if critical system-level fields are absent."""
        required = {"system_name", "catalog"}
        missing = required - set(system.keys())
        if missing:
            raise ValueError(
                f"Metadata 'system' block is missing required keys: {missing}"
            )

    @staticmethod
    def _require_keys(entry: Dict[str, Any], required: set[str], kind: str) -> None:
        missing = required - set(entry.keys())
        if missing:
            name = entry.get("name", "<unnamed>")
            raise ValueError(
                f"Metadata {kind} '{name}' is missing required keys: {missing}"
            )


if __name__ == "__main__":
    from pathlib import Path

    yaml_path = Path(__file__).parents[2] / "poc" / "metadata" / "iec_cim_metadata.yaml"
    meta = Metadata(yaml_path)
    meta_models = meta.get_all_component_models()
    print(f"meta_models: ({meta_models}):")

    # print(f"System : {meta.system_name}  →  clean: {meta._clean_name}")
    # print(f"Schemas: staging={meta._schema_names.staging}")
    # print(f"         raw_vault={meta._schema_names.raw_vault}")
    # print(f"         business_vault={meta._schema_names.business_vault}")
    # print()

    # hubs = meta.get_hub_models()
    # print(f"Hubs ({len(hubs)}):")
    # for h in hubs:
    #     print(f"  {h.name}  pk={h.src_pk}  nk={h.src_nk}  source={h.source_model}")

    # links = meta.get_link_models()
    # print(f"\nLinks ({len(links)}):")
    # for lnk in links:
    #     print(f"  {lnk.name}  pk={lnk.src_pk}  fk={lnk.src_fk}")

    # sats = meta.get_satellite_models()
    # print(f"\nSatellites ({len(sats)}):")
    # for s in sats:
    #     print(f"  {s.name}  pk={s.src_pk}  hashdiff={s.src_hashdiff}")

    # eff_sats = meta.get_eff_sat_models()
    # print(f"\nEff Sats ({len(eff_sats)}):")
    # for e in eff_sats:
    #     print(f"  {e.name}  dfk={e.src_dfk}  sfk={e.src_sfk}")

    # staging = meta.get_staging_models()
    # print(f"\nStaging ({len(staging)}):")
    # for s in staging:
    #     print(f"  {s.name}  source={s.source_model}")

    # proj = meta.get_project_model()
    # print(f"\nProject  : name={proj.name}  profile={proj.profile}")
    # print(f"  stg_schema={proj.stg_schema}")
    # print(f"  raw_vault_schema={proj.raw_vault_schema}")
    # print(f"  business_vault_schema={proj.business_vault_schema}")
    # print(f"  vars={proj.vars}")
