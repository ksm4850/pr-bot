import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.project import ProjectModel
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository):
    async def create(
        self,
        source: str,
        source_project_id: str,
        repo_url: str,
        repo_platform: str,
    ) -> ProjectModel:
        now = datetime.now(UTC)
        db_project = ProjectModel(
            id=str(uuid.uuid4()),
            source=source,
            source_project_id=source_project_id,
            repo_url=repo_url,
            repo_platform=repo_platform,
            created_at=now,
            updated_at=now,
        )
        self.session.add(db_project)
        try:
            await self.session.flush()
        except IntegrityError:
            raise ValueError(
                f"Already exists: source={source}, project_id={source_project_id}"
            )
        return db_project

    async def get(self, source: str, source_project_id: str) -> ProjectModel | None:
        result = await self.session.execute(
            select(ProjectModel).where(
                ProjectModel.source == source,
                ProjectModel.source_project_id == source_project_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(self, source: str | None = None) -> list[ProjectModel]:
        query = select(ProjectModel).order_by(ProjectModel.created_at.desc())
        if source:
            query = query.where(ProjectModel.source == source)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete(self, source: str, source_project_id: str) -> bool:
        db_project = await self.get(source, source_project_id)
        if not db_project:
            return False
        await self.session.delete(db_project)
        await self.session.flush()
        return True
