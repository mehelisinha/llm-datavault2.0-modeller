"""FastAPI application powering the React UI.

A thin HTTP layer over :class:`DwaService`. No business logic lives here —
every route delegates to the service facade so the same code is exercised by
API tests and by future direct-Python callers (notebooks, Dagster sensors).

Auth: out of scope for Phase A/B; ``X-Actor`` header carries the reviewer
identity. Phase B7 adds Entra ID JWT validation.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI

from dbt_builder.api.routers import approvals, discovery, history, pipeline, plans

_TITLE = "DWA Metadata Generator API"
_VERSION = "0.2.0-phase-b"
_DESCRIPTION = (
    "HTTP surface for the Data Vault metadata generator. "
    "Backs the React UI (Connect / Select Tables / Define BV / Review / History)."
)


def _configure_logging() -> None:
    """Route app logs (orchestrator, agents, service) to the uvicorn handler.

    Uvicorn only configures its own loggers; without this, INFO-level logs from
    application modules are dropped because the root logger defaults to WARNING.
    Honours ``DWA_API_LOG_LEVEL`` (default INFO).
    """
    level_name = os.getenv("DWA_API_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        root.addHandler(handler)
    root.setLevel(level)
    for name in ("dbt_builder", "uvicorn", "uvicorn.error"):
        logging.getLogger(name).setLevel(level)


def create_app() -> FastAPI:
    """Build a fresh FastAPI instance with all routers mounted.

    Returned per-call so tests can construct isolated apps and so the same
    factory can be reused by ASGI servers, lifespan managers, and test
    fixtures without leaking module-level state.
    """
    _configure_logging()
    app = FastAPI(title=_TITLE, version=_VERSION, description=_DESCRIPTION)
    app.include_router(discovery.router)
    app.include_router(plans.router)
    app.include_router(approvals.router)
    app.include_router(history.router)
    app.include_router(pipeline.router)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok"}

    return app


# Module-level instance kept for ``uvicorn dbt_builder.api:app`` compatibility.
app = create_app()

__all__ = ["app", "create_app"]
