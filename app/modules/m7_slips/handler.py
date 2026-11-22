from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, conint

from app.manifest import canonical
from app.modules.m7_slips.archiving import replay, submit

router = APIRouter(prefix="/api", tags=["裁床签条"])


class RunRequest(BaseModel):
    sample: str = "dirty"
    kerf_mm: conint(strict=True, ge=1, le=20) = 5


@router.post("/runs", status_code=201)
def create(payload: RunRequest, request: Request, response: Response):
    manifest, reused = submit(request.app.state.archive, request.app.state.settings.samples, payload.sample, payload.kerf_mm)
    if reused:
        response.status_code = 200
    return {"manifest": manifest, "reused": reused}


@router.get("/runs")
def recent(request: Request):
    return {"runs": request.app.state.archive.recent()}


@router.get("/runs/{run_id}")
def archived(run_id: str, request: Request):
    return request.app.state.archive.read(run_id)


@router.post("/runs/{run_id}/rerun")
def rerun(run_id: str, request: Request):
    manifest = replay(request.app.state.archive, request.app.state.settings.samples, run_id)
    return {"manifest": manifest, "verified": True}


@router.get("/export/{run_id}")
def download(run_id: str, request: Request):
    document = request.app.state.archive.read(run_id)
    return Response(canonical(document) + "\n", media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="fabric-{run_id[:12]}.json"'})
