"""
MetadataReader — parses the DWA YAML metadata config and produces typed
Data Vault component objects (Hub, Link, Satellite) ready to pass to DVGenerator.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Union

import yaml

from dv_components.models.hub import Hub
from dv_components.models.link import Link
from dv_components.models.satellite import Satellite

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

DVComponent = Union[Hub, Link, Satellite]


# ---------------------------------------------------------------------------
# MetadataReader
# ---------------------------------------------------------------------------


class MetadataReader:
    """
    Reads a YAML metadata config file and produces Hub, Link, and Satellite
    objects for the DVGenerator to render into dbt model files.

    Usage::

        reader = MetadataReader("src/metadata/iec_cim_metadata.yaml")
        hubs       = reader.get_hubs()
        satellites = reader.get_satellites()
        links      = reader.get_links()
        all_comps  = reader.get_all_components()
    """

    def __init__(self, config_path: Union[str, Path]):
        self._path = Path(config_path)
        self._config: Dict[str, Any] = self._load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self) -> Dict[str, Any]:
        if not self._path.exists():
            raise FileNotFoundError(f"Metadata config not found: {self._path}")
        with self._path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        self._validate_top_level(data)
        return data

    @staticmethod
    def _validate_top_level(data: Dict[str, Any]) -> None:
        required = {"system", "hubs", "satellites", "links"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(
                f"Metadata config is missing required top-level keys: {missing}"
            )

    # ------------------------------------------------------------------
    # System info
    # ------------------------------------------------------------------

    @property
    def system(self) -> Dict[str, Any]:
        return self._config["system"]

    # ------------------------------------------------------------------
    # Hubs
    # ------------------------------------------------------------------

    def get_hubs(self) -> List[Hub]:
        """Return one Hub object per hub definition in the YAML."""
        hubs: List[Hub] = []
        for entry in self._config.get("hubs", []):
            self._require_keys(
                entry, {"name", "staging_model", "business_key", "hash_key"}, "hub"
            )
            hub = Hub(
                name=entry["name"],
                source_models=[entry["staging_model"]],
                src_pk=entry["hash_key"],
                src_nk=entry["business_key"],
            )
            hubs.append(hub)
        return hubs

    # ------------------------------------------------------------------
    # Satellites
    # ------------------------------------------------------------------

    def get_satellites(self) -> List[Satellite]:
        """Return one Satellite object per satellite definition in the YAML."""
        satellites: List[Satellite] = []
        for entry in self._config.get("satellites", []):
            self._require_keys(
                entry,
                {"name", "source_model", "hash_key", "hashdiff", "payload"},
                "satellite",
            )
            sat = Satellite(
                name=entry["name"],
                source_models=[entry["source_model"]],
                src_pk=entry["hash_key"],
                src_hashdiff=entry["hashdiff"],
                src_payload=list(entry["payload"]),
                src_eff=entry.get("effective_from"),
            )
            satellites.append(sat)
        return satellites

    # ------------------------------------------------------------------
    # Links
    # ------------------------------------------------------------------

    def get_links(self) -> List[Link]:
        """Return one Link object per link definition in the YAML."""
        links: List[Link] = []
        for entry in self._config.get("links", []):
            self._require_keys(
                entry,
                {"name", "source_model", "hash_key", "fk_columns"},
                "link",
            )
            link = Link(
                name=entry["name"],
                source_models=[entry["source_model"]],
                src_pk=entry["hash_key"],
                src_fk=list(entry["fk_columns"]),
            )
            links.append(link)
        return links

    # ------------------------------------------------------------------
    # Convenience: all components in generation order
    # ------------------------------------------------------------------

    def get_all_components(self) -> List[DVComponent]:
        """Return all components in dependency order: Hubs → Links → Satellites."""
        return self.get_hubs() + self.get_links() + self.get_satellites()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _require_keys(entry: Dict[str, Any], required: set, kind: str) -> None:
        missing = required - set(entry.keys())
        if missing:
            name = entry.get("name", "<unnamed>")
            raise ValueError(
                f"Metadata {kind} '{name}' is missing required keys: {missing}"
            )
