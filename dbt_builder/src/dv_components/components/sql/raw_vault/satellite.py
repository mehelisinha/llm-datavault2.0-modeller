"""
Satellite components for Data Vault v2.

Contains:
- SatelliteBase: abstract base for both satellite flavors
- Satellite:     regular satellite (src_hashdiff + src_payload)
- EffSat:        effectivity satellite (src_dfk + src_eff, tracks relationship lifecycle)
- SatelliteFactory: creates the right flavor based on model type
"""

from abc import abstractmethod
from logging import Logger

from dbt_builder.src.dv_components.components.base import DVBaseRawVaultComponent
from dbt_builder.src.dv_components.pydantic_model.sql.raw_vaul import (
    EffSatModel,
    SatelliteModel,
)


class SatelliteBaseComponent(DVBaseRawVaultComponent):
    """Abstract base for all satellite component flavors."""

    @abstractmethod
    def _get_render_kwargs(self) -> dict: ...

    @property
    @abstractmethod
    def _sql_template_body(self) -> str: ...

    @property
    def _pk_tests(self) -> list[str]:
        # A satellite historises each hash key over time, so its grain is the composite
        # (hash key + load date). The hash key alone repeats across versions — testing it
        # for `unique` is therefore wrong by Data Vault design. Keep only `not_null` here;
        # the composite uniqueness is asserted at model level (`_model_level_tests`).
        return ["not_null"]

    @property
    def _model_level_tests(self) -> list[dict]:
        return [
            {
                "dbt_utils.unique_combination_of_columns": {
                    "combination_of_columns": [self.model.src_pk, self.model.src_ldts],
                }
            }
        ]


class SatComponent(SatelliteBaseComponent):
    """Regular Data Vault Satellite (descriptive attributes with hashdiff)."""

    def __init__(self, model: SatelliteModel, logger: Logger):
        super().__init__(model=model, logger=logger)

        if not isinstance(model, SatelliteModel):
            raise ValueError(f"Expected SatelliteModel, got {type(model)}")
        self.model: SatelliteModel = model

    def _get_render_kwargs(self) -> dict:
        return dict(
            config_options=self._build_sql_config(
                {
                    "unique_key": [
                        self.model.src_pk,
                        self.model.src_ldts,
                    ]
                }
            ),
            source_model=self.model.source_model[0],
            src_pk=self.model.src_pk,
            src_hashdiff=self.model.src_hashdiff,
            src_payload=self._formatter.format_list(self.model.src_payload),
            src_ldts=self.model.src_ldts,
            src_source=self.model.src_source,
            src_eff=self.model.src_eff,
        )

    @property
    def _sql_template_body(self) -> str:
        return """
<% set rendered = render_config(config_options) %>
<<rendered>>
{%- set source_model = '<<source_model>>' -%}
{%- set src_pk       = '<<src_pk>>' -%}
{%- set src_hashdiff = '<<src_hashdiff>>' -%}
{%- set src_payload  = <<src_payload>> -%}
{%- set src_ldts     = '<<src_ldts>>' -%}
{%- set src_source   = '<<src_source>>' -%}
<% if src_eff %>{%- set src_eff      = '<<src_eff>>' -%}
<% endif %>{{ automate_dv.sat(
    src_pk      = src_pk,
    src_hashdiff= src_hashdiff,
    src_payload = src_payload,
    src_ldts    = src_ldts,
    src_source  = src_source,<% if src_eff %>
    src_eff     = src_eff,<% endif %>
    source_model= source_model
) }}"""

    @property
    def _cols_for_yml(self) -> list[dict]:
        return self._default_cols_for_yml + [
            {"name": self.model.src_hashdiff, "tests": ["not_null"]},
        ]


class EffSatComponent(SatelliteBaseComponent):
    """Effectivity Satellite — tracks relationship lifecycle (open/close via CDC). It is always attached to a link."""

    def __init__(self, model: EffSatModel, logger: Logger):
        super().__init__(model=model, logger=logger)

        if not isinstance(model, EffSatModel):
            raise ValueError(f"Expected EffSatModel, got {type(model)}")
        self.model: EffSatModel = model

    def _get_render_kwargs(self) -> dict:
        sfk = self.model.src_sfk
        # Render as a Jinja list literal for multi-FK links, or a quoted string for single FK
        src_sfk_rendered = (
            self._formatter.format_list(sfk) if isinstance(sfk, list) else f"'{sfk}'"
        )
        return dict(
            config_options=self._build_sql_config(
                {"unique_key": [self.model.src_pk, self.model.src_ldts]}
            ),
            source_model=self.model.source_model[0],
            src_pk=self.model.src_pk,
            src_dfk=self.model.src_dfk,
            src_sfk=src_sfk_rendered,
            src_eff=self.model.src_eff,
            src_start_date=self.model.src_start_date,  # when a relationship starts in the source system
            src_end_date=self.model.src_end_date,
            src_ldts=self.model.src_ldts,
            src_source=self.model.src_source,
        )

    @property
    def _sql_template_body(self) -> str:
        return """
<% set rendered = render_config(config_options) %>
<<rendered>>
{%- set source_model = '<<source_model>>' -%}
{%- set src_pk       = '<<src_pk>>' -%}
{%- set src_dfk      = '<<src_dfk>>' -%}
{%- set src_sfk      = <<src_sfk>> -%}

{%- set src_start_date = '<<src_start_date>>' -%}
{%- set src_end_date = '<<src_end_date>>' -%}

{%- set src_eff      = '<<src_eff>>' -%}
{%- set src_ldts     = '<<src_ldts>>' -%}
{%- set src_source   = '<<src_source>>' -%}
{{ automate_dv.eff_sat(
    src_pk         = src_pk,
    src_dfk        = src_dfk,
    src_sfk        = src_sfk,
    src_start_date = src_start_date,
    src_end_date   = src_end_date,
    src_eff        = src_eff,
    src_ldts       = src_ldts,
    src_source     = src_source,
    source_model   = source_model
) }}"""

    @property
    def _cols_for_yml(self) -> list[dict]:
        config = self._default_cols_for_yml
        if self.model.src_dfk != self.model.src_pk:
            config.append({"name": self.model.src_dfk, "tests": ["not_null"]})
        return config


class SatComponentFactory:
    """Returns the correct satellite component based on the model's dv_type."""

    def __new__(
        cls, model: SatelliteModel | EffSatModel, logger: Logger
    ) -> SatelliteBaseComponent:
        if isinstance(model, EffSatModel):
            return EffSatComponent(model=model, logger=logger)
        return SatComponent(model=model, logger=logger)


if __name__ == "__main__":
    from shared.src.logger.default_logger import default_logger

    # --- Regular Satellite ---
    model = SatelliteModel(
        name="sat_terminal_details",
        source_model=["stg_terminals"],
        src_pk="HK_TERMINAL",
        src_hashdiff="HASHDIFF_TERMINAL_DETAILS",
        src_payload=["name", "sequence_number"],
        src_ldts="LOAD_DATE",
        src_eff="EFFECTIVE_FROM",
    )

    sat = SatComponentFactory(model=model, logger=default_logger)
    print(sat.generate_sql_str())

    # --- Effectivity Satellite ---
    eff_model = EffSatModel(
        name="eff_sat_terminal_equipment_node",
        source_model=["stg_terminals"],
        src_pk="HK_TERMINAL_EQUIPMENT_NODE",
        src_dfk="HK_TERMINAL_EQUIPMENT_NODE",
        src_eff="EFFECTIVE_FROM",
        src_sfk="SRC_SFK",
        src_end_date="SRC_END_DATE",
        src_start_date="SRC_START_DATE",
        src_ldts="LOAD_DATE",
    )

    eff = SatComponentFactory(model=eff_model, logger=default_logger)
    print(eff.generate_sql_str())
