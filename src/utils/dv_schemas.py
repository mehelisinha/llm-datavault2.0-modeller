"""Data Vault schema-layer enum and schema-name generator.

Provides a canonical naming convention for DV schema names:
    ``{clean_system_name}_{layer}``

Example::

    names = DvSchemaNames("IEC61968_CIM")
    names.staging         # "iec61968_cim_staging"
    names.raw_vault       # "iec61968_cim_raw_vault"
    names.business_vault  # "iec61968_cim_business_vault"
"""

from __future__ import annotations

from enum import StrEnum

from src.utils.system_name import SystemNameCleaner


class DvSchemaLayer(StrEnum):
    """Canonical Data Vault schema layer identifiers."""

    STAGING = "staging"
    RAW_VAULT = "raw_vault"
    BUSINESS_VAULT = "business_vault"


class DvSchemaNames:
    """Generates standardised schema names for a given source system.

    Schema names follow the pattern ``{clean_system_name}_{layer}``.

    Args:
        system_name: Raw system name from the metadata YAML
                     (e.g. ``"IEC61968_CIM"`` or ``"My System v2.0"``).
    """

    def __init__(self, system_name: str) -> None:
        self._prefix: str = SystemNameCleaner.clean(system_name)

    def get(self, layer: DvSchemaLayer) -> str:
        """Return the full schema name for the given *layer*."""
        return f"{self._prefix}_{layer}"

    @property
    def staging(self) -> str:
        return self.get(DvSchemaLayer.STAGING)

    @property
    def raw_vault(self) -> str:
        return self.get(DvSchemaLayer.RAW_VAULT)

    @property
    def business_vault(self) -> str:
        return self.get(DvSchemaLayer.BUSINESS_VAULT)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"DvSchemaNames(prefix={self._prefix!r}, "
            f"staging={self.staging!r}, raw_vault={self.raw_vault!r}, "
            f"business_vault={self.business_vault!r})"
        )
