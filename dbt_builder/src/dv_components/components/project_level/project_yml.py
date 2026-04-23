from logging import Logger

from shared.src.infra.file_manager.concrete.yml_handler import YamlHandler
from dbt_builder.src.dv_components.components.project_level.base import DVProjYmlBaseGenerator
from dbt_builder.src.dv_components.pydantic_model.proj_level.dv_yml import DVProjectModel


class ProjectComponent(DVProjYmlBaseGenerator):
    """Generates dbt_project.yml configuration from a DVProjectModel."""

    _INCREMENTAL_CONFIG = {
        "+materialized": "incremental",
        "+incremental_strategy": "merge",
    }
    # Fields that are internal to DWA and must not appear in dbt_project.yml
    _INTERNAL_FIELDS = {
        "dv_type",
        "system",
        "catalog",
        "stg_schema",
        "raw_vault_schema",
        "business_vault_schema",
        "layer",
    }

    def __init__(self, model: DVProjectModel, logger: Logger):
        super().__init__(model=model, logger=logger)
        if not isinstance(model, DVProjectModel):
            raise ValueError(f"Expected DVProjectModel, got {type(model)}")
        # self.model: DVProjectModel = model

    # ------------------------------------------------------------------
    # Project dict assembly
    # ------------------------------------------------------------------

    @property
    def _yaml_template(self) -> dict:
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

    def _get_filtered_params(self) -> dict:
        return {
            k: v
            for k, v in self.model.model_dump().items()
            if k not in self._INTERNAL_FIELDS and v is not None
        }

    # ------------------------------------------------------------------
    # Model config
    # ------------------------------------------------------------------

    def _get_config(self) -> dict:
        config = {}
        if self.model.stg_schema:
            config["staging"] = self._staging_config()
        if self.model.raw_vault_schema:
            config["raw_vault"] = self._raw_vault_config()
        if self.model.business_vault_schema:
            config["business_vault"] = self._business_vault_config()
        return {self.model.name: config}

    def _staging_config(self) -> dict:
        config: dict = {
            "+schema": self.model.stg_schema,
            "+materialized": "view",
            "+tags": ["staging"],
        }
        if self.model.catalog:
            config["+catalog"] = self.model.catalog
        return config

    def _raw_vault_config(self) -> dict:
        sat_config = self._INCREMENTAL_CONFIG.copy()
        config: dict = {
            "+schema": self.model.raw_vault_schema,
            "+tags": ["raw_vault"],
            "hubs": self._INCREMENTAL_CONFIG.copy(),
            "links": self._INCREMENTAL_CONFIG.copy(),
            "satellites": sat_config,
            "eff_sats": sat_config.copy(),
        }
        if self.model.catalog:
            config["+catalog"] = self.model.catalog
        return config

    def _business_vault_config(self) -> dict:
        config: dict = {
            "+schema": self.model.business_vault_schema,
            "+materialized": "table",
            "+tags": ["business_vault"],
        }
        if self.model.catalog:
            config["+catalog"] = self.model.catalog
        return config


if __name__ == "__main__":
    from shared.src.logger.default_logger import default_logger

    link_model = DVProjectModel(
        name="iec_dv2",
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

    dbt_project = ProjectComponent(model=link_model, logger=default_logger)
    wml = dbt_project.generate_yml_str()
