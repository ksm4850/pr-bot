import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.error import ParsedError
from app.models.job import JobModel, JobStatus, JobTaskModel, JobTaskType
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository):
    async def create(self, parsed_error: ParsedError) -> str:
        job_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        stacktrace_json = json.dumps(
            [frame.model_dump() for frame in parsed_error.frames],
            ensure_ascii=False,
        )
        db_job = JobModel(
            id=job_id,
            status=JobStatus.PENDING.value,
            source=parsed_error.source.value,
            source_project_id=parsed_error.source_project_id,
            source_issue_id=parsed_error.source_issue_id,
            title=parsed_error.title,
            message=parsed_error.message,
            level=parsed_error.level,
            environment=parsed_error.environment,
            exception_type=parsed_error.exception_type,
            transaction=parsed_error.transaction,
            filename=parsed_error.filename,
            lineno=parsed_error.lineno,
            function=parsed_error.function,
            stacktrace=stacktrace_json,
            source_url=parsed_error.source_url,
            raw_payload=parsed_error.raw_payload,
            created_at=now,
            updated_at=now,
        )
        self.session.add(db_job)
        try:
            await self.session.flush()
        except IntegrityError:
            raise ValueError(
                f"Already exists: source={parsed_error.source.value}, "
                f"issue_id={parsed_error.source_issue_id}"
            )
        return job_id

    async def exists(self, source: str, source_issue_id: str) -> bool:
        result = await self.session.execute(
            select(JobModel.id).where(
                JobModel.source == source,
                JobModel.source_issue_id == source_issue_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def get(self, job_id: str) -> JobModel | None:
        result = await self.session.execute(
            select(JobModel).where(JobModel.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_pending(self) -> JobModel | None:
        result = await self.session.execute(
            select(JobModel)
            .where(JobModel.status == JobStatus.PENDING.value)
            .order_by(JobModel.created_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        work_branch: str | None = None,
        error_log: str | None = None,
        increment_retry: bool = False,
    ) -> bool:
        db_job = await self.get(job_id)
        if not db_job:
            return False
        db_job.status = status.value
        db_job.updated_at = datetime.now(UTC)
        if work_branch is not None:
            db_job.work_branch = work_branch
        if error_log is not None:
            db_job.error_log = error_log
        if increment_retry:
            db_job.retry_count += 1
        await self.session.flush()
        return True

    async def list_jobs(self, status: JobStatus | None = None, offset: int = 0, limit: int = 100) -> list[JobModel]:
        query = select(JobModel).order_by(JobModel.created_at.desc()).offset(offset).limit(limit)
        if status:
            query = query.where(JobModel.status == status.value)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ── Job Tasks ─────────────────────────────────────────────────

    async def add_task(
        self,
        job_id: str,
        type: JobTaskType,
        content: dict | str | None = None,
    ) -> JobTaskModel:
        """에이전트 작업 이벤트 기록"""
        # 현재 job의 마지막 sequence 조회
        result = await self.session.execute(
            select(JobTaskModel.sequence)
            .where(JobTaskModel.job_id == job_id)
            .order_by(JobTaskModel.sequence.desc())
            .limit(1)
        )
        last_seq = result.scalar_one_or_none()
        sequence = (last_seq or 0) + 1

        db_task = JobTaskModel(
            id=str(uuid.uuid4()),
            job_id=job_id,
            sequence=sequence,
            type=type.value,
            content=json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else content,
            created_at=datetime.now(UTC),
        )
        self.session.add(db_task)
        await self.session.flush()
        return db_task

    async def list_tasks(self, job_id: str) -> list[JobTaskModel]:
        """job의 작업 히스토리 순서대로 조회"""
        result = await self.session.execute(
            select(JobTaskModel)
            .where(JobTaskModel.job_id == job_id)
            .order_by(JobTaskModel.sequence.asc())
        )
        return list(result.scalars().all())
