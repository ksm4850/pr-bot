from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.project import Project, RepoPlatform
from app.services.project import ProjectService

router = APIRouter()
service = ProjectService()


class CreateProjectRequest(BaseModel):
    source: str              # "sentry", "cloudwatch", "datadog"
    source_project_id: str   # "4509981525278720"
    repo_url: str            # "https://github.com/org/repo"
    repo_platform: RepoPlatform


@router.post("", response_model=Project, status_code=201)
async def create_project(body: CreateProjectRequest) -> Project:
    """프로젝트 등록"""
    try:
        return await service.create(
            source=body.source,
            source_project_id=body.source_project_id,
            repo_url=body.repo_url,
            repo_platform=body.repo_platform.value,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=list[Project])
async def list_projects(source: str | None = None) -> list[Project]:
    """프로젝트 목록 조회"""
    return await service.list(source=source)


@router.get("/{source}/{source_project_id}", response_model=Project)
async def get_project(source: str, source_project_id: str) -> Project:
    """프로젝트 조회"""
    project = await service.get(source, source_project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{source}/{source_project_id}", status_code=204)
async def delete_project(source: str, source_project_id: str) -> None:
    """프로젝트 삭제"""
    deleted = await service.delete(source, source_project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")