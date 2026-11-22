from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, conint, conlist

from app.modules.m8_resume import service
from app.pipeline import plan_batch
from app.source import inputs

router = APIRouter(prefix="/api", tags=["续裁确认"])
Kerf = conint(strict=True, ge=1, le=20)
Cut = conint(strict=True, ge=1)


class CutReceipt(BaseModel):
    receipt_id: str
    roll: str
    cuts: conlist(Cut, min_length=1, max_length=200)


@router.get("/resume")
def preview(request: Request, sample: str = "dirty", kerf_mm: Kerf = 5):
    """未归档时按样例即席生成续裁确认单（第 0 版，不落库）。"""
    files = inputs(request.app.state.settings.samples, sample)
    return service.preview(plan_batch(files, kerf_mm))


@router.get("/resume/{run_id}")
def current(run_id: str, request: Request):
    return service.sheet(request.app.state.archive, run_id)


@router.get("/resume/{run_id}/history")
def history(run_id: str, request: Request):
    return service.history(request.app.state.archive, run_id)


@router.get("/resume/{run_id}/versions/{number}")
def version(run_id: str, number: int, request: Request):
    return service.version(request.app.state.archive, run_id, number)


@router.post("/resume/{run_id}/receipts", status_code=201)
def record(run_id: str, payload: CutReceipt, request: Request, response: Response):
    result = service.submit(request.app.state.archive, run_id,
                            {"receipt_id": payload.receipt_id, "roll": payload.roll, "cuts": payload.cuts})
    if result["replayed"]:
        response.status_code = 200
    return result
