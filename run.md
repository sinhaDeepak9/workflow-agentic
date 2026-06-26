## Running the project

From the project root (`workflow-agentic`):

**1. Create a virtual environment**

macOS / Linux:
```bash
python -m venv .venv
source .venv/bin/activate
```
Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Create your env file** from the template
```bash
cp .env.example .env          # macOS / Linux
Copy-Item .env.example .env   # Windows PowerShell
```

**4. Start the API server**
```bash
uvicorn app.main:app --reload
```

The server runs at `http://127.0.0.1:8000`.
Open `http://127.0.0.1:8000/docs` for the interactive Swagger UI.

---

## API reference

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |

### Workflows
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/workflows` | List all workflows (filterable, paginated) |
| POST | `/api/workflows` | Start a new workflow instance |
| GET | `/api/workflows/{id}` | Get workflow summary |
| GET | `/api/workflows/{id}/state` | Get full workflow state + variables |
| PATCH | `/api/workflows/{id}/state` | Admin patch of workflow variables |
| POST | `/api/workflows/{id}/resume` | Manually resume a waiting workflow |
| POST | `/api/workflows/{id}/cancel` | Cancel a workflow (admin only) |
| GET | `/api/workflows/{id}/audit` | Full audit / event history |

### Tasks
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tasks` | List all tasks across all workflows (filterable, paginated) |
| GET | `/api/workflows/{id}/tasks` | List tasks for a specific workflow |
| GET | `/api/workflows/{id}/tasks/{taskId}` | Get a single task |
| POST | `/api/workflows/{id}/tasks/{taskId}/claim` | Claim a task |
| POST | `/api/workflows/{id}/tasks/{taskId}/complete` | Complete a task (resumes workflow) |
| POST | `/api/workflows/{id}/tasks/{taskId}/delegate` | Delegate a task |
| POST | `/api/workflows/{id}/tasks/{taskId}/reassign` | Admin reassign a task |
| POST | `/api/workflows/{id}/tasks/{taskId}/comments` | Add a comment |
| GET | `/api/workflows/{id}/tasks/{taskId}/data` | Get task draft / output data |
| PATCH | `/api/workflows/{id}/tasks/{taskId}/data` | Save draft data |

### Graph visualisation
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/graph/png` | Static workflow graph PNG |
| GET | `/api/graph/mermaid` | Static workflow graph as Mermaid source |
| GET | `/api/workflows/{id}/graph/png` | Per-instance PNG with node state colouring |
| GET | `/api/workflows/{id}/graph/mermaid` | Per-instance Mermaid source with node state colouring |

**Node colours** on the per-instance graph:
- 🟢 **Green** — node has completed execution
- 🟡 **Amber** — node is currently active / waiting for human input
- ⬜ **Grey** — node has not yet executed

Both graph endpoints accept `?xray=true` (default) to expand subgraph internals.

### Definitions
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/workflow-definitions/{type}/versions` | List all definition versions |
| GET | `/api/workflow-definitions/{type}/versions/{v}` | Get a specific version |
| POST | `/api/workflow-definitions/{type}/versions` | Publish a new version (admin only) |
| POST | `/api/workflow-definitions/{type}/versions/{v}/validate-migration` | Check migration safety |

---

## Filter reference

### GET /api/workflows
| Query param | Example | Description |
|-------------|---------|-------------|
| `status` | `?status=RUNNING&status=WAITING_ON_HUMAN_TASK` | One or more statuses (multi-value) |
| `workflow_type` | `?workflow_type=HawaiReportApproval` | Case-insensitive exact match |
| `current_node` | `?current_node=report_submission_review` | Node the workflow is paused at |
| `definition_version` | `?definition_version=1` | Pinned definition version |
| `owner` | `?owner=alice` | Substring match across `targetUser`, `reviewer`, `supervisor`, `reportOwners` |
| `created_after` | `?created_after=1750000000` | Unix epoch lower bound |
| `created_before` | `?created_before=1760000000` | Unix epoch upper bound |
| `page` / `pageSize` | `?page=2&pageSize=10` | Pagination (default 1 / 20, max 200) |

### GET /api/tasks
| Query param | Example | Description |
|-------------|---------|-------------|
| `workflowId` | `?workflowId=wf_abc123` | Restrict to one workflow |
| `status` | `?status=PENDING&status=IN_PROGRESS` | One or more statuses (multi-value) |
| `taskType` | `?taskType=report_submission_review` | Task type name |
| `assignee` | `?assignee=alice` | Substring match on assignee |
| `effectiveAssignee` | `?effectiveAssignee=alice` | Resolves delegation chain |
| `candidateGroup` | `?candidateGroup=supervisors` | Substring match on candidate groups |
| `dueBefore` | `?dueBefore=2026-07-31` | ISO date (YYYY-MM-DD) |
| `dueAfter` | `?dueAfter=2026-06-01` | ISO date (YYYY-MM-DD) |
| `createdAfter` | `?createdAfter=1750000000` | Unix epoch lower bound |
| `createdBefore` | `?createdBefore=1760000000` | Unix epoch upper bound |
| `page` / `pageSize` | `?page=1&pageSize=50` | Pagination (default 1 / 20, max 200) |

---

## Quick smoke test (bash)

```bash
# 1. Start a workflow (pauses at Report Submission Review)
WF=$(curl -s -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{"actor":"admin.user","variables":{"reportType":"Quarterly","reviewer":"alice.reviewer","supervisor":"bob.super","slaDays":14}}')
echo $WF | python3 -m json.tool
WF_ID=$(echo $WF | python3 -c "import sys,json; print(json.load(sys.stdin)['workflowId'])")

# 2. List open tasks for the workflow
curl -s "http://localhost:8000/api/workflows/${WF_ID}/tasks" | python3 -m json.tool

# 3. Get the coloured graph PNG (green=done, amber=active, grey=pending)
curl -s "http://localhost:8000/api/workflows/${WF_ID}/graph/png" -o graph.png

# 4. Complete the Report Submission Review task (escalate → triggers Supervisor Review)
TASK_ID=$(curl -s "http://localhost:8000/api/workflows/${WF_ID}/tasks" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['taskId'])")

curl -s -X POST "http://localhost:8000/api/workflows/${WF_ID}/tasks/${TASK_ID}/complete" \
  -H "Content-Type: application/json" \
  -d "{\"actor\":\"alice.reviewer\",\"expectedTaskVersion\":0,
       \"output\":{\"isEscalated\":true,\"isApproved\":false,
                   \"decision\":\"Accepted & Denied\",
                   \"resubmissionRequiredBy\":\"2026-07-10\"},
       \"comment\":\"Missing items\"}" | python3 -m json.tool

# 5. Workflow is now at Supervisor Review — check state
curl -s "http://localhost:8000/api/workflows/${WF_ID}/state" | python3 -m json.tool

# 6. Filter workflows by status
curl -s "http://localhost:8000/api/workflows?status=WAITING_ON_HUMAN_TASK" | python3 -m json.tool

# 7. Filter tasks by assignee across all workflows
curl -s "http://localhost:8000/api/tasks?assignee=alice" | python3 -m json.tool
```

## Quick smoke test (PowerShell)

```powershell
# 1. Start a workflow
$wf = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/workflows `
  -ContentType application/json `
  -Body '{"actor":"admin.user","variables":{"reportType":"Quarterly","reviewer":"alice.reviewer","supervisor":"bob.super","slaDays":14}}'
$wf

# 2. List open tasks
Invoke-RestMethod "http://127.0.0.1:8000/api/workflows/$($wf.workflowId)/tasks"

# 3. Complete the task (escalate)
$task = (Invoke-RestMethod "http://127.0.0.1:8000/api/workflows/$($wf.workflowId)/tasks")[0]
Invoke-RestMethod -Method Post -ContentType application/json `
  -Uri "http://127.0.0.1:8000/api/workflows/$($wf.workflowId)/tasks/$($task.taskId)/complete" `
  -Body (@{
    actor               = $task.assignee
    expectedTaskVersion = $task.taskVersion
    output = @{ isEscalated=$true; isApproved=$false; decision="Accepted & Denied"; resubmissionRequiredBy="2026-07-10" }
    comment = "Missing items"
  } | ConvertTo-Json)

# 4. Check state and audit
Invoke-RestMethod "http://127.0.0.1:8000/api/workflows/$($wf.workflowId)/state"
Invoke-RestMethod "http://127.0.0.1:8000/api/workflows/$($wf.workflowId)/audit"

# 5. Filter workflows and tasks
Invoke-RestMethod "http://127.0.0.1:8000/api/workflows?status=WAITING_ON_HUMAN_TASK"
Invoke-RestMethod "http://127.0.0.1:8000/api/tasks?assignee=alice"
```

---

## Notes
- `admin.user` is the seeded admin (from `ADMIN_USERS` in `.env`). Only admins may patch state, cancel, reassign tasks, publish definitions, and validate migrations.
- Stores are **in-memory** — all data resets on server restart (`STORE_BACKEND=memory`).
- All list endpoints return `{ total, page, pageSize, items[] }` and sort newest-first.
- The `idempotency_key` field on start/complete/delegate/cancel prevents duplicate effects from UI retries.
