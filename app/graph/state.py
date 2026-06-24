"""LangGraph state schema for the HawaiReportApproval workflow.

All process-level variables (Read.md) plus control fields are declared as
channels so nodes may return updates for them.
"""
from __future__ import annotations

from typing import Any, List, Optional, TypedDict


class GraphState(TypedDict, total=False):
    # Process-level variables
    reportType: str
    instanceDescription: str
    reportOwners: List[str]
    targetUser: str
    mqdUser: str
    healthPlanName: str
    reportingPeriod: str
    dueDate: str
    reviewer: str
    supervisor: str
    isEscalated: Optional[bool]
    isApproved: Optional[bool]
    mcoEmail: str
    mcoUser: str
    slaDate: str
    reminder1: str
    reminder2: str
    userList: List[str]
    decision: Optional[str]
    slaSuper: str
    resubmissionRequiredBy: Optional[str]
    processActivationTime: float
    internalSubmissionId: str
    slaDays: int
    notification: str

    # Control fields
    current_node: Optional[str]
    current_task_id: Optional[str]


CONTROL_KEYS = {"current_node", "current_task_id"}
