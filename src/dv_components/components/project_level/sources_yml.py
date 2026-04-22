from logging import Logger

from src.dv_components.components.project_level.base import DVProjYmlBaseGenerator
from src.dv_components.pydantic_model.proj_level.dv_yml import (
    DvSourceModel,
    TableConfig,
)


class SourcesComponent(DVProjYmlBaseGenerator):
    """Generates sources.yml configuration from a DVSourceModel."""

    _INTERNAL_FIELDS = {
        "dv_type",
        "layer",
    }

    def __init__(self, model: DvSourceModel, logger: Logger):
        super().__init__(model=model, logger=logger)

        if not isinstance(model, DvSourceModel):
            raise ValueError(f"Expected DVSourceModel, got {type(model)}")
        self.sources_model: DvSourceModel = model

    # ------------------------------------------------------------------
    # Project dict assembly
    # ------------------------------------------------------------------
    @property
    def _yaml_template(self) -> dict:

        data = self.model.model_dump(
            by_alias=True,
            exclude={*self._INTERNAL_FIELDS},
        )
        sources_data = {}
        sources_data["sources"] = [data]
        return sources_data


if __name__ == "__main__":
    from shared.logger.default_logger import default_logger

    model = DvSourceModel(
        name="bronze",
        database="edh_unreg_silver_dev_st",
        schema="bronze",
        tables=[
            TableConfig(name="conducting_equipment"),
            TableConfig(name="connectivity_nodes"),
            TableConfig(name="terminals"),
        ],
    )

    dbt_project = SourcesComponent(model=model, logger=default_logger)
    wml = dbt_project.generate_yml_str()
