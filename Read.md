
# HawaiReportApproval – LangGraph Conversion

## Overview

This repository/document set describes how to convert the `HawaiReportApproval` BPMN workflow into a **LangGraph-based deterministic workflow** with:

- **workflow-definition versioning**
- **workflow instance state management**
- **human task APIs**
- **task-local data storage**
- **pause/resume orchestration**
- **timer/reminder side effects**
- **schema evolution for variables added/removed during design**

This workflow should **not** be treated as a free-form autonomous AI agent. The correct target design is a **stateful governed workflow** with human-in-the-loop steps.

---

## Workflow Summary

### BPMN intent

The uploaded BPMN process performs the following business flow:

1. Initialize submission state.
2. Create report owner object and calculate due dates / SLA values.
3. Resolve report ownership via business rules.
4. Set reviewer(s) and notify related users.
5. Pause on **Report Submission Review**.
6. Send reminders while the review task remains open.
7. If escalated, assign supervisor and pause on **Supervisor Review**.
8. Merge review paths.
9. Route to final notification based on `decision`:
   - `Accepted`
   - `Accepted & Approved`
   - `Accepted & Denied`

---

## Recommended LangGraph Model

### High-level graph

```text
START
  → initialize_submission
  → get_report_owner
  → setup_reviewers_and_notifications
  → join_setup
  → report_submission_review (pause)
       ├─ reviewer reminder side jobs while task open
       └─ check_escalation
            ├─ escalated → choose_supervisor → supervisor_review (pause)
            │                  ├─ supervisor reminder side jobs while task open
            │                  └─ merge_review_paths
            └─ not escalated → merge_review_paths
  → route_final_decision
       ├─ Accepted → notify_mco_accepted → END
       ├─ Accepted & Approved → notify_mco_accepted_approved → END
       └─ Accepted & Denied → notify_mco_denied → END
```

### Why LangGraph fits

LangGraph is a good fit because this process needs:

- persisted workflow state
- human-task pause/resume
- deterministic conditional routing
- long-running execution
- reminder/event side effects
- explicit workflow control rather than pure agent autonomy

---

## Architecture Layers

### 1. Workflow Definition Layer
Stores **design-time** information:

- workflow type
- definition version
- state schema version
- variable registry
- task schemas
- migration rules
- routing metadata

### 2. Workflow Instance Layer
Stores **runtime workflow state**:

- workflow id
- current node
- current task id
- workflow status
- process variables
- bound definition version

### 3. Task Layer
Stores **human task runtime data**:

- task id
- task type
- status
- assignee / candidate users / groups
- draft form data
- output data
- delegated from / delegated to
- due date / created at / completed at
- comments / attachments

---

## Variable Design

### Process-Level Variables
These belong to the workflow instance state and affect routing, reminders, or notifications.

Examples:

- `reportType`
- `instanceDescription`
- `reportOwners`
- `targetUser`
- `mqdUser`
- `healthPlanName`
- `reportingPeriod`
- `dueDate`
- `reviewer`
- `isEscalated`
- `isApproved`
- `mcoEmail`
- `mcoUser`
- `slaDate`
- `reminder1`
- `reminder2`
- `userList`
- `decision`
- `slaSuper`
- `resubmissionRequiredBy`
- `processActivationTime`
- `internalSubmissionId`
- `slaDays`
- reminder expressions

### Task-Level Variables
These belong to a specific human task instance.

Examples:

- `taskId`
- `taskType`
- `status`
- `assignee`
- `candidateUsers`
- `candidateGroups`
- `draftData`
- `outputData`
- `delegatedFrom`
- `delegatedTo`
- `comments`
- `createdAt`
- `completedAt`

---

## Variable Evolution Rules

Since variables can be **added or removed while designing the workflow**, the implementation must use **versioned definitions**.

### Rules

1. Every workflow instance is bound to a **definition version**.
2. New variables are added through a **new definition version**.
3. Removed variables are deprecated first, then removed in later versions.
4. Renaming a variable should be treated as:
   - add new variable
   - migrate value
   - deprecate old variable
5. Type changes require a new version and migration strategy.
6. Running instances should remain pinned to the version they started with unless migrated explicitly.

---

## Human Task Handling

### Human tasks in this workflow

- `Report Submission Review`
- `Supervisor Review`

### Human task behavior in LangGraph

A human task node should:

1. create a task record in the task store
2. write `currentTaskId` and `currentNode` into workflow state
3. set workflow status to `WAITING_ON_HUMAN_TASK`
4. pause graph execution
5. wait for API-driven completion / delegation / reassignment

### Task completion bridge

On completion:

1. validate payload against task schema version
2. persist task output
3. map task output into workflow state
4. update checkpoint/state version
5. resume graph execution

---

## Reminder / Timer Model

BPMN boundary timers should be implemented via scheduler/background jobs.

### Rules

- reminders must not advance the graph
- reminders must run only if task is still open
- reminders must resolve the **current effective assignee** after delegation/reassignment
- reminder jobs must be auditable

---

## API Surface

This project expects three main API groups:

### Workflow APIs
- workflow summary
- workflow state read/update
- resume
- cancel
- audit/events

### Human Task APIs
- list tasks
- get task
- claim
- delegate
- reassign
- complete
- comment
- task-local data read/update

### Workflow Definition APIs
- list definition versions
- get version details
- publish new version
- validate migration compatibility

See `API_information.md` for the full contract.

---

## Implementation Guidance

### Recommended storage separation

- **workflow_definition** table/collection
- **workflow_instance** table/collection
- **workflow_task** table/collection
- **audit_event** table/collection

### Recommended operational controls

- optimistic locking on task/state update
- idempotency keys for complete/delegate/resume/cancel
- RBAC checks on every state/task mutation
- audit event emission on all workflow and task actions

---

## Suggested Next Steps

1. Implement workflow-definition persistence.
2. Build workflow instance state store.
3. Implement human task APIs.
4. Add LangGraph pause/resume logic.
5. Add reminder scheduler.
6. Add migration validation for future workflow-definition versions.

---

## Files

- `Read.md` → overview and architecture
- `claude.md` → implementation guidance / engineering instructions
- `API_information.md` → API contract summary
