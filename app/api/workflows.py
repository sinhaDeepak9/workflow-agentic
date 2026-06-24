"""Workflow REST endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from app.api import serializers
from app.container import get_container
from app.models.api import (
    CancelRequest,
    PatchStateRequest,
    ResumeRequest,
    StartWorkflowRequest,
)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


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
