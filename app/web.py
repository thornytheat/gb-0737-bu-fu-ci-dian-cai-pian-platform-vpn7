from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import ROOT, SAMPLES, VERSION

router = APIRouter()
templates = Jinja2Templates(directory=ROOT / "app/templates")
MODULES = (("intake", "验布采信"), ("locate", "疵点定位"), ("zones", "禁切区间"), ("fit", "裁片配长"),
           ("changeovers", "换卷核算"), ("ledger", "用布勾稽"), ("slips", "裁床签条"))


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "folio.html", {"samples": SAMPLES, "modules": MODULES, "version": VERSION})


@router.get("/api/health")
def health():
    return {"ready": True, "rules": VERSION}
