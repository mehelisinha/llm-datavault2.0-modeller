from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class FileHandler(ABC):

    @abstractmethod
    def read(self, file_path: Path) -> Any:
        pass

    @abstractmethod
    def _write(self, file_path: Path, content: Any) -> None:
        pass

    def write(self, file_path: Path, content: Any, overwrite: bool = False) -> None:
        if file_path.exists() and not overwrite:
            return

        file_path.parent.mkdir(parents=True, exist_ok=True)
        self._write(file_path, content)

    def ensure_exists(self, file_path: Path) -> None:
        if not file_path.exists():
            raise FileNotFoundError(file_path)
