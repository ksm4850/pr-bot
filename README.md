# PR-Bot

에러 트래킹 웹훅 → Job Queue → Claude Agent → 자동 브랜치 생성 서비스

Sentry 등 에러 트래킹 서비스에서 웹훅을 수신하면, Claude AI가 에러를 분석하고 코드를 수정한 뒤 GitHub/GitLab에 브랜치를 자동으로 생성합니다.

## 아키텍처

```
┌──────────────┐    Webhook     ┌──────────────┐      Save       ┌──────────┐
│ Sentry       │ ─────────────→ │   FastAPI    │ ──────────────→ │  SQLite  │
└──────────────┘                │ + Dashboard  │                 │  (Jobs)  │
                                └──────────────┘                 └────┬─────┘
                                                                      │
                                                                 Polling
                                                                 (atomic)
                                                                      │
                                 ┌──────────────┐                     │
                                 │  Worker(s)   │ ←───────────────────┘
                                 │ (백그라운드)   │
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
2. **파싱 & 저장** — 에러 정보 파싱 후 SQLite Job Queue에 저장 (중복 체크, 재발생 시 자동 재오픈)
3. **Worker 폴링** — 등록된 프로젝트의 Job만 atomic하게 가져옴 (`UPDATE RETURNING`, 다중 워커 안전)
4. **Opus 플랜** — Claude Opus가 에러를 분석하고 수정 계획 수립
5. **Sonnet 실행** — Claude Sonnet이 bash/write_file 도구로 코드 수정 및 커밋
6. **PR 브랜치** — `fix/{job_id}` 브랜치를 원격으로 push

## 기술 스택

| 영역 | 기술 |
|------|------|
| Framework | FastAPI |
| AI | Anthropic API (Opus 4.6 + Sonnet 4.6) 또는 Claude Code CLI |
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
# ── 에이전트 모드 ("api" 또는 "claude-code") ──
AGENT_MODE=api

# ── API 모드 설정 ──
ANTHROPIC_API_KEY=sk-ant-...

# ── Claude Code 모드 설정 ──
# 여러 계정 토큰을 쉼표로 구분하여 rate limit 시 자동 로테이션
CLAUDE_TOKENS=sk-ant-oat01-aaa,sk-ant-oat01-bbb

# ── Git 플랫폼 (사용할 것만 설정) ──
GITHUB_TOKEN=ghp_...
GITLAB_TOKEN=glpat-...

# ── Git 커밋 정보 ──
BOT_GIT_NAME=pr-bot
BOT_GIT_EMAIL=pr-bot@example.com

# ── Sentry ──
SENTRY_WEBHOOK_SECRET=your_secret
SENTRY_DSN=https://...@sentry.io/...    # 선택

# ── 기타 ──
WORKSPACE_DIR=/tmp/pr-bot-workspaces    # 기본: ~/.pr-bot-workspaces
WORKER_POLL_INTERVAL=5                  # 기본: 5초
```

### 에이전트 모드

| 모드 | 설정 | 필요 키 | 특징 |
|------|------|---------|------|
| **API** | `AGENT_MODE=api` | `ANTHROPIC_API_KEY` | Anthropic API 직접 호출, 토큰 비용 발생 |
| **Claude Code** | `AGENT_MODE=claude-code` | `CLAUDE_TOKENS` | Claude Code CLI 서브프로세스, 구독 기반 (Pro/Max) |

Claude Code 모드에서는 여러 구독 계정의 토큰을 등록하여 rate limit 시 자동 로테이션됩니다.

### 실행

```bash
# API 서버 실행 (Worker 내장, 서버 시작 시 자동 실행)
uv run uvicorn app.main:app --reload --port 8000
```

- 대시보드: http://localhost:8000
- API 문서: http://localhost:8000/docs

## 웹 대시보드

서버 실행 후 `http://localhost:8000`에서 접근 가능합니다.

- **Jobs 탭** — Job 목록 (상태별 필터링), 상세 정보, 에이전트 작업 히스토리
- **Projects 탭** — 프로젝트 등록/삭제
- **Worker 상태** — 실시간 상태 표시, Start/Stop 제어

## 사용 방법

### 1. 프로젝트 등록

에러 소스와 Git 레포지토리를 연결합니다. (대시보드 또는 API)

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

### 3. 자동 수정 확인

에러 발생 시 자동으로 `fix/{job_id}` 브랜치가 생성됩니다. GitHub/GitLab에서 PR을 직접 열어 검토 후 머지하세요.

> 동일 에러가 재발생하면 (DONE/FAILED 상태) 자동으로 PENDING으로 재오픈되어 다시 처리됩니다.

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
| `GET` | `/worker/status` | Worker 상태 조회 |
| `POST` | `/worker/start` | Worker 시작 |
| `POST` | `/worker/stop` | Worker 중지 |

## Job 상태 흐름

```
PENDING → PROCESSING → DONE
    ↑         │
    │         ├→ RATE_LIMITED → (대기 후 재처리)
    │         │
    └─────────├→ PENDING (재시도, 최대 3회)
              │
              └→ FAILED (치명적 에러 또는 재시도 초과)

웹훅 재수신 시:
  DONE/FAILED → PENDING (자동 재오픈)
  PENDING/PROCESSING/RATE_LIMITED → 무시 (중복)
```

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
│   ├── api/              # FastAPI 라우터
│   │   ├── webhook.py    # 웹훅 엔드포인트
│   │   ├── projects.py   # 프로젝트 CRUD
│   │   ├── jobs.py       # Job 조회
│   │   ├── worker.py     # Worker 상태/제어
│   │   └── test_errors.py # 테스트용 에러 트리거
│   ├── core/
│   │   ├── config.py     # 환경 변수 설정
│   │   ├── database.py   # SQLAlchemy 엔진/세션 (ContextVar)
│   │   └── middleware.py  # DB 세션 미들웨어
│   ├── models/           # ORM + Pydantic 모델
│   ├── repositories/     # DB 접근 레이어
│   ├── services/
│   │   ├── agent.py      # Claude 에이전트 (API + Claude Code 듀얼 모드)
│   │   ├── job_queue.py  # Job 서비스
│   │   ├── project.py    # 프로젝트 서비스
│   │   ├── workspace.py  # Git clone/branch/push
│   │   ├── worker_manager.py # Worker 라이프사이클 관리
│   │   └── parsers/      # 에러 소스별 파서
│   ├── prompts/          # 에이전트 프롬프트 (플래너/실행자)
│   ├── static/           # 웹 대시보드 (index.html)
│   └── worker.py         # Job 폴링 루프
├── tests/
└── data/                 # SQLite DB
```
