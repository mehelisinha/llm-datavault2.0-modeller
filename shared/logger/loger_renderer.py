import textwrap
from collections.abc import Iterable
from dataclasses import fields, is_dataclass
from typing import Any

from pydantic import BaseModel

RenderableModel = BaseModel | Any  # runtime-dispatched


class LoggerRender:
    """Render log messages as list bloks with emogies
    """
    @staticmethod
    def render_kv_block(
        title: str,
        emoji: str,
        items: Iterable[tuple[str, object]],
        label_width: int = 35,
    ) -> str:
        lines = "\n".join(
            f"- {label:<{label_width}} → {value}" for label, value in items
        )

        text = (
            "==============================================================\n"
            f"{emoji} {title}\n"
            "==============================================================\n"
            f"{lines}"
        )

        return f"\n{textwrap.dedent(text)}"

    @staticmethod
    def render_model_block(
        obj: RenderableModel,
        title: str,
        emoji: str,
        label_width: int = 35,
    ) -> str:
        if LoggerRender.is_pydantic_model(obj):
            return LoggerRender.render_pydantic_block(obj, title, emoji, label_width)

        if is_dataclass(obj):
            return LoggerRender.render_dataclass_block(obj, title, emoji, label_width)

        raise TypeError(f"Unsupported model type: {type(obj).__name__}")

    @staticmethod
    def is_pydantic_model(obj: Any) -> bool:
        return isinstance(obj, BaseModel)

    @staticmethod
    def render_dataclass_block(
        obj: Any,
        title: str,
        emoji: str,
        label_width: int = 35,
    ) -> str:
        items: list[tuple[str, Any]] = []
        for f in fields(obj):
            label = f.metadata.get("label")
            if not label:
                continue

            value = getattr(obj, f.name)
            if f.name == "run_id":
                value = value.hex()

            items.append((label, value))

        return LoggerRender.render_kv_block(title, emoji, items, label_width)

    @staticmethod
    def render_pydantic_block(
        model: BaseModel,
        title: str,
        emoji: str,
        label_width: int = 35,
    ) -> str:
        items: list[tuple[str, Any]] = []

        for name, field in model.model_fields.items():
            label = field.description or name

            value = getattr(model, name)
            if hasattr(value, "hex"):
                value = value.hex()

            items.append((label, value))

        return LoggerRender.render_kv_block(
            title=title,
            emoji=emoji,
            items=items,
            label_width=label_width,
        )
