"""
Unit tests for:
  - shared/infra/file_manager/file_handler_factory.py — FileHandlerFactory
  - shared/infra/file_manager/file_manager.py          — FileManager
"""

import json
import tempfile
import unittest
from pathlib import Path

from shared.src.infra.file_manager.concrete.json_handler import JsonHandler
from shared.src.infra.file_manager.concrete.text_handler import TextHandler
from shared.src.infra.file_manager.concrete.yml_handler import YamlHandler
from shared.src.infra.file_manager.file_handler_factory import FileHandlerFactory
from shared.src.infra.file_manager.file_manager import FileManager
from shared.tests.conftest import SharedTestBase

# ---------------------------------------------------------------------------
# FileHandlerFactory
# ---------------------------------------------------------------------------


class TestFileHandlerFactoryDispatch(SharedTestBase):
    """FileHandlerFactory.get must return the correct handler for each extension."""

    def test_yml_returns_yaml_handler(self) -> None:
        self.assertIsInstance(FileHandlerFactory.get("yml"), YamlHandler)

    def test_yaml_returns_yaml_handler(self) -> None:
        self.assertIsInstance(FileHandlerFactory.get("yaml"), YamlHandler)

    def test_json_returns_json_handler(self) -> None:
        self.assertIsInstance(FileHandlerFactory.get("json"), JsonHandler)

    def test_sql_returns_text_handler(self) -> None:
        self.assertIsInstance(FileHandlerFactory.get("sql"), TextHandler)

    def test_txt_returns_text_handler(self) -> None:
        self.assertIsInstance(FileHandlerFactory.get("txt"), TextHandler)

    def test_css_returns_text_handler(self) -> None:
        self.assertIsInstance(FileHandlerFactory.get("css"), TextHandler)

    def test_unknown_extension_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            FileHandlerFactory.get("parquet")

    def test_extension_lookup_is_case_insensitive(self) -> None:
        self.assertIsInstance(FileHandlerFactory.get("YML"), YamlHandler)
        self.assertIsInstance(FileHandlerFactory.get("JSON"), JsonHandler)


# ---------------------------------------------------------------------------
# FileManager.read
# ---------------------------------------------------------------------------


class TestFileManagerRead(SharedTestBase):
    """FileManager.read must delegate to the correct handler based on extension."""

    def test_read_yaml_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".yml", mode="w", delete=False) as f:
            f.write("system: dwa\n")
            path = Path(f.name)
        try:
            result = FileManager.read(path)
            self.assertEqual(result["system"], "dwa")
        finally:
            path.unlink(missing_ok=True)

    def test_read_json_file(self) -> None:
        data = {"env": "dev"}
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(data, f)
            path = Path(f.name)
        try:
            result = FileManager.read(path)
            self.assertEqual(result["env"], "dev")
        finally:
            path.unlink(missing_ok=True)

    def test_read_text_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("plain text content")
            path = Path(f.name)
        try:
            result = FileManager.read(path)
            self.assertEqual(result, "plain text content")
        finally:
            path.unlink(missing_ok=True)

    def test_read_missing_file_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            FileManager.read("/no/such/file.yml")

    def test_read_unknown_extension_raises_value_error(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            path = Path(f.name)
        try:
            with self.assertRaises(ValueError):
                FileManager.read(path)
        finally:
            path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# FileManager.write
# ---------------------------------------------------------------------------


class TestFileManagerWrite(SharedTestBase):
    """FileManager.write must delegate to the correct handler and respect overwrite."""

    def test_write_yaml_file(self) -> None:
        data = {"written": True}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "out.yml"
            FileManager.write(path, data, overwrite=True)
            result = FileManager.read(path)
            self.assertTrue(result["written"])

    def test_write_json_file(self) -> None:
        data = {"count": 42}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "out.json"
            FileManager.write(path, data, overwrite=True)
            result = FileManager.read(path)
            self.assertEqual(result["count"], 42)

    def test_write_text_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "note.txt"
            FileManager.write(path, "hello", overwrite=True)
            result = FileManager.read(path)
            self.assertEqual(result, "hello")

    def test_write_does_not_overwrite_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "stable.yml"
            FileManager.write(path, {"v": 1}, overwrite=True)
            FileManager.write(path, {"v": 999})  # overwrite=False by default
            result = FileManager.read(path)
            self.assertEqual(result["v"], 1)

    def test_write_unknown_extension_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "data.parquet"
            with self.assertRaises(ValueError):
                FileManager.write(path, b"bytes", overwrite=True)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
