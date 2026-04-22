# models.py
from __future__ import annotations

from abc import ABC
from typing import Literal

from pydantic import ConfigDict, Field

from src.dv_components.pydantic_model.base import DVNamedModel

# ── Shared building blocks ────────────────────────────────────────────────────


class DvBaseSqlModel(DVNamedModel, ABC):
    """Fields shared by every dbt-file-generating component."""

    model_config = ConfigDict(populate_by_name=True)

    source_model: list[str]
    src_source: str = "RECORD_SOURCE"
    schema_name: str = Field(default="raw_vault", alias="schema")

    @property
    def file_extension(self) -> list[Literal["sql", "yml"]]:
        return ["sql", "yml"]
