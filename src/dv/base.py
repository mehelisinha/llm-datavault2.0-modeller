"""
Base class for Data Vault components.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class DVComponent(ABC):
    """Abstract base class for Data Vault components."""

    def __init__(self, name: str, schema: str = "raw_vault"):
        self.name = name
        self.schema = schema

    @abstractmethod
    def generate_sql(self) -> str:
        """Generate the SQL code for this component."""
        pass

    def get_config(self) -> Dict[str, Any]:
        """Get the dbt config for this component."""
        return {
            "materialized": "incremental",
            "incremental_strategy": "merge",
            "tags": [self.schema, self.__class__.__name__.lower()],
        }

    def get_file_path(self, base_path: str = "models") -> str:
        """Get the file path for this component."""
        component_type = self.__class__.__name__.lower()
        return f"{base_path}/{self.schema}/{component_type}s/{self.name}.sql"
