# PR-Bot

에러 트래킹 웹훅 → Job Queue → Claude Agent → 자동 브랜치 생성 서비스

Sentry 등 에러 트래킹 서비스에서 웹훅을 수신하면, Claude AI가 에러를 분석하고 코드를 수정한 뒤 GitHub/GitLab에 브랜치를 자동으로 생성합니다.

## 아키텍처

```
┌──────────────┐    Webhook     ┌──────────────┐      Save       ┌──────────┐
│ Sentry       │ ─────────────→ │   FastAPI    │ ──────────────→ │  SQLite  │
└──────────────┘                │   (API)      │                 │  (Jobs)  │
                                └──────────────┘                 └────┬─────┘
                                                                       │
                                                                  Polling
                                                                       │
                                 ┌──────────────┐                      │
                                 │    Worker    │ ←────────────────────┘
                                 │  (백그라운드)  │
                                 └──────┬───────┘
                                        │
                          ┌─────────────┴─────────────┐
                          ▼                           ▼
                   ┌─────────────┐           ┌─────────────┐
                   │ Opus (플랜)  │    →     │ Sonnet (실행)│
                   │ 에러 분석    │           │ 코드 수정    │
                   │ 수정 플랜    │           │ 커밋 & Push  │
                   └─────────────┘           └─────────────┘
                                                       │
                                                       ▼
                                              ┌──────────────┐
                                              │ GitHub/GitLab│
                                              │  (브랜치)     │
                                              └──────────────┘
```

### 처리 흐름

1. **웹훅 수신** — Sentry가 에러 발생 시 `/webhook/sentry`로 POST 요청
2. **파싱 & 저장** — 에러 정보 파싱 후 SQLite Job Queue에 저장 (중복 체크)
3. **Worker 폴링** — 백그라운드 Worker가 Pending Job을 FIFO로 가져옴
4. **Opus 플랜** — Claude Opus가 에러를 분석하고 수정 계획 수립
5. **Sonnet 실행** — Claude Sonnet이 bash/write_file 도구로 코드 수정 및 커밋
6. **PR 브랜치** — `fix/{job_id}` 브랜치를 원격으로 push

## 기술 스택

| 영역 | 기술 |
|------|------|
| Framework | FastAPI |
| AI | Anthropic API (Opus 4.6 + Sonnet 4.6) |
| DB | SQLite + SQLAlchemy (async) |
| Git | GitHub / GitLab |
| Python | 3.12+ |
| Package Manager | uv |
| Test | pytest, pytest-asyncio |

## 설치 및 실행

### 요구사항

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) 패키지 매니저
- git

### 설치

```bash
git clone https://github.com/your-org/pr-bot.git
cd pr-bot
uv sync
```

### 환경 변수 설정

프로젝트 루트에 `.env` 파일 생성:

```bash
# Claude AI
ANTHROPIC_API_KEY=sk-ant-...

# Git 플랫폼 (사용할 것만 설정)
GITHUB_TOKEN=ghp_...
GITLAB_TOKEN=glpat-...

# Sentry 웹훅 시크릿
SENTRY_WEBHOOK_SECRET=your_secret

# Sentry DSN (에러 모니터링, 선택)
SENTRY_DSN=https://...@sentry.io/...

# 워크스페이스 디렉토리 (기본: ~/.pr-bot-workspaces)
WORKSPACE_DIR=/tmp/pr-bot-workspaces

# Worker 폴링 간격 (기본: 5초)
WORKER_POLL_INTERVAL=5
```

### 실행

```bash
# API 서버 실행 (Worker 내장)
uv run uvicorn app.main:app --reload --port 8000
```

서버 시작 시 Worker가 백그라운드에서 자동으로 함께 실행됩니다.

API 문서: http://localhost:8000/docs

## 사용 방법

### 1. 프로젝트 등록

에러 소스와 Git 레포지토리를 연결합니다.

```bash
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{
    "source": "sentry",
    "source_project_id": "4509981525278720",
    "repo_url": "https://github.com/your-org/your-repo",
    "repo_platform": "github"
  }'
```

### 2. Sentry 웹훅 연결

Sentry 프로젝트 설정 → Integrations → Webhooks에서 아래 URL 등록:

```
http://your-server:8000/webhook/sentry
```

### 3. PR 확인

에러 발생 시 자동으로 `fix/{job_id}` 브랜치가 생성됩니다. GitHub/GitLab에서 PR을 직접 열어 검토 후 머지하세요.

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/health` | 헬스체크 |
| `POST` | `/webhook/sentry` | Sentry 웹훅 수신 |
| `POST` | `/projects` | 프로젝트 등록 |
| `GET` | `/projects` | 프로젝트 목록 |
| `DELETE` | `/projects/{source}/{project_id}` | 프로젝트 삭제 |
| `GET` | `/jobs` | Job 목록 (상태 필터, 페이징) |
| `GET` | `/jobs/{job_id}` | Job 상세 조회 |
| `GET` | `/jobs/{job_id}/tasks` | Job 에이전트 작업 히스토리 |
| `GET` | `/worker` | Worker 상태 조회 |

## 새 에러 소스 추가

1. `app/models/job.py` — `ErrorSource` enum에 추가
2. `app/services/parsers/new_source.py` — `ErrorParser` 구현
3. `app/services/parsers/__init__.py` — 레지스트리 등록
4. `app/api/webhook.py` — 엔드포인트 추가

```python
class ErrorParser(ABC):
    @property
    @abstractmethod
    def source(self) -> ErrorSource: ...

    @abstractmethod
    def parse(self, payload: dict) -> ParsedError: ...
```

## 테스트

```bash
# 전체 테스트
uv run pytest -v

# 특정 파일
uv run pytest tests/test_parsers.py -v

# 커버리지
uv run pytest --cov=app
```

| 테스트 파일 | 대상 |
|------------|------|
| `test_models.py` | Job, ErrorSource, StackFrame, ParsedError |
| `test_parsers.py` | SentryParser, 파서 레지스트리 |
| `test_job_queue.py` | Job CRUD |
| `test_webhook.py` | `/health`, `/webhook/sentry` API |

## 디렉토리 구조

```
pr-bot/
├── app/
│   ├── api/            # FastAPI 라우터
│   │   ├── webhook.py  # 웹훅 엔드포인트
│   │   ├── projects.py # 프로젝트 관리
│   │   ├── jobs.py     # Job 조회
│   │   └── worker.py   # Worker 상태
│   ├── core/
│   │   ├── config.py   # 환경 변수 설정
│   │   ├── database.py # SQLAlchemy 엔진/세션
│   │   └── middleware.py
│   ├── models/         # ORM + Pydantic 모델
│   ├── repositories/   # DB 접근 레이어
│   ├── services/
│   │   ├── agent.py    # Claude 에이전트 (Opus + Sonnet)
│   │   ├── job_queue.py
│   │   ├── workspace.py # Git clone/push
│   │   └── parsers/    # 에러 소스별 파서
│   ├── prompts/        # 에이전트 프롬프트
│   └── worker.py       # Job 폴링 루프
├── tests/
└── data/               # SQLite DB
```
