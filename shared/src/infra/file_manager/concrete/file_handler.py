from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

# from shared.logger.default_logger import default_logger


class FileHandler(ABC):
    @classmethod
    @abstractmethod
    def read(cls, file_path: Path) -> Any: ...

    @classmethod
    @abstractmethod
    def _write(cls, file_path: Path, content: Any) -> None: ...

    @classmethod
    def write(cls, file_path: Path, content: Any, overwrite: bool = False) -> None:
        if file_path.exists() and not overwrite:
            return
        file_path.parent.mkdir(parents=True, exist_ok=True)
        cls._write(file_path, content)

    @classmethod
    def ensure_exists(cls, file_path: Path) -> None:
        if not file_path.exists():
            raise FileNotFoundError(file_path)
