from pathlib import Path
from typing import Any

import yaml

from shared.infra.file_manager.concrete.file_handler import FileHandler


class YamlHandler(FileHandler):
    def read(self, file_path: Path):
        self.ensure_exists(file_path)
        with file_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _write(self, file_path: Path, content: Any):
        with file_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(content, f)
