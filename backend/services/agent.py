"""Claude Agent 서비스 - Opus(플랜) + Sonnet(실행) 2단계"""

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path

import anthropic
from core.database import db_context
from core.config import settings
from models.job import Job, JobTaskType
from prompts.fix_error import (
    EXECUTOR_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    build_execute_prompt,
    build_plan_prompt,
)
from services.job_queue import JobService

logger = logging.getLogger(__name__)


class RateLimitedError(Exception):
    """Agent 실행 중 API rate limit 발생 (모든 토큰 소진)"""
    def __init__(self, retry_after: float | None = None):
        self.retry_after = retry_after
        super().__init__(f"Rate limited (retry_after={retry_after}s)")


class TokenPool:
    """Claude Code 구독 토큰 로테이션 풀"""

    def __init__(self, tokens: list[str]):
        self._tokens = tokens
        self._index = 0

    @property
    def available(self) -> bool:
        return len(self._tokens) > 0

    @property
    def current(self) -> str | None:
        if not self._tokens:
            return None
        return self._tokens[self._index]

    def rotate(self) -> bool:
        """다음 토큰으로 전환. 한 바퀴 돌았으면 False."""
        if len(self._tokens) <= 1:
            return False
        next_idx = (self._index + 1) % len(self._tokens)
        if next_idx == 0:
            return False  # 모든 토큰 소진
        self._index = next_idx
        logger.info("[token-pool] Rotated to token %d/%d", self._index + 1, len(self._tokens))
        return True

    def reset(self) -> None:
        """첫 번째 토큰으로 복귀 (새 Job 시작 시)"""
        self._index = 0

    def make_env(self) -> dict[str, str]:
        """현재 토큰으로 subprocess 환경변수 생성"""
        env = {**os.environ}
        token = self.current
        if token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = token
        return env

PLANNER_MODEL = "claude-opus-4-6"
EXECUTOR_MODEL = "claude-sonnet-4-6"

MAX_TURNS = 30
BASH_TIMEOUT = 60  # seconds

TOOLS: list[anthropic.types.ToolParam] = [
    {
        "name": "bash",
        "description": (
            "Run a shell command in the repository workspace. "
            "Use this to read files (cat, grep), edit files, run tests, and git operations. "
            "The working directory is set to the repository root."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 60)",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file, creating or overwriting it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to the repository root",
                },
                "content": {
                    "type": "string",
                    "description": "File content to write",
                },
            },
            "required": ["path", "content"],
        },
    },
]


class AgentService:
    def __init__(self):
        mode = settings.agent_mode

        if mode == "api":
            if not settings.anthropic_api_key:
                raise ValueError("AGENT_MODE=api 이지만 ANTHROPIC_API_KEY가 설정되지 않았습니다")
            self._client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key,
            )
            self.token_pool = TokenPool([])
        else:
            tokens = settings.get_claude_tokens()
            if not tokens:
                raise ValueError("AGENT_MODE=claude-code 이지만 CLAUDE_TOKENS가 설정되지 않았습니다")
            self._client = None  # claude-code 모드에서는 미사용
            self.token_pool = TokenPool(tokens)

    async def run(
        self,
        job: Job,
        repo_dir: Path,
        work_branch: str,
        job_svc: JobService,
        *,
        resume: bool = False,
    ) -> None:
        """Opus로 플랜 수립 → Sonnet으로 실행. 실패 시 예외 raise.

        resume=True이면 이전 task에서 플랜을 복원하고 Sonnet 실행만 수행.
        """
        mode = settings.agent_mode
        logger.info("[agent] Mode: %s | job %s | resume=%s", mode, job.id, resume)

        plan: str | None = None
        prev_context: str | None = None

        if resume:
            plan, prev_context = await self._restore_from_tasks(job.id, job_svc)
            if plan:
                logger.info("[agent] Restored plan (%d chars) from previous tasks", len(plan))

        if not plan:
            logger.info("[agent] Phase 1: Planning (Opus) for job %s", job.id)
            if mode == "claude-code":
                plan = await self._plan_claude_code(job, repo_dir, job_svc)
            else:
                plan = await self._plan(job, repo_dir, job_svc)

        logger.info("[agent] Phase 2: Executing (Sonnet) for job %s", job.id)
        if mode == "claude-code":
            summary = await self._execute_claude_code(job, repo_dir, work_branch, plan, job_svc)
        else:
            summary = await self._execute(job, repo_dir, work_branch, plan, job_svc, prev_context=prev_context)

        if summary:
            logger.info("[agent] Saving summary for job %s", job.id)
            async with db_context():
                await job_svc.add_task(job.id, JobTaskType.MESSAGE, content=f"[SUMMARY]\n{summary}", label="최종 완료 요약")

    async def _restore_from_tasks(self, job_id: str, job_svc: JobService) -> tuple[str | None, str | None]:
        """이전 task에서 플랜과 작업 컨텍스트 복원"""
        async with db_context():
            tasks = await job_svc.list_tasks(job_id)

        plan: str | None = None
        context_parts: list[str] = []

        for task in tasks:
            if not task.content:
                continue
            if task.type == JobTaskType.MESSAGE and task.content.startswith("[PLAN]\n"):
                plan = task.content[len("[PLAN]\n"):]
            elif task.type == JobTaskType.MESSAGE and not task.content.startswith("[SUMMARY]\n"):
                context_parts.append(f"[이전 응답] {task.content}")
            elif task.type == JobTaskType.TOOL_USE:
                try:
                    data = json.loads(task.content) if isinstance(task.content, str) else task.content
                    context_parts.append(
                        f"[이전 도구 호출] {data.get('tool', '?')}: {str(data.get('input', ''))[:200]}"
                    )
                except (json.JSONDecodeError, AttributeError):
                    pass

        prev_context = "\n".join(context_parts) if context_parts else None
        return plan, prev_context

    # ── Phase 1: Planner (Opus) ───────────────────────────────────

    async def _plan(self, job: Job, repo_dir: Path, job_svc: JobService) -> str:
        """Opus가 에러를 분석하고 수정 플랜 반환 (도구 없음)"""
        file_content = self._read_source_file(job, repo_dir)
        user_prompt = build_plan_prompt(job, file_content)

        try:
            response = await self._client.messages.create(
                model=PLANNER_MODEL,
                max_tokens=4096,
                system=PLANNER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except anthropic.RateLimitError as e:
            retry_after = None
            if hasattr(e, "response") and e.response is not None:
                retry_after_str = e.response.headers.get("retry-after")
                if retry_after_str:
                    try:
                        retry_after = float(retry_after_str)
                    except ValueError:
                        pass
            raise RateLimitedError(retry_after=retry_after) from e

        plan = "\n".join(
            block.text for block in response.content if block.type == "text"
        )
        logger.info(
            "[planner] Plan created (%d chars) | tokens: %d in / %d out",
            len(plan), response.usage.input_tokens, response.usage.output_tokens,
        )


        async with db_context():
            await job_svc.add_tokens(job.id, response.usage.input_tokens, response.usage.output_tokens)
            await job_svc.add_task(job.id, JobTaskType.MESSAGE, content=f"[PLAN]\n{plan}", label="Opus 수정 플랜 수립")

        return plan

    def _read_source_file(self, job: Job, repo_dir: Path) -> str | None:
        """에러 발생 파일 내용 읽기 (Opus 컨텍스트용)"""
        if not job.filename:
            return None
        filepath = Path(job.filename.replace("\\", "/"))
        full_path = repo_dir / filepath
        if not full_path.exists():
            return None
        try:
            return full_path.read_text(encoding="utf-8")
        except Exception:
            return None

    # ── Phase 2: Executor (Sonnet) ────────────────────────────────

    async def _execute(
        self,
        job: Job,
        repo_dir: Path,
        work_branch: str,
        plan: str,
        job_svc: JobService,
        *,
        prev_context: str | None = None,
    ) -> str:
        """Sonnet이 플랜을 받아 도구로 코드 수정 + 커밋. 완료 요약 반환."""
        user_prompt = build_execute_prompt(job, repo_dir, work_branch, plan)
        if prev_context:
            user_prompt += (
                "\n\n## Previous Progress (rate limit로 중단됨)\n"
                "이전 작업에서 아래 진행 내역이 있습니다. 이어서 작업하세요.\n\n"
                f"{prev_context}"
            )
        messages: list[anthropic.types.MessageParam] = [
            {"role": "user", "content": user_prompt},
        ]
        last_text = ""

        for turn in range(MAX_TURNS):
            try:
                response = await self._client.messages.create(
                    model=EXECUTOR_MODEL,
                    max_tokens=8096,
                    system=EXECUTOR_SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=messages,
                )
            except anthropic.RateLimitError as e:
                retry_after = None
                if hasattr(e, "response") and e.response is not None:
                    retry_after_str = e.response.headers.get("retry-after")
                    if retry_after_str:
                        try:
                            retry_after = float(retry_after_str)
                        except ValueError:
                            pass
                logger.warning("[executor] Rate limited at turn %d (retry_after=%s)", turn + 1, retry_after)
                raise RateLimitedError(retry_after=retry_after) from e

            async with db_context():
                await job_svc.add_tokens(job.id, response.usage.input_tokens, response.usage.output_tokens)
            await self._log_message(job.id, response, job_svc)
            messages.append({"role": "assistant", "content": response.content})

            texts = [b.text for b in response.content if b.type == "text" and b.text]
            if texts:
                last_text = "\n".join(texts)

            if response.stop_reason == "end_turn":
                logger.info("[executor] Completed in %d turns", turn + 1)
                return last_text

            if response.stop_reason != "tool_use":
                raise RuntimeError(f"Unexpected stop_reason: {response.stop_reason}")

            tool_results: list[anthropic.types.ToolResultBlockParam] = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = await self._execute_tool(block.name, block.input, repo_dir)
                await self._log_tool(job.id, block, result, job_svc)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

            messages.append({"role": "user", "content": tool_results})

        raise RuntimeError(f"Agent exceeded max turns ({MAX_TURNS})")

    # ── Phase 1 (claude-code 모드): Claude Code CLI subprocess ────

    async def _plan_claude_code(self, job: Job, repo_dir: Path, job_svc: JobService) -> str:
        """claude CLI subprocess로 Opus가 플랜 수립. 구독제 사용.

        claude-code 모드에서는 file_content를 넣지 않음 — Claude Code가 직접 파일 탐색.
        """
        prompt = f"{PLANNER_SYSTEM_PROMPT}\n\n{build_plan_prompt(job, file_content=None)}"

        result = await self._run_claude_cli(
            ["claude", "-p", "--model", PLANNER_MODEL],
            input_text=prompt,
            cwd=repo_dir,
        )

        plan = result.strip()
        logger.info("[planner/claude-code] Plan created (%d chars)", len(plan))

        async with db_context():
            await job_svc.add_task(job.id, JobTaskType.MESSAGE, content=f"[PLAN]\n{plan}", label="Opus 수정 플랜 수립")

        return plan

    # ── Phase 2 (claude-code 모드): Claude Code CLI subprocess ────

    async def _execute_claude_code(
        self,
        job: Job,
        repo_dir: Path,
        work_branch: str,
        plan: str,
        job_svc: JobService,
    ) -> str:
        """claude CLI subprocess로 Sonnet이 플랜 실행. 구독제 사용."""
        prompt = build_execute_prompt(job, repo_dir, work_branch, plan)

        output = await self._run_claude_cli(
            ["claude", "-p", "--model", EXECUTOR_MODEL, "--dangerously-skip-permissions"],
            input_text=prompt,
            cwd=repo_dir,
        )

        logger.info("[executor/claude-code] Done | output: %d chars", len(output))

        async with db_context():
            await job_svc.add_task(
                job.id,
                JobTaskType.MESSAGE,
                content=output,
                label="Claude Code 실행 완료",
            )

        return output

    # ── Claude CLI 공통 실행 (토큰 로테이션 포함) ────────────────

    async def _run_claude_cli(
        self,
        cmd: list[str],
        *,
        input_text: str,
        cwd: Path,
        timeout: int = 600,
    ) -> str:
        """claude CLI 실행. rate limit 시 토큰 로테이션 후 재시도."""
        while True:
            env = self.token_pool.make_env()
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                input=input_text,
                cwd=cwd,
                capture_output=True,
                encoding="utf-8",
                timeout=timeout,
                env=env,
            )

            if result.returncode == 0:
                return result.stdout.strip()

            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            output = stderr or stdout  # stderr 비면 stdout 확인

            # rate limit 감지 → 토큰 로테이션 시도
            if self._is_rate_limit_error(output):
                token_idx = self.token_pool._index + 1
                total = len(self.token_pool._tokens) if self.token_pool._tokens else 0
                logger.warning(
                    "[claude-cli] Rate limited (token %d/%d): %s",
                    token_idx, total, output[:200],
                )
                if self.token_pool.rotate():
                    logger.info("[claude-cli] Retrying with next token...")
                    continue
                # 모든 토큰 소진
                raise RateLimitedError()

            raise RuntimeError(f"claude CLI failed (exit {result.returncode}): {output}")

    @staticmethod
    def _is_rate_limit_error(stderr: str) -> bool:
        lower = stderr.lower()
        return any(kw in lower for kw in ("rate limit", "rate_limit", "429", "too many requests"))

    async def _execute_tool(
        self,
        name: str,
        inputs: dict,
        repo_dir: Path,
    ) -> str:
        if name == "bash":
            return await self._run_bash(inputs["command"], repo_dir, inputs.get("timeout", BASH_TIMEOUT))
        if name == "write_file":
            return self._write_file(inputs["path"], inputs["content"], repo_dir)
        return f"Unknown tool: {name}"

    async def _run_bash(self, command: str, cwd: Path, timeout: int) -> str:
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=cwd,
                timeout=timeout,
            )
            output = result.stdout.decode(errors="replace")
            if result.returncode != 0:
                return f"[exit {result.returncode}]\n{output}"
            return output or "(no output)"
        except subprocess.TimeoutExpired:
            return f"[timeout after {timeout}s]"
        except Exception as e:
            return f"[error] {e}"

    def _write_file(self, path: str, content: str, repo_dir: Path) -> str:
        target = (repo_dir / path).resolve()
        # 워크스페이스 밖 쓰기 방지
        if not str(target).startswith(str(repo_dir.resolve())):
            return f"[error] Path outside repository: {path}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Written {len(content)} bytes to {path}"

    async def _log_message(
        self,
        job_id: str,
        response: anthropic.types.Message,
        job_svc: JobService,
    ) -> None:
        texts = [b.text for b in response.content if b.type == "text" and b.text]
        if texts:
            full_text = "\n".join(texts)
            first_line = full_text.split("\n")[0].strip()[:80]

            async with db_context():
                await job_svc.add_task(
                    job_id,
                    JobTaskType.MESSAGE,
                    content=full_text,
                    label=first_line or "Sonnet 응답",
                )

    async def _log_tool(
        self,
        job_id: str,
        block: anthropic.types.ToolUseBlock,
        result: str,
        job_svc: JobService,
    ) -> None:
        if block.name == "bash":
            label = f"bash: {str(block.input.get('command', ''))[:70]}"
        elif block.name == "write_file":
            label = f"파일 작성: {block.input.get('path', '')}"
        else:
            label = block.name


        async with db_context():
            await job_svc.add_task(
                job_id,
                JobTaskType.TOOL_USE,
                content={
                    "tool": block.name,
                    "input": block.input,
                    "output": result,
                },
                label=label,
            )
