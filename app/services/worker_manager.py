"""Worker 생명주기 관리 - FastAPI 내에서 백그라운드 태스크로 실행"""

import asyncio
import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class WorkerManager:
    """Worker asyncio 태스크 관리 (싱글톤)"""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._worker = None  # app.worker.Worker (순환 import 방지용 지연 import)
        self.started_at: datetime | None = None
        self.stopped_at: datetime | None = None
        self.error: str | None = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def current_job_id(self) -> str | None:
        if self._worker:
            return getattr(self._worker, "current_job_id", None)
        return None

    def status(self) -> dict:
        task_status = "stopped"
        if self._task:
            if self._task.done():
                exc = self._task.exception() if not self._task.cancelled() else None
                task_status = "crashed" if exc else "stopped"
            else:
                task_status = "running"

        return {
            "status": task_status,
            "current_job_id": self.current_job_id,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "error": self.error,
        }

    async def start(self) -> None:
        if self.is_running:
            raise RuntimeError("Worker is already running")

        from app.worker import Worker  # 지연 import

        self._worker = Worker()
        self.error = None
        self.started_at = datetime.now(UTC)
        self.stopped_at = None
        self._task = asyncio.create_task(self._run_worker())
        logger.info("Worker started")

    async def stop(self, timeout: float = 30.0) -> None:
        if not self.is_running:
            raise RuntimeError("Worker is not running")

        self._worker.stop()
        try:
            await asyncio.wait_for(self._task, timeout=timeout)
        except asyncio.TimeoutError:
            self._task.cancel()
            logger.warning("Worker did not stop gracefully, cancelled")

        self.stopped_at = datetime.now(UTC)
        logger.info("Worker stopped")

    async def _run_worker(self) -> None:
        try:
            await self._worker.run()
        except Exception as e:
            self.error = str(e)
            self.stopped_at = datetime.now(UTC)
            logger.error("Worker crashed: %s", e)


# 싱글톤
worker_manager = WorkerManager()
