"""테스트용 에러 엔드포인트 - Sentry 캡처 확인용"""

from sqlalchemy import func, select, text

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
    result = numerator / denominator  # ZeroDivisionError
    return {"result": result}


@router.get("/value-error")
async def trigger_value_error():
    """ValueError - 잘못된 타입 변환"""
    user_input = "not-a-number"
    user_id = int(user_input)  # ValueError: invalid literal for int()
    return {"user_id": user_id}


@router.get("/n-plus-one")
async def trigger_n_plus_one():
    """SQLAlchemy N+1 쿼리 문제

    projects 목록을 1번 조회한 뒤,
    각 project마다 별도 쿼리로 job을 조회하는 전형적인 N+1 패턴.
    """
    session = db_session.get()

    # 단일 쿼리: LEFT JOIN으로 프로젝트별 job 수를 한 번에 조회
    stmt = (
        select(
            ProjectModel.id,
            func.count(JobModel.id).label("job_count"),
        )
        .outerjoin(
            JobModel,
            ProjectModel.source_project_id == JobModel.source_project_id,
        )
        .group_by(ProjectModel.id)
    )
    result = await session.execute(stmt)
    rows = result.all()

    project_jobs = [
        {"project_id": row.id, "job_count": row.job_count}
        for row in rows
    ]

    return {"project_jobs": project_jobs}


@router.get("/key-error")
async def trigger_key_error():
    """KeyError - 존재하지 않는 딕셔너리 키 접근"""
    config = {
        "host": "localhost",
        "port": 5432,
    }
    # 설정에 없는 키에 접근
    db_password = config["password"]  # KeyError: 'password'
    return {"password": db_password}
