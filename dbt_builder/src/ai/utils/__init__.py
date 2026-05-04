"""AI-layer utility helpers.

Currently exposes only :func:`stable_id` from :mod:`ids`. The package exists as
a separate namespace so future helpers (text normalisation, prompt formatting,
retry decorators) can be added without touching call sites.
"""

from __future__ import annotations

from dbt_builder.src.ai.utils.ids import stable_id, stable_short_id

__all__ = ["stable_id", "stable_short_id"]
