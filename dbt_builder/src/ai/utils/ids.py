"""Deterministic content-addressable identifiers.

The AI layer caches LLM responses, embedding vectors, and modelling decisions
keyed by the *content* that produced them. Using a stable hash means the same
inputs always map to the same cache key — across processes, machines, and
Python upgrades — without coordinating a counter.

We use SHA-1 because:

* it is shipped in the standard library (no extra dep),
* the output is short enough for filesystem-friendly keys,
* collision resistance against random inputs is more than sufficient for
  cache addressing (this is *not* a cryptographic identity check).

Two flavours are exposed:

* :func:`stable_id`        — full 40-char hex digest (use for primary keys).
* :func:`stable_short_id`  — first 12 chars (use for log lines and filenames).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

_SEPARATOR = "\x1f"  # ASCII unit separator; cannot appear in normal inputs.


def _normalize(parts: Iterable[object]) -> str:
    """Normalize an iterable of parts into a deterministic string.

    Each part is converted to ``str()`` then trimmed and lower-cased so that
    surrounding whitespace and case differences do not produce distinct ids.
    Parts are joined with the ASCII unit-separator (``\\x1f``) which cannot
    appear in normal text inputs, eliminating any ambiguity caused by parts
    that happen to contain the separator character themselves.

    None and empty parts are preserved (rendered as empty strings) so that the
    *positional* identity of the inputs is retained: ``stable_id("a", "")`` and
    ``stable_id("a")`` deliberately produce different ids.
    """
    return _SEPARATOR.join("" if p is None else str(p).strip().lower() for p in parts)


def stable_id(*parts: object) -> str:
    """Return a 40-char SHA-1 hex digest of the given parts.

    Examples
    --------
    >>> stable_id("hub", "conducting_equipment") == stable_id(
    ...     " HUB ", "Conducting_Equipment"
    ... )
    True
    >>> len(stable_id("anything"))
    40
    """
    if not parts:
        raise ValueError("stable_id requires at least one part")
    payload = _normalize(parts).encode("utf-8")
    return hashlib.sha1(payload, usedforsecurity=False).hexdigest()


def stable_short_id(*parts: object, length: int = 12) -> str:
    """Return the first ``length`` characters of :func:`stable_id`.

    The default of 12 hex chars (~48 bits) is collision-safe for the entity
    counts encountered in a single source system (well under one million).
    Use :func:`stable_id` when storing keys that may be combined across
    systems or kept indefinitely.
    """
    if not 4 <= length <= 40:
        raise ValueError("length must be between 4 and 40 characters")
    return stable_id(*parts)[:length]
