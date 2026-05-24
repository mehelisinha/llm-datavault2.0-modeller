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

import logging
import re
from pathlib import Path
from typing import Protocol, runtime_checkable

import yaml

_log = logging.getLogger(__name__)

# ── helpers ──────────────────────────────────────────────────────────────────


def catalog_from_yaml(rendered_yaml: str) -> str:
    """Extract ``system.catalog`` from a rendered metadata YAML string.

    Returns ``"unknown"`` when the field is absent or the YAML is malformed,
    so a missing catalog never causes a hard failure at save time.
    """
    try:
        parsed = yaml.safe_load(rendered_yaml)
        catalog = parsed.get("system", {}).get("catalog", "")
        if catalog and re.match(r"^[a-z0-9_\-]+$", str(catalog), re.IGNORECASE):
            return str(catalog).lower()
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
    "LocalYamlStore",
    "YamlStore",
    "catalog_from_yaml",
]
