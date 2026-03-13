"""Git 워크스페이스 관리 - 레포별 캐싱"""

import asyncio
import re
import subprocess
from pathlib import Path

from app.core.config import settings
from app.models.project import RepoPlatform


class WorkspaceService:
    """레포별 git 워크스페이스 관리.

    - repo_url → 로컬 디렉토리 매핑 캐시 유지
    - 첫 사용 시 clone, 이후 pull
    - 프로젝트별 토큰으로 인증
    """

    def __init__(self):
        self._cache: dict[str, Path] = {}  # repo_url → cloned path

    def _repo_dir(self, repo_url: str) -> Path:
        safe_name = re.sub(r"[^\w.-]", "_", repo_url.split("://")[-1])
        return settings.workspace_dir / safe_name

    def _authenticated_url(self, repo_url: str, platform: str, token: str | None) -> str:
        """토큰을 URL에 삽입 (https://token@host/...)"""
        if not token:
            return repo_url
        if platform == RepoPlatform.GITHUB.value:
            return repo_url.replace("https://", f"https://x-access-token:{token}@")
        if platform == RepoPlatform.GITLAB.value:
            return repo_url.replace("https://", f"https://oauth2:{token}@")
        return repo_url

    async def prepare(self, repo_url: str, platform: str, token: str | None = None) -> Path:
        """레포 clone 또는 pull 후 워크스페이스 경로 반환"""
        repo_dir = self._repo_dir(repo_url)
        auth_url = self._authenticated_url(repo_url, platform, token)

        if repo_dir.exists():
            # 토큰 변경에 대응: remote URL 갱신
            await self._run([
                "git", "-C", str(repo_dir),
                "remote", "set-url", "origin", auth_url,
            ])
            await self._run(["git", "-C", str(repo_dir), "fetch", "--all", "--prune"])
        else:
            settings.workspace_dir.mkdir(parents=True, exist_ok=True)
            await self._run(["git", "clone", auth_url, str(repo_dir)])

        # 봇 전용 커밋 author 설정
        await self._run(["git", "-C", str(repo_dir), "config", "user.name", settings.bot_git_name])
        await self._run(["git", "-C", str(repo_dir), "config", "user.email", settings.bot_git_email])

        self._cache[repo_url] = repo_dir
        return repo_dir

    async def get_default_branch(self, repo_dir: Path) -> str:
        """기본 브랜치 이름 조회 (로컬 refs 사용, 네트워크 불필요)"""
        try:
            output = await self._run([
                "git", "-C", str(repo_dir),
                "symbolic-ref", "refs/remotes/origin/HEAD",
            ])
            # "refs/remotes/origin/main" → "main"
            return output.strip().split("/")[-1]
        except RuntimeError:
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
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Git command failed: {' '.join(cmd)}\n{result.stderr.decode().strip()}"
            )
        return result.stdout.decode()
