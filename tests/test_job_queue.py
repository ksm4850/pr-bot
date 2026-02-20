import pytest

from app.models.error import ParsedError, StackFrame
from app.models.job import ErrorSource, JobStatus
from app.services.job_queue import JobService


@pytest.fixture
def sample_parsed_error() -> ParsedError:
    return ParsedError(
        source=ErrorSource.SENTRY,
        source_issue_id="test-issue-123",
        title="Test Error",
        message="Something went wrong",
        level="error",
        environment="prod",
        filename="app/main.py",
        lineno=42,
        function="handler",
        frames=[
            StackFrame(filename="app/main.py", lineno=42, function="handler"),
            StackFrame(filename="app/utils.py", lineno=10, function="helper"),
        ],
        source_url="https://sentry.io/issues/123",
        raw_payload='{"test": "payload"}',
    )


@pytest.fixture
def svc() -> JobService:
    return JobService()


class TestCreateJob:
    async def test_create_job_returns_id(self, db_session, svc, sample_parsed_error):
        job_id = await svc.create_job(sample_parsed_error)
        assert job_id is not None
        assert len(job_id) == 36

    async def test_create_job_stores_all_fields(self, db_session, svc, sample_parsed_error):
        job_id = await svc.create_job(sample_parsed_error)
        job = await svc.get_job(job_id)

        assert job.source == ErrorSource.SENTRY
        assert job.source_issue_id == "test-issue-123"
        assert job.title == "Test Error"
        assert job.message == "Something went wrong"
        assert job.level == "error"
        assert job.environment == "prod"
        assert job.filename == "app/main.py"
        assert job.lineno == 42
        assert job.function == "handler"
        assert job.status == JobStatus.PENDING

    async def test_create_job_stores_stacktrace_as_json(self, db_session, svc, sample_parsed_error):
        job_id = await svc.create_job(sample_parsed_error)
        job = await svc.get_job(job_id)

        assert job.stacktrace is not None
        assert "app/main.py" in job.stacktrace
        assert "app/utils.py" in job.stacktrace


class TestJobExists:
    async def test_job_exists_returns_false_when_not_exists(self, db_session, svc):
        exists = await svc.job_exists(ErrorSource.SENTRY, "non-existent-id")
        assert exists is False

    async def test_job_exists_returns_true_when_exists(self, db_session, svc, sample_parsed_error):
        await svc.create_job(sample_parsed_error)
        exists = await svc.job_exists(ErrorSource.SENTRY, "test-issue-123")
        assert exists is True


class TestGetPendingJob:
    async def test_get_pending_job_returns_none_when_empty(self, db_session, svc):
        job = await svc.get_pending_job()
        assert job is None

    async def test_get_pending_job_returns_oldest_first(self, db_session, svc, sample_parsed_error):
        sample_parsed_error.source_issue_id = "issue-1"
        job_id_1 = await svc.create_job(sample_parsed_error)

        sample_parsed_error.source_issue_id = "issue-2"
        await svc.create_job(sample_parsed_error)

        job = await svc.get_pending_job()
        assert job.id == job_id_1

    async def test_get_pending_job_skips_processing(self, db_session, svc, sample_parsed_error):
        sample_parsed_error.source_issue_id = "issue-1"
        job_id_1 = await svc.create_job(sample_parsed_error)
        await svc.update_job_status(job_id_1, JobStatus.PROCESSING)

        sample_parsed_error.source_issue_id = "issue-2"
        job_id_2 = await svc.create_job(sample_parsed_error)

        job = await svc.get_pending_job()
        assert job.id == job_id_2


class TestUpdateJobStatus:
    async def test_update_status_to_processing(self, db_session, svc, sample_parsed_error):
        job_id = await svc.create_job(sample_parsed_error)
        await svc.update_job_status(job_id, JobStatus.PROCESSING)

        job = await svc.get_job(job_id)
        assert job.status == JobStatus.PROCESSING

    async def test_update_status_to_done_with_work_branch(self, db_session, svc, sample_parsed_error):
        job_id = await svc.create_job(sample_parsed_error)
        await svc.update_job_status(job_id, JobStatus.DONE, work_branch="fix/job-abc123")

        job = await svc.get_job(job_id)
        assert job.status == JobStatus.DONE
        assert job.work_branch == "fix/job-abc123"

    async def test_update_status_to_failed_with_error_log(self, db_session, svc, sample_parsed_error):
        job_id = await svc.create_job(sample_parsed_error)
        await svc.update_job_status(job_id, JobStatus.FAILED, error_log="Claude failed")

        job = await svc.get_job(job_id)
        assert job.status == JobStatus.FAILED
        assert job.error_log == "Claude failed"

    async def test_update_status_increments_retry_count(self, db_session, svc, sample_parsed_error):
        job_id = await svc.create_job(sample_parsed_error)

        await svc.update_job_status(job_id, JobStatus.FAILED, increment_retry=True)
        job = await svc.get_job(job_id)
        assert job.retry_count == 1

        await svc.update_job_status(job_id, JobStatus.PENDING, increment_retry=True)
        job = await svc.get_job(job_id)
        assert job.retry_count == 2


class TestListJobs:
    async def test_list_jobs_empty(self, db_session, svc):
        jobs = await svc.list_jobs()
        assert jobs == []

    async def test_list_jobs_returns_all(self, db_session, svc, sample_parsed_error):
        sample_parsed_error.source_issue_id = "issue-1"
        await svc.create_job(sample_parsed_error)

        sample_parsed_error.source_issue_id = "issue-2"
        await svc.create_job(sample_parsed_error)

        jobs = await svc.list_jobs()
        assert len(jobs) == 2

    async def test_list_jobs_filter_by_status(self, db_session, svc, sample_parsed_error):
        sample_parsed_error.source_issue_id = "issue-1"
        job_id_1 = await svc.create_job(sample_parsed_error)
        await svc.update_job_status(job_id_1, JobStatus.DONE)

        sample_parsed_error.source_issue_id = "issue-2"
        await svc.create_job(sample_parsed_error)

        assert len(await svc.list_jobs(status=JobStatus.PENDING)) == 1
        assert len(await svc.list_jobs(status=JobStatus.DONE)) == 1
