import json
from pathlib import Path
from typing import Any

from shared.infra.file_manager.concrete.file_handler import FileHandler


class JsonHandler(FileHandler):
    def read(self, file_path: Path):
        self.ensure_exists(file_path)
        return json.loads(file_path.read_text(encoding="utf-8"))

    def _write(self, file_path: Path, content: Any):
        file_path.write_text(json.dumps(content, indent=2), encoding="utf-8")
