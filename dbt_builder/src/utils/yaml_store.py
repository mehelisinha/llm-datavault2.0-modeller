"""YAML metadata store — persists approved metadata YAMLs per catalog.

Storage implementations live here (non-AI utility tier) so both Databricks
notebook tasks and the AI service facade can use them without crossing
architectural boundaries. The AI-aware factory ``make_yaml_store`` stays in
``dbt_builder.src.ai.store.yaml_store``.

Two implementations are provided:

* :class:`LocalYamlStore`  — filesystem (dev / CI), no extra dependencies.
* :class:`AdlsYamlStore`   — Azure Data Lake Storage Gen2 (production), uses
  ``azure-storage-file-datalake`` (``[ai]`` extras).

Path convention (shared by both implementations)::

    catalogs/
        {catalog_id}/
            latest.yaml              ← always the most-recently approved YAML
            v{version}_{plan_id}.yaml  ← immutable per-approval history entry
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Protocol, runtime_checkable

import yaml

_log = logging.getLogger(__name__)

# ── helpers ──────────────────────────────────────────────────────────────────


def catalog_from_yaml(rendered_yaml: str) -> str:
    """Extract the catalog identifier from a rendered metadata YAML string.

    Looks at ``system.catalog`` first; falls back to ``system.system_id``
    (which is what the metadata-v3 emitter populates by default). Returns
    ``"unknown"`` only when both are absent or the YAML is malformed, so
    a missing catalog never causes a hard failure at save time.
    """
    try:
        parsed = yaml.safe_load(rendered_yaml)
        system = parsed.get("system", {}) if isinstance(parsed, dict) else {}
        for key in ("catalog", "system_id"):
            value = system.get(key, "")
            if value and re.match(r"^[a-z0-9_\-]+$", str(value), re.IGNORECASE):
                return str(value).lower()
    except Exception:
        pass
    return "unknown"


def _versioned_name(version: int, plan_id: str) -> str:
    """Return a safe filename for the versioned copy, e.g. ``v3_abc123.yaml``."""
    safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", plan_id)[:40]
    return f"v{version}_{safe_id}.yaml"


# ── Protocol ─────────────────────────────────────────────────────────────────


@runtime_checkable
class YamlStore(Protocol):
    """Minimum surface the service facade depends on."""

    def save(
        self,
        *,
        catalog_id: str,
        plan_id: str,
        version: int,
        rendered_yaml: str,
    ) -> str:
        """Persist *rendered_yaml* and return the canonical path / URL."""
        ...

    def get_latest(self, catalog_id: str) -> str:
        """Return the content of the latest approved YAML for *catalog_id*.

        Raises :exc:`FileNotFoundError` when no approved YAML exists yet.
        """
        ...


# ── Local (filesystem) implementation ────────────────────────────────────────


class LocalYamlStore:
    """Filesystem-backed store.  No Azure dependencies; safe for dev and CI."""

    def __init__(self, root: str | Path = ".cache/approved_yamls") -> None:
        self._root = Path(root)

    def save(
        self,
        *,
        catalog_id: str,
        plan_id: str,
        version: int,
        rendered_yaml: str,
    ) -> str:
        catalog_dir = self._root / "catalogs" / catalog_id
        catalog_dir.mkdir(parents=True, exist_ok=True)

        versioned = catalog_dir / _versioned_name(version, plan_id)
        versioned.write_text(rendered_yaml, encoding="utf-8")

        latest = catalog_dir / "latest.yaml"
        latest.write_text(rendered_yaml, encoding="utf-8")

        _log.info("LocalYamlStore: saved %s (v%d) → %s", catalog_id, version, latest)
        return str(latest)

    def get_latest(self, catalog_id: str) -> str:
        latest = self._root / "catalogs" / catalog_id / "latest.yaml"
        if not latest.exists():
            raise FileNotFoundError(
                f"No approved YAML found for catalog '{catalog_id}' under {self._root}"
            )
        return latest.read_text(encoding="utf-8")


# ── ADLS Gen2 implementation ─────────────────────────────────────────────────


class AdlsYamlStore:
    """Azure Data Lake Storage Gen2 backed store for production use."""

    def __init__(
        self,
        *,
        account_name: str,
        container: str,
        tenant_id: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        # Lazy imports so LocalYamlStore works without the optional dep installed.
        from azure.identity import ClientSecretCredential
        from azure.storage.filedatalake import DataLakeServiceClient

        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        self._service = DataLakeServiceClient(
            account_url=f"https://{account_name}.dfs.core.windows.net",
            credential=credential,
        )
        self._container = container

    def _fs(self):
        return self._service.get_file_system_client(self._container)

    def _upload(self, path: str, data: bytes, *, overwrite: bool) -> None:
        fs = self._fs()
        parent = path.rsplit("/", 1)[0]
        try:
            fs.create_directory(parent)
        except Exception:
            pass
        file_client = fs.get_file_client(path)
        file_client.upload_data(data, overwrite=overwrite, length=len(data))

    def save(
        self,
        *,
        catalog_id: str,
        plan_id: str,
        version: int,
        rendered_yaml: str,
    ) -> str:
        data = rendered_yaml.encode("utf-8")

        versioned_path = f"catalogs/{catalog_id}/{_versioned_name(version, plan_id)}"
        self._upload(versioned_path, data, overwrite=False)

        latest_path = f"catalogs/{catalog_id}/latest.yaml"
        self._upload(latest_path, data, overwrite=True)

        url = (
            f"abfss://{self._container}@"
            f"{self._service.account_name}.dfs.core.windows.net/"
            f"{latest_path}"
        )
        _log.info("AdlsYamlStore: saved %s (v%d) → %s", catalog_id, version, url)
        return url

    def get_latest(self, catalog_id: str) -> str:
        path = f"catalogs/{catalog_id}/latest.yaml"
        file_client = self._fs().get_file_client(path)
        try:
            download = file_client.download_file()
            return download.readall().decode("utf-8")
        except Exception as exc:
            raise FileNotFoundError(
                f"No approved YAML found for catalog '{catalog_id}' "
                f"in container '{self._container}'"
            ) from exc


__all__ = [
    "AdlsYamlStore",
    "DeltaYamlStore",
    "LocalYamlStore",
    "YamlStore",
    "catalog_from_yaml",
]


# ── Delta (Databricks SQL warehouse) implementation ──────────────────────────


class DeltaYamlStore:
    """Unity-Catalog Delta-backed YAML store.

    Persists every approved YAML as an immutable row in
    ``{catalog}.{schema}.{table}`` with columns::

        catalog      STRING  (the source-system catalog, NOT the UC catalog)
        plan_id      STRING
        version      INT
        yaml_text    STRING
        yaml_sha256  STRING
        created_at   TIMESTAMP

    ``get_latest`` returns the most recent row per ``catalog``. The table
    is created on first use (``CREATE TABLE IF NOT EXISTS``) so first
    deploy is zero-touch beyond granting the warehouse principal MODIFY
    on the schema.
    """

    def __init__(
        self,
        executor,  # type: ignore[no-untyped-def]  # DatabricksSqlExecutor (avoid cycle)
        *,
        catalog: str = "dwa_meta",
        schema: str = "default",
        table: str = "yaml_versions",
    ) -> None:
        from dbt_builder.src.utils.databricks_sql import DatabricksSqlExecutor

        if not isinstance(executor, DatabricksSqlExecutor):  # defensive at boundary
            raise TypeError("executor must be a DatabricksSqlExecutor instance.")
        # Identifier whitelist — these go into raw SQL, never user-supplied at runtime.
        for ident in (catalog, schema, table):
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", ident):
                raise ValueError(f"Invalid Delta identifier: {ident!r}")
        self._exec = executor
        self._fqn = f"`{catalog}`.`{schema}`.`{table}`"
        self._ensure_table()

    def _ensure_table(self) -> None:
        # USING DELTA is implicit on a Unity Catalog managed table but we make
        # it explicit so external workspaces with a non-Delta default still
        # land on Delta. PARTITIONED BY (catalog) keeps the common "latest per
        # catalog" lookup cheap as the table grows.
        self._exec.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self._fqn} (
                catalog      STRING NOT NULL,
                plan_id      STRING NOT NULL,
                version      INT    NOT NULL,
                yaml_text    STRING NOT NULL,
                yaml_sha256  STRING NOT NULL,
                created_at   TIMESTAMP NOT NULL
            ) USING DELTA
            PARTITIONED BY (catalog)
            """
        )

    def save(
        self,
        *,
        catalog_id: str,
        plan_id: str,
        version: int,
        rendered_yaml: str,
    ) -> str:
        digest = hashlib.sha256(rendered_yaml.encode("utf-8")).hexdigest()
        self._exec.execute(
            f"""
            INSERT INTO {self._fqn}
                (catalog, plan_id, version, yaml_text, yaml_sha256, created_at)
            VALUES (?, ?, ?, ?, ?, current_timestamp())
            """,
            (catalog_id, plan_id, int(version), rendered_yaml, digest),
        )
        url = f"delta://{self._fqn}#catalog={catalog_id};plan_id={plan_id};version={version}"
        _log.info("DeltaYamlStore: saved %s (v%d) → %s", catalog_id, version, url)
        return url

    def get_latest(self, catalog_id: str) -> str:
        row = self._exec.fetchone(
            f"""
            SELECT yaml_text FROM {self._fqn}
            WHERE catalog = ?
            ORDER BY created_at DESC, version DESC
            LIMIT 1
            """,
            (catalog_id,),
        )
        if row is None:
            raise FileNotFoundError(
                f"No approved YAML found for catalog '{catalog_id}' in {self._fqn}"
            )
        return str(row[0])
