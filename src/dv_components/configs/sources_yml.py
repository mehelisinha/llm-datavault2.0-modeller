from logging import Logger
from pathlib import Path

from src.dv_components.configs.base_yml_generator import BaseYmlGenerator
from src.dv_components.models.model import DVComponentModel, DVSourceModel, TableConfig


class DBTSources(BaseYmlGenerator):
    """Generates sources.yml configuration from a DVSourcesModel."""

    def __init__(self, model: DVComponentModel, logger: Logger):
        super().__init__(logger=logger)
        self.model = model
        if not isinstance(model.meta, DVSourceModel):
            raise ValueError(f"Expected DVProjectModel, got {type(model.meta)}")
        self.sources_model: DVSourceModel = model.meta

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> str:
        """Return the sources.yml content as a YAML string."""
        return super().generate()

    def write(
        self,
        project_path: str,
        yaml_content: str | None = None,
    ):
        if yaml_content is not None:
            out_path = Path(project_path) / self._relative_output_path()
            return self._write_content(out_path, yaml_content)
        return super().write(project_path=project_path)

    # ------------------------------------------------------------------
    # Project dict assembly
    # ------------------------------------------------------------------

    def _build_yaml_dict(self) -> dict:

        data = self.model.meta.model_dump(
            by_alias=True,
            exclude={"dv_type"},
        )
        sources_data = {}
        sources_data["sources"] = [data]
        return sources_data

    def _relative_output_path(self) -> Path:
        return Path("models") / "staging" / "sources.yml"


if __name__ == "__main__":
    from shared.logger.default_logger import default_logger

    model = DVSourceModel(
        name="bronze",
        database="edh_unreg_silver_dev_st",
        schema="bronze",
        tables=[
            TableConfig(name="conducting_equipment"),
            TableConfig(name="connectivity_nodes"),
            TableConfig(name="terminals"),
        ],
    )

    model = DVComponentModel(name="iec_dv2", meta=model)
    dbt_project = DBTSources(model=model, logger=default_logger)
    wml = dbt_project.generate()
