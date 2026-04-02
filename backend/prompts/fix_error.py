"""Claude Agent 시스템/유저 프롬프트 빌더"""

import json
from pathlib import Path

from models.job import Job


# ── Planner (Opus) ────────────────────────────────────────────────

PLANNER_SYSTEM_PROMPT = """\
You are a senior software engineer specializing in debugging production errors.

Your task:
1. Analyze the error report and source code carefully
2. Identify the root cause precisely
3. Write a concrete fix plan

Your fix plan must include:
- Root cause (1-2 sentences)
- Exact file path and line numbers to change
- The specific code change (show before/after)
- Why this fixes the issue

Rules:
- Always plan to fix the actual bug. Never suggest skipping, excluding, or commenting out the broken code.
- Do NOT judge whether the code is "test code" or "intentional" — production threw this error, so it must be fixed.
- Be precise and specific. Another engineer will implement your plan exactly as written.
- Do NOT implement the fix yourself — only plan it.
- Always respond in Korean (한국어로 응답).
"""


def build_plan_prompt(job: Job, file_content: str | None) -> str:
    """Opus용 플랜 프롬프트: 에러 정보 + 파일 내용"""
    parts = [
        "## Error Report",
        "",
        f"**Title**: {job.title}",
    ]
    if job.subtitle:
        parts.append(f"**Subtitle**: {job.subtitle}")

    parts += [
        f"**Exception**: {job.exception_type or 'Unknown'}",
        f"**Message**: {job.message or '(no message)'}",
        f"**Environment**: {job.environment or 'unknown'}",
    ]

    if job.transaction:
        parts += [f"**Endpoint**: {job.transaction}"]

    parts += [
        "",
        "**Error Location**:",
        f"- File: `{job.filename or 'unknown'}`",
        f"- Line: {job.lineno or 'unknown'}",
        f"- Function: `{job.function or 'unknown'}`",
    ]

    if job.stacktrace:
        try:
            frames = json.loads(job.stacktrace)
            # innermost (actual error) frame만 상세히 보여줌
            inner = frames[-1] if frames else None
            if inner:
                pre = "\n".join(inner.get("pre_context") or [])
                ctx = inner.get("context_line", "")
                post = "\n".join(inner.get("post_context") or [])
                parts += [
                    "",
                    "**Code Context** (lines around the error):",
                    "```python",
                    pre,
                    f">>> {ctx}  # ← error here",
                    post,
                    "```",
                ]
        except Exception:
            pass

    if file_content:
        parts += [
            "",
            f"**Full Source File** (`{job.filename}`):",
            "```python",
            file_content,
            "```",
        ]
    elif job.filename:
        # file_content가 없으면 (경로 불일치 등) 파일 탐색 지시
        parts += [
            "",
            f"**Note**: 파일 `{job.filename}`을 직접 찾지 못했습니다.",
            f"레포지토리에서 `find . -path '*{job.filename}'` 등으로 실제 경로를 찾아 분석하세요.",
        ]

    parts += [
        "",
        "## Task",
        "Analyze the error above and write a precise fix plan.",
        "Do NOT write code to fix it — only describe what needs to change and why.",
    ]

    return "\n".join(parts)


# ── Executor (Sonnet) ─────────────────────────────────────────────

EXECUTOR_SYSTEM_PROMPT = """\
You are an expert software engineer implementing a bug fix.

You have been given an error report and a fix plan from a senior engineer.

Your task:
1. Follow the fix plan precisely
2. Use the bash tool to read files if you need clarification
3. Make the minimal required code changes using write_file or bash
4. Commit with a clear message

Rules:
- Always fix the actual bug in the code. Never skip, exclude, or comment out the problematic code.
- Do NOT judge whether the code is "test code", "intentional", or "expected to fail" — just fix the error.
- Only fix the specific bug. Do not refactor or change unrelated code.
- Always end with a git commit. The branch is already checked out.
- Do NOT push to remote. The system handles that.
- Commit message format: "fix: <short description>"
- Always respond in Korean (한국어로 응답). Commit messages are in English.
"""


def build_execute_prompt(job: Job, repo_dir: Path, work_branch: str, plan: str) -> str:
    """Sonnet용 실행 프롬프트: 에러 요약 + Opus 플랜"""
    return "\n".join([
        "## Error Summary",
        "",
        f"**Title**: {job.title}",
        f"**Subtitle**: {job.subtitle or ''}",
        f"**File**: `{job.filename or 'unknown'}` line {job.lineno or '?'}",
        f"**Exception**: {job.exception_type}: {job.message or ''}",
        "",
        "## Fix Plan (from senior engineer)",
        "",
        plan,
        "",
        "## Workspace",
        f"- Repository root: `{repo_dir}`",
        f"- Branch: `{work_branch}` (already checked out)",
        "",
        "Implement the fix plan above and commit your changes.",
    ])
