import os
from logging import Logger

from shared.infra.file_manager.file_manager import FileManager
from shared.logger.default_logger import default_logger
from src.dv_components.factory.dv_model_factory import DVComponentFactory
from src.dv_components.models.model import DVComponentModel


class DVComponentManager:
    @classmethod
    def generate_sql(
        cls,
        model: DVComponentModel,
        logger: Logger = default_logger,
    ) -> str:
        component = DVComponentFactory.create(model=model, logger=logger)
        return component.generate()

    @classmethod
    def write_sql_file(
        cls,
        model: DVComponentModel,
        project_path: str,
        logger: Logger = default_logger,
    ) -> str:
        sql = cls.generate_sql(model=model, logger=logger)

        path = model.base_models_path
        output_dir = os.path.join(project_path, path) if path else project_path
        out_path = os.path.join(output_dir, f"{model.name}.sql")

        FileManager.write(out_path, sql, overwrite=True)
        return out_path
