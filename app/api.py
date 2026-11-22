from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.pipeline import plan_batch
from app.source import inputs

router = APIRouter(prefix="/api")
Kerf = Annotated[int, Query(ge=1, le=20)]


def get_stage(request, stage, sample, kerf, run_id):
    if run_id is not None:
        document = request.app.state.archive.read(run_id)
        return {"run_id": run_id, "data": document["snapshot"][stage]}
    files = inputs(request.app.state.settings.samples, sample)
    return {"run_id": None, "data": plan_batch(files, kerf, stage)[stage]}


@router.get("/intake", tags=["验布采信"])
def intake(request: Request, sample: str = "dirty", kerf_mm: Kerf = 5, run_id: str | None = None):
    return get_stage(request, "intake", sample, kerf_mm, run_id)


@router.get("/locate", tags=["疵点定位"])
def locate(request: Request, sample: str = "dirty", kerf_mm: Kerf = 5, run_id: str | None = None):
    return get_stage(request, "locate", sample, kerf_mm, run_id)


@router.get("/zones", tags=["禁切区间"])
def zones(request: Request, sample: str = "dirty", kerf_mm: Kerf = 5, run_id: str | None = None):
    return get_stage(request, "zones", sample, kerf_mm, run_id)


@router.get("/fit", tags=["裁片配长"])
def fit(request: Request, sample: str = "dirty", kerf_mm: Kerf = 5, run_id: str | None = None):
    return get_stage(request, "fit", sample, kerf_mm, run_id)


@router.get("/changeovers", tags=["换卷核算"])
def changeovers(request: Request, sample: str = "dirty", kerf_mm: Kerf = 5, run_id: str | None = None):
    return get_stage(request, "changeovers", sample, kerf_mm, run_id)


@router.get("/ledger", tags=["用布勾稽"])
def ledger(request: Request, sample: str = "dirty", kerf_mm: Kerf = 5, run_id: str | None = None):
    return get_stage(request, "ledger", sample, kerf_mm, run_id)


@router.get("/slips", tags=["裁床签条"])
def slips(request: Request, sample: str = "dirty", kerf_mm: Kerf = 5, run_id: str | None = None):
    return get_stage(request, "slips", sample, kerf_mm, run_id)


@router.get("/preview", tags=["工作台"])
def preview(request: Request, sample: str = "dirty", kerf_mm: Kerf = 5):
    files = inputs(request.app.state.settings.samples, sample)
    return {"manifest": None, "snapshot": plan_batch(files, kerf_mm)}
