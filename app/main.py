"""FastAPI application entrypoint.

Run with:
    uvicorn app.main:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from app.api import definitions, graph, task_list, tasks, workflow_graph, workflows
from app.config.settings import get_settings
from app.container import get_container
from app.errors import WorkflowError


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = get_container()
    container.reminder_service.start()
    try:
        yield
    finally:
        container.reminder_service.stop()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)


@app.exception_handler(WorkflowError)
async def workflow_error_handler(request: Request, exc: WorkflowError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.__class__.__name__, "message": exc.message},
    )


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "workflowType": settings.workflow_type}


app.include_router(workflows.router)
app.include_router(tasks.router)
app.include_router(task_list.router)
app.include_router(definitions.router)
app.include_router(graph.router)
app.include_router(workflow_graph.router)
