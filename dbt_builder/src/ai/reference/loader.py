"""Load approved raw-vault YAML files as typed few-shot reference examples.

The previous pipeline used FAISS / Azure AI Search to retrieve similar
hub/sat/link structures at prompt time. That worked but it (a) required a
running embedding deployment, (b) was non-deterministic across cache
invalidations, and (c) added a network hop per agent call.

The new design loads a directory of curated raw-vault YAMLs once, parses
each into a small typed record, and selects the most relevant examples
using a lexical overlap score. Selection is pure and reproducible.

Layout assumed (matches the existing repo)::

    models/raw_vault/
        hubs/        hub_*.yml
        links/       link_*.yml
        satellites/  sat_*.yml

Anything that does not match the expected dbt YAML envelope is silently
skipped; that lets the loader run against a partially-populated repo.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

# Repository root: this file lives at
#   <repo>/dbt_builder/src/ai/reference/loader.py
# so parents[4] == <repo>.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_REFERENCE_ROOT = _REPO_ROOT / "models" / "raw_vault"

# Subdirectory -> kind. Keeping this explicit rather than guessing from the
# filename means a misplaced file (e.g. a hub yaml dropped into satellites/)
# is surfaced loudly via test failures instead of silently mis-tagged.
_KIND_BY_DIRNAME: dict[str, "ReferenceKind"]


class ReferenceKind(str, Enum):
    """Kind of Data Vault object the reference describes."""

    HUB = "hub"
    SATELLITE = "satellite"
    LINK = "link"


_KIND_BY_DIRNAME = {
    "hubs": ReferenceKind.HUB,
    "satellites": ReferenceKind.SATELLITE,
    "links": ReferenceKind.LINK,
}


# Tokens of length < 2 carry no signal and inflate the overlap denominator
# (e.g. table name "a" matching "a" in everything). This matches typical
# information-retrieval stopword length cutoffs.
_MIN_TOKEN_LEN = 2

# Common DV2 prefixes stripped before tokenising so e.g. ``hub_terminal``
# and ``sat_terminal_details`` both produce ``terminal`` as a high-signal
# token. Order matters: longest prefix first.
_DV_PREFIXES: tuple[str, ...] = ("hub_", "sat_", "link_", "stg_")


def _tokenize(name: str) -> frozenset[str]:
    """Lowercase, strip DV prefixes, split on non-alphanumerics."""
    lowered = name.lower()
    for prefix in _DV_PREFIXES:
        if lowered.startswith(prefix):
            lowered = lowered[len(prefix) :]
            break
    return frozenset(tok for tok in re.split(r"[^a-z0-9]+", lowered) if len(tok) >= _MIN_TOKEN_LEN)


class ReferenceExample(BaseModel):
    """A single approved raw-vault object loaded from disk.

    Only the fields downstream agents actually need are captured. The raw
    YAML body is preserved as ``raw_yaml`` so the YAML Generator can do
    byte-equality comparisons against the canonical example.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(description="Model name, e.g. ``hub_terminal``.")
    kind: ReferenceKind
    source_models: tuple[str, ...] = Field(
        default=(),
        description="Staging models the object reads from (e.g. ``stg_terminals``).",
    )
    src_pk: str | None = Field(default=None, description="Hash key column.")
    src_nk: str | None = Field(default=None, description="Business key (hubs only).")
    src_hashdiff: str | None = Field(default=None, description="Hashdiff column (satellites only).")
    src_payload: tuple[str, ...] = Field(
        default=(), description="Payload columns (satellites only)."
    )
    src_fk: tuple[str, ...] = Field(default=(), description="Foreign-key hubs (links only).")
    raw_yaml: str = Field(description="Original YAML body, byte-preserved.")
    source_path: str = Field(description="Repository-relative path of the file.")

    @property
    def search_tokens(self) -> frozenset[str]:
        """Tokens used for lexical relevance scoring."""
        toks = set(_tokenize(self.name))
        for src in self.source_models:
            toks |= _tokenize(src)
        return frozenset(toks)


def _coerce_str_tuple(value: Any) -> tuple[str, ...]:
    """Accept list/tuple/None, return a tuple of strings (skip non-str entries)."""
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value if isinstance(v, (str, int, float)))
    return ()


def _parse_dbt_model_yaml(
    path: Path, *, expected_kind: ReferenceKind, raw_text: str
) -> ReferenceExample | None:
    """Parse one dbt models YAML file. Return ``None`` if it isn't a valid example.

    The dbt envelope is::

        version: 2
        models:
          - name: hub_xxx
            meta:
              dv_type: hub
              source_models: [stg_xxx]
              src_pk: HK_XXX
              ...

    A file that doesn't conform (multi-model, missing meta, wrong dv_type)
    is skipped — the loader is permissive on input so a half-migrated repo
    doesn't break everything.
    """
    try:
        doc = yaml.safe_load(raw_text)
    except yaml.YAMLError:
        return None
    if not isinstance(doc, dict):
        return None
    models = doc.get("models")
    if not isinstance(models, list) or len(models) != 1:
        return None
    model = models[0]
    if not isinstance(model, dict):
        return None
    name = model.get("name")
    meta = model.get("meta")
    if not isinstance(name, str) or not isinstance(meta, dict):
        return None
    dv_type = meta.get("dv_type")
    if dv_type != expected_kind.value:
        return None

    return ReferenceExample(
        name=name,
        kind=expected_kind,
        source_models=_coerce_str_tuple(meta.get("source_models")),
        src_pk=meta.get("src_pk") if isinstance(meta.get("src_pk"), str) else None,
        src_nk=meta.get("src_nk") if isinstance(meta.get("src_nk"), str) else None,
        src_hashdiff=(
            meta.get("src_hashdiff") if isinstance(meta.get("src_hashdiff"), str) else None
        ),
        src_payload=_coerce_str_tuple(meta.get("src_payload")),
        src_fk=_coerce_str_tuple(meta.get("src_fk")),
        raw_yaml=raw_text,
        source_path=str(path.relative_to(_REPO_ROOT))
        if path.is_absolute() and _REPO_ROOT in path.parents
        else str(path),
    )


class ReferenceLoader:
    """Load and query a directory of raw-vault YAML reference files.

    The loader is read-only and immutable after construction: every public
    method is pure with respect to the on-disk state captured at
    construction time. To pick up new files, build a new loader.
    """

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)
        self._examples: tuple[ReferenceExample, ...] = self._load_all()

    @classmethod
    def from_corpus_rows(cls, rows: Iterable[Any]) -> ReferenceLoader:
        """Build a loader from stored corpus rows instead of a directory.

        Each row must expose ``kind`` (a :class:`ReferenceKind` value),
        ``source_path`` and ``yaml_text`` — exactly what ``DeltaExampleStore``
        returns. The stored YAML is parsed with the SAME parser used for on-disk
        files, so database- and file-sourced examples are indistinguishable
        downstream. Rows whose kind is unknown or whose YAML no longer parses are
        skipped, so a partially-populated corpus never breaks retrieval.
        """
        examples: list[ReferenceExample] = []
        for row in rows:
            try:
                kind = ReferenceKind(row.kind)
            except (ValueError, AttributeError):
                continue
            example = _parse_dbt_model_yaml(
                Path(row.source_path), expected_kind=kind, raw_text=row.yaml_text
            )
            if example is not None:
                examples.append(example)
        loader = cls.__new__(cls)
        loader._root = Path("delta://corpus")
        loader._examples = tuple(examples)
        return loader

    # ── construction helpers ────────────────────────────────────────────────
    def _load_all(self) -> tuple[ReferenceExample, ...]:
        if not self._root.is_dir():
            return ()
        loaded: list[ReferenceExample] = []
        for dirname, kind in _KIND_BY_DIRNAME.items():
            subdir = self._root / dirname
            if not subdir.is_dir():
                continue
            for yml_path in sorted(subdir.glob("*.yml")):
                try:
                    raw = yml_path.read_text(encoding="utf-8")
                except OSError:
                    continue
                example = _parse_dbt_model_yaml(yml_path, expected_kind=kind, raw_text=raw)
                if example is not None:
                    loaded.append(example)
        return tuple(loaded)

    # ── inspection ──────────────────────────────────────────────────────────
    @property
    def root(self) -> Path:
        return self._root

    def all(self) -> tuple[ReferenceExample, ...]:
        """Return every loaded example. Iteration order is stable."""
        return self._examples

    def by_kind(self, kind: ReferenceKind) -> tuple[ReferenceExample, ...]:
        return tuple(ex for ex in self._examples if ex.kind is kind)

    # ── selection ───────────────────────────────────────────────────────────
    def select_relevant(
        self,
        target_name: str,
        *,
        kinds: Sequence[ReferenceKind] | None = None,
        limit: int = 3,
    ) -> tuple[ReferenceExample, ...]:
        """Pick the top ``limit`` examples by lexical overlap with ``target_name``.

        Ties are broken deterministically by example name so the same input
        always produces the same prompt block — this is the property that
        lets the YAML Generator have a byte-equality snapshot test.
        """
        if limit <= 0:
            return ()
        target_tokens = _tokenize(target_name)
        candidates: Iterable[ReferenceExample] = (
            self._examples if kinds is None else (ex for ex in self._examples if ex.kind in kinds)
        )

        scored: list[tuple[int, str, ReferenceExample]] = []
        for ex in candidates:
            overlap = len(target_tokens & ex.search_tokens)
            if overlap == 0:
                continue
            # Negative score so default ascending sort yields highest first;
            # secondary key is the name (ascending) for deterministic ties.
            scored.append((-overlap, ex.name, ex))
        scored.sort()
        return tuple(ex for _, _, ex in scored[:limit])

    # ── prompt rendering ────────────────────────────────────────────────────
    def to_prompt_block(self, examples: Sequence[ReferenceExample]) -> str:
        """Render examples as a compact, model-friendly text block.

        The format is intentionally *not* JSON — LLMs handle a clearly
        labelled outline more reliably than a wall of nested objects, and
        we already validate the model's reply against a typed schema.
        """
        if not examples:
            return "(no reference examples available)"
        lines: list[str] = []
        for idx, ex in enumerate(examples, start=1):
            lines.append(f"### Reference {idx}: {ex.name} ({ex.kind.value})")
            if ex.source_models:
                lines.append(f"  source_models: {list(ex.source_models)}")
            if ex.src_pk:
                lines.append(f"  src_pk:        {ex.src_pk}")
            if ex.src_nk:
                lines.append(f"  src_nk:        {ex.src_nk}")
            if ex.src_hashdiff:
                lines.append(f"  src_hashdiff:  {ex.src_hashdiff}")
            if ex.src_payload:
                lines.append(f"  src_payload:   {list(ex.src_payload)}")
            if ex.src_fk:
                lines.append(f"  src_fk:        {list(ex.src_fk)}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


@lru_cache(maxsize=1)
def get_default_loader() -> ReferenceLoader:
    """Process-wide cached loader pointing at ``<repo>/models/raw_vault``.

    Cached because parsing is cheap but constant — we don't want to re-read
    the directory on every agent call. Tests that need to vary the root
    must construct :class:`ReferenceLoader` directly.
    """
    return ReferenceLoader(_DEFAULT_REFERENCE_ROOT)
