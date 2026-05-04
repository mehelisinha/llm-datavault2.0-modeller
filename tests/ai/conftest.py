"""Shared pytest configuration for AI-layer tests.

Markers
-------
- ``ai``   : any test in the AI layer (auto-applied to every test under tests/ai/).
- ``live`` : test requires live Azure credentials and will incur token costs.
             These are skipped by default; opt-in with ``pytest -m live``.

Fixtures live in this file when shared across multiple test modules; module-local
fixtures should stay close to the test that uses them.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

# Make the repo root importable so ``dbt_builder.src.ai...`` resolves without
# needing an editable install. The existing pyproject.toml has a known
# setuptools flat-layout issue that prevents ``pip install -e .`` today; this
# bootstrap keeps the AI test suite runnable in the meantime and is harmless
# once the project is properly installable.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers so ``pytest --strict-markers`` does not warn."""
    config.addinivalue_line("markers", "ai: AI-layer test")
    config.addinivalue_line(
        "markers",
        "live: requires live Azure credentials and incurs token cost (deselect by default)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-tag everything under tests/ai/ with the ``ai`` marker."""
    for item in items:
        item.add_marker(pytest.mark.ai)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repository root."""
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def tmp_yaml(tmp_path: Path) -> Iterator[Path]:
    """Yield a temp directory dedicated to YAML fixture files for one test."""
    target = tmp_path / "yaml"
    target.mkdir()
    yield target
