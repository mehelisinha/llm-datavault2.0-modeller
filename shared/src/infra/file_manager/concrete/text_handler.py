from pathlib import Path

from shared.src.infra.file_manager.concrete.file_handler import FileHandler


class TextHandler(FileHandler):
    @classmethod
    def read(cls, file_path: Path):
        cls.ensure_exists(file_path)
        return file_path.read_text(encoding="utf-8")

    @classmethod
    def _write(cls, file_path: Path, content: str) -> None:
        file_path.write_text(content, encoding="utf-8")
