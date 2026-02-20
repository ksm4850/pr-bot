from datetime import datetime

from app.models.error import ParsedError, StackFrame
from app.models.job import ErrorSource, Job, JobStatus


class TestJobModel:
    """Job 모델 테스트"""

    def test_job_default_status(self):
        """기본 상태가 PENDING인지 확인"""
        job = Job(
            id="test-123",
            source=ErrorSource.SENTRY,
            source_issue_id="issue-456",
            title="Test Error",
        )

        assert job.status == JobStatus.PENDING
        assert job.retry_count == 0

    def test_job_all_fields(self):
        """모든 필드가 정상 설정되는지 확인"""
        job = Job(
            id="test-123",
            status=JobStatus.PROCESSING,
            source=ErrorSource.SENTRY,
            source_issue_id="issue-456",
            title="Test Error",
            message="Something went wrong",
            level="error",
            environment="prod",
            filename="app/main.py",
            lineno=42,
            function="handler",
            repo_url="https://github.com/test/repo",
            repo_platform="github",
        )

        assert job.id == "test-123"
        assert job.status == JobStatus.PROCESSING
        assert job.source == ErrorSource.SENTRY
        assert job.filename == "app/main.py"
        assert job.lineno == 42

    def test_job_status_enum(self):
        """JobStatus enum 값 확인"""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.PROCESSING.value == "processing"
        assert JobStatus.DONE.value == "done"
        assert JobStatus.FAILED.value == "failed"


class TestErrorSource:
    """ErrorSource enum 테스트"""

    def test_error_source_values(self):
        """ErrorSource enum 값 확인"""
        assert ErrorSource.SENTRY.value == "sentry"
        assert ErrorSource.CLOUDWATCH.value == "cloudwatch"
        assert ErrorSource.DATADOG.value == "datadog"


class TestStackFrame:
    """StackFrame 모델 테스트"""

    def test_stack_frame_creation(self):
        """StackFrame 생성"""
        frame = StackFrame(
            filename="app/main.py",
            abs_path="/home/user/project/app/main.py",
            function="handler",
            lineno=42,
            context_line="    raise ValueError('error')",
            pre_context=["def handler():", "    # do something"],
            post_context=["", "def other():"],
        )

        assert frame.filename == "app/main.py"
        assert frame.lineno == 42
        assert frame.function == "handler"

    def test_stack_frame_optional_fields(self):
        """StackFrame 선택적 필드"""
        frame = StackFrame(filename="test.py")

        assert frame.filename == "test.py"
        assert frame.lineno is None
        assert frame.pre_context is None


class TestParsedError:
    """ParsedError 모델 테스트"""

    def test_parsed_error_required_fields(self):
        """필수 필드만으로 생성"""
        error = ParsedError(
            source=ErrorSource.SENTRY,
            source_issue_id="123",
            title="Test Error",
        )

        assert error.source == ErrorSource.SENTRY
        assert error.source_issue_id == "123"
        assert error.title == "Test Error"
        assert error.frames == []

    def test_parsed_error_with_frames(self):
        """프레임 포함 생성"""
        frames = [
            StackFrame(filename="a.py", lineno=1),
            StackFrame(filename="b.py", lineno=2),
        ]
        error = ParsedError(
            source=ErrorSource.SENTRY,
            source_issue_id="123",
            title="Test Error",
            frames=frames,
        )

        assert len(error.frames) == 2
        assert error.frames[0].filename == "a.py"
