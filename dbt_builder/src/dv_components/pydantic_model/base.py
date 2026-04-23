# models.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, model_validator

# ── Shared building blocks ────────────────────────────────────────────────────


class DVBaseModel(BaseModel, ABC):
    dv_type: Literal[
        "base"
    ]  # to satisfy discriminator requirement; overridden in subclasses
    layer: str | None = None


class DVNamedModel(DVBaseModel, ABC):
    name: str
    description: str | None = None

    @model_validator(mode="after")
    def _default_description(self) -> DVNamedModel:
        if not self.description:
            self.description = f"Data Vault {self.dv_type} for {self.name}"
        return self

    @property
    @abstractmethod
    def models_path(self) -> str: ...

    @property
    def file_name(self) -> str:
        return f"{self.name}"
