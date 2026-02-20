from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from app.models.job import ErrorSource
from app.services.job_queue import JobService
from app.services.parsers import get_parser

router = APIRouter()
job_service = JobService()


def print_parsed_error(parsed) -> None:
    """파싱된 에러 정보를 읽기 쉽게 출력"""
    print("\n" + "=" * 70)
    print("📥 SENTRY WEBHOOK PARSED")
    print("=" * 70)

    print(f"\n🔑 식별 정보:")
    print(f"   issue_id     : {parsed.source_issue_id}")
    print(f"   environment  : {parsed.environment}  ← 깃 브랜치 결정")

    print(f"\n❌ 예외 정보:")
    print(f"   type         : {parsed.exception_type}")
    print(f"   message      : {parsed.message}")

    print(f"\n📍 에러 위치 (in_app=True):")
    print(f"   filename     : {parsed.filename}")
    print(f"   lineno       : {parsed.lineno}")
    print(f"   function     : {parsed.function}")

    print(f"\n📝 코드 컨텍스트:")
    if parsed.frames:
        last_frame = parsed.frames[-1]
        if last_frame.pre_context:
            for line in last_frame.pre_context:
                print(f"       {line}")
        if last_frame.context_line:
            print(f"   >>> {last_frame.context_line}  ← 에러 발생 라인")
        if last_frame.post_context:
            for line in last_frame.post_context:
                print(f"       {line}")
    else:
        print("   (컨텍스트 없음)")

    print(f"\n🔗 추가 정보:")
    print(f"   transaction  : {parsed.transaction}")
    print(f"   sentry_url   : {parsed.source_url}")
    print(f"   level        : {parsed.level}")

    print(f"\n📚 스택트레이스 (in_app만, {len(parsed.frames)}개):")
    for i, frame in enumerate(parsed.frames):
        print(f"   [{i}] {frame.filename}:{frame.lineno} in {frame.function}")

    print("\n" + "=" * 70 + "\n")


@router.post("/sentry")
async def sentry_webhook(request: Request) -> dict:
    """Sentry webhook endpoint → Job 생성"""
    payload = await request.json()

    parser = get_parser(ErrorSource.SENTRY)
    try:
        parsed = parser.parse(payload)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 파싱 결과 출력
    print_parsed_error(parsed)

    # 중복 체크
    if await job_service.job_exists(parsed.source, parsed.source_issue_id):
        print(f"⚠️  Duplicate issue: {parsed.source_issue_id}")
        return {
            "status": "duplicate",
            "source": parsed.source.value,
            "issue_id": parsed.source_issue_id,
        }

    # Job 생성
    job_id = await job_service.create_job(parsed)
    print(f"✅ Job created: {job_id}")

    return {
        "status": "created",
        "job_id": job_id,
        "source": parsed.source.value,
        "issue_id": parsed.source_issue_id,
        "title": parsed.title,
    }
