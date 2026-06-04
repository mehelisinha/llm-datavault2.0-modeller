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

# The HTTP/UI surface (``dbt_builder/api/*``) MAY import the AI layer, but only
# through the public facade (``ai.service``) and the typed contracts
# (``ai.contracts.*``). Any other AI sub-package (``ai.agents``, ``ai.pipeline``,
# ``ai.discovery``, ``ai.rendering``, ``ai.embeddings``, ``ai.validation``,
# ``ai.store``, ``ai.utils``) is internal — touching it from the API layer
# would let a route bypass approval / validation guardrails.
API_PYTHON_ROOT = REPO_ROOT / "dbt_builder" / "api"
API_ALLOWED_AI_PREFIXES = (
    "dbt_builder.src.ai.service",
    "dbt_builder.src.ai.contracts",
)

# Removed sub-packages (or sub-packages on a removal path) that nothing should
# import. Embeddings/RAG infrastructure is being deprecated in Phase C; this
# guardrail makes the deprecation visible immediately as a failing test on any
# new import. Remove an entry once the corresponding folder is deleted.
DEPRECATED_AI_SUBPACKAGES = ("dbt_builder.src.ai.embeddings",)

# Modules that the AI layer is allowed to import. Anything starting with one
# of these prefixes is fine; everything else is flagged. Standard-library and
# third-party packages are not constrained here (managed via pyproject [ai]).
AI_ALLOWED_IMPORT_PREFIXES = (
    AI_PACKAGE_PREFIX,
    # Shared storage utility used by both the AI service facade and the
    # Databricks notebook task (`dbt_builder/src/tasks/generate_dbt_models.py`).
    # Keeping the storage classes in `utils` avoids a forbidden non-AI →
    # AI import; the AI layer only wires them to `AISettings` here.
    "dbt_builder.src.utils.yaml_store",
    # GitLab MR client + Databricks SQL executor live in utils for the same
    # reason as yaml_store: they are pure infrastructure (no AI imports) and
    # need to be reachable from non-AI callers (notebook tasks, CLI tools)
    # without crossing the AI boundary. The AI layer wires them to AISettings.
    "dbt_builder.src.utils.gitlab_mr",
    "dbt_builder.src.utils.databricks_sql",
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


@pytest.mark.parametrize("source_file", _iter_python_files((API_PYTHON_ROOT,)))
def test_api_layer_only_imports_ai_service_and_contracts(source_file: Path):
    """The HTTP/UI layer must go through the service facade.

    Anything in ``dbt_builder/api/`` may import only ``ai.service`` and
    ``ai.contracts.*``. Reaching into ``ai.agents``, ``ai.pipeline``,
    ``ai.embeddings``, ``ai.validation``, ``ai.store``, ``ai.discovery``,
    ``ai.rendering`` or ``ai.utils`` would let a route call internals and
    bypass approval / validation guardrails.
    """
    offending: list[str] = []
    for name in _imports_in(source_file):
        if not name.startswith(AI_PACKAGE_PREFIX):
            continue
        if not any(name.startswith(prefix) for prefix in API_ALLOWED_AI_PREFIXES):
            offending.append(name)
    assert not offending, (
        f"{source_file.relative_to(REPO_ROOT)} imports AI internals: {offending}. "
        "API layer must go through dbt_builder.src.ai.service / .contracts."
    )


@pytest.mark.parametrize(
    "source_file",
    _iter_python_files((AI_PACKAGE_PATH, API_PYTHON_ROOT) + NON_AI_PYTHON_ROOTS),
)
def test_no_one_imports_deprecated_ai_subpackages(source_file: Path):
    """Nothing in the repo (except the deprecated package itself) may import
    deprecated AI sub-packages — currently the embeddings / RAG stack."""
    offending: list[str] = []
    for name in _imports_in(source_file):
        for deprecated in DEPRECATED_AI_SUBPACKAGES:
            if not name.startswith(deprecated):
                continue
            # Allow modules inside the deprecated package itself to import
            # their own siblings while it still exists.
            try:
                rel = source_file.relative_to(REPO_ROOT)
            except ValueError:  # pragma: no cover
                rel = source_file
            module_dotted = ".".join(rel.with_suffix("").parts)
            if module_dotted.startswith(deprecated):
                continue
            offending.append(name)
    assert not offending, (
        f"{source_file.relative_to(REPO_ROOT)} imports deprecated AI sub-packages: "
        f"{offending}. These packages are scheduled for removal — replace with "
        "the deterministic Python pipeline (catalog inspector / diff analyzer)."
    )
