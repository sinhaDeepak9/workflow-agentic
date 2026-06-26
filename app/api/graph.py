"""Workflow graph visualisation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response

from app.container import get_container

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get(
    "/png",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
    summary="Render the workflow graph as a PNG image",
)
def graph_png(xray: bool = Query(True, description="Expand subgraph internals")):
    try:
        graph = get_container().graph.get_graph(xray=xray)
        png_bytes = graph.draw_mermaid_png()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Graph render failed: {exc}") from exc
    return Response(content=png_bytes, media_type="image/png")


@router.get(
    "/mermaid",
    response_class=PlainTextResponse,
    summary="Return the workflow graph as Mermaid diagram source",
)
def graph_mermaid(xray: bool = Query(True, description="Expand subgraph internals")):
    graph = get_container().graph.get_graph(xray=xray)
    return PlainTextResponse(content=graph.draw_mermaid(), media_type="text/plain")
