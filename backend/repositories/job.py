import json
import uuid
from datetime import UTC, datetime

from datetime import UTC, datetime

from sqlalchemy import case, select, update
from sqlalchemy.exc import IntegrityError

from models.error import ParsedError
from models.job import JobModel, JobStatus, JobTaskModel, JobTaskType
from models.project import ProjectModel
from repositories.base import BaseRepository


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
            subtitle=parsed_error.subtitle,
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

    async def get_by_source(self, source: str, source_issue_id: str) -> JobModel | None:
        result = await self.session.execute(
            select(JobModel).where(
                JobModel.source == source,
                JobModel.source_issue_id == source_issue_id,
            )
        )
        return result.scalar_one_or_none()

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

    async def get_next_job(self) -> JobModel | None:
        """Atomic UPDATE RETURNING으로 다음 job을 가져오며 즉시 PROCESSING으로 전환.

        여러 워커가 동시에 호출해도 같은 job을 가져가지 않음.
        등록된 프로젝트가 있는 job만 대상 (projects 조인).
        우선순위: RATE_LIMITED(대기 완료) > PENDING, FIFO.
        """
        now = datetime.now(UTC)
        priority = case(
            (JobModel.status == JobStatus.RATE_LIMITED.value, 0),
            else_=1,
        )
        # 서브쿼리: projects 조인하여 등록된 프로젝트가 있는 job만 선택
        subq = (
            select(JobModel.id)
            .join(
                ProjectModel,
                (JobModel.source == ProjectModel.source)
                & (JobModel.source_project_id == ProjectModel.source_project_id),
            )
            .where(
                (
                    (JobModel.status == JobStatus.RATE_LIMITED.value)
                    & (
                        (JobModel.rate_limited_until == None)  # noqa: E711
                        | (JobModel.rate_limited_until <= now)
                    )
                )
                | (JobModel.status == JobStatus.PENDING.value)
            )
            .order_by(priority, JobModel.created_at.asc())
            .limit(1)
            .scalar_subquery()
        )
        # atomic UPDATE ... RETURNING
        stmt = (
            update(JobModel)
            .where(JobModel.id == subq)
            .values(status=JobStatus.PROCESSING.value, updated_at=now)
            .returning(JobModel)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        work_branch: str | None = None,
        error_log: str | None = None,
        increment_retry: bool = False,
        rate_limited_until: datetime | None = None,
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
        if status == JobStatus.RATE_LIMITED:
            db_job.rate_limited_until = rate_limited_until
        elif db_job.rate_limited_until is not None:
            # rate limit 해제 시 초기화
            db_job.rate_limited_until = None
        await self.session.flush()
        return True

    async def list_jobs(
        self,
        status: JobStatus | None = None,
        source_project_id: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[JobModel]:
        query = select(JobModel).order_by(JobModel.created_at.desc()).offset(offset).limit(limit)
        if status:
            query = query.where(JobModel.status == status.value)
        if source_project_id:
            query = query.where(JobModel.source_project_id == source_project_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ── Job Tasks ─────────────────────────────────────────────────

    async def add_task(
        self,
        job_id: str,
        type: JobTaskType,
        content: dict | str | None = None,
        label: str | None = None,
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
            label=label,
            content=json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else content,
            created_at=datetime.now(UTC),
        )
        self.session.add(db_task)
        await self.session.flush()
        return db_task

    async def add_tokens(self, job_id: str, input_tokens: int, output_tokens: int) -> None:
        """토큰 사용량 누적"""
        db_job = await self.get(job_id)
        if db_job:
            db_job.input_tokens += input_tokens
            db_job.output_tokens += output_tokens
            await self.session.flush()

    async def list_tasks(self, job_id: str) -> list[JobTaskModel]:
        """job의 작업 히스토리 순서대로 조회"""
        result = await self.session.execute(
            select(JobTaskModel)
            .where(JobTaskModel.job_id == job_id)
            .order_by(JobTaskModel.sequence.asc())
        )
        return list(result.scalars().all())
