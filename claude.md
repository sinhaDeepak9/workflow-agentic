
# claude.md

## Purpose

This file provides **engineering guidance** for anyone implementing the `HawaiReportApproval` BPMN-to-LangGraph conversion.

It is not a runtime spec. It is a build-time implementation note describing design constraints and expected engineering behavior.

---

## Core Principle

Treat this workflow as a **governed business workflow**, not as a free-form autonomous AI agent.

The LangGraph implementation should prioritize:

- deterministic routing
- process state integrity
- human-in-the-loop orchestration
- strong audit behavior
- version-safe variable management
- operational safety under schema evolution

---

## Design Constraints

### 1. Workflow-definition driven runtime
Do not hard-code the workflow variable list directly into business logic without version awareness.

The runtime must always know:

- `workflowType`
- `definitionVersion`
- `stateSchemaVersion`
- task schema version

### 2. Separate stores
Do not mix workflow state with task state.

Required separation:

- **definition store**
- **workflow state / checkpoint store**
- **task store**
- **audit/event store**

### 3. Task output promotion
Task completion must not only mark the task complete.

It must also:

- validate output schema
- persist output
- promote allowed task fields into workflow state
- resume graph execution

### 4. Reminder correctness
Reminder jobs must always resolve the current assignee dynamically.

If a task is delegated or reassigned, reminder notifications should go to the effective assignee, not the original one.

### 5. Schema evolution safety
Variable changes at design time must be implemented through definition versioning.

Never silently mutate live state schema for already running instances.

---

## Required Runtime Concepts

### Workflow statuses
Suggested enum:

- `RUNNING`
- `WAITING_ON_HUMAN_TASK`
- `COMPLETED`
- `FAILED`
- `CANCELLED`

### Task statuses
Suggested enum:

- `PENDING`
- `IN_PROGRESS`
- `DELEGATED`
- `COMPLETED`
- `CANCELLED`
- `ESCALATED` (optional business state)

---

## Human Task Implementation Notes

### Report Submission Review
Expected output fields:

- `isEscalated`
- `isApproved`
- `decision`
- `resubmissionRequiredBy`
- optional reviewer comment

### Supervisor Review
Expected output fields:

- `isApproved`
- `decision`
- optional supervisor comment

### Pause/Resume Pattern
When entering a human task node:

1. create task record
2. write `currentTaskId`
3. write `currentNode`
4. update workflow status to `WAITING_ON_HUMAN_TASK`
5. checkpoint graph state
6. exit/pause

When completing a human task:

1. validate task ownership / authorization
2. validate task version
3. validate payload schema
4. persist task output
5. promote mapped output fields into workflow state
6. checkpoint updated workflow state
7. resume graph

---

## Concurrency Requirements

Use optimistic locking / expected version checks for:

- workflow state patch
- task completion
- task delegation
- task reassignment
- task draft save

Recommended fields:

- `stateVersion`
- `taskVersion`

Reject stale updates with a conflict response.

---

## Idempotency Requirements

Support idempotency keys for at least:

- task completion
- task delegation
- workflow resume
- workflow cancel

This protects against UI retries and duplicate client calls.

---

## Authorization Guidance

At minimum, enforce checks for:

- who can view workflow state
- who can patch workflow state
- who can claim a task
- who can complete a task
- who can delegate or reassign a task
- who can publish workflow definition versions
- who can validate migrations

---

## Migration Guidance

When a new definition version is created:

### Safe options
1. Keep existing instances pinned to the version they started with.
2. Offer an explicit migration process.

### Never do silently
- remove a variable from a live instance with no migration
- rename a variable in place
- change variable type without migration

---

## Auditing Guidance

Emit audit events for:

- workflow started
- workflow state patched
- task created
- task claimed
- task delegated
- task reassigned
- task completed
- task commented
- reminder sent
- workflow resumed
- workflow cancelled
- definition version published
- migration validated

---

## Recommended Data Shapes

### Workflow instance
```json
{
  "workflowId": "wf_456",
  "workflowType": "HawaiReportApproval",
  "definitionVersion": 7,
  "stateSchemaVersion": 7,
  "stateVersion": 15,
  "status": "WAITING_ON_HUMAN_TASK",
  "currentNode": "report_submission_review",
  "currentTaskId": "task_123",
  "variables": {}
}
```

### Task record
```json
{
  "taskId": "task_123",
  "workflowId": "wf_456",
  "taskType": "report_submission_review",
  "taskSchemaVersion": 3,
  "taskVersion": 7,
  "status": "PENDING",
  "assignee": "reviewer.user",
  "candidateUsers": [],
  "candidateGroups": [],
  "draftData": {},
  "outputData": null
}
```

---

## Final Engineering Rule

If there is ever a conflict between convenience and state correctness, choose **state correctness**.

This workflow is used for governed human review, escalation, and formal outcomes. Reliability, auditability, and version safety matter more than implementation speed.
