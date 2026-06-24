"""Pydantic request/response models for the REST API surface."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Workflow APIs
# --------------------------------------------------------------------------- #
class StartWorkflowRequest(BaseModel):
    actor: str
    variables: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None


class PatchStateRequest(BaseModel):
    actor: str
    reason: Optional[str] = None
    expected_state_version: int = Field(..., alias="expectedStateVersion")
    updates: Dict[str, Any]

    model_config = {"populate_by_name": True}


class ResumeRequest(BaseModel):
    actor: str
    idempotency_key: Optional[str] = None


class CancelRequest(BaseModel):
    actor: str
    reason: Optional[str] = None
    idempotency_key: Optional[str] = None


# --------------------------------------------------------------------------- #
# Task APIs
# --------------------------------------------------------------------------- #
class ClaimTaskRequest(BaseModel):
    actor: str
    expected_task_version: int = Field(..., alias="expectedTaskVersion")
    model_config = {"populate_by_name": True}


class DelegateTaskRequest(BaseModel):
    actor: str
    delegate_to: str = Field(..., alias="delegateTo")
    reason: Optional[str] = None
    expected_task_version: int = Field(..., alias="expectedTaskVersion")
    idempotency_key: Optional[str] = None
    model_config = {"populate_by_name": True}


class ReassignTaskRequest(BaseModel):
    actor: str
    assign_to: str = Field(..., alias="assignTo")
    reason: Optional[str] = None
    expected_task_version: int = Field(..., alias="expectedTaskVersion")
    model_config = {"populate_by_name": True}


class CompleteTaskRequest(BaseModel):
    actor: str
    expected_task_version: int = Field(..., alias="expectedTaskVersion")
    output: Dict[str, Any]
    comment: Optional[str] = None
    idempotency_key: Optional[str] = None
    model_config = {"populate_by_name": True}


class CommentRequest(BaseModel):
    actor: str
    text: str


class PatchTaskDataRequest(BaseModel):
    actor: str
    expected_task_version: int = Field(..., alias="expectedTaskVersion")
    draft_data: Dict[str, Any] = Field(..., alias="draftData")
    model_config = {"populate_by_name": True}


# --------------------------------------------------------------------------- #
# Definition APIs
# --------------------------------------------------------------------------- #
class PublishDefinitionRequest(BaseModel):
    actor: str
    state_schema_version: int = Field(..., alias="stateSchemaVersion")
    variable_registry: List[str] = Field(..., alias="variableRegistry")
    task_schemas: Dict[str, Dict[str, Any]] = Field(..., alias="taskSchemas")
    output_promotion: Dict[str, List[str]] = Field(..., alias="outputPromotion")
    deprecated_variables: List[str] = Field(default_factory=list, alias="deprecatedVariables")
    model_config = {"populate_by_name": True}


class ValidateMigrationRequest(BaseModel):
    actor: str
    from_version: int = Field(..., alias="fromVersion")
    model_config = {"populate_by_name": True}
