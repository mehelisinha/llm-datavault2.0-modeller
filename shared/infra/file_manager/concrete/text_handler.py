from pathlib import Path

from shared.infra.file_manager.concrete.file_handler import FileHandler


class TextHandler(FileHandler):
    def read(self, file_path: Path):
        self.ensure_exists(file_path)
        return file_path.read_text(encoding="utf-8")

    def _write(self, file_path: Path, content: str)->None:
        file_path.write_text(content, encoding="utf-8")
