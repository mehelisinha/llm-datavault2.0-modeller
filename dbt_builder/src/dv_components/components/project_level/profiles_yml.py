from logging import Logger

from dbt_builder.src.dv_components.components.project_level.base import DVProjYmlBaseGenerator
from dbt_builder.src.dv_components.pydantic_model.proj_level.dv_yml import (
    DVProfileOutputModel,
    DvProfilesModel,
)


class ProfilesComponent(DVProjYmlBaseGenerator):
    """Generates profiles.yml configuration from a DVProfileModel."""

    _INTERNAL_FIELDS = {
        "dv_type",
        "layer",
    }

    def __init__(self, model: DvProfilesModel, logger: Logger):
        super().__init__(model=model, logger=logger)

        if not isinstance(model, DvProfilesModel):
            raise ValueError(f"Expected DvProfilesModel, got {type(model)}")
        self.profile_model: DvProfilesModel = model

    # ------------------------------------------------------------------
    # Project dict assembly
    # ------------------------------------------------------------------
    @property
    def _yaml_template(self) -> dict:

        return {
            self.profile_model.name: {
                "target": self.profile_model.target,
                "outputs": {
                    k: v.model_dump(by_alias=True, exclude_none=True)
                    for k, v in self.profile_model.outputs.items()
                    if k not in self._INTERNAL_FIELDS and v is not None
                },
            }
        }


if __name__ == "__main__":
    from shared.src.logger.default_logger import default_logger
    # from src.dv_components.pydantic_model.config.dv_yml import DVProfileModel, DVProfileOutputModel, DVProfileComputeWarehouse

    model = DvProfilesModel(
        name="iec_dv2",
        target="dev",
        outputs={
            "dev": DVProfileOutputModel(
                host="localhost",
                http_path="/sql/protocolv1/o/0/iec_dv2",
                token="{{ env_var('DBT_DATABRICKS_TOKEN') }}",
                type="databricks",
                catalog="edh_unreg_silver_dev_st",
                schema="dv2",
                # compute=DVProfileComputeWarehouse(name="DWA_TEST"),
            )
        },
    )

    dbt_project = ProfilesComponent(model=model, logger=default_logger)
    wml = dbt_project.generate_yml_str()
