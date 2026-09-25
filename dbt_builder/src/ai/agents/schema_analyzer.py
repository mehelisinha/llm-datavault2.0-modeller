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

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
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

# Number of skipped-table names retained per skip reason for use in error
# messages. Bounded so the message stays readable on schemas with hundreds of
# tables; the *count* of skipped tables is always exact, only the sample is
# truncated.
_SKIP_SAMPLE_LIMIT = 5

# Sentinel key used in `BronzeAnalysisSummary.skipped_by_category` /
# `skipped_sample_names` for bronze tables that have no entry in the change-set
# at all. Kept as a module constant so call-sites do not have to import the
# string literal and so the value is one place to change if the contract ever
# adds a real "unclassified" category.
UNCLASSIFIED_SKIP_REASON = "missing-from-change-set"


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

# Type alias for the key set of the per-reason breakdown maps. Either a
# concrete `ChangeCategory` (the change-set classified the table) or
# `UNCLASSIFIED_SKIP_REASON` (the change-set had no entry for it).
SkipReason = ChangeCategory | str


class _Modeller(Protocol):
    """Structural interface so SchemaAnalyzer accepts ModellingAgent or a stub."""

    def propose(self, payload: DiscoveryPayload) -> ModelingPlan: ...


@dataclass(frozen=True)
class BronzeAnalysisSummary:
    """Structured diagnostic produced by the actionability filter.

    Returned as a by-product of :meth:`SchemaAnalyzer._classify_for_analysis`
    and exposed on :attr:`SchemaAnalyzerError.summary` so callers (pipeline
    orchestrator, API error handlers, UIs, log scrapers) can render counts
    and per-reason breakdowns without parsing the human-readable message.

    The breakdown is observation-only: it reports what the skip predicate
    actually decided, never assumes any particular set of skipped categories.
    Customising the predicate therefore naturally shifts these numbers.

    Attributes
    ----------
    catalog, schema_name
        Origin of the bronze snapshot (``bronze.catalog`` and
        ``bronze.schema_name``). Useful when the error is propagated far from
        the call-site.
    bronze_total
        Number of tables observed in the bronze snapshot.
    actionable_count
        Number of tables that survived the skip predicate.
    skipped_by_category
        Count of skipped tables keyed by :class:`SkipReason`. Keys are
        :class:`ChangeCategory` values for tables the change-set classified,
        and :data:`UNCLASSIFIED_SKIP_REASON` for tables missing from the
        change-set entirely. Reasons absent from the mapping had zero skips.
    skipped_sample_names
        Up to :data:`_SKIP_SAMPLE_LIMIT` bronze-table names per skip reason,
        in original snapshot order. The full count remains accurate in
        ``skipped_by_category``; only the sample is truncated.
    """

    catalog: str
    schema_name: str
    bronze_total: int
    actionable_count: int
    skipped_by_category: Mapping[SkipReason, int] = field(default_factory=dict)
    skipped_sample_names: Mapping[SkipReason, tuple[str, ...]] = field(default_factory=dict)

    @property
    def skipped_count(self) -> int:
        """Total tables that were filtered out (derived; never store twice)."""
        return self.bronze_total - self.actionable_count


class SchemaAnalyzerError(RuntimeError):
    """Raised when the analyzer cannot build a payload to send to the LLM.

    When the cause is "nothing was actionable", :attr:`summary` carries the
    structured :class:`BronzeAnalysisSummary` so callers can render counts /
    per-category breakdowns without parsing :func:`str(exc)`.
    """

    def __init__(self, message: str, *, summary: BronzeAnalysisSummary | None = None) -> None:
        super().__init__(message)
        self.summary = summary


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


def _format_skip_reason(reason: SkipReason) -> str:
    """Render a skip-reason key for an error message.

    Pure function so the message format is easy to unit-test independently
    of the analyzer state. Uses ``ChangeCategory.value`` (the enum's own
    lowercase string) for categories, so adding a new category requires no
    edit here.
    """
    return reason.value if isinstance(reason, ChangeCategory) else reason


def _format_empty_actionable_message(summary: BronzeAnalysisSummary) -> str:
    """Build a multi-line, actionable error message for the empty-actionable case.

    The message distinguishes the *empty bronze snapshot* failure mode from
    the *everything was skipped* mode, and lists the per-reason breakdown
    with up to :data:`_SKIP_SAMPLE_LIMIT` example table names per reason.

    Kept as a top-level function so it can be unit-tested without
    instantiating an analyzer.
    """
    location = f"{summary.catalog}.{summary.schema_name}"

    if summary.bronze_total == 0:
        return (
            f"No actionable bronze tables: bronze snapshot for {location} is empty. "
            "Check that the schema exists and that the snapshot request did not "
            "filter every table out (include_patterns / exclude_patterns / explicit "
            "`tables` allowlist)."
        )

    lines = [
        f"No actionable bronze tables in {location} after applying the skip "
        f"predicate ({summary.bronze_total} bronze tables observed, "
        f"0 actionable, {summary.skipped_count} skipped).",
        "Skip breakdown:",
    ]
    for reason, count in summary.skipped_by_category.items():
        sample = summary.skipped_sample_names.get(reason, ())
        sample_text = ", ".join(sample)
        if count > len(sample):
            sample_text = f"{sample_text}, … (+{count - len(sample)} more)"
        lines.append(f"  - {count} {_format_skip_reason(reason)}: {sample_text}")
    return "\n".join(lines)


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

    # ── internal: one-pass classification (DRY source of truth) ────────────
    def _classify_for_analysis(
        self,
        bronze: BronzeSnapshot,
        change_set: ChangeSet,
    ) -> tuple[tuple[BronzeTable, ...], BronzeAnalysisSummary]:
        """Filter bronze tables once, returning actionables + diagnostic summary.

        Single source of truth shared by :meth:`select_actionable` and
        :meth:`build_payload`. Running the skip predicate exactly once per
        call guarantees the summary used in error messages can never disagree
        with the actionable list (which it would, if the two methods iterated
        separately).
        """
        change_by_name = {c.table_name.lower(): c for c in change_set.changes}
        actionable: list[BronzeTable] = []
        skipped_counts: dict[SkipReason, int] = {}
        skipped_samples: dict[SkipReason, list[str]] = {}

        for table in bronze.tables:
            change = change_by_name.get(table.name.lower())
            if self._skip(table, change):
                reason: SkipReason = (
                    change.category if change is not None else UNCLASSIFIED_SKIP_REASON
                )
                skipped_counts[reason] = skipped_counts.get(reason, 0) + 1
                sample = skipped_samples.setdefault(reason, [])
                if len(sample) < _SKIP_SAMPLE_LIMIT:
                    sample.append(table.name)
            else:
                actionable.append(table)

        summary = BronzeAnalysisSummary(
            catalog=bronze.catalog,
            schema_name=bronze.schema_name,
            bronze_total=len(bronze.tables),
            actionable_count=len(actionable),
            skipped_by_category=dict(skipped_counts),
            skipped_sample_names={k: tuple(v) for k, v in skipped_samples.items()},
        )
        return tuple(actionable), summary

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
        actionable, _ = self._classify_for_analysis(bronze, change_set)
        return actionable

    def build_payload(
        self,
        *,
        system: SourceSystem,
        bronze: BronzeSnapshot,
        change_set: ChangeSet,
        catalog_snapshot: CatalogSnapshot | None = None,
    ) -> DiscoveryPayload:
        """Build the :class:`DiscoveryPayload` that will be sent to the LLM."""
        actionable, summary = self._classify_for_analysis(bronze, change_set)
        if not actionable:
            raise SchemaAnalyzerError(
                _format_empty_actionable_message(summary),
                summary=summary,
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
