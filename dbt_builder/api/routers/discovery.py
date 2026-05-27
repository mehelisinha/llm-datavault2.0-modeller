"""Discovery routes — catalog listing and pipeline snapshot (Steps 1–3)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.api import databricks_uc
from dbt_builder.api.discovery_callables import (
    resolve_snapshot_callables,
    tables_to_include_patterns,
)
from dbt_builder.api.settings import ApiSettings, get_settings
from dbt_builder.api.stub_catalog import list_tables_for_catalog
from dbt_builder.src.ai.contracts.catalog import (
    BronzeSnapshot,
    CatalogSnapshot,
    ChangeSet,
)
from dbt_builder.src.ai.contracts.payloads import SourceSystem
from dbt_builder.src.ai.pipeline.snapshot_helpers import greenfield_catalog_snapshot
from dbt_builder.src.ai.service import DwaService, get_service

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


class CatalogListResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    catalogs: tuple[str, ...]


class SchemaListResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog: str
    schemas: tuple[str, ...]


class TableListResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog: str
    schema_name: str
    tables: tuple[str, ...]


class SnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog: str = Field(min_length=1)
    bronze_schema: str = Field(min_length=1)
    # Optional: when omitted (or empty) the snapshot is treated as a greenfield
    # build — no existing vault to compare against, so every bronze table is
    # classified as NEW by the diff analyzer. When provided, the existing
    # behavior runs: `inspect_catalog` scans this schema for hubs/links/sats.
    vault_schema: str | None = Field(default=None, min_length=1)
    system_id: str | None = None
    system_name: str | None = None
    record_source: str | None = None
    metadata_yaml_path: str | None = None
    # Explicit table allowlist (preferred over regex patterns when the UI
    # provides a multi-select list). When non-empty, only these tables are
    # read from the bronze schema; include_patterns is ignored.
    tables: tuple[str, ...] = ()
    include_patterns: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()


class SnapshotResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    system: SourceSystem
    catalog_snapshot: CatalogSnapshot
    bronze_snapshot: BronzeSnapshot
    change_set: ChangeSet


def _effective_include_patterns(body: SnapshotRequest) -> tuple[str, ...]:
    return tables_to_include_patterns(body.tables, body.include_patterns)


def _list_catalogs_stub(settings: ApiSettings) -> tuple[str, ...]:
    return tuple(sorted(settings.stub_catalog_map.keys()))


def _list_schemas_stub(settings: ApiSettings, catalog: str) -> tuple[str, ...]:
    schemas = settings.stub_catalog_map.get(catalog)
    if schemas is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown catalog '{catalog}'.",
        )
    return tuple(schemas)


def _list_catalogs_spark() -> tuple[str, ...]:
    from shared.utils.spark import get_spark

    spark = get_spark()
    rows = spark.sql("SHOW CATALOGS").collect()
    return tuple(sorted(str(row[0]) for row in rows))


def _list_catalogs_databricks(settings: ApiSettings) -> tuple[str, ...]:
    return databricks_uc.list_catalogs(databricks_uc.get_workspace_client(settings))


def _list_schemas_databricks(settings: ApiSettings, catalog: str) -> tuple[str, ...]:
    return databricks_uc.list_schemas(databricks_uc.get_workspace_client(settings), catalog)


def _list_tables_databricks(settings: ApiSettings, catalog: str, schema: str) -> tuple[str, ...]:
    return databricks_uc.list_tables(databricks_uc.get_workspace_client(settings), catalog, schema)


def _list_tables_stub(catalog: str, schema_name: str, settings: ApiSettings) -> tuple[str, ...]:
    return list_tables_for_catalog(catalog, schema_name, settings.metadata_dir)


def _list_tables_spark(catalog: str, schema_name: str) -> tuple[str, ...]:
    from shared.utils.spark import get_spark

    spark = get_spark()
    rows = spark.sql(f"SHOW TABLES IN `{catalog}`.`{schema_name}`").collect()
    return tuple(
        sorted(str(row.tableName) for row in rows if not getattr(row, "isTemporary", False))
    )


def _list_schemas_spark(catalog: str) -> tuple[str, ...]:
    from shared.utils.spark import get_spark

    spark = get_spark()
    rows = spark.sql(f"SHOW SCHEMAS IN `{catalog}`").collect()
    return tuple(sorted(str(row[0]) for row in rows))


def _run_snapshot_stub(
    body: SnapshotRequest,
    settings: ApiSettings,
    service: DwaService,
) -> SnapshotResponse:
    catalog = body.catalog
    list_vault_entities, describe_vault, list_bronze_tables, describe_bronze = (
        resolve_snapshot_callables(
            settings,
            catalog=catalog,
            bronze_schema=body.bronze_schema,
            vault_schema=body.vault_schema,
        )
    )
    if body.vault_schema:
        catalog_snapshot = service.inspect_catalog(
            catalog=catalog,
            schema_name=body.vault_schema,
            list_entities=list_vault_entities,
            describe_table=describe_vault,
            metadata_yaml_path=body.metadata_yaml_path,
        )
    else:
        catalog_snapshot = greenfield_catalog_snapshot(catalog, body.bronze_schema)
    bronze_snapshot = service.read_bronze(
        catalog=catalog,
        schema_name=body.bronze_schema,
        list_tables=list_bronze_tables,
        describe_table=describe_bronze,
        include_patterns=_effective_include_patterns(body),
        exclude_patterns=body.exclude_patterns,
    )
    change_set = service.diff(catalog_snapshot, bronze_snapshot)
    system = SourceSystem(
        system_id=body.system_id or settings.default_system_id,
        system_name=body.system_name or settings.default_system_name,
        source_type="delta",
        catalog=catalog,
        schema_name=body.bronze_schema,
        record_source=body.record_source or settings.default_record_source,
    )
    return SnapshotResponse(
        system=system,
        catalog_snapshot=catalog_snapshot,
        bronze_snapshot=bronze_snapshot,
        change_set=change_set,
    )


def _run_snapshot_spark(
    body: SnapshotRequest,
    settings: ApiSettings,
    service: DwaService,
) -> SnapshotResponse:
    from shared.utils.spark import get_spark

    spark = get_spark()

    def list_entities(catalog: str, schema_name: str) -> list[tuple[str, str]]:
        rows = spark.sql(f"SHOW TABLES IN `{catalog}`.`{schema_name}`").collect()
        return [(str(row.tableName), str(row.tableType or "TABLE")) for row in rows]

    def describe_vault(
        catalog: str, schema_name: str, table: str
    ) -> list[tuple[str, str, bool, str | None]]:
        rows = spark.sql(f"DESCRIBE TABLE `{catalog}`.`{schema_name}`.`{table}`").collect()
        return [
            (
                str(row.col_name),
                str(row.data_type),
                bool(row.nullable),
                getattr(row, "comment", None),
            )
            for row in rows
            if row.col_name and not str(row.col_name).startswith("#")
        ]

    def list_tables(catalog: str, schema_name: str) -> list[str]:
        rows = spark.sql(f"SHOW TABLES IN `{catalog}`.`{schema_name}`").collect()
        return [str(row.tableName) for row in rows]

    def describe_bronze(
        catalog: str, schema_name: str, table: str
    ) -> list[tuple[str, str, bool, str | None, bool]]:
        rows = spark.sql(f"DESCRIBE TABLE `{catalog}`.`{schema_name}`.`{table}`").collect()
        return [
            (
                str(row.col_name),
                str(row.data_type),
                bool(row.nullable),
                getattr(row, "comment", None),
                bool(getattr(row, "is_partition", False)),
            )
            for row in rows
            if row.col_name and not str(row.col_name).startswith("#")
        ]

    if body.vault_schema:
        catalog_snapshot = service.inspect_catalog(
            catalog=body.catalog,
            schema_name=body.vault_schema,
            list_entities=list_entities,
            describe_table=describe_vault,
            metadata_yaml_path=body.metadata_yaml_path,
        )
    else:
        catalog_snapshot = greenfield_catalog_snapshot(body.catalog, body.bronze_schema)
    bronze_snapshot = service.read_bronze(
        catalog=body.catalog,
        schema_name=body.bronze_schema,
        list_tables=list_tables,
        describe_table=describe_bronze,
        include_patterns=_effective_include_patterns(body),
        exclude_patterns=body.exclude_patterns,
    )
    change_set = service.diff(catalog_snapshot, bronze_snapshot)
    system = SourceSystem(
        system_id=body.system_id or settings.default_system_id,
        system_name=body.system_name or settings.default_system_name,
        source_type="delta",
        catalog=body.catalog,
        schema_name=body.bronze_schema,
        record_source=body.record_source or settings.default_record_source,
    )
    return SnapshotResponse(
        system=system,
        catalog_snapshot=catalog_snapshot,
        bronze_snapshot=bronze_snapshot,
        change_set=change_set,
    )


def _run_snapshot_databricks(
    body: SnapshotRequest,
    settings: ApiSettings,
    service: DwaService,
) -> SnapshotResponse:
    client = databricks_uc.get_workspace_client(settings)
    list_vault_entities, describe_vault, list_bronze_tables, describe_bronze = (
        databricks_uc.make_snapshot_callables(
            client,
            catalog=body.catalog,
            vault_schema=body.vault_schema or body.bronze_schema,
            bronze_schema=body.bronze_schema,
        )
    )
    if body.vault_schema:
        catalog_snapshot = service.inspect_catalog(
            catalog=body.catalog,
            schema_name=body.vault_schema,
            list_entities=list_vault_entities,
            describe_table=describe_vault,
            metadata_yaml_path=body.metadata_yaml_path,
        )
    else:
        catalog_snapshot = greenfield_catalog_snapshot(body.catalog, body.bronze_schema)
    bronze_snapshot = service.read_bronze(
        catalog=body.catalog,
        schema_name=body.bronze_schema,
        list_tables=list_bronze_tables,
        describe_table=describe_bronze,
        include_patterns=_effective_include_patterns(body),
        exclude_patterns=body.exclude_patterns,
    )
    change_set = service.diff(catalog_snapshot, bronze_snapshot)
    system = SourceSystem(
        system_id=body.system_id or settings.default_system_id,
        system_name=body.system_name or settings.default_system_name,
        source_type="delta",
        catalog=body.catalog,
        schema_name=body.bronze_schema,
        record_source=body.record_source or settings.default_record_source,
    )
    return SnapshotResponse(
        system=system,
        catalog_snapshot=catalog_snapshot,
        bronze_snapshot=bronze_snapshot,
        change_set=change_set,
    )


@router.get("/catalogs", response_model=CatalogListResponse)
def list_catalogs(
    settings: Annotated[ApiSettings, Depends(get_settings)],
) -> CatalogListResponse:
    if settings.discovery_mode == "stub":
        return CatalogListResponse(catalogs=_list_catalogs_stub(settings))
    if settings.discovery_mode == "databricks":
        try:
            return CatalogListResponse(catalogs=_list_catalogs_databricks(settings))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unity Catalog REST listing failed: {exc}",
            ) from exc
    try:
        return CatalogListResponse(catalogs=_list_catalogs_spark())
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Spark catalog listing failed: {exc}",
        ) from exc


@router.get("/catalogs/{catalog}/schemas", response_model=SchemaListResponse)
def list_schemas(
    catalog: str,
    settings: Annotated[ApiSettings, Depends(get_settings)],
) -> SchemaListResponse:
    if settings.discovery_mode == "stub":
        return SchemaListResponse(catalog=catalog, schemas=_list_schemas_stub(settings, catalog))
    if settings.discovery_mode == "databricks":
        try:
            return SchemaListResponse(
                catalog=catalog,
                schemas=_list_schemas_databricks(settings, catalog),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unity Catalog REST schema listing failed: {exc}",
            ) from exc
    try:
        return SchemaListResponse(catalog=catalog, schemas=_list_schemas_spark(catalog))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Spark schema listing failed: {exc}",
        ) from exc


@router.get("/catalogs/{catalog}/schemas/{schema}/tables", response_model=TableListResponse)
def list_tables(
    catalog: str,
    schema: str,
    settings: Annotated[ApiSettings, Depends(get_settings)],
) -> TableListResponse:
    if settings.discovery_mode == "stub":
        tables = _list_tables_stub(catalog, schema, settings)
        return TableListResponse(catalog=catalog, schema_name=schema, tables=tables)
    if settings.discovery_mode == "databricks":
        try:
            return TableListResponse(
                catalog=catalog,
                schema_name=schema,
                tables=_list_tables_databricks(settings, catalog, schema),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unity Catalog REST table listing failed: {exc}",
            ) from exc
    try:
        return TableListResponse(
            catalog=catalog,
            schema_name=schema,
            tables=_list_tables_spark(catalog, schema),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Spark table listing failed: {exc}",
        ) from exc


@router.post("/snapshot", response_model=SnapshotResponse)
def snapshot(
    body: SnapshotRequest,
    settings: Annotated[ApiSettings, Depends(get_settings)],
    service: Annotated[DwaService, Depends(get_service)],  # noqa: B008
) -> SnapshotResponse:
    if settings.discovery_mode == "stub":
        return _run_snapshot_stub(body, settings, service)
    if settings.discovery_mode == "databricks":
        try:
            return _run_snapshot_databricks(body, settings, service)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unity Catalog REST snapshot failed: {exc}",
            ) from exc
    try:
        return _run_snapshot_spark(body, settings, service)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Spark snapshot failed: {exc}",
        ) from exc
