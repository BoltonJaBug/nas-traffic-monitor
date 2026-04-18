from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.services import router as services_router
from app.api.summary import router as summary_router
from app.api.alerts import router as alerts_router
from app.api.settings import router as settings_router
from app.api.dashboard import router as dashboard_router
from app.auth import ensure_admin_user
from app.database import db
from app.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    ensure_admin_user()
    start_scheduler()
    logger.info("NAS Traffic Monitor started")
    yield
    stop_scheduler()
    logger.info("NAS Traffic Monitor stopped")


app = FastAPI(title="NAS Traffic Monitor", version="0.1.0", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(services_router)
app.include_router(summary_router)
app.include_router(alerts_router)
app.include_router(settings_router)
app.include_router(dashboard_router)

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
