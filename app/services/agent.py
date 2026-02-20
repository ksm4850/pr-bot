"""Claude Agent 서비스 - Anthropic SDK 에이전트 루프"""

import asyncio
import json
import logging
from pathlib import Path

import anthropic

from app.core.config import settings
from app.models.job import Job, JobTaskType
from app.prompts.fix_error import SYSTEM_PROMPT, build_user_prompt
from app.services.job_queue import JobService

logger = logging.getLogger(__name__)

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
        """에이전트 루프 실행. 실패 시 예외 raise."""
        user_prompt = build_user_prompt(job, repo_dir, work_branch)
        messages: list[anthropic.types.MessageParam] = [
            {"role": "user", "content": user_prompt},
        ]

        logger.info(f"[agent] Starting agent for job {job.id}")

        for turn in range(MAX_TURNS):
            response = await self._client.messages.create(
                model="claude-opus-4-6",
                max_tokens=8096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            # 에이전트 메시지 로그
            await self._log_message(job.id, response, job_svc)

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                logger.info(f"[agent] Completed in {turn + 1} turns")
                return

            if response.stop_reason != "tool_use":
                raise RuntimeError(f"Unexpected stop_reason: {response.stop_reason}")

            # 도구 실행
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
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=cwd,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode(errors="replace")
            if proc.returncode != 0:
                return f"[exit {proc.returncode}]\n{output}"
            return output or "(no output)"
        except asyncio.TimeoutError:
            proc.kill()
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
            from app.core.database import db_context
            async with db_context():
                await job_svc.add_task(
                    job_id,
                    JobTaskType.MESSAGE,
                    content="\n".join(texts),
                )

    async def _log_tool(
        self,
        job_id: str,
        block: anthropic.types.ToolUseBlock,
        result: str,
        job_svc: JobService,
    ) -> None:
        from app.core.database import db_context
        async with db_context():
            await job_svc.add_task(
                job_id,
                JobTaskType.TOOL_USE,
                content={
                    "tool": block.name,
                    "input": block.input,
                    "output": result[:2000],  # DB 크기 제한
                },
            )
