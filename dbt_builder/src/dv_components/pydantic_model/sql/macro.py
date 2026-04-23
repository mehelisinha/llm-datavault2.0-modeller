from __future__ import annotations

from typing import Literal

from dbt_builder.src.dv_components.pydantic_model.base import DVNamedModel

# ── Raw vault leaf models ─────────────────────────────────────────────────────


class MacroModel(DVNamedModel):
    name: str
    dv_type: Literal["macro"] = "macro"
    layer: Literal["MCR"] = "MCR"

    @property
    def models_path(self) -> str:
        return "macros"

    @property
    def file_extension(self) -> list[Literal["sql", "yml"]]:
        return ["sql"]
