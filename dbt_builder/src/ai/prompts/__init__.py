"""Filesystem-backed rule-prompt loader.

Lets the automated pipeline agents (modeller, BV architect, planner) share
ONE editable rule set with the manual Claude-Code agents instead of
duplicating the modelling rules in Python string literals.

Rule files are plain Markdown with optional YAML front-matter:

    ---
    name: ...
    description: ...
    ---
    <the rules the agent should follow>

The front-matter (Claude-Code metadata) is stripped; only the body is
returned. Files live in this package by default; override the directory via
``AISettings.ai_prompts_dir`` for ops who keep prompts outside the wheel
(e.g. pointing at the repo's loose ``dv-metadata-*.md`` skills).

A missing or unreadable file returns ``""`` so callers fall back to their
built-in default — a bad path can never crash a pipeline run.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent


def _resolve_dir() -> Path:
    """Return the directory to load rule files from (settings override > package)."""
    try:
        from dbt_builder.src.ai.settings import get_settings

        configured = get_settings().ai_prompts_dir
    except Exception:
        configured = ""
    return Path(configured).expanduser() if configured else _PACKAGE_DIR


def _strip_frontmatter(text: str) -> str:
    """Drop a leading ``---``-delimited YAML front-matter block, if present."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    newline = text.find("\n", end + 1)
    return text[newline + 1:] if newline != -1 else ""


@lru_cache(maxsize=None)
def load_rules(name: str) -> str:
    """Return the body of rule file ``<name>.md`` (front-matter stripped).

    Cached per ``name``. Returns ``""`` when the file is absent or unreadable
    so the caller can fall back to its built-in default.
    """
    path = _resolve_dir() / f"{name}.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return _strip_frontmatter(text).strip()
