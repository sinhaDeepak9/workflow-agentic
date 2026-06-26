"""Global task listing endpoint (cross-workflow, filterable, paginated)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query

from app.api import serializers
from app.container import get_container

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get(
    "",
    summary="List all tasks across all workflows",
    description=(
        "Returns a paginated list of task records across every workflow instance.\n\n"
        "**Filters**\n"
        "- `workflow_id` — restrict to a single workflow\n"
        "- `status` — one or more: `PENDING`, `IN_PROGRESS`, `DELEGATED`, `COMPLETED`, `CANCELLED`, `ESCALATED`\n"
        "- `task_type` — e.g. `report_submission_review`, `supervisor_review`\n"
        "- `assignee` — substring match on `assignee` field\n"
        "- `effective_assignee` — substring match on effective assignee (resolves delegation)\n"
        "- `candidate_group` — substring match against any of the task's candidate groups\n"
        "- `due_before` / `due_after` — ISO date string bounds (YYYY-MM-DD) on `due_date`\n"
        "- `created_after` / `created_before` — Unix epoch float bounds on `created_at`\n\n"
        "Results are sorted by `created_at` descending (newest first)."
    ),
)
def list_all_tasks(
    workflow_id: Optional[str] = Query(None, alias="workflowId", description="Restrict to a single workflow"),
    status: Optional[List[str]] = Query(
        None,
        description="One or more task statuses",
        example=["PENDING", "IN_PROGRESS"],
    ),
    task_type: Optional[str] = Query(None, alias="taskType", description="Task type name"),
    assignee: Optional[str] = Query(None, description="Substring match on assignee"),
    effective_assignee: Optional[str] = Query(
        None, alias="effectiveAssignee", description="Substring match on effective assignee (resolves delegation)"
    ),
    candidate_group: Optional[str] = Query(
        None, alias="candidateGroup", description="Substring match on candidate groups"
    ),
    due_before: Optional[str] = Query(
        None, alias="dueBefore", description="ISO date (YYYY-MM-DD) — tasks due on or before this date"
    ),
    due_after: Optional[str] = Query(
        None, alias="dueAfter", description="ISO date (YYYY-MM-DD) — tasks due on or after this date"
    ),
    created_after: Optional[float] = Query(
        None, alias="createdAfter", description="Unix epoch — return tasks created after this time"
    ),
    created_before: Optional[float] = Query(
        None, alias="createdBefore", description="Unix epoch — return tasks created before this time"
    ),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=200, alias="pageSize", description="Items per page"),
):
    c = get_container()
    result = c.task_service.list_all_tasks(
        workflow_id=workflow_id,
        status=status,
        task_type=task_type,
        assignee=assignee,
        effective_assignee=effective_assignee,
        candidate_group=candidate_group,
        due_before=due_before,
        due_after=due_after,
        created_after=created_after,
        created_before=created_before,
        page=page,
        page_size=page_size,
    )
    return {
        "total": result["total"],
        "page": result["page"],
        "pageSize": result["pageSize"],
        "items": [serializers.task_view(t) for t in result["items"]],
    }
