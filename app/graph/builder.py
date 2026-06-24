"""Compile the LangGraph StateGraph with a checkpointer for pause/resume."""
from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import build_nodes, route_escalation, route_final_decision
from app.graph.state import GraphState

if TYPE_CHECKING:
    from app.container import Container


def build_graph(container: "Container"):
    nodes = build_nodes(container)
    g = StateGraph(GraphState)

    for name, fn in nodes.items():
        g.add_node(name, fn)

    g.add_edge(START, "initialize_submission")
    g.add_edge("initialize_submission", "get_report_owner")
    g.add_edge("get_report_owner", "setup_reviewers_and_notifications")
    g.add_edge("setup_reviewers_and_notifications", "join_setup")
    g.add_edge("join_setup", "report_submission_review")

    g.add_conditional_edges(
        "report_submission_review",
        route_escalation,
        {
            "choose_supervisor": "choose_supervisor",
            "merge_review_paths": "merge_review_paths",
        },
    )
    g.add_edge("choose_supervisor", "supervisor_review")
    g.add_edge("supervisor_review", "merge_review_paths")

    g.add_conditional_edges(
        "merge_review_paths",
        route_final_decision,
        {
            "notify_mco_accepted": "notify_mco_accepted",
            "notify_mco_accepted_approved": "notify_mco_accepted_approved",
            "notify_mco_denied": "notify_mco_denied",
        },
    )
    g.add_edge("notify_mco_accepted", END)
    g.add_edge("notify_mco_accepted_approved", END)
    g.add_edge("notify_mco_denied", END)

    return g.compile(checkpointer=MemorySaver())
