"""Entry point for the fusion container.

FastAPI lifespan owns the single shared httpx.AsyncClient (mirrors
inference/main.py pattern). Bootstrap builds a minimal app whose lifespan
replaces routes with the fully wired ones once the loop is running.

No os.environ.get() — all config via pydantic-settings (Rule 8).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
import structlog
import uvicorn
from fastapi import FastAPI

from fusion.comfort_index import ComfortIndexState
from fusion.config import Settings
from fusion.context_state import ContextState
from fusion.enrichment import Enrichment
from fusion.health import build_app
from fusion.ledger import CoachLedger
from fusion.suppression import SuppressionGate

log = structlog.get_logger(__name__)


def main() -> None:  # pragma: no cover — integration entry point
    settings = Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            ctx = ContextState()
            enricher = Enrichment(client, settings, ctx)
            gate = SuppressionGate(ctx, enricher)
            ledger = CoachLedger(settings)
            comfort = ComfortIndexState(settings)
            wired_app = build_app(
                settings=settings,
                ctx=ctx,
                gate=gate,
                enricher=enricher,
                client=client,
                ledger=ledger,
                comfort=comfort,
            )
            for route in wired_app.routes:
                app.router.routes.append(route)
            app.state.client = client
            app.state.ctx = ctx
            app.state.gate = gate
            app.state.enricher = enricher
            app.state.ledger = ledger
            app.state.comfort = comfort
            log.info("fusion.started", port=settings.port)
            try:
                yield
            finally:
                ledger.close()
                log.info("fusion.shutting_down")

    # Bootstrap shell: real routes are appended in lifespan.
    app = FastAPI(title="fusion")
    app.router.lifespan_context = lifespan
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":  # pragma: no cover
    main()
