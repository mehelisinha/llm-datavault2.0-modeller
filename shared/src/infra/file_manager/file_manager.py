from logging import Logger
from pathlib import Path
from typing import Any

from shared.src.infra.file_manager.file_handler_factory import FileHandlerFactory
from shared.src.logger.default_logger import default_logger


class FileManager:
    @staticmethod
    def read(file_path: str | Path, logger: Logger = default_logger):
        path = Path(file_path)
        try:
            handler = FileHandlerFactory.get(path.suffix.lstrip("."))
            return handler.read(path)
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {str(e)[:200]}")
            raise ValueError(f"Error occurred while reading file: {str(e)}") from e

    @staticmethod
    def write(
        file_path: str | Path,
        content: Any,
        logger: Logger = default_logger,
        overwrite: bool = False,
    ):
        try:
            path = Path(file_path)
            handler = FileHandlerFactory.get(path.suffix.lstrip("."))
            handler.write(path, content, overwrite)
        except Exception as e:
            logger.error(f"Error writing to file {file_path}: {str(e)[:200]}")
            raise ValueError(f"Error occurred while writing to file: {str(e)}") from e
