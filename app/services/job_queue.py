"""Job Queue 서비스 - JobRepository 위임"""

from app.models.error import ParsedError
from app.models.job import ErrorSource, Job, JobStatus, JobTask, JobTaskType
from app.repositories.job import JobRepository


class JobService:
    def __init__(self, repo: JobRepository | None = None):
        self.repo = repo or JobRepository()

    async def create_job(self, parsed_error: ParsedError) -> str:
        return await self.repo.create(parsed_error)

    async def job_exists(self, source: ErrorSource, source_issue_id: str) -> bool:
        return await self.repo.exists(source.value, source_issue_id)

    async def get_job(self, job_id: str) -> Job | None:
        db_job = await self.repo.get(job_id)
        return Job.from_orm(db_job) if db_job else None

    async def get_pending_job(self) -> Job | None:
        db_job = await self.repo.get_pending()
        return Job.from_orm(db_job) if db_job else None

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        work_branch: str | None = None,
        error_log: str | None = None,
        increment_retry: bool = False,
    ) -> bool:
        return await self.repo.update_status(
            job_id, status,
            work_branch=work_branch,
            error_log=error_log,
            increment_retry=increment_retry,
        )

    async def add_task(
        self,
        job_id: str,
        type: JobTaskType,
        content: dict | str | None = None,
    ) -> JobTask:
        db_task = await self.repo.add_task(job_id, type, content)
        return JobTask.from_orm(db_task)

    async def list_tasks(self, job_id: str) -> list[JobTask]:
        db_tasks = await self.repo.list_tasks(job_id)
        return [JobTask.from_orm(t) for t in db_tasks]

    async def list_jobs(
        self, status: JobStatus | None = None, offset: int = 0, limit: int = 100
    ) -> list[Job]:
        db_jobs = await self.repo.list_jobs(status=status, offset=offset, limit=limit)
        return [Job.from_orm(j) for j in db_jobs]
