"""Approved-YAML learning corpus: explode a plan into per-object examples.

The feedback loop's write half. On approval, a :class:`ModelingPlan` is turned
into one :class:`RvExampleRow` per raw-vault object (hub / link / satellite) by
rendering it with the SAME deterministic :class:`YamlGenerator` the pipeline
uses, then storing each object's dbt YAML. Because the stored text is exactly
what the generator emits, the read half (:class:`ReferenceLoader`) can re-parse
it with its existing parser — the two halves never drift.

Only raw-vault objects are captured (the generator is called with ``bv=None``);
business-vault artefacts are not few-shot material for the modelling agent.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from dbt_builder.src.ai.agents.yaml_generator import (
    HUBS_DIR,
    LINKS_DIR,
    SATELLITES_DIR,
    YamlGenerator,
)
from dbt_builder.src.ai.reference import ReferenceKind
from dbt_builder.src.ai.store.executor import (
    has_databricks_creds,
    make_databricks_executor,
)
from dbt_builder.src.utils.yaml_store import DeltaExampleStore, RvExampleRow

if TYPE_CHECKING:
    from dbt_builder.src.ai.contracts.decisions import ModelingPlan
    from dbt_builder.src.ai.settings import AISettings

# Raw-vault output directory (leaf name) -> corpus kind. Keyed off the
# generator's own path constants so a layout change can never silently
# mis-tag examples.
_DIR_TO_KIND: dict[str, str] = {
    HUBS_DIR.name: ReferenceKind.HUB.value,
    SATELLITES_DIR.name: ReferenceKind.SATELLITE.value,
    LINKS_DIR.name: ReferenceKind.LINK.value,
}


def plan_to_example_rows(
    plan: ModelingPlan,
    *,
    catalog_id: str,
    plan_id: str,
    version: int,
    approved_by: str,
    generator: YamlGenerator | None = None,
) -> list[RvExampleRow]:
    """Render ``plan`` and return one :class:`RvExampleRow` per raw-vault object.

    Pure: no I/O, no persistence. ``generator`` is injectable for testing but
    defaults to a fresh stateless :class:`YamlGenerator`.
    """
    bundle = (generator or YamlGenerator()).render(plan=plan)  # bv=None → RV only
    rows: list[RvExampleRow] = []
    for file in bundle.files:
        path = PurePosixPath(file.path)
        kind = _DIR_TO_KIND.get(path.parent.name)
        if kind is None:
            continue  # not a raw-vault object (defensive; none emitted here)
        rows.append(
            RvExampleRow(
                catalog=catalog_id,
                plan_id=plan_id,
                version=version,
                object_name=path.stem,
                kind=kind,
                source_path=file.path,
                yaml_text=file.body.decode("utf-8"),
                approved_by=approved_by,
            )
        )
    return rows


def make_example_store(settings: AISettings) -> DeltaExampleStore | None:
    """Return a :class:`DeltaExampleStore` when Databricks is configured, else None.

    The corpus is Delta-only (it needs SQL retrieval). Returns ``None`` for the
    local / ADLS backends so dev and CI keep working without a warehouse — the
    caller simply skips corpus persistence in that case.
    """
    backend = (getattr(settings, "metadata_store_backend", "auto") or "auto").lower()
    if backend not in ("delta", "auto"):
        return None
    if not has_databricks_creds(settings):
        return None
    executor = make_databricks_executor(settings)
    return DeltaExampleStore(
        executor,
        catalog=settings.metadata_delta_catalog,
        schema=settings.metadata_delta_schema,
        table=settings.metadata_delta_examples_table,
    )


__all__ = ["make_example_store", "plan_to_example_rows"]
