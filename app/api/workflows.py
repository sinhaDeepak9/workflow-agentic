"""Workflow REST endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query

from app.api import serializers
from app.container import get_container
from app.models.api import (
    CancelRequest,
    PatchStateRequest,
    ResumeRequest,
    StartWorkflowRequest,
)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get(
    "",
    summary="List all workflow instances",
    description=(
        "Returns a paginated list of workflow instances with optional filters.\n\n"
        "**Filters**\n"
        "- `status` — one or more: `RUNNING`, `WAITING_ON_HUMAN_TASK`, `COMPLETED`, `FAILED`, `CANCELLED`\n"
        "- `workflow_type` — case-insensitive exact match on workflow type name\n"
        "- `current_node` — exact match on the node the workflow is currently at\n"
        "- `definition_version` — pin to a specific definition version\n"
        "- `owner` — substring match across `targetUser`, `reviewer`, `supervisor`, `reportOwners`\n"
        "- `created_after` / `created_before` — Unix epoch float bounds on `created_at`\n\n"
        "Results are sorted by `created_at` descending (newest first)."
    ),
)
def list_workflows(
    status: Optional[List[str]] = Query(
        None,
        description="Filter by one or more workflow statuses",
        example=["RUNNING", "WAITING_ON_HUMAN_TASK"],
    ),
    workflow_type: Optional[str] = Query(None, description="Case-insensitive workflow type name"),
    current_node: Optional[str] = Query(None, description="Node the workflow is currently paused at"),
    definition_version: Optional[int] = Query(None, description="Workflow definition version"),
    owner: Optional[str] = Query(
        None, description="Substring match across targetUser, reviewer, supervisor, reportOwners"
    ),
    created_after: Optional[float] = Query(None, description="Unix epoch — return instances created after this time"),
    created_before: Optional[float] = Query(None, description="Unix epoch — return instances created before this time"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=200, alias="pageSize", description="Items per page"),
):
    c = get_container()
    result = c.workflow_service.list_workflows(
        status=status,
        workflow_type=workflow_type,
        current_node=current_node,
        definition_version=definition_version,
        owner=owner,
        created_after=created_after,
        created_before=created_before,
        page=page,
        page_size=page_size,
    )
    return {
        "total": result["total"],
        "page": result["page"],
        "pageSize": result["pageSize"],
        "items": [serializers.workflow_summary(i) for i in result["items"]],
    }


@router.post("")
def start_workflow(body: StartWorkflowRequest):
    c = get_container()
    instance = c.workflow_service.start_workflow(
        actor=body.actor, variables=body.variables, idempotency_key=body.idempotency_key
    )
    return serializers.workflow_summary(instance)


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str):
    instance = get_container().instance_store.get(workflow_id)
    return serializers.workflow_summary(instance)


@router.get("/{workflow_id}/state")
def get_workflow_state(workflow_id: str):
    instance = get_container().instance_store.get(workflow_id)
    return serializers.workflow_state(instance)


@router.patch("/{workflow_id}/state")
def patch_workflow_state(workflow_id: str, body: PatchStateRequest):
    c = get_container()
    instance = c.workflow_service.patch_state(
        workflow_id=workflow_id,
        actor=body.actor,
        expected_state_version=body.expected_state_version,
        updates=body.updates,
        reason=body.reason,
    )
    return serializers.workflow_state(instance)


@router.post("/{workflow_id}/resume")
def resume_workflow(workflow_id: str, body: ResumeRequest):
    c = get_container()
    instance = c.workflow_service.resume_workflow(
        workflow_id=workflow_id, actor=body.actor, idempotency_key=body.idempotency_key
    )
    return serializers.workflow_summary(instance)


@router.post("/{workflow_id}/cancel")
def cancel_workflow(workflow_id: str, body: CancelRequest):
    c = get_container()
    instance = c.workflow_service.cancel_workflow(
        workflow_id=workflow_id, actor=body.actor, reason=body.reason,
        idempotency_key=body.idempotency_key,
    )
    return serializers.workflow_summary(instance)


@router.get("/{workflow_id}/audit")
def get_audit(workflow_id: str):
    c = get_container()
    c.instance_store.get(workflow_id)
    return [serializers.audit_view(e) for e in c.audit_service.history(workflow_id)]


@router.get("/{workflow_id}/events")
def get_events(workflow_id: str):
    # Same backing store as audit for this scaffold.
    return get_audit(workflow_id)
