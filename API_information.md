
# API_information.md

## Overview

This file summarizes the REST API contract required for the LangGraph-based `HawaiReportApproval` workflow implementation.

A complete OpenAPI contract can be derived from this structure.

---

## API Groups

### 1. Workflow APIs
- get workflow summary
- get workflow state
- patch workflow state
- resume workflow
- cancel workflow
- get audit history
- get workflow events

### 2. Human Task APIs
- list tasks
- get task details/status
- claim task
- delegate task
- reassign task
- complete task
- comment on task
- get task-local data
- patch task-local data

### 3. Workflow Definition APIs
- list definition versions
- get definition version
- publish new definition version
- validate migration compatibility

---

## Workflow APIs

### GET `/api/workflows/{workflowId}`
Returns workflow execution summary.

**Response example**
```json
{
  "workflowId": "wf_456",
  "workflowType": "HawaiReportApproval",
  "definitionVersion": 7,
  "stateSchemaVersion": 7,
  "status": "WAITING_ON_HUMAN_TASK",
  "currentNode": "report_submission_review",
  "currentTaskId": "task_123"
}
```

### GET `/api/workflows/{workflowId}/state`
Reads workflow/process variables.

**Response example**
```json
{
  "workflowId": "wf_456",
  "workflowType": "HawaiReportApproval",
  "definitionVersion": 7,
  "stateSchemaVersion": 7,
  "status": "WAITING_ON_HUMAN_TASK",
  "currentNode": "report_submission_review",
  "currentTaskId": "task_123",
  "variables": {
    "reviewer": "reviewer.user",
    "decision": null,
    "isEscalated": null
  }
}
```

### PATCH `/api/workflows/{workflowId}/state`
Updates workflow/process variables.

**Request example**
```json
{
  "actor": "admin.user",
  "reason": "Reviewer changed after delegation",
  "expectedStateVersion": 15,
  "updates": {
    "reviewer": "backup.reviewer"
  }
}
```

### POST `/api/workflows/{workflowId}/resume`
Resumes a paused workflow.

### POST `/api/workflows/{workflowId}/cancel`
Cancels the workflow.

### GET `/api/workflows/{workflowId}/audit`
Returns audit history.

### GET `/api/workflows/{workflowId}/events`
Returns event stream / operational events.

---

## Human Task APIs

### GET `/api/workflows/{workflowId}/tasks`
Lists tasks for a workflow.

### GET `/api/workflows/{workflowId}/tasks/{taskId}`
Returns task status/details.

**Response example**
```json
{
  "taskId": "task_123",
  "workflowId": "wf_456",
  "taskType": "report_submission_review",
  "taskSchemaVersion": 3,
  "taskName": "Report Submission Review",
  "status": "PENDING",
  "assignee": "reviewer.user",
  "candidateUsers": ["reviewer.user"],
  "candidateGroups": ["supervisors"],
  "allowedActions": ["claim", "delegate", "complete"]
}
```

### POST `/api/workflows/{workflowId}/tasks/{taskId}/claim`
Claims a task.

**Request example**
```json
{
  "actor": "reviewer.user",
  "expectedTaskVersion": 5
}
```

### POST `/api/workflows/{workflowId}/tasks/{taskId}/delegate`
Delegates a task.

**Request example**
```json
{
  "actor": "reviewer.user",
  "delegateTo": "backup.reviewer",
  "reason": "Out of office",
  "expectedTaskVersion": 5
}
```

### POST `/api/workflows/{workflowId}/tasks/{taskId}/reassign`
Reassigns a task administratively.

### POST `/api/workflows/{workflowId}/tasks/{taskId}/complete`
Completes a task and promotes mapped output fields into workflow state.

**Request example**
```json
{
  "actor": "reviewer.user",
  "expectedTaskVersion": 7,
  "output": {
    "isEscalated": true,
    "isApproved": false,
    "decision": "Accepted & Denied",
    "resubmissionRequiredBy": "2026-07-10"
  },
  "comment": "Missing required items"
}
```

**Response example**
```json
{
  "taskId": "task_123",
  "workflowId": "wf_456",
  "taskStatus": "COMPLETED",
  "workflowStatus": "RUNNING",
  "resumed": true,
  "promotedVariables": {
    "isEscalated": true,
    "isApproved": false,
    "decision": "Accepted & Denied",
    "resubmissionRequiredBy": "2026-07-10"
  }
}
```

### POST `/api/workflows/{workflowId}/tasks/{taskId}/comments`
Adds a task comment.

### GET `/api/workflows/{workflowId}/tasks/{taskId}/data`
Returns task-local data such as drafts/output.

### PATCH `/api/workflows/{workflowId}/tasks/{taskId}/data`
Updates task-local draft data.

---

## Workflow Definition APIs

### GET `/api/workflow-definitions/{workflowType}/versions`
Lists workflow definition versions.

### GET `/api/workflow-definitions/{workflowType}/versions/{version}`
Gets a specific version of the workflow definition.

### POST `/api/workflow-definitions/{workflowType}/versions`
Publishes a new workflow definition version.

**Purpose**
Use this when variables are added, removed, renamed, or type-changed during workflow design.

### POST `/api/workflow-definitions/{workflowType}/versions/{version}/validate-migration`
Validates whether old workflow instances can safely migrate to a new version.

---

## Required Validation Rules

1. Workflow state updates must validate against **definition version**.
2. Task payloads must validate against **task schema version**.
3. Existing running instances should remain version-pinned unless explicitly migrated.
4. Delegation may require workflow state updates when reminders/notifications depend on reviewer fields.
5. Reminder workers must check effective assignee dynamically.

---

## Status Enums

### Workflow status
- `RUNNING`
- `WAITING_ON_HUMAN_TASK`
- `COMPLETED`
- `FAILED`
- `CANCELLED`

### Task status
- `PENDING`
- `IN_PROGRESS`
- `DELEGATED`
- `COMPLETED`
- `CANCELLED`
- `ESCALATED`

---

## Cross-Cutting Requirements

### Optimistic Locking
Use version checks such as:
- `expectedStateVersion`
- `expectedTaskVersion`

### Idempotency
Recommended for:
- task completion
- task delegation
- workflow resume
- workflow cancel

### Authorization
Every mutation endpoint should enforce actor authorization.

### Auditability
All changes to state, task lifecycle, and workflow definitions must emit audit events.
