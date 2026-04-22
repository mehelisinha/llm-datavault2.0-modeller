"""Utility for sanitising source-system names for use in identifiers and schema names."""

from __future__ import annotations

import re


class SystemNameCleaner:
    """
    Removes characters that are problematic in SQL identifiers, file names, and
    schema names (spaces, dots, dashes, slashes, colons, etc.) and collapses
    the result to a lowercase, underscore-delimited string.

    Examples::

        SystemNameCleaner.clean("IEC61968_CIM")      # "iec61968_cim"
        SystemNameCleaner.clean("My System v2.0")    # "my_system_v2_0"
        SystemNameCleaner.clean("EDH-Bronze/Silver")  # "edh_bronze_silver"
    """

    _PROBLEMATIC: re.Pattern[str] = re.compile(r'[\s.\-/\\:*?"<>|@#$%^&()+=\[\]{}]+')
    _MULTI_UNDERSCORE: re.Pattern[str] = re.compile(r"_+")

    @classmethod
    def clean(cls, name: str) -> str:
        """Return a sanitised, lowercase identifier from *name*.

        Raises:
            ValueError: if *name* is empty or reduces to an empty string after cleaning.
        """
        if not name or not name.strip():
            raise ValueError("System name must not be empty.")
        cleaned = cls._PROBLEMATIC.sub("_", name)
        cleaned = cls._MULTI_UNDERSCORE.sub("_", cleaned).strip("_")
        if not cleaned:
            raise ValueError(
                f"System name '{name}' reduced to an empty string after cleaning."
            )
        return cleaned.lower()
