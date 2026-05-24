"""Schema Analyzer agent (Step 4 of the v2 metadata-generator pipeline).

This is the *pipeline-aware* wrapper around the lower-level
:class:`~dbt_builder.src.ai.agents.modeller.ModellingAgent`. Responsibilities:

1. Filter the bronze snapshot down to tables the diff says are
   *actionable* (``NEW`` or ``DRIFT``) — and let callers narrow further
   via a custom ``skip_predicate``.
2. Adapt the typed pipeline contracts (:class:`BronzeSnapshot` /
   :class:`SourceSystem`) into the :class:`DiscoveryPayload` the LLM
   modeller already understands. Keeping the conversion in one place
   means the LLM contract can evolve without touching the rest of the
   pipeline.
3. Delegate the LLM call to an injected ``propose_fn``. The default is
   ``ModellingAgent.propose``, but tests and offline runs can pass any
   callable that maps payload → :class:`ModelingPlan`. This is the seam
   that keeps the module importable without an Azure OpenAI client.

What this module *does not* do
------------------------------
* It does not generate YAML — that is the YAML Generator agent's job.
* It does not propose business-vault objects — that is the BV Architect's job.
* It does not validate the plan — that is the Validator's job.

Each of those sits behind its own module so the pipeline composes from
small pieces with single responsibilities.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from dbt_builder.src.ai.contracts.catalog import (
    BronzeSnapshot,
    BronzeTable,
    CatalogSnapshot,
    ChangeCategory,
    ChangeSet,
    TableChange,
)
from dbt_builder.src.ai.contracts.decisions import ModelingPlan
from dbt_builder.src.ai.contracts.payloads import (
    DiscoveryPayload,
    InferredType,
    SourceColumn,
    SourceSystem,
    SourceTable,
)

if TYPE_CHECKING:
    pass


# Coarse mapping from raw Spark/Delta dtypes to InferredType. Kept narrow
# on purpose: the LLM gets the raw_dtype anyway, and a wide mapping table
# tends to drift from reality. Anything unmatched falls through to UNKNOWN.
_RAW_DTYPE_PREFIXES: tuple[tuple[str, InferredType], ...] = (
    ("string", InferredType.STRING),
    ("varchar", InferredType.STRING),
    ("char", InferredType.STRING),
    ("text", InferredType.STRING),
    ("bigint", InferredType.INTEGER),
    ("int", InferredType.INTEGER),
    ("smallint", InferredType.INTEGER),
    ("tinyint", InferredType.INTEGER),
    ("long", InferredType.INTEGER),
    ("double", InferredType.FLOAT),
    ("float", InferredType.FLOAT),
    ("decimal", InferredType.FLOAT),
    ("numeric", InferredType.FLOAT),
    ("boolean", InferredType.BOOLEAN),
    ("bool", InferredType.BOOLEAN),
    ("date", InferredType.DATE),
    ("timestamp", InferredType.TIMESTAMP),
    ("uuid", InferredType.UUID),
    ("json", InferredType.JSON),
    ("struct", InferredType.JSON),
    ("array", InferredType.JSON),
    ("map", InferredType.JSON),
)


def _infer_type(raw_dtype: str) -> InferredType:
    """Best-effort coarse type inference from a raw Spark/Delta dtype string."""
    lowered = raw_dtype.strip().lower()
    for prefix, kind in _RAW_DTYPE_PREFIXES:
        if lowered.startswith(prefix):
            return kind
    return InferredType.UNKNOWN


# Public type aliases. A skip predicate lets callers express custom rules
# (e.g. "skip anything still in quarantine") without sub-classing.
SkipPredicate = Callable[[BronzeTable, TableChange | None], bool]
ProposeFn = Callable[[DiscoveryPayload], ModelingPlan]


class _Modeller(Protocol):
    """Structural interface so SchemaAnalyzer accepts ModellingAgent or a stub."""

    def propose(self, payload: DiscoveryPayload) -> ModelingPlan: ...


class SchemaAnalyzerError(RuntimeError):
    """Raised when the analyzer cannot build a payload to send to the LLM."""


def bronze_table_to_source_table(table: BronzeTable) -> SourceTable:
    """Adapter: pipeline :class:`BronzeTable` -> LLM :class:`SourceTable`.

    Pure / lossless for the fields the modeller cares about. Sample values
    and column profiles are absent in the bronze snapshot, so the resulting
    payload omits them — the LLM relies on raw dtypes plus the (optional)
    business-key hint instead.
    """
    columns = tuple(
        SourceColumn(
            name=col.name,
            raw_dtype=col.raw_dtype,
            inferred_type=_infer_type(col.raw_dtype),
            nullable=col.nullable,
            description=col.comment,
            ordinal_position=idx,
        )
        for idx, col in enumerate(table.columns)
    )
    return SourceTable(
        name=table.name,
        schema_name=table.schema_name,
        catalog=table.catalog,
        columns=columns,
    )


def _default_skip_predicate(_: BronzeTable, change: TableChange | None) -> bool:
    """Skip when the change category is UNCHANGED, ORPHANED, or unknown.

    A bronze table with no entry in the change-set is treated as unknown
    rather than implicitly NEW: callers must classify every bronze table
    before sending it through the analyzer, and we'd rather skip than
    silently spend tokens on something the diff didn't authorise.
    """
    if change is None:
        return True
    return change.category in (ChangeCategory.UNCHANGED, ChangeCategory.ORPHANED)


class SchemaAnalyzer:
    """Step 4 — turn a bronze snapshot + change-set into a :class:`ModelingPlan`.

    Parameters
    ----------
    propose_fn
        Callable that takes a :class:`DiscoveryPayload` and returns a
        :class:`ModelingPlan`. In production this is bound to
        :meth:`ModellingAgent.propose`; in tests it's a deterministic
        stub. Required — the analyzer never constructs an LLM client
        itself, which keeps it cheap to instantiate and test.
    skip_predicate
        Optional override of the default UNCHANGED/ORPHANED skip rule.
        Returning ``True`` means "do not send this table to the LLM".
    """

    def __init__(
        self,
        *,
        propose_fn: ProposeFn,
        skip_predicate: SkipPredicate | None = None,
    ) -> None:
        if propose_fn is None:
            raise ValueError("propose_fn is required")
        self._propose_fn = propose_fn
        self._skip = skip_predicate or _default_skip_predicate

    @classmethod
    def from_modeller(
        cls,
        modeller: _Modeller,
        *,
        skip_predicate: SkipPredicate | None = None,
    ) -> SchemaAnalyzer:
        """Convenience constructor that binds an existing modeller's propose method."""
        return cls(propose_fn=modeller.propose, skip_predicate=skip_predicate)

    # ── public ──────────────────────────────────────────────────────────────
    def select_actionable(
        self,
        bronze: BronzeSnapshot,
        change_set: ChangeSet,
    ) -> tuple[BronzeTable, ...]:
        """Apply the skip predicate and return the bronze tables to be analysed.

        Selection is deterministic: tables are returned in the same order
        they appear in the bronze snapshot, with skipped entries filtered
        out. Idempotent across repeated calls with the same inputs — the
        property the byte-equality snapshot tests rely on.
        """
        change_by_name = {c.table_name.lower(): c for c in change_set.changes}
        return tuple(
            t for t in bronze.tables if not self._skip(t, change_by_name.get(t.name.lower()))
        )

    def build_payload(
        self,
        *,
        system: SourceSystem,
        bronze: BronzeSnapshot,
        change_set: ChangeSet,
        catalog_snapshot: CatalogSnapshot | None = None,
    ) -> DiscoveryPayload:
        """Build the :class:`DiscoveryPayload` that will be sent to the LLM."""
        actionable = self.select_actionable(bronze, change_set)
        if not actionable:
            raise SchemaAnalyzerError(
                "No actionable bronze tables after applying skip predicate; "
                "nothing for the schema analyzer to propose."
            )
        return DiscoveryPayload(
            system=system,
            tables=tuple(bronze_table_to_source_table(t) for t in actionable),
            catalog_snapshot=catalog_snapshot,
        )

    def analyze(
        self,
        *,
        system: SourceSystem,
        bronze: BronzeSnapshot,
        change_set: ChangeSet,
        catalog_snapshot: CatalogSnapshot | None = None,
    ) -> ModelingPlan:
        """Top-level entry point: select -> build -> delegate to the modeller."""
        payload = self.build_payload(
            system=system,
            bronze=bronze,
            change_set=change_set,
            catalog_snapshot=catalog_snapshot,
        )
        return self._propose_fn(payload)
