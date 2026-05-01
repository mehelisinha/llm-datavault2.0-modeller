"""Architectural tests enforcing isolation of the AI layer.

These tests exist to make sure the AI work remains an opt-in side car: nothing
outside ``dbt_builder/src/ai/`` is allowed to import from it, and the AI layer
must keep its imports limited to known-safe siblings (currently itself only).

If a future feature genuinely needs a non-AI module to call into the AI layer,
update :data:`ALLOWED_INBOUND_MODULES` (or remove the offending check) so the
intent is recorded explicitly in the test diff rather than silently introduced.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AI_PACKAGE_PATH = REPO_ROOT / "dbt_builder" / "src" / "ai"
AI_PACKAGE_PREFIX = "dbt_builder.src.ai"

# Source trees that must NOT import the AI layer.
NON_AI_PYTHON_ROOTS = (
    REPO_ROOT / "dbt_builder" / "src" / "dv_components",
    REPO_ROOT / "dbt_builder" / "src" / "runners",
    REPO_ROOT / "dbt_builder" / "src" / "scripts",
    REPO_ROOT / "dbt_builder" / "src" / "tasks",
    REPO_ROOT / "dbt_builder" / "src" / "utils",
    REPO_ROOT / "shared" / "src",
)

# Modules that the AI layer is allowed to import. Anything starting with one
# of these prefixes is fine; everything else is flagged. Standard-library and
# third-party packages are not constrained here (managed via pyproject [ai]).
AI_ALLOWED_IMPORT_PREFIXES = (
    AI_PACKAGE_PREFIX,
    # Add other sibling modules here as the AI layer grows; e.g. shared.config.
)

# First-party top-level packages whose import from the AI layer would be a
# violation. Standard-library and third-party imports are ignored to keep the
# rule pragmatic and low-noise.
FIRST_PARTY_TOP_LEVELS = ("dbt_builder", "shared", "poc", "dwa_dv_generator")


def _iter_python_files(roots: tuple[Path, ...]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    return files


def _imports_in(file_path: Path) -> list[str]:
    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # Treat unreadable files (e.g. OneDrive cloud-only placeholders, locked
        # build artefacts) as having no imports rather than failing the test.
        # Real import-boundary violations are still detected on every file we
        # *can* read.
        return []
    tree = ast.parse(source, filename=str(file_path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


@pytest.mark.parametrize("source_file", _iter_python_files(NON_AI_PYTHON_ROOTS))
def test_non_ai_modules_do_not_import_ai_layer(source_file: Path):
    """No module outside dbt_builder/src/ai/ may import the AI layer."""
    offending = [name for name in _imports_in(source_file) if name.startswith(AI_PACKAGE_PREFIX)]
    assert not offending, (
        f"{source_file.relative_to(REPO_ROOT)} imports AI layer: {offending}. "
        f"AI work must remain opt-in."
    )


@pytest.mark.parametrize("source_file", _iter_python_files((AI_PACKAGE_PATH,)))
def test_ai_layer_only_imports_allowed_first_party_modules(source_file: Path):
    """The AI layer must not reach back into unrelated first-party packages."""
    bad: list[str] = []
    for name in _imports_in(source_file):
        top = name.split(".", 1)[0]
        if top not in FIRST_PARTY_TOP_LEVELS:
            continue  # third-party / stdlib — out of scope for this rule
        if not any(name.startswith(p) for p in AI_ALLOWED_IMPORT_PREFIXES):
            bad.append(name)
    assert not bad, (
        f"{source_file.relative_to(REPO_ROOT)} imports disallowed first-party "
        f"modules: {bad}. Update AI_ALLOWED_IMPORT_PREFIXES if the new "
        f"dependency is intentional."
    )
