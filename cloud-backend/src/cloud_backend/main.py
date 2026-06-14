from __future__ import annotations

import structlog
from fastapi import FastAPI

from .api.error_handlers import unhandled_exception_handler
from .config import get_settings
from .routes.admin_alert_classes import router as admin_alert_classes_router
from .routes.ai_pipeline import router as ai_pipeline_router
from .routes.ai_quality import router as ai_quality_router
from .routes.alerts_sse import router as alerts_router
from .routes.analytics import router as analytics_router
from .routes.auth import router as auth_router
from .routes.capacity_review import capacity_review_router
from .routes.config import router as config_router
from .routes.escalations import router as escalations_router
from .routes.escalations_audit import router as escalations_audit_router
from .routes.fleet import router as fleet_router
from .routes.health import router as health_router
from .routes.ingest import router as ingest_router
from .routes.kpi import router as kpi_router
from .routes.maintenance import router as maintenance_router
from .routes.preferences import router as preferences_router

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

log = structlog.get_logger()

app = FastAPI(title="OEBB Cloud Backend", version="0.1.0")

app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(auth_router)
app.include_router(analytics_router)
app.include_router(capacity_review_router)
app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(fleet_router)
app.include_router(alerts_router)
app.include_router(admin_alert_classes_router)
app.include_router(config_router)
app.include_router(ai_pipeline_router)
app.include_router(ai_quality_router)
app.include_router(maintenance_router)
app.include_router(preferences_router)
app.include_router(escalations_router)
app.include_router(escalations_audit_router)
app.include_router(kpi_router)


@app.on_event("startup")
async def _startup() -> None:
    settings = get_settings()
    log.info("cloud_backend_started", db_url=settings.database_url)
