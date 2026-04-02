from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.jobs import router as jobs_router
from api.projects import router as projects_router
from api.test_errors import router as test_errors_router
from api.webhook import router as webhook_router
from api.setting import router as setting_router
from api.worker import router as worker_router
from core.config import settings
from core.database import init_db
from core.middleware import DBSessionMiddleware
from services.worker_manager import worker_manager

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
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)
app.add_middleware(DBSessionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")
api_router.include_router(webhook_router, prefix="/webhook", tags=["webhook"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
api_router.include_router(worker_router, prefix="/worker", tags=["worker"])
api_router.include_router(setting_router, prefix="/settings", tags=["settings"])
api_router.include_router(test_errors_router, prefix="/test-errors", tags=["test-errors"])


@api_router.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(api_router)
