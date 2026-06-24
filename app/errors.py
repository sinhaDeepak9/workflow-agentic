"""Shared exceptions used across services and stores."""
from __future__ import annotations


class WorkflowError(Exception):
    """Base error with an HTTP status hint."""

    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(WorkflowError):
    status_code = 404


class ConflictError(WorkflowError):
    """Optimistic-lock / stale-version violation."""

    status_code = 409


class AuthorizationError(WorkflowError):
    status_code = 403


class ValidationFailure(WorkflowError):
    status_code = 422
