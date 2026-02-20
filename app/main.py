from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.jobs import router as jobs_router
from app.api.projects import router as projects_router
from app.api.webhook import router as webhook_router
from app.core.database import init_db
from app.core.middleware import DBSessionMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행"""
    # Startup
    await init_db()
    print("Database initialized")
    yield
    # Shutdown
    print("Shutting down")


app = FastAPI(
    title="PR-Bot",
    description="Error tracking webhook → Claude Agent → Auto PR",
    lifespan=lifespan,
)
app.add_middleware(DBSessionMiddleware)

app.include_router(webhook_router, prefix="/webhook", tags=["webhook"])
app.include_router(projects_router, prefix="/projects", tags=["projects"])
app.include_router(jobs_router, prefix="/jobs", tags=["jobs"])


@app.get("/health")
async def health():
    return {"status": "ok"}
