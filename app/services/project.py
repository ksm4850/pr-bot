from app.models.project import Project, ProjectModel, RepoPlatform
from app.repositories.project import ProjectRepository


class ProjectService:
    def __init__(self, repo: ProjectRepository | None = None):
        self.repo = repo or ProjectRepository()

    async def create(
        self,
        source: str,
        source_project_id: str,
        repo_url: str,
        repo_platform: RepoPlatform,
    ) -> Project:
        db_project = await self.repo.create(
            source=source,
            source_project_id=source_project_id,
            repo_url=repo_url,
            repo_platform=repo_platform.value,
        )
        return Project.from_orm(db_project)

    async def get(self, source: str, source_project_id: str) -> Project | None:
        db_project = await self.repo.get(source, source_project_id)
        return Project.from_orm(db_project) if db_project else None

    async def list(self, source: str | None = None) -> list[Project]:
        db_projects = await self.repo.list(source=source)
        return [Project.from_orm(p) for p in db_projects]

    async def delete(self, source: str, source_project_id: str) -> bool:
        return await self.repo.delete(source, source_project_id)
