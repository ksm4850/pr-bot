"""Worker - Job Queue 폴링 루프

실행 방법:
    uv run python -m app.worker
"""

import asyncio
import logging
import signal

import anthropic

from app.core.config import settings
from app.core.database import db_context, init_db
from app.models.job import Job, JobStatus, JobTaskType
from app.services.agent import AgentService
from app.services.job_queue import JobService
from app.services.project import ProjectService
from app.services.workspace import WorkspaceService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker")

MAX_RETRY = 3

# 재시도 없이 즉시 FAILED 처리할 에러
FATAL_ERRORS = (
    anthropic.AuthenticationError,   # API 키 오류
    anthropic.PermissionDeniedError, # 권한 없음
)

def _is_billing_error(e: Exception) -> bool:
    """크레딧 소진 / 결제 오류 판별"""
    if isinstance(e, anthropic.BadRequestError):
        msg = str(e).lower()
        return "credit" in msg or "billing" in msg or "quota" in msg
    if isinstance(e, anthropic.APIStatusError):
        return e.status_code == 402
    return False


class Worker:
    def __init__(self):
        self.job_svc = JobService()
        self.project_svc = ProjectService()
        self.workspace_svc = WorkspaceService()
        self.agent_svc = AgentService()
        self._running = True
        self.current_job_id: str | None = None  # WorkerManager가 상태 노출에 사용

    async def run(self):
        logger.info("Worker started (poll_interval=%ds)", settings.worker_poll_interval)
        while self._running:
            try:
                async with db_context():
                    job = await self.job_svc.get_pending_job()

                if job:
                    await self._process(job)
                else:
                    await asyncio.sleep(settings.worker_poll_interval)

            except Exception:
                logger.exception("Unexpected worker error")
                await asyncio.sleep(settings.worker_poll_interval)

    async def _process(self, job: Job) -> None:
        self.current_job_id = job.id
        logger.info("Processing job %s: %s", job.id, job.title)

        # ── 1. PROCESSING 상태로 전환 ────────────────────────────────
        async with db_context():
            await self.job_svc.update_job_status(job.id, JobStatus.PROCESSING)
            await self.job_svc.add_task(job.id, JobTaskType.STATUS, content="processing")

        try:
            # ── 2. 프로젝트 정보 조회 (repo_url) ──────────────────────
            if not job.source_project_id:
                raise ValueError("job.source_project_id is missing — cannot lookup repo")

            async with db_context():
                project = await self.project_svc.get(job.source.value, job.source_project_id)

            if not project:
                raise ValueError(
                    f"No project registered for {job.source.value}/{job.source_project_id}"
                )

            # ── 3. 워크스페이스 준비 (clone/fetch) ────────────────────
            repo_dir = await self.workspace_svc.prepare(project.repo_url, project.repo_platform.value)

            # ── 4. 작업 브랜치 생성 ───────────────────────────────────
            base_branch = await self.workspace_svc.get_default_branch(repo_dir)
            work_branch = f"fix/{job.id[:8]}"
            await self.workspace_svc.create_work_branch(repo_dir, base_branch, work_branch)

            logger.info("Branch ready: %s (base: %s)", work_branch, base_branch)

            # ── 5. Claude 에이전트 실행 ───────────────────────────────
            await self.agent_svc.run(job, repo_dir, work_branch, self.job_svc)

            # ── 6. 변경사항 push ──────────────────────────────────────
            await self.workspace_svc.push_branch(repo_dir, work_branch)

            # ── 7. DONE 처리 ──────────────────────────────────────────
            async with db_context():
                await self.job_svc.update_job_status(
                    job.id,
                    JobStatus.DONE,
                    work_branch=work_branch,
                )
                await self.job_svc.add_task(job.id, JobTaskType.STATUS, content="done")

            logger.info("Job %s done → branch: %s", job.id, work_branch)

        except Exception as e:
            error_msg = str(e)
            logger.error("Job %s failed: %s", job.id, error_msg)

            fatal = isinstance(e, FATAL_ERRORS) or _is_billing_error(e)
            if fatal:
                logger.critical("Fatal error (no retry): %s", error_msg)

            async with db_context():
                new_retry = (job.retry_count or 0) + 1
                if fatal or new_retry >= MAX_RETRY:
                    next_status = JobStatus.FAILED
                else:
                    next_status = JobStatus.PENDING

                await self.job_svc.update_job_status(
                    job.id,
                    next_status,
                    error_log=error_msg,
                    increment_retry=True,
                )
                await self.job_svc.add_task(
                    job.id,
                    JobTaskType.ERROR,
                    content={"error": error_msg, "retry": new_retry, "fatal": fatal},
                )

            if next_status == JobStatus.PENDING:
                logger.info("Job %s → retrying (%d/%d)", job.id, new_retry, MAX_RETRY)

        finally:
            self.current_job_id = None

    def stop(self):
        logger.info("Worker stopping...")
        self._running = False


async def main():
    await init_db()

    worker = Worker()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.stop)

    await worker.run()
    logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
