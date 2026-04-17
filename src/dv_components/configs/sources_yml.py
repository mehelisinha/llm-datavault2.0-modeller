from logging import Logger
from pathlib import Path

import yaml

from src.dv_components.models.model import DVComponentModel, DVSourceModel, TableConfig


class DBTSources:
    """Generates sources.yml configuration from a DVSourcesModel."""

    def __init__(self, model: DVComponentModel, logger: Logger):
        self.model = model
        self.logger = logger
        if not isinstance(model.meta, DVSourceModel):
            raise ValueError(f"Expected DVProjectModel, got {type(model.meta)}")
        self.sources_model: DVSourceModel = model.meta

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> str:
        """Return the dbt_project.yml content as a YAML string."""
        yaml_str = yaml.dump(
            self._build_project_dict(), sort_keys=False, default_flow_style=False
        )
        self.logger.debug(f"Generated sources.yml:\n{yaml_str}")
        return yaml_str

    def write(self, project_path: str, yaml_content: str):
        out_path = Path(project_path) / "models" / "staging" / "sources.yml"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(yaml_content, encoding="utf-8")
        self.logger.debug(f"  YML  → {out_path}")
        return out_path

    # ------------------------------------------------------------------
    # Project dict assembly
    # ------------------------------------------------------------------

    def _build_project_dict(self) -> dict:

        data = self.model.meta.model_dump(
            by_alias=True,
            exclude={"dv_type"},
        )
        sources_data = {}
        sources_data["sources"] = [data]
        return sources_data


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
