from fastapi import APIRouter, HTTPException, Query

from app.models.job import Job, JobStatus, JobTask
from app.services.job_queue import JobService

router = APIRouter()
service = JobService()


@router.get("", response_model=list[Job])
async def list_jobs(
    status: JobStatus | None = Query(None, description="상태 필터 (pending/processing/done/failed)"),
    page: int = Query(1, ge=1, description="페이지 번호 (1부터)"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 항목 수"),
) -> list[Job]:
    """Job 목록 조회 (페이징 + 상태 필터)"""
    offset = (page - 1) * limit
    return await service.list_jobs(status=status, offset=offset, limit=limit)


@router.get("/{job_id}", response_model=Job)
async def get_job(job_id: str) -> Job:
    """Job 단건 조회"""
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/tasks", response_model=list[JobTask])
async def list_job_tasks(job_id: str) -> list[JobTask]:
    """Job 에이전트 작업 히스토리 조회"""
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return await service.list_tasks(job_id)
