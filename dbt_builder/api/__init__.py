"""FastAPI application powering the React UI.

Phase A scope: a thin HTTP layer over :class:`DwaService`. No business logic
lives here — every route delegates to the service facade so the same code is
exercised by API tests and by future direct-Python callers (notebooks, Dagster
sensors). LLM agent endpoints (analyze, generate) are stubbed to return 501
until Phase B wires them in.

Auth: out of scope for Phase A; ``X-Actor`` header carries the reviewer
identity. Phase B adds Entra ID JWT validation.
"""

from __future__ import annotations

from fastapi import FastAPI

from dbt_builder.api.routers import approvals, history, plans

app = FastAPI(
    title="DWA Metadata Generator API",
    version="0.1.0-phase-a",
    description=(
        "HTTP surface for the Data Vault metadata generator. "
        "Backs the React UI (Connect / Select Tables / Define BV / Review / History)."
    ),
)

app.include_router(plans.router)
app.include_router(approvals.router)
app.include_router(history.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
