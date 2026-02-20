"""Claude Agent 시스템/유저 프롬프트 빌더"""

import json
from pathlib import Path

from app.models.job import Job


SYSTEM_PROMPT = """\
You are an expert software engineer tasked with fixing bugs in a codebase.
You have been given information about an error that occurred in production.
Your job is to:
1. Analyze the error and stacktrace
2. Locate the root cause in the source code
3. Implement a minimal, correct fix
4. Commit the fix with a clear commit message

Rules:
- Only fix the specific bug reported. Do not refactor or improve unrelated code.
- Use the bash tool to read files, run tests, and commit changes.
- If you cannot reproduce or understand the issue after investigation, commit a comment explaining what you found.
- Always end with a git commit. The branch is already created — just commit your changes.
- Do NOT push to remote. The system will handle that.
- Commit message format: "fix: <short description>\\n\\n<details if needed>"
"""


def build_user_prompt(job: Job, repo_dir: Path, work_branch: str) -> str:
    """Job 정보로 에이전트 유저 프롬프트 생성"""
    frames_text = ""
    if job.stacktrace:
        try:
            frames = json.loads(job.stacktrace)
            lines = []
            for f in frames:
                loc = f.get("filename", "?")
                if f.get("lineno"):
                    loc += f":{f['lineno']}"
                fn = f.get("function", "")
                ctx = f.get("context_line", "").strip()
                lines.append(f"  {loc} in {fn}()" + (f"\n    > {ctx}" if ctx else ""))
            frames_text = "\n".join(lines)
        except Exception:
            frames_text = job.stacktrace

    parts = [
        f"## Error Report",
        f"",
        f"**Title**: {job.title}",
        f"**Source**: {job.source.value} (issue: {job.source_issue_id})",
        f"**Environment**: {job.environment or 'unknown'}",
        f"**Level**: {job.level or 'error'}",
        f"",
        f"**Exception**: {job.exception_type or 'Unknown'}",
        f"**Message**: {job.message or '(no message)'}",
    ]

    if job.transaction:
        parts += [f"**Endpoint**: {job.transaction}"]

    parts += [
        f"",
        f"**Error Location**:",
        f"- File: `{job.filename or 'unknown'}`",
        f"- Line: {job.lineno or 'unknown'}",
        f"- Function: `{job.function or 'unknown'}`",
    ]

    if frames_text:
        parts += [
            f"",
            f"**Stacktrace** (in-app frames only, innermost last):",
            f"```",
            frames_text,
            f"```",
        ]

    if job.source_url:
        parts += [f"", f"**Source URL**: {job.source_url}"]

    parts += [
        f"",
        f"## Workspace",
        f"- Repository: `{repo_dir}`",
        f"- Branch: `{work_branch}` (already checked out)",
        f"",
        f"Please investigate, fix the bug, and commit your changes.",
    ]

    return "\n".join(parts)
