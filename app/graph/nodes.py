"""Graph nodes and routing functions.

Deterministic business logic. Human-task nodes follow the pause/resume pattern
from claude.md: create task -> mark waiting -> interrupt -> (on resume) promote
mapped output fields into workflow state.
"""
from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from langgraph.types import interrupt

from app.graph.state import GraphState
from app.models.enums import TaskType

if TYPE_CHECKING:
    from app.container import Container


def _workflow_id(config) -> str:
    return config["configurable"]["thread_id"]


def build_nodes(container: "Container") -> Dict[str, Callable]:
    """Return the node callables bound to the given container."""

    # -- deterministic setup nodes ------------------------------------------- #
    def initialize_submission(state: "GraphState", config) -> dict:
        now = time.time()
        sla_days = state.get("slaDays", 14)
        return {
            "internalSubmissionId": f"sub_{uuid.uuid4().hex[:10]}",
            "processActivationTime": now,
            "slaDays": sla_days,
            "dueDate": _add_days(now, sla_days),
            "slaDate": _add_days(now, sla_days),
            "isEscalated": state.get("isEscalated"),
            "current_node": "initialize_submission",
        }

    def get_report_owner(state: "GraphState", config) -> dict:
        owners: List[str] = state.get("reportOwners") or []
        target = state.get("targetUser") or (owners[0] if owners else "report.owner")
        return {
            "reportOwners": owners or [target],
            "targetUser": target,
            "current_node": "get_report_owner",
        }

    def setup_reviewers_and_notifications(state: "GraphState", config) -> dict:
        reviewer = state.get("reviewer") or "reviewer.user"
        user_list = sorted(
            set(
                filter(
                    None,
                    [reviewer, state.get("targetUser"), state.get("mqdUser")]
                    + (state.get("reportOwners") or []),
                )
            )
        )
        return {
            "reviewer": reviewer,
            "userList": user_list,
            "reminder1": "R/PT24H",
            "reminder2": "R/PT48H",
            "current_node": "setup_reviewers_and_notifications",
        }

    def join_setup(state: "GraphState", config) -> dict:
        return {"current_node": "join_setup"}

    def choose_supervisor(state: "GraphState", config) -> dict:
        return {
            "supervisor": state.get("supervisor") or "supervisor.user",
            "slaSuper": _add_days(time.time(), 7),
            "current_node": "choose_supervisor",
        }

    def merge_review_paths(state: "GraphState", config) -> dict:
        return {"current_node": "merge_review_paths"}

    # -- human-task node factory --------------------------------------------- #
    def human_task_node(
        node_name: str,
        task_type: TaskType,
        task_name: str,
        assignee_key: str,
        candidate_groups: List[str],
    ) -> Callable:
        def _node(state: "GraphState", config) -> dict:
            workflow_id = _workflow_id(config)
            task = container.task_service.ensure_task(
                workflow_id=workflow_id,
                node=node_name,
                task_type=task_type.value,
                task_name=task_name,
                assignee=state.get(assignee_key),
                candidate_groups=candidate_groups,
                due_date=state.get("dueDate"),
            )
            container.workflow_service.mark_waiting(workflow_id, node_name, task.task_id)

            # Pause until the task is completed via the API (Command resume).
            output = interrupt(
                {"taskId": task.task_id, "node": node_name, "taskType": task_type.value}
            )

            promoted = container.definition_service.filter_promotion(
                workflow_id, task_type.value, output or {}
            )
            updates = dict(promoted)
            updates["current_node"] = node_name
            updates["current_task_id"] = None
            return updates

        return _node

    report_submission_review = human_task_node(
        "report_submission_review",
        TaskType.REPORT_SUBMISSION_REVIEW,
        "Report Submission Review",
        assignee_key="reviewer",
        candidate_groups=["supervisors"],
    )
    supervisor_review = human_task_node(
        "supervisor_review",
        TaskType.SUPERVISOR_REVIEW,
        "Supervisor Review",
        assignee_key="supervisor",
        candidate_groups=["supervisors"],
    )

    # -- final notification nodes -------------------------------------------- #
    def _notify(node_name: str, message: str) -> Callable:
        def _node(state: "GraphState", config) -> dict:
            return {"notification": message, "current_node": node_name}

        return _node

    return {
        "initialize_submission": initialize_submission,
        "get_report_owner": get_report_owner,
        "setup_reviewers_and_notifications": setup_reviewers_and_notifications,
        "join_setup": join_setup,
        "report_submission_review": report_submission_review,
        "choose_supervisor": choose_supervisor,
        "supervisor_review": supervisor_review,
        "merge_review_paths": merge_review_paths,
        "notify_mco_accepted": _notify("notify_mco_accepted", "MCO notified: Accepted"),
        "notify_mco_accepted_approved": _notify(
            "notify_mco_accepted_approved", "MCO notified: Accepted & Approved"
        ),
        "notify_mco_denied": _notify("notify_mco_denied", "MCO notified: Accepted & Denied"),
    }


# --------------------------------------------------------------------------- #
# Routing functions
# --------------------------------------------------------------------------- #
def route_escalation(state: "GraphState") -> str:
    return "choose_supervisor" if state.get("isEscalated") else "merge_review_paths"


def route_final_decision(state: "GraphState") -> str:
    decision: Optional[str] = state.get("decision")
    if decision == "Accepted & Approved":
        return "notify_mco_accepted_approved"
    if decision == "Accepted & Denied":
        return "notify_mco_denied"
    return "notify_mco_accepted"


def _add_days(epoch: float, days: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(epoch + days * 86400))
