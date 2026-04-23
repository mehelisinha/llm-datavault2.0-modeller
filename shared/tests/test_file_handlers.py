"""
Unit tests for shared/infra/file_manager/concrete/ — FileHandler subclasses.

Tests use Python's built-in tempfile module so no third-party fixtures are
needed; the test suite is runnable on Databricks without any extra setup.
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..")))
import json
import tempfile
import unittest
from pathlib import Path

from shared.src.infra.file_manager.concrete.file_handler import FileHandler
from shared.src.infra.file_manager.concrete.json_handler import JsonHandler
from shared.src.infra.file_manager.concrete.text_handler import TextHandler
from shared.src.infra.file_manager.concrete.yml_handler import YamlHandler
from shared.tests.conftest import SharedTestBase

# ---------------------------------------------------------------------------
# YamlHandler
# ---------------------------------------------------------------------------


class TestYamlHandlerRead(SharedTestBase):
    """YamlHandler.read must parse valid YAML files correctly."""

    def test_read_returns_dict(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".yml", mode="w", delete=False) as f:
            f.write("key: value\nnumber: 42\n")
            path = Path(f.name)
        try:
            result = YamlHandler.read(path)
            self.assertEqual(result["key"], "value")
            self.assertEqual(result["number"], 42)
        finally:
            path.unlink(missing_ok=True)

    def test_read_raises_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            YamlHandler.read(Path("/nonexistent/path/file.yml"))


class TestYamlHandlerWrite(SharedTestBase):
    """YamlHandler.write must persist dicts as valid YAML."""

    def test_write_dict_and_read_back(self) -> None:
        data = {"name": "dwa", "version": 1}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "out.yml"
            YamlHandler.write(path, data, overwrite=True)
            result = YamlHandler.read(path)
            self.assertEqual(result["name"], "dwa")
            self.assertEqual(result["version"], 1)

    def test_write_does_not_overwrite_by_default(self) -> None:
        original = {"value": "original"}
        replacement = {"value": "replaced"}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "no-overwrite.yml"
            YamlHandler.write(path, original, overwrite=True)
            YamlHandler.write(path, replacement, overwrite=False)  # must be a no-op
            result = YamlHandler.read(path)
            self.assertEqual(result["value"], "original")

    def test_write_string_content_written_as_is(self) -> None:
        raw_yaml = "key: value\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "raw.yml"
            YamlHandler.write(path, raw_yaml, overwrite=True)
            self.assertEqual(path.read_text(encoding="utf-8"), raw_yaml)


class TestYamlHandlerGenerate(SharedTestBase):
    """YamlHandler.generate must return a YAML string without writing a file."""

    def test_generate_returns_string(self) -> None:
        result = YamlHandler.generate({"a": 1})
        self.assertIsInstance(result, str)
        self.assertIn("a: 1", result)

    def test_generate_with_jinja_double_quotes_expressions(self) -> None:
        data = {"secret": "{{ env_var('MY_VAR') }}"}
        result = YamlHandler.generate_with_jinja(data)
        self.assertIn("{{", result)
        self.assertIn("}}", result)

    def test_to_kebab_case_converts_underscores(self) -> None:
        result = YamlHandler.to_kebab_case({"my_key": "my_value"})
        self.assertIn("my-key", result)
        self.assertEqual(result["my-key"], "my_value")


# ---------------------------------------------------------------------------
# JsonHandler
# ---------------------------------------------------------------------------


class TestJsonHandlerRead(SharedTestBase):
    """JsonHandler.read must parse valid JSON files correctly."""

    def test_read_returns_dict(self) -> None:
        data = {"x": 1, "y": [2, 3]}
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(data, f)
            path = Path(f.name)
        try:
            result = JsonHandler.read(path)
            self.assertEqual(result["x"], 1)
            self.assertEqual(result["y"], [2, 3])
        finally:
            path.unlink(missing_ok=True)

    def test_read_raises_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            JsonHandler.read(Path("/no/such/file.json"))


class TestJsonHandlerWrite(SharedTestBase):
    """JsonHandler.write must persist dicts as valid JSON."""

    def test_write_and_read_back(self) -> None:
        data = {"env": "dev", "active": True}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cfg.json"
            JsonHandler.write(path, data, overwrite=True)
            result = JsonHandler.read(path)
            self.assertEqual(result["env"], "dev")
            self.assertTrue(result["active"])

    def test_write_creates_parent_dirs(self) -> None:
        data = {"k": "v"}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sub" / "dir" / "out.json"
            JsonHandler.write(path, data, overwrite=True)
            self.assertTrue(path.exists())


# ---------------------------------------------------------------------------
# TextHandler
# ---------------------------------------------------------------------------


class TestTextHandlerRead(SharedTestBase):
    """TextHandler.read must return file content as a plain string."""

    def test_read_returns_string(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("hello world")
            path = Path(f.name)
        try:
            result = TextHandler.read(path)
            self.assertEqual(result, "hello world")
        finally:
            path.unlink(missing_ok=True)

    def test_read_raises_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            TextHandler.read(Path("/missing/file.txt"))


class TestTextHandlerWrite(SharedTestBase):
    """TextHandler.write must persist the exact string content."""

    def test_write_and_read_back(self) -> None:
        content = "SELECT * FROM hub_customer;"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "query.sql"
            TextHandler.write(path, content, overwrite=True)
            result = TextHandler.read(path)
            self.assertEqual(result, content)


# ---------------------------------------------------------------------------
# FileHandler base (via ensure_exists)
# ---------------------------------------------------------------------------


class TestFileHandlerEnsureExists(SharedTestBase):
    """FileHandler.ensure_exists must raise when the file is absent."""

    def test_raises_for_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            FileHandler.ensure_exists(Path("/does/not/exist.yml"))

    def test_passes_for_existing_file(self) -> None:
        with tempfile.NamedTemporaryFile() as f:
            try:
                FileHandler.ensure_exists(Path(f.name))
            except FileNotFoundError:
                self.fail("ensure_exists raised FileNotFoundError for an existing file")


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
