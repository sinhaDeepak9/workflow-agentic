"""Human task REST endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from app.api import serializers
from app.container import get_container
from app.models.api import (
    ClaimTaskRequest,
    CommentRequest,
    CompleteTaskRequest,
    DelegateTaskRequest,
    PatchTaskDataRequest,
    ReassignTaskRequest,
)

router = APIRouter(prefix="/api/workflows/{workflow_id}/tasks", tags=["tasks"])


@router.get("")
def list_tasks(workflow_id: str):
    c = get_container()
    return [serializers.task_view(t) for t in c.task_service.list_tasks(workflow_id)]


@router.get("/{task_id}")
def get_task(workflow_id: str, task_id: str):
    task = get_container().task_service.get_task(task_id)
    return serializers.task_view(task)


@router.post("/{task_id}/claim")
def claim_task(workflow_id: str, task_id: str, body: ClaimTaskRequest):
    task = get_container().task_service.claim_task(
        task_id, body.actor, body.expected_task_version
    )
    return serializers.task_view(task)


@router.post("/{task_id}/delegate")
def delegate_task(workflow_id: str, task_id: str, body: DelegateTaskRequest):
    task = get_container().task_service.delegate_task(
        task_id, body.actor, body.delegate_to, body.reason,
        body.expected_task_version, body.idempotency_key,
    )
    return serializers.task_view(task)


@router.post("/{task_id}/reassign")
def reassign_task(workflow_id: str, task_id: str, body: ReassignTaskRequest):
    task = get_container().task_service.reassign_task(
        task_id, body.actor, body.assign_to, body.reason, body.expected_task_version
    )
    return serializers.task_view(task)


@router.post("/{task_id}/complete")
def complete_task(workflow_id: str, task_id: str, body: CompleteTaskRequest):
    return get_container().task_service.complete_task(
        task_id, body.actor, body.expected_task_version, body.output,
        body.comment, body.idempotency_key,
    )


@router.post("/{task_id}/comments")
def comment_task(workflow_id: str, task_id: str, body: CommentRequest):
    task = get_container().task_service.add_comment(task_id, body.actor, body.text)
    return serializers.task_view(task)


@router.get("/{task_id}/data")
def get_task_data(workflow_id: str, task_id: str):
    return get_container().task_service.get_task_data(task_id)


@router.patch("/{task_id}/data")
def patch_task_data(workflow_id: str, task_id: str, body: PatchTaskDataRequest):
    task = get_container().task_service.patch_task_data(
        task_id, body.actor, body.expected_task_version, body.draft_data
    )
    return serializers.task_view(task)
