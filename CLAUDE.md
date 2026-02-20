# PR-Bot - AI Instructions

> 에러 트래킹 웹훅 → Job Queue → Claude Agent → 자동 PR 생성 서비스

## 프로젝트 개요

Sentry, CloudWatch 등 에러 트래킹 서비스에서 웹훅을 받으면 DB에 Job으로 저장하고, Worker가 polling으로 Job을 가져와 Claude Agent SDK로 에러를 분석/수정한 뒤 GitHub/GitLab에 PR을 자동 생성하는 서비스.

## 기술 스택

- **Framework**: FastAPI
- **AI**: claude-agent-sdk (Python)
- **DB**: SQLite + SQLAlchemy (async) - Job Queue 저장
- **Git**: GitHub + GitLab (둘 다 지원)
- **Python**: 3.12+
- **Package Manager**: uv
- **Test**: pytest, pytest-asyncio

## 아키텍처

```
┌──────────────┐
│ Sentry       │──┐
├──────────────┤  │   Webhook    ┌──────────────┐      Save       ┌──────────┐
│ CloudWatch   │──┼────────────→ │   FastAPI    │ ──────────────→ │  SQLite  │
├──────────────┤  │              │   (API)      │                 │  (Jobs)  │
│ Datadog      │──┘              └──────────────┘                 └────┬─────┘
└──────────────┘                                                       │
                                                                  Polling
                                                                       │
                                 ┌──────────────┐                      │
                                 │    Worker    │ ←────────────────────┘
                                 │  (별도 프로세스) │
                                 └──────┬───────┘
                                        │
                                        ↓
                                 ┌──────────────┐
                                 │ claude-agent │  ← 에러 분석
                                 │     -sdk     │  ← git clone
                                 │              │  ← 코드 수정
                                 │              │  ← PR 생성
                                 └──────────────┘
                                        │
                                        ↓
                                 ┌──────────────┐
                                 │ GitHub/GitLab│
                                 └──────────────┘
```

## 디렉토리 구조

```
pr-bot/
├── app/
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── repositories/
│   ├── services/
│   │   └── parsers/
│   └── prompts/
├── tests/
└── data/
```

## 파서 추상화

```python
# 새 에러 소스 추가 시:
# 1. app/models/job.py - ErrorSource enum에 추가
# 2. app/services/parsers/new_source.py 생성
# 3. app/services/parsers/__init__.py - 레지스트리 등록
# 4. app/api/webhook.py - 엔드포인트 추가

class ErrorParser(ABC):
    @property
    @abstractmethod
    def source(self) -> ErrorSource: ...

    @abstractmethod
    def parse(self, payload: dict) -> ParsedError: ...
```

## 테스트

```bash
# 전체 테스트 실행
uv run pytest -v

# 특정 테스트 실행
uv run pytest tests/test_parsers.py -v

# 커버리지
uv run pytest --cov=app
```

### 테스트 파일 구조

| 파일 | 테스트 대상 |
|------|-------------|
| `test_models.py` | Job, ErrorSource, StackFrame, ParsedError |
| `test_parsers.py` | SentryParser, 파서 레지스트리 |
| `test_job_queue.py` | create_job, get_job, update_job_status, list_jobs |
| `test_webhook.py` | `/health`, `/webhook/sentry` API |

### 테스트 작성 규칙

- 새 기능 추가 시 반드시 테스트 작성
- fixture는 `conftest.py`에 정의
- 클래스로 그룹화 (e.g., `TestSentryParser`)

## 구현 상태

### Phase 1: 프로젝트 셋업 [완료]
- [x] pyproject.toml 의존성 추가
- [x] 디렉토리 구조 생성
- [x] app/main.py - FastAPI 앱

### Phase 2: 웹훅 + 파서 [완료]
- [x] app/models/job.py - Job, ErrorSource, JobStatus
- [x] app/models/error.py - ParsedError, StackFrame
- [x] app/services/parsers/base.py - ErrorParser 추상 클래스
- [x] app/services/parsers/sentry.py - SentryParser
- [x] app/api/webhook.py - POST /webhook/sentry
- [x] 테스트 작성 (23개 통과)

### Phase 3: Job Queue [완료]
- [x] app/core/config.py - Settings (database_path)
- [x] app/core/database.py - SQLAlchemy async engine/session
- [x] app/models/job.py - JobModel (ORM) + Job (Pydantic)
- [x] app/services/job_queue.py - Job CRUD (create, get, update, list)
- [x] app/api/webhook.py - 중복 체크 + Job 생성 연동
- [x] tests/test_job_queue.py - 15개 테스트 추가 (총 39개 통과)

### Phase 4: Worker + Claude Agent [미구현]
- [ ] app/prompts/fix_error.py
- [ ] app/services/agent.py
- [ ] app/worker.py

### Phase 5: 고급 기능 [미구현]
- [ ] 중복 PR 방지
- [ ] 실패 시 retry
- [ ] 실패 시 fallback (Issue 생성)

## 실행 방법

```bash
# 의존성 설치
uv sync

# API 서버 실행
uv run uvicorn app.main:app --reload --port 8000

# 테스트 실행
uv run pytest -v

# Worker 실행 (미구현)
# uv run python -m app.worker
```

## 환경 변수

```bash
# .env.example (미생성)
SENTRY_WEBHOOK_SECRET=xxx
ANTHROPIC_API_KEY=xxx
GITHUB_TOKEN=xxx
GITLAB_TOKEN=xxx
WORKSPACE_DIR=/tmp/pr-bot-workspaces
DATABASE_URL=sqlite:///data/jobs.db
WORKER_POLL_INTERVAL=5
```

## 현재 진행 상태

**완료**: 웹훅 엔드포인트 + Sentry 파서 + Job Queue (SQLAlchemy)
**다음**: Worker + Claude Agent SDK 연동

### Job Queue API

```python
from app.services.job_queue import (
    create_job,        # ParsedError → Job ID
    job_exists,        # 중복 체크
    get_job,           # ID로 조회
    get_pending_job,   # 대기 중 Job 하나 (FIFO)
    update_job_status, # 상태 변경 (pr_url, error_log, retry_count)
    list_jobs,         # 목록 조회 (상태 필터링)
)
```

### DB 저장 필드 (Claude Agent용)

| 필드 | 설명 | 예시 |
|------|------|------|
| `issue_id` | Sentry 이슈 ID | "7244067205" |
| `environment` | 환경 (→ 깃 브랜치) | "dev", "prod" |
| `exception_type` | 예외 타입 | "ZeroDivisionError" |
| `message` | 예외 메시지 | "division by zero" |
| `filename` | 에러 발생 파일 | "app.py" |
| `lineno` | 에러 발생 라인 | 364 |
| `function` | 에러 발생 함수 | "trigger_error" |
| `transaction` | API 엔드포인트 | "/sentry-debug" |
| `stacktrace` | 스택트레이스 (JSON) | in_app=True만 |

### Sentry 파서 특징

- `exception.values[-1]`에서 실제 예외 정보 추출
- `in_app=True` 프레임만 필터링 (라이브러리 코드 제외)
- `context_line`, `pre_context`, `post_context` 저장

---

## 아키텍처 규칙 (AI 필독)

### 레이어 구조

```
API Handler → Service → Repository → DB
```

- **Service**: 비즈니스 로직만. DB 직접 접근 금지
- **Repository**: DB 접근만. 비즈니스 로직 금지
- **클래스**로 작성 (dependency-injector 사용 예정)

```python
class FooRepository(BaseRepository):
    async def create(self, ...) -> FooModel: ...

class FooService:
    def __init__(self, repo: FooRepository | None = None):
        self.repo = repo or FooRepository()
```

### DB 세션: ContextVar + Middleware

- **미들웨어**가 요청마다 세션 생성 → `db_session` (ContextVar) 저장 → commit/rollback
- **Repository**는 `self.session` (= `db_session.get()`) 으로 세션 꺼냄
- Repository는 `flush()`만. `commit()`은 미들웨어 담당

```python
# ❌ 직접 import 금지 (reset_engine() 후 구세션 참조 버그)
from app.core.database import AsyncSessionLocal

# ✅ 모듈로 참조
from app.core import database
async with database.AsyncSessionLocal() as session: ...
```

### 테스트 fixture

- **Repository 테스트**: `db_session` fixture → ContextVar 직접 설정
- **HTTP 테스트**: `client` fixture → TestClient → 미들웨어가 ContextVar 자동 설정

### 새 도메인 추가 시 체크리스트

1. `app/models/foo.py` - `FooModel` (ORM) + `Foo` (Pydantic)
2. `app/repositories/foo.py` - `FooRepository(BaseRepository)`
3. `app/services/foo.py` - `FooService`
4. `app/api/foos.py` - 라우터
5. `app/core/database.py` - `init_db()`에 모델 import 추가
6. `app/main.py` - 라우터 등록

---

_이 파일은 세션 간 컨텍스트 유지를 위해 사용됩니다._
