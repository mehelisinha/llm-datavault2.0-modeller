import os
from logging import Logger

from dv_components.factory.dv_model_factory import DVComponentFactory
from shared.infra.file_manager.file_manager import FileManager
from shared.logger.default_logger import default_logger
from src.dv_components.components.model import DVComponentModel


class DVComponentManager:
    @classmethod
    def _get_file_format(cls):
        pass

    @classmethod
    def generate_sql(
        cls,
        model: DVComponentModel,
        source_models: list[str],
        logger: Logger = default_logger,
    ) -> str:
        component = DVComponentFactory.create(
            model=model, source_models=source_models, logger=logger
        )
        return component.generate_sql()

    @classmethod
    def write_sql_file(
        cls,
        model: DVComponentModel,
        source_models: list[str],
        project_path: str,
        logger: Logger = default_logger,
    ) -> str:

        sql = cls.generate_sql(model=model, source_models=source_models, logger=logger)

        path = model.base_models_path
        if path:
            output_dir = os.path.join(project_path, path, f"{model.dv_type}s")
        else:
            output_dir = project_path
        out_path = os.path.join(output_dir, f"{model.name}.sql")

        FileManager.write(out_path, sql, overwrite=True)

        return out_path
