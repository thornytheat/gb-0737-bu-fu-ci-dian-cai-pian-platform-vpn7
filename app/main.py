from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import router as stages
from app.archive import Archive
from app.config import ROOT, Settings
from app.modules.m7_slips.handler import router as runs
from app.reasons import FabricError
from app.web import router as web


def build_application(settings=None):
    settings = settings or Settings.from_env()
    archive = Archive(settings.database)

    @asynccontextmanager
    async def lifespan(app):
        archive.setup()
        yield

    app = FastAPI(title="布幅疵点裁片台", lifespan=lifespan)
    app.state.archive, app.state.settings = archive, settings

    @app.exception_handler(FabricError)
    async def reject(request: Request, error: FabricError):
        return JSONResponse({"error": error.response()}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, error: RequestValidationError):
        return JSONResponse({"error": FabricError("FORM_INVALID").response()}, status_code=422)

    app.mount("/static", StaticFiles(directory=ROOT / "app/static"), name="static")
    app.include_router(stages)
    app.include_router(runs)
    app.include_router(web)
    return app


app = build_application()
