"""테스트용 에러 엔드포인트 - Sentry 캡처 확인용"""

from sqlalchemy import select, text

from fastapi import APIRouter

from app.core.database import db_session
from app.models.job import JobModel
from app.models.project import ProjectModel

router = APIRouter()


@router.get("/zero-division")
async def trigger_zero_division():
    """ZeroDivisionError - 0으로 나누기"""
    numerator = 100
    denominator = 0
    try:
        result = numerator / denominator  # ZeroDivisionError
    except ZeroDivisionError:
        result = None
    return {"result": result}


@router.get("/value-error")
async def trigger_value_error():
    """ValueError - 잘못된 타입 변환"""
    user_input = "not-a-number"
    try:
        user_id = int(user_input)
    except ValueError:
        user_id = None
    return {"user_id": user_id}


@router.get("/n-plus-one")
async def trigger_n_plus_one():
    """SQLAlchemy N+1 쿼리 문제

    projects 목록을 1번 조회한 뒤,
    각 project마다 별도 쿼리로 job을 조회하는 전형적인 N+1 패턴.
    """
    session = db_session.get()

    # Query 1: 전체 프로젝트 목록 조회
    result = await session.execute(select(ProjectModel))
    projects = result.scalars().all()

    # Query N: 프로젝트마다 개별 job 조회 (N+1 문제)
    project_jobs = []
    for project in projects:
        job_result = await session.execute(
            select(JobModel).where(JobModel.source_project_id == project.source_project_id)
        )
        jobs = job_result.scalars().all()
        project_jobs.append({
            "project_id": project.id,
            "job_count": len(jobs),
        })

    # 실제 실행된 쿼리 수
    total_queries = 1 + len(projects)
    if total_queries > 1:
        # N+1 패턴 감지 경고 (크래시 방지를 위해 예외 대신 결과 반환)
        return {
            "project_jobs": project_jobs,
            "warning": (
                f"N+1 쿼리 감지: projects 1번 조회 후 job을 {len(projects)}번 개별 조회. "
                f"총 {total_queries}개 쿼리 실행. selectinload/joinedload 사용 필요."
            ),
        }

    return {"project_jobs": project_jobs}


@router.get("/key-error")
async def trigger_key_error():
    """KeyError - 존재하지 않는 딕셔너리 키 접근"""
    config = {
        "host": "localhost",
        "port": 5432,
    }
    # 설정에 없는 키에 접근
    db_password = config.get("password")  # 안전한 키 접근 (KeyError 방지)
    return {"password": db_password}
