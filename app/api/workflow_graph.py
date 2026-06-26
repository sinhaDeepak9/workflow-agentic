"""Workflow-instance graph visualisation endpoint.

Returns the LangGraph workflow diagram for a specific workflow instance with
nodes coloured by execution state:
  - completed  : green  (#10B981) — node has already executed
  - active     : amber  (#F59E0B) — node is currently running / waiting
  - pending    : grey   (#E5E7EB) — node has not yet executed
"""
from __future__ import annotations

import re
from typing import Set, Tuple

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response
from langchain_core.runnables.graph_mermaid import draw_mermaid_png

from app.container import get_container
from app.models.enums import WorkflowStatus

router = APIRouter(prefix="/api/workflows", tags=["workflow-graph"])

# ── colour palette ────────────────────────────────────────────────────────── #
_STYLE_COMPLETED = "fill:#10B981,stroke:#059669,color:#ffffff,line-height:1.2"
_STYLE_ACTIVE = (
    "fill:#F59E0B,stroke:#D97706,color:#ffffff,stroke-width:3px,line-height:1.2"
)
_STYLE_PENDING = "fill:#E5E7EB,stroke:#9CA3AF,color:#374151,line-height:1.2"

# Pattern matches the three default classDef lines the LangGraph mermaid
# renderer always emits so we can replace them with our custom palette.
_CLASSDEF_RE = re.compile(
    r"\tclassDef default [^\n]+\n\tclassDef first [^\n]+\n\tclassDef last [^\n]+"
)
_REPLACEMENT_CLASSDEFS = (
    f"\tclassDef default {_STYLE_PENDING}\n"
    f"\tclassDef first fill-opacity:0\n"
    f"\tclassDef last fill:#bfb6fc\n"
    f"\tclassDef completed {_STYLE_COMPLETED}\n"
    f"\tclassDef active {_STYLE_ACTIVE}"
)


# ── helpers ───────────────────────────────────────────────────────────────── #

def _resolve_node_states(workflow_id: str) -> Tuple[Set[str], Set[str]]:
    """Return (completed_nodes, active_nodes) for the given workflow instance.

    Completed nodes are collected from the LangGraph state history — every
    write recorded in metadata["writes"] represents a node that has finished.
    The current node is stripped from the completed set and placed in active
    instead so it renders in amber while it is still being worked on.
    """
    container = get_container()
    instance = container.instance_store.get(workflow_id)
    config = {"configurable": {"thread_id": workflow_id}}

    completed: Set[str] = set()
    for snapshot in container.graph.get_state_history(config):
        for node_name in (snapshot.metadata.get("writes") or {}):
            if node_name != "__start__":
                completed.add(node_name)

    # Current node is still in progress — move it to active.
    active: Set[str] = set()
    current = instance.current_node
    if current:
        completed.discard(current)
        active.add(current)

    # For a fully completed workflow every executed node stays green;
    # there is no "active" node because the graph has run to __end__.
    if instance.status == WorkflowStatus.COMPLETED:
        active.clear()

    return completed, active


def _build_colored_mermaid(workflow_id: str, xray: bool) -> str:
    """Build a Mermaid diagram string with per-state node colouring."""
    container = get_container()
    completed, active = _resolve_node_states(workflow_id)

    base = container.graph.get_graph(xray=xray).draw_mermaid()

    # Swap out the three default classDef lines for our custom palette.
    diagram = _CLASSDEF_RE.sub(_REPLACEMENT_CLASSDEFS, base)

    # Append class-assignment statements at the end of the diagram.
    assignments: list[str] = []
    if completed:
        assignments.append(f"\tclass {','.join(sorted(completed))} completed;")
    if active:
        assignments.append(f"\tclass {','.join(sorted(active))} active;")

    if assignments:
        diagram = diagram.rstrip("\n") + "\n" + "\n".join(assignments) + "\n"

    return diagram


# ── endpoints ─────────────────────────────────────────────────────────────── #

@router.get(
    "/{workflow_id}/graph/png",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
    summary="Workflow graph PNG with node colouring by execution state",
    description=(
        "Renders the workflow graph for a specific instance.\n\n"
        "**Node colours**\n"
        "- 🟢 **Green** — node has completed execution\n"
        "- 🟡 **Amber** — node is currently active / waiting for human input\n"
        "- ⬜ **Grey** — node has not yet executed\n\n"
        "Use `?xray=true` (default) to expand subgraph internals."
    ),
)
def workflow_graph_png(
    workflow_id: str,
    xray: bool = Query(True, description="Expand subgraph internals"),
):
    try:
        diagram = _build_colored_mermaid(workflow_id, xray)
        png_bytes = draw_mermaid_png(diagram)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Graph render failed: {exc}") from exc
    return Response(content=png_bytes, media_type="image/png")


@router.get(
    "/{workflow_id}/graph/mermaid",
    response_class=PlainTextResponse,
    summary="Workflow graph Mermaid source with node colouring by execution state",
)
def workflow_graph_mermaid(
    workflow_id: str,
    xray: bool = Query(True, description="Expand subgraph internals"),
):
    diagram = _build_colored_mermaid(workflow_id, xray)
    return PlainTextResponse(content=diagram, media_type="text/plain")
