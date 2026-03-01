from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.jobs import router as jobs_router
from app.api.projects import router as projects_router
from app.api.test_errors import router as test_errors_router
from app.api.webhook import router as webhook_router
from app.api.worker import router as worker_router
from app.core.config import settings
from app.core.database import init_db
from app.core.middleware import DBSessionMiddleware
from app.services.worker_manager import worker_manager

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=1.0,
        send_default_pii=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await worker_manager.start()
    yield
    if worker_manager.is_running:
        await worker_manager.stop(timeout=10.0)


app = FastAPI(
    title="PR-Bot",
    description="Error tracking webhook → Claude Agent → Auto PR",
    lifespan=lifespan,
)
app.add_middleware(DBSessionMiddleware)

app.include_router(webhook_router, prefix="/webhook", tags=["webhook"])
app.include_router(projects_router, prefix="/projects", tags=["projects"])
app.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
app.include_router(worker_router, prefix="/worker", tags=["worker"])
app.include_router(test_errors_router, prefix="/test-errors", tags=["test-errors"])

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse("app/static/index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
