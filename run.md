## Running the project

From the project root (workflow-agentic):

**1. (Optional) Create a virtual environment**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**2. Install dependencies**
```powershell
pip install -r requirements.txt
```

**3. Create your env file** from the template
```powershell
Copy-Item .env.example .env
```

**4. Start the API server**
```powershell
uvicorn app.main:app --reload
```

The server runs at `http://127.0.0.1:8000`. Open `http://127.0.0.1:8000/docs` for the interactive Swagger UI.

## Quick smoke test (PowerShell)

Once running, exercise the full human-in-the-loop flow:

```powershell
# 1. Start a workflow (pauses on Report Submission Review)
$wf = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/workflows `
  -ContentType application/json `
  -Body '{"actor":"admin.user","variables":{"reportType":"Quarterly"}}'
$wf

# 2. Find the open task
$task = (Invoke-RestMethod http://127.0.0.1:8000/api/workflows/$($wf.workflowId)/tasks)[0]
$task

# 3. Complete it — escalate (promotes fields, resumes graph)
Invoke-RestMethod -Method Post -ContentType application/json `
  -Uri "http://127.0.0.1:8000/api/workflows/$($wf.workflowId)/tasks/$($task.taskId)/complete" `
  -Body (@{
    actor               = $task.assignee
    expectedTaskVersion = $task.taskVersion
    output = @{ isEscalated=$true; isApproved=$false; decision="Accepted & Denied"; resubmissionRequiredBy="2026-07-10" }
    comment = "Missing items"
  } | ConvertTo-Json)

# 4. Inspect state / audit
Invoke-RestMethod http://127.0.0.1:8000/api/workflows/$($wf.workflowId)/state
Invoke-RestMethod http://127.0.0.1:8000/api/workflows/$($wf.workflowId)/audit
```

## Notes
- `admin.user` is the seeded admin (from `ADMIN_USERS` in `.env`) and may patch state, cancel, reassign, publish definitions, and validate migrations.
- Stores are **in-memory**, so all workflows/tasks reset when the server restarts (`STORE_BACKEND=memory`).
- The earlier terminal `Exit Code: 1` is just a PowerShell `Select-String` artifact — the Python output printed correctly; it doesn't indicate a failure.