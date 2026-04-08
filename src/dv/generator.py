"""
Generator for Data Vault models.
"""

import os
from typing import List

from .base import DVComponent


class DVGenerator:
    """Generator for Data Vault components."""

    def __init__(self, base_path: str = "models"):
        self.base_path = base_path

    def generate_component(self, component: DVComponent, overwrite: bool = False):
        """Generate the SQL file for a component."""
        file_path = component.get_file_path(self.base_path)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        if os.path.exists(file_path) and not overwrite:
            print(f"File {file_path} already exists. Skipping.")
            return

        with open(file_path, "w") as f:
            f.write(component.generate_sql())

        print(f"Generated {file_path}")

    def generate_components(self, components: List[DVComponent], overwrite: bool = False):
        """Generate SQL files for multiple components."""
        for component in components:
            self.generate_component(component, overwrite)
