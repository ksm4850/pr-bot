from fastapi import APIRouter, HTTPException

from app.services.worker_manager import worker_manager

router = APIRouter()


@router.get("/status")
async def get_status() -> dict:
    """Worker 상태 조회"""
    return worker_manager.status()


@router.post("/start", status_code=200)
async def start_worker() -> dict:
    """Worker 시작"""
    try:
        await worker_manager.start()
        return {"ok": True, "status": "started"}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/stop", status_code=200)
async def stop_worker(timeout: float = 30.0) -> dict:
    """Worker 중지 (graceful, 최대 timeout초 대기)"""
    try:
        await worker_manager.stop(timeout=timeout)
        return {"ok": True, "status": "stopped"}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
