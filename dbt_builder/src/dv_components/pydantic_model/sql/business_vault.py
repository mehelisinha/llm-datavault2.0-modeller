"""
Pydantic models for Business Vault components.

Covers the four BV patterns used in Data Vault 2.0:
  - PIT (Point-in-Time)  — query-assist snapshots of satellite watermarks
  - Bridge               — pre-joined hub/link traversals for active relationships
  - Dim (Dimension view) — current-state, denormalised star-schema dimensions
  - Fact (Fact view)     — star-schema facts joining bridge + dimensions
  - BvSat                — derived / cleansed attributes on top of raw-vault satellites

All models inherit from ``BusinessVaultBaseModel`` which itself extends
``DvBaseSqlModel``, ensuring compatibility with ``DVComponentManager``
(``file_extension``, ``populate_by_name``, ``models_path``).
"""

from __future__ import annotations

from abc import ABC
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from dbt_builder.src.dv_components.pydantic_model.enums import DBTModelNames, DbtPaths
from dbt_builder.src.dv_components.pydantic_model.sql.base import DvBaseSqlModel


# ── Sub-models (nested structures, not DVNamedModel) ──────────────────────────


class PitSatelliteEntry(BaseModel):
    """One satellite's contribution to a PIT table.

    ``pk`` and ``ldts`` are the column names as they exist in the satellite
    model.  At template-render time these are wrapped in the nested mapping
    that automate_dv's ``pit`` macro expects::

        { sat_name: { pk: {PK: <pk>}, ldts: {LDTS: <ldts>} } }
    """

    name: str
    pk: str
    ldts: str

    @property
    def dv_macro_entry(self) -> dict[str, Any]:
        """Return the automate_dv-compatible dict for this satellite."""
        return {self.name: {"pk": {"PK": self.pk}, "ldts": {"LDTS": self.ldts}}}


class BridgeWalkEntry(BaseModel):
    """One step in a bridge walk: a link + its effectivity satellite.

    Captures enough information for the template to produce the full
    ``bridge_walk`` mapping expected by the automate_dv ``bridge`` macro.

    ``end_date`` and ``ldts`` default to the automate_dv column-name
    conventions and can be overridden per-entry if needed.
    """

    link: str
    eff_sat: str
    link_pk: str
    link_fk: str
    end_date: str = "END_DATE"
    ldts: str = "LOAD_DATE"

    @property
    def dv_macro_entry(self) -> dict[str, Any]:
        """Return the automate_dv-compatible dict for this bridge walk step."""
        return {
            self.eff_sat: {
                "bridge_link_pk": {"BRIDGE_LINK_PK": self.link_pk},
                "bridge_end_date": {"BRIDGE_END_DATE": self.end_date},
                "bridge_load_date": {"BRIDGE_LOAD_DATE": self.ldts},
                "link_table": self.link,
                "eff_sat_table": self.eff_sat,
            }
        }


class DimSatelliteEntry(BaseModel):
    """One satellite contributing columns to a dimension view."""

    name: str
    columns: list[str]


# ── Business Vault base ────────────────────────────────────────────────────────


class BusinessVaultBaseModel(DvBaseSqlModel, ABC):
    """Base for all Business Vault SQL models.

    Inherits ``file_extension``, ``model_config`` (``populate_by_name``), and
    ``source_model`` from ``DvBaseSqlModel``.  Overrides ``schema_name`` to
    default to ``business_vault`` and sets the layer tag.
    """

    layer: Literal["BV"] = "BV"
    src_ldts: str = Field(default="LOAD_DATE", description="Load-date-timestamp column")
    # Override the raw-vault default schema to business_vault
    schema_name: str = Field(default="business_vault", alias="schema")


# ── Point-in-Time ─────────────────────────────────────────────────────────────


class PitModel(BusinessVaultBaseModel):
    """Point-in-Time table model.

    Snapshots the latest LDTS watermark for each satellite of a hub at
    every ``as_of`` date, enabling efficient historical joins without full
    satellite scans.

    ``source_model`` should contain the driving hub model name.
    ``satellites`` lists every satellite whose LDTS should be tracked.
    """

    dv_type: Literal["pit"] = DBTModelNames.PIT  # type: ignore[assignment]
    src_pk: str = Field(description="Hub hash key column (PK of the PIT table)")
    satellites: list[PitSatelliteEntry] = Field(
        min_length=1, description="Satellites whose watermarks are snapshotted"
    )

    @property
    def models_path(self) -> str:
        return DbtPaths.PIT_TABLES

    @property
    def satellites_dv(self) -> dict[str, Any]:
        """Merged automate_dv ``satellites`` mapping for template rendering."""
        result: dict[str, Any] = {}
        for sat in self.satellites:
            result.update(sat.dv_macro_entry)
        return result


# ── Bridge ────────────────────────────────────────────────────────────────────


class BridgeModel(BusinessVaultBaseModel):
    """Bridge table model.

    Pre-joins a driving hub to one or more links and their effectivity
    satellites, surfacing only currently-active relationships.

    ``source_model`` should contain the driving hub model name.
    ``stage_tables_ldts`` maps each staging model name to its LDTS column,
    as required by the automate_dv ``bridge`` macro's incremental logic.
    """

    dv_type: Literal["bridge"] = DBTModelNames.BRIDGE  # type: ignore[assignment]
    src_pk: str = Field(description="Driving hub hash key (entry point)")
    bridge_walk: list[BridgeWalkEntry] = Field(
        min_length=1, description="Ordered link→eff_sat traversal steps"
    )
    stage_tables_ldts: dict[str, str] = Field(
        description="stage_model_name → LDTS_column_name; used for incremental watermarking"
    )

    @property
    def models_path(self) -> str:
        return DbtPaths.BRIDGE_TABLES

    @property
    def bridge_walk_dv(self) -> dict[str, Any]:
        """Merged automate_dv ``bridge_walk`` mapping for template rendering."""
        result: dict[str, Any] = {}
        for step in self.bridge_walk:
            result.update(step.dv_macro_entry)
        return result


# ── Dimension (star schema) ────────────────────────────────────────────────────


class DimModel(BusinessVaultBaseModel):
    """Dimension view model (star schema).

    Exposes the current state of a hub entity by joining the hub with its
    PIT table and the listed satellites.  Produces a single, denormalised
    row per business key — suitable for BI consumption.

    ``source_model`` should contain the hub model name.
    ``pit_table`` drives the "as-of" join that selects the latest satellite
    records without requiring ``ROW_NUMBER`` on every satellite.
    """

    dv_type: Literal["dim"] = DBTModelNames.DIM  # type: ignore[assignment]
    src_pk: str = Field(description="Hub hash key")
    business_key: str = Field(description="Natural / business key column")
    pit_table: str = Field(description="PIT table that drives the as-of join")
    satellites: list[DimSatelliteEntry] = Field(
        min_length=1, description="Satellites contributing columns to the dimension"
    )

    @property
    def models_path(self) -> str:
        return DbtPaths.DIM_TABLES


# ── Fact (star schema) ────────────────────────────────────────────────────────


class FactModel(BusinessVaultBaseModel):
    """Fact view model (star schema).

    Joins a bridge table with dimension views to produce reporting-ready,
    star-schema fact rows.

    ``source_model`` should contain the bridge table model name.
    ``grain`` lists the column(s) that define the unique grain of the fact
    (typically the link PK or a composite of dimension PKs).
    ``measures`` lists derived numeric columns; may be empty for activity facts.
    """

    dv_type: Literal["fact"] = DBTModelNames.FACT  # type: ignore[assignment]
    grain: list[str] = Field(
        min_length=1,
        description="Column(s) that define the fact grain (used as unique_key for incremental)",
    )
    dimensions: list[str] = Field(
        min_length=1, description="dim_table model names joined to this fact"
    )
    measures: list[str] = Field(
        default_factory=list,
        description="Derived metric column names (empty for activity/event facts)",
    )

    @property
    def models_path(self) -> str:
        return DbtPaths.FACT_TABLES

    @model_validator(mode="after")
    def _source_model_is_bridge(self) -> FactModel:
        if len(self.source_model) != 1:
            raise ValueError(
                "FactModel.source_model must contain exactly one bridge table name."
            )
        return self

    @property
    def bridge_table(self) -> str:
        """Convenience accessor for the single bridge source model."""
        return self.source_model[0]


# ── Business Vault Satellite ───────────────────────────────────────────────────


class BvSatModel(BusinessVaultBaseModel):
    """Business Vault satellite model.

    Applies business rules — derivation, cleansing, classification — on top
    of one raw-vault satellite or hub.  Lives in the ``business_vault`` schema.

    Structurally identical to a raw-vault satellite but:
      - ``source_model`` references a raw-vault sat or hub (not a staging view)
      - ``layer`` is ``"BV"`` instead of ``"RWV"``
      - ``models_path`` routes to the bv_sats sub-folder
    """

    dv_type: Literal["bv_sat"] = DBTModelNames.BV_SAT  # type: ignore[assignment]
    src_pk: str = Field(description="Hub hash key (inherited from parent hub)")
    src_hashdiff: str = Field(description="Hashdiff column for change detection")
    src_payload: list[str] = Field(
        min_length=1, description="Derived / cleansed attribute columns"
    )
    src_eff: str | None = Field(
        default=None, description="Business effective-from date column (optional)"
    )

    @model_validator(mode="after")
    def _single_source_model(self) -> BvSatModel:
        if len(self.source_model) != 1:
            raise ValueError("BvSatModel must have exactly one source_model.")
        return self

    @property
    def models_path(self) -> str:
        return DbtPaths.BV_SATELLITES
