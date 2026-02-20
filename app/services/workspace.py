"""Git 워크스페이스 관리 - 레포별 캐싱"""

import asyncio
import re
from pathlib import Path

from app.core.config import settings
from app.models.project import RepoPlatform


class WorkspaceService:
    """레포별 git 워크스페이스 관리.

    - repo_url → 로컬 디렉토리 매핑 캐시 유지
    - 첫 사용 시 clone, 이후 pull
    - github_token/gitlab_token 자동 주입
    """

    def __init__(self):
        self._cache: dict[str, Path] = {}  # repo_url → cloned path

    def _repo_dir(self, repo_url: str) -> Path:
        safe_name = re.sub(r"[^\w.-]", "_", repo_url.split("://")[-1])
        return settings.workspace_dir / safe_name

    def _authenticated_url(self, repo_url: str, platform: str) -> str:
        """토큰을 URL에 삽입 (https://token@host/...)"""
        if platform == RepoPlatform.GITHUB.value and settings.github_token:
            return repo_url.replace("https://", f"https://oauth2:{settings.github_token}@")
        if platform == RepoPlatform.GITLAB.value and settings.gitlab_token:
            return repo_url.replace("https://", f"https://oauth2:{settings.gitlab_token}@")
        return repo_url

    async def prepare(self, repo_url: str, platform: str) -> Path:
        """레포 clone 또는 pull 후 워크스페이스 경로 반환"""
        repo_dir = self._repo_dir(repo_url)
        auth_url = self._authenticated_url(repo_url, platform)

        if repo_url in self._cache and repo_dir.exists():
            await self._run(["git", "-C", str(repo_dir), "fetch", "--all", "--prune"])
        else:
            settings.workspace_dir.mkdir(parents=True, exist_ok=True)
            await self._run(["git", "clone", auth_url, str(repo_dir)])
            self._cache[repo_url] = repo_dir

        return repo_dir

    async def get_default_branch(self, repo_dir: Path) -> str:
        """원격 기본 브랜치 이름 조회"""
        output = await self._run(["git", "-C", str(repo_dir), "remote", "show", "origin"])
        for line in output.splitlines():
            if "HEAD branch:" in line:
                return line.split("HEAD branch:")[-1].strip()
        return "main"

    async def create_work_branch(
        self,
        repo_dir: Path,
        base_branch: str,
        work_branch: str,
    ) -> None:
        """base 브랜치 기준으로 work 브랜치 생성 후 체크아웃"""
        await self._run([
            "git", "-C", str(repo_dir),
            "checkout", "-B", work_branch, f"origin/{base_branch}",
        ])

    async def commit_all(self, repo_dir: Path, message: str) -> str | None:
        """변경사항 전체 커밋. 변경 없으면 None 반환"""
        status = await self._run(["git", "-C", str(repo_dir), "status", "--porcelain"])
        if not status.strip():
            return None
        await self._run(["git", "-C", str(repo_dir), "add", "-A"])
        await self._run(["git", "-C", str(repo_dir), "commit", "-m", message])
        result = await self._run(["git", "-C", str(repo_dir), "rev-parse", "HEAD"])
        return result.strip()

    async def push_branch(self, repo_dir: Path, work_branch: str) -> None:
        """work 브랜치를 원격으로 push"""
        await self._run([
            "git", "-C", str(repo_dir),
            "push", "origin", work_branch, "--force-with-lease",
        ])

    async def _run(self, cmd: list[str]) -> str:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"Git command failed: {' '.join(cmd)}\n{stderr.decode().strip()}"
            )
        return stdout.decode()
