# SentinelMesh — Improved Track 02 Submission

**Track:** Agent Memory and Coordination  
**Graph engine:** FalkorDB  
**UI:** Streamlit

SentinelMesh is a multi-agent SRE incident-triage prototype. Triage, diagnosis, and remediation planning share persistent graph state instead of passing large chat histories. The graph models service dependencies (semantic memory), incident events and handoffs (episodic memory), and reusable playbooks (procedural memory).

## What changed in this improved version

- **Honest remediation states:** generated playbooks are `PROPOSED`; the app never claims commands ran.
- **No shell execution:** remediation is represented as safe steps and requires operator review.
- **Explicit verification:** only a separately recorded successful health check changes the incident to `VERIFIED_RECOVERY`; failed checks become `RECOVERY_FAILED`.
- **Evidence-qualified diagnosis:** candidate root causes include deployment provenance and dependency path, and are explicitly not represented as causal proof.
- **Idempotent writes:** seed data uses `MERGE`; episodic events and handoffs use deterministic IDs to reduce duplicates on reruns.
- **Tenant graph selection:** each tenant uses a separate FalkorDB graph name.
- **Audit trail:** ordered episodic records show the agent, action, note, and evidence.
- **Safe reset:** seeding is non-destructive by default; deleting a tenant graph requires a separate confirmation in the UI.
- **Automated safety tests:** tests check that application code does not invoke shell/process execution and that generated playbooks are not silently marked approved.

## Architecture

1. **TriageAgent** records the incident, links it to the alerting service, computes centrality when the algorithm is available, and creates a graph-backed handoff.
2. **DiagnosisAgent** traverses dependency and deployment provenance, returns a candidate cause, and records the evidence and a weighted path result when available.
3. **RemediationAgent** retrieves an existing playbook or stores a proposed plan. It does not execute commands.
4. **Operator/mock verification** records an explicit simulated health-check outcome.
5. **Audit view** reads the incident's episodic memory from FalkorDB.

## Requirements

- Python 3.10+
- Docker Desktop or Docker Engine with Compose
- FalkorDB image access

## Quick start — Windows PowerShell

```powershell
# From this folder
docker compose up -d
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run dashboard.py
```

Open the Streamlit URL shown in the terminal (normally `http://localhost:8501`). In the app:
1. Select a tenant.
2. Click **Seed demo topology**.
3. Launch a synthetic incident.
4. Inspect the candidate diagnosis, playbook, and audit trail.
5. Record a mock recovery verification. This is a simulation only.

## Quick start — macOS/Linux

```bash
docker compose up -d
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run dashboard.py
```

## Tests

```bash
python -m pytest -q
```

These tests validate safety contracts and source-level invariants. They do **not** prove that a running FalkorDB deployment supports every graph algorithm or Cypher query. Run an integration test against your exact FalkorDB image before presenting algorithm availability as verified.

## Important limitations (be transparent with judges)

- This is a synthetic prototype, not a production incident-response tool.
- The sample topology and deployment provenance are seeded demo data.
- A deployment linked to a reachable service is a **candidate clue**, not proof of causation. Real deployments need telemetry, time-window filtering, competing hypotheses, and calibrated confidence.
- PageRank and `algo.SPpaths` availability can depend on FalkorDB version/plugins. The app reports algorithm errors rather than inventing results.
- The health-check result is entered by the operator for demonstration. It is not an actual Kubernetes/Redis health check.
- Tenant graph names demonstrate data separation, not complete production-grade tenant security. Authentication, authorization, network restrictions, and tenant-level access control remain necessary.
- No shell commands are run by this project.

## Demo narrative (90 seconds)

1. Seed the tenant graph.
2. Trigger an incident at `api-gateway`.
3. Show the graph-backed handoff and candidate dependency path.
4. Show the proposed/recalled playbook and point out that no commands were executed.
5. Start a fresh Streamlit session without reseeding and run a new incident ID to demonstrate graph persistence.
6. Record a mock health-check failure, then a successful verification in a controlled second run.
7. Inspect the audit trail and explain the difference between a candidate cause and verified recovery.

## Judge-facing metrics to collect before claiming results

Run a documented set of synthetic scenarios and report:
- root-cause candidate top-1 accuracy;
- correct playbook retrieval rate;
- false-cause rate on ambiguous scenarios;
- verified recovery rate (with explicit mock/integration-test definition);
- repeat-run idempotency;
- cross-session playbook retrieval;
- per-tenant isolation test results;
- median and p95 end-to-end runtime.

Do not report target metrics as measured results until you have run the experiments and saved the outputs.
