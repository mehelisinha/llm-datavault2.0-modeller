from logging import Logger
from pathlib import Path

from dv_components.components.TBD_model import DVComponentModel, DVProjectModel
from dv_components.TBD_configs.TBD_base_yml_generator import BaseYmlGenerator

from shared.src.infra.file_manager.concrete.yml_handler import YamlHandler


class DBTProject(BaseYmlGenerator):
    """Generates dbt_project.yml configuration from a DVProjectModel."""

    _INCREMENTAL_CONFIG = {
        "+materialized": "incremental",
        "+incremental-strategy": "merge",
    }
    # Fields that are internal to DWA and must not appear in dbt_project.yml
    _INTERNAL_FIELDS = {
        "dv_type",
        "system",
        "catalog",
        "stg_schema",
        "raw_vault_schema",
        "business_vault_schema",
    }

    def __init__(self, model: DVComponentModel, logger: Logger):
        super().__init__(logger=logger)
        self.model = model
        if not isinstance(model.meta, DVProjectModel):
            raise ValueError(f"Expected DVProjectModel, got {type(model.meta)}")
        self.proj_model: DVProjectModel = model.meta

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> str:
        """Return the dbt_project.yml content as a YAML string."""
        return super().generate()

    def write(
        self,
        project_path: str,
        yaml_content: str | None = None,
    ):
        if yaml_content is not None:
            out_path = Path(project_path) / self._relative_output_path()
            return self._write_content(out_path, yaml_content)
        return super().write(output_path=project_path)

    # ------------------------------------------------------------------
    # Project dict assembly
    # ------------------------------------------------------------------

    def _build_yaml_dict(self) -> dict:
        params = self._get_filtered_params()
        # vars keys are user-defined (e.g. load_date) — must NOT be kebab-cased
        vars_val = params.pop("vars", None)

        project: dict = {
            "name": self.model.name,
            **YamlHandler.to_kebab_case(params),
        }
        if vars_val:
            project["vars"] = vars_val
        project["models"] = self._get_config()
        return project

    def _relative_output_path(self) -> Path:
        return Path("dbt_project.yml")

    def _get_filtered_params(self) -> dict:
        return {
            k: v
            for k, v in self.model.meta.model_dump().items()
            if k not in self._INTERNAL_FIELDS and v is not None
        }

    # ------------------------------------------------------------------
    # Model config
    # ------------------------------------------------------------------

    def _get_config(self) -> dict:
        config = {}
        if self.proj_model.stg_schema:
            config["staging"] = self._staging_config()
        if self.proj_model.raw_vault_schema:
            config["raw_vault"] = self._raw_vault_config()
        if self.proj_model.business_vault_schema:
            config["business_vault"] = self._business_vault_config()
        return {self.model.name: config}

    def _staging_config(self) -> dict:
        config: dict = {
            "+schema": self.proj_model.stg_schema,
            "+materialized": "view",
            "+tags": ["staging"],
        }
        if self.proj_model.catalog:
            config["+catalog"] = self.proj_model.catalog
        return config

    def _raw_vault_config(self) -> dict:
        sat_config = self._INCREMENTAL_CONFIG.copy()
        config: dict = {
            "+schema": self.proj_model.raw_vault_schema,
            "+tags": ["raw_vault"],
            "hubs": self._INCREMENTAL_CONFIG.copy(),
            "links": self._INCREMENTAL_CONFIG.copy(),
            "satellites": sat_config,
            "eff_sats": sat_config.copy(),
        }
        if self.proj_model.catalog:
            config["+catalog"] = self.proj_model.catalog
        return config

    def _business_vault_config(self) -> dict:
        config: dict = {
            "+schema": self.proj_model.business_vault_schema,
            "+materialized": "table",
            "+tags": ["business_vault"],
        }
        if self.proj_model.catalog:
            config["+catalog"] = self.proj_model.catalog
        return config


if __name__ == "__main__":
    from shared.src.logger.default_logger import default_logger

    link_model = DVProjectModel(
        system="TEST",
        profile="iec_dv2_databricks",
        model_paths=["models"],
        analysis_paths=["analyses"],
        test_paths=["tests"],
        seed_paths=None,
        macro_paths=None,
        snapshot_paths=None,
        target_path="target",
        clean_targets=None,
        vars={
            "load_date": "{{ run_started_at.strftime('%Y-%m-%d') }}",
            "record_source": "IEC61968_CIM",
        },
        stg_schema="poc_staging",
        raw_vault_schema="poc_raw_vault",
        business_vault_schema="poc_sbusiness_vault",
    )

    model = DVComponentModel(name="iec_dv2", meta=link_model)
    dbt_project = DBTProject(model=model, logger=default_logger)
    wml = dbt_project.generate()
