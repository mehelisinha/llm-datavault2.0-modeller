"""
Unit tests for shared/logger/loger_renderer.py — LoggerRender.
"""

import unittest
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from shared.src.logger.loger_renderer import LoggerRender
from shared.tests.conftest import SharedTestBase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SamplePydantic(BaseModel):
    name: str = Field(description="System name")
    version: int = Field(description="Schema version")


@dataclass
class _SampleDataclass:
    run_id: bytes = field(default=b"\x00" * 16, metadata={"label": "Run ID"})
    system: str = field(default="dwa", metadata={"label": "System"})
    _hidden: str = field(default="private", metadata={})  # no label → excluded


# ---------------------------------------------------------------------------
# is_pydantic_model
# ---------------------------------------------------------------------------


class TestLoggerRenderIsPydantic(SharedTestBase):
    """is_pydantic_model must correctly distinguish Pydantic from non-Pydantic objects."""

    def test_returns_true_for_pydantic_instance(self) -> None:
        model = _SamplePydantic(name="iec", version=2)
        self.assertTrue(LoggerRender.is_pydantic_model(model))

    def test_returns_false_for_plain_dict(self) -> None:
        self.assertFalse(LoggerRender.is_pydantic_model({"key": "val"}))

    def test_returns_false_for_dataclass(self) -> None:
        dc = _SampleDataclass()
        self.assertFalse(LoggerRender.is_pydantic_model(dc))


# ---------------------------------------------------------------------------
# render_kv_block
# ---------------------------------------------------------------------------


class TestLoggerRenderKvBlock(SharedTestBase):
    """render_kv_block must produce a formatted multi-line string."""

    def test_contains_title(self) -> None:
        result = LoggerRender.render_kv_block(
            title="My Title", emoji="🔹", items=[("Key", "Value")]
        )
        self.assertIn("My Title", result)

    def test_contains_key_value_pair(self) -> None:
        result = LoggerRender.render_kv_block(
            title="T", emoji="✅", items=[("Environment", "dev"), ("Version", 2)]
        )
        self.assertIn("Environment", result)
        self.assertIn("dev", result)
        self.assertIn("Version", result)

    def test_empty_items_still_renders(self) -> None:
        result = LoggerRender.render_kv_block(title="Empty", emoji="ℹ️", items=[])
        self.assertIn("Empty", result)


# ---------------------------------------------------------------------------
# render_pydantic_block
# ---------------------------------------------------------------------------


class TestLoggerRenderPydanticBlock(SharedTestBase):
    """render_pydantic_block must use field descriptions as labels."""

    def test_contains_field_description(self) -> None:
        model = _SamplePydantic(name="cim", version=3)
        result = LoggerRender.render_pydantic_block(
            model, title="Pydantic Test", emoji="🧩"
        )
        self.assertIn("System name", result)
        self.assertIn("Schema version", result)

    def test_contains_field_values(self) -> None:
        model = _SamplePydantic(name="cim", version=3)
        result = LoggerRender.render_pydantic_block(model, title="T", emoji="✅")
        self.assertIn("cim", result)
        self.assertIn("3", result)


# ---------------------------------------------------------------------------
# render_dataclass_block
# ---------------------------------------------------------------------------


class TestLoggerRenderDataclassBlock(SharedTestBase):
    """render_dataclass_block must only include fields that have a 'label' metadata key."""

    def test_labeled_fields_are_included(self) -> None:
        dc = _SampleDataclass(system="dwa")
        result = LoggerRender.render_dataclass_block(dc, title="DC Test", emoji="📄")
        self.assertIn("System", result)
        self.assertIn("dwa", result)

    def test_unlabeled_fields_are_excluded(self) -> None:
        dc = _SampleDataclass()
        result = LoggerRender.render_dataclass_block(dc, title="T", emoji="📄")
        self.assertNotIn("private", result)

    def test_run_id_rendered_as_hex(self) -> None:
        run_id_bytes = b"\xde\xad\xbe\xef" + b"\x00" * 12
        dc = _SampleDataclass(run_id=run_id_bytes)
        result = LoggerRender.render_dataclass_block(dc, title="T", emoji="📄")
        self.assertIn(run_id_bytes.hex(), result)


# ---------------------------------------------------------------------------
# render_model_block (dispatcher)
# ---------------------------------------------------------------------------


class TestLoggerRenderModelBlock(SharedTestBase):
    """render_model_block must dispatch correctly based on type."""

    def test_dispatches_to_pydantic_renderer(self) -> None:
        model = _SamplePydantic(name="x", version=1)
        result = LoggerRender.render_model_block(model, title="T", emoji="✅")
        self.assertIn("System name", result)

    def test_dispatches_to_dataclass_renderer(self) -> None:
        dc = _SampleDataclass(system="dwa")
        result = LoggerRender.render_model_block(dc, title="T", emoji="✅")
        self.assertIn("System", result)

    def test_raises_for_unsupported_type(self) -> None:
        with self.assertRaises(TypeError):
            LoggerRender.render_model_block({"not": "a model"}, title="T", emoji="❌")


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
