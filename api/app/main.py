from __future__ import annotations

from typing import Dict

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.app.config import settings
from api.app.routes.ai_tasks import router as ai_tasks_router
from api.app.routes.career_brain import router as career_brain_router
from api.app.routes.health import router as health_router
from api.app.routes.jobs import router as jobs_router
from api.app.routes.masters import router as masters_router
from api.app.routes.tailored_examples import router as tailored_examples_router
from api.app.routes.tailoring import router as tailoring_router
from api.app.schemas.common import ErrorResponse

app = FastAPI(title="ApplAI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    payload = ErrorResponse(detail=str(exc), code="value_error").model_dump()
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload)


@app.get("/", response_model=Dict[str, str], tags=["meta"])
def root() -> Dict[str, str]:
    return {"name": "ApplAI API", "docs": "/docs"}


from fastapi.staticfiles import StaticFiles

# Health router exposes GET /health (see api.app.routes.health).
app.include_router(health_router)
app.include_router(masters_router)
app.include_router(tailoring_router)
app.include_router(jobs_router)
app.include_router(career_brain_router)
app.include_router(tailored_examples_router)
app.include_router(ai_tasks_router)

app.mount("/static-docs", StaticFiles(directory="docs"), name="static-docs")
