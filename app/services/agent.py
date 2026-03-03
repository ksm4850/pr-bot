"""Claude Agent 서비스 - Opus(플랜) + Sonnet(실행) 2단계"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path

import anthropic
from app.core.database import db_context
from app.core.config import settings
from app.models.job import Job, JobTaskType
from app.prompts.fix_error import (
    EXECUTOR_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    build_execute_prompt,
    build_plan_prompt,
)
from app.services.job_queue import JobService

logger = logging.getLogger(__name__)

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
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
        )

    async def run(
        self,
        job: Job,
        repo_dir: Path,
        work_branch: str,
        job_svc: JobService,
    ) -> None:
        """Opus로 플랜 수립 → Sonnet으로 실행. 실패 시 예외 raise."""
        mode = settings.agent_mode
        logger.info("[agent] Mode: %s | job %s", mode, job.id)

        logger.info("[agent] Phase 1: Planning (Opus) for job %s", job.id)
        if mode == "claude-code":
            plan = await self._plan_claude_code(job, repo_dir, job_svc)
        else:
            plan = await self._plan(job, repo_dir, job_svc)

        logger.info("[agent] Phase 2: Executing (Sonnet) for job %s", job.id)
        if mode == "claude-code":
            summary = await self._execute_claude_code(job, repo_dir, work_branch, plan, job_svc)
        else:
            summary = await self._execute(job, repo_dir, work_branch, plan, job_svc)

        if summary:
            logger.info("[agent] Saving summary for job %s", job.id)
            from app.core.database import db_context
            async with db_context():
                await job_svc.add_task(job.id, JobTaskType.MESSAGE, content=f"[SUMMARY]\n{summary}", label="최종 완료 요약")

    # ── Phase 1: Planner (Opus) ───────────────────────────────────

    async def _plan(self, job: Job, repo_dir: Path, job_svc: JobService) -> str:
        """Opus가 에러를 분석하고 수정 플랜 반환 (도구 없음)"""
        file_content = self._read_source_file(job, repo_dir)
        user_prompt = build_plan_prompt(job, file_content)

        response = await self._client.messages.create(
            model=PLANNER_MODEL,
            max_tokens=4096,
            system=PLANNER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

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
    ) -> str:
        """Sonnet이 플랜을 받아 도구로 코드 수정 + 커밋. 완료 요약 반환."""
        user_prompt = build_execute_prompt(job, repo_dir, work_branch, plan)
        messages: list[anthropic.types.MessageParam] = [
            {"role": "user", "content": user_prompt},
        ]
        last_text = ""

        for turn in range(MAX_TURNS):
            response = await self._client.messages.create(
                model=EXECUTOR_MODEL,
                max_tokens=8096,
                system=EXECUTOR_SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

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
        """claude CLI subprocess로 Opus가 플랜 수립. 구독제 사용."""
        file_content = self._read_source_file(job, repo_dir)
        prompt = f"{PLANNER_SYSTEM_PROMPT}\n\n{build_plan_prompt(job, file_content)}"

        result = await asyncio.to_thread(
            subprocess.run,
            [
                "claude", "-p",
                "--model", PLANNER_MODEL,
            ],
            input=prompt,
            cwd=repo_dir,
            capture_output=True,
            encoding="utf-8",
            timeout=300,
        )

        if result.returncode != 0:
            raise RuntimeError(f"claude CLI (planner) failed (exit {result.returncode}): {result.stderr.strip()}")

        plan = result.stdout.strip()
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

        result = await asyncio.to_thread(
            subprocess.run,
            [
                "claude", "-p",
                "--model", EXECUTOR_MODEL,
                "--dangerously-skip-permissions",
            ],
            input=prompt,
            cwd=repo_dir,
            capture_output=True,
            encoding="utf-8",
            timeout=600,
        )

        output = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode != 0:
            raise RuntimeError(f"claude CLI failed (exit {result.returncode}): {stderr}")

        logger.info("[executor/claude-code] Done | output: %d chars", len(output))

        async with db_context():
            await job_svc.add_task(
                job.id,
                JobTaskType.MESSAGE,
                content=output,
                label="Claude Code 실행 완료",
            )

        return output

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
            from app.core.database import db_context
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
