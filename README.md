# SentinelMesh — Multi-Agent SRE Swarm

SentinelMesh is a hackathon prototype for coordinating specialized SRE agents through shared graph memory in FalkorDB. The dashboard uses a guided, gamified mission flow with mission XP, objectives, incident response, graph intelligence, and an audit/evidence view.

## Features

- Guided incident-response mission UI with replayable objectives and XP
- Tenant-scoped graph memory for demo workspaces
- Triage, diagnosis, and remediation agents that coordinate through graph records
- Service dependency and deployment-provenance tracing
- Optional graph centrality / path analysis when the relevant FalkorDB procedures are available
- Persistent incident event history and audit export
- Generated remediation plans remain proposals; the application does not execute shell commands
- Recovery verification is a user-entered simulated outcome, not an actual service health probe

## Requirements

- Python 3.10+ recommended
- Docker Desktop with FalkorDB, or an already-running compatible FalkorDB instance
- Windows PowerShell instructions below

## Run on Windows

### 1. Check whether FalkorDB is already running

```powershell
docker ps --filter "name=sentinel_falkordb"
Test-NetConnection localhost -Port 6379
```

If your existing `sentinel_falkordb` container is running and port 6379 succeeds, reuse it. **Do not run `docker compose up -d` in this project**, because this compose file uses the same container name and host port.

If you do not already have FalkorDB running, start it once from this folder:

```powershell
docker compose up -d
```

### 2. Install Python dependencies

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks virtual-environment activation, use ` .\.venv\Scripts\python.exe ` instead of `python` in the commands below.

### 3. Run tests

```powershell
python -m pytest -q
```

These tests check source-level safety contracts; they do not replace a live integration test against FalkorDB.

### 4. Launch the dashboard

```powershell
$env:FALKORDB_HOST = "localhost"
$env:FALKORDB_PORT = "6379"
python -m streamlit run dashboard.py
```

Open the local URL Streamlit prints, usually http://localhost:8501.

## Suggested demo flow

1. Select a tenant/workspace in the sidebar.
2. Click **Prepare demo environment**.
3. Use the guided incident-response mission to launch the swarm.
4. Show the triage handoff, diagnosis candidate, and remediation plan.
5. Demonstrate the optional graph-intelligence view if supported by the database.
6. Record a simulated verification result and inspect/export the audit trail.

Use a fresh or dedicated demo tenant if you want a clean recording. Do not use the tenant-reset control unless you intend to delete that tenant's graph data.

## Architecture

- `dashboard.py` — Streamlit guided mission interface and workflow orchestration
- `agents.py` — triage, diagnosis, and remediation agents
- `memory_manager.py` — FalkorDB graph persistence, topology seeding, provenance tracing, playbook memory, verification records, and audit trail
- `docker-compose.yml` — local FalkorDB service
- `tests/` — lightweight source-level safety tests

## Important limitations

- This is a prototype, not a production SRE controller.
- Root-cause outputs are candidate explanations, not proof of causation.
- Verification outcomes are entered by the operator for demonstration; the app does not perform real Redis/Kubernetes health checks.
- Remediation plans are recorded for review; no shell commands are executed.
- Tenant-specific graph names are a demo isolation mechanism, not a complete production security boundary.
- Graph algorithm availability depends on the FalkorDB image and installed procedures.

## Track

Agent Memory and Coordination — shared graph memory is used to persist incident state, service dependencies, deployment provenance, playbooks, handoffs, and audit events.
