"""Minimal actor-based authorization (RBAC) per claude.md guidance."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.errors import AuthorizationError
from app.models.domain import TaskRecord

if TYPE_CHECKING:
    from app.container import Container


class Authorizer:
    def __init__(self, container: "Container") -> None:
        self._c = container

    @property
    def _enabled(self) -> bool:
        return self._c.settings.auth_enabled

    def is_admin(self, actor: str) -> bool:
        return actor in self._c.settings.admin_user_set

    def _deny(self, message: str) -> None:
        raise AuthorizationError(message)

    # -- workflow ---------------------------------------------------------- #
    def require_patch_state(self, actor: str) -> None:
        if self._enabled and not self.is_admin(actor):
            self._deny(f"{actor} may not patch workflow state")

    def require_cancel(self, actor: str) -> None:
        if self._enabled and not self.is_admin(actor):
            self._deny(f"{actor} may not cancel the workflow")

    # -- tasks ------------------------------------------------------------- #
    def require_claim(self, actor: str, task: TaskRecord) -> None:
        if not self._enabled or self.is_admin(actor):
            return
        if task.assignee and task.assignee != actor:
            self._deny(f"{actor} may not claim a task assigned to {task.assignee}")
        if task.candidate_users and actor not in task.candidate_users:
            self._deny(f"{actor} is not a candidate user for this task")

    def require_complete(self, actor: str, task: TaskRecord) -> None:
        if not self._enabled or self.is_admin(actor):
            return
        if actor != task.effective_assignee:
            self._deny(f"{actor} is not the effective assignee for this task")

    def require_delegate(self, actor: str, task: TaskRecord) -> None:
        if not self._enabled or self.is_admin(actor):
            return
        if actor != task.effective_assignee:
            self._deny(f"{actor} may not delegate this task")

    def require_reassign(self, actor: str) -> None:
        if self._enabled and not self.is_admin(actor):
            self._deny(f"{actor} may not administratively reassign tasks")

    # -- definitions ------------------------------------------------------- #
    def require_publish_definition(self, actor: str) -> None:
        if self._enabled and not self.is_admin(actor):
            self._deny(f"{actor} may not publish workflow definitions")

    def require_validate_migration(self, actor: str) -> None:
        if self._enabled and not self.is_admin(actor):
            self._deny(f"{actor} may not validate migrations")
