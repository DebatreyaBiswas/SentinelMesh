import os
import pandas as pd
import streamlit as st
from memory_manager import IncidentMemoryManager
from agents import TriageAgent, DiagnosisAgent, RemediationAgent

st.set_page_config(page_title="SentinelMesh | Incident Operations", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root { --sm-bg:#0b1120; --sm-panel:#111b2e; --sm-border:#26364f; --sm-muted:#93a4bc; --sm-blue:#60a5fa; }
.stApp { background: radial-gradient(ellipse at top left, #14213b 0%, #0b1120 46%, #080d18 100%); }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1500px; }
[data-testid="stSidebar"] { background: #0e1728; border-right: 1px solid var(--sm-border); }
[data-testid="stMetric"] { background: linear-gradient(145deg,#142139,#10192a); border:1px solid var(--sm-border); padding:16px 18px; border-radius:14px; }
[data-testid="stMetricLabel"] p { color:#9eb0c9 !important; }
[data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--sm-border) !important; border-radius:16px !important; }
.stButton > button, .stFormSubmitButton > button { border-radius:10px; min-height:2.65rem; font-weight:600; transition:all .15s ease; }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] { background:linear-gradient(90deg,#3b82f6,#6366f1); border:0; }
.stButton > button:hover, .stFormSubmitButton > button:hover { border-color:#60a5fa; transform:translateY(-1px); }
.sm-eyebrow { color:#7dd3fc; font-size:.74rem; font-weight:800; letter-spacing:.16em; text-transform:uppercase; }
.sm-hero { padding:24px 26px; border:1px solid #2a3b58; border-radius:18px; background:linear-gradient(120deg,rgba(30,58,138,.38),rgba(17,27,46,.92) 65%,rgba(49,46,129,.28)); margin-bottom:18px; }
.sm-pill { display:inline-block; padding:5px 10px; border:1px solid #36516f; border-radius:999px; color:#bfdbfe; font-size:.76rem; background:#14243b; }
.sm-card { padding:16px 18px; border:1px solid var(--sm-border); border-radius:14px; background:rgba(17,27,46,.78); min-height:112px; }
.sm-muted { color:var(--sm-muted); font-size:.88rem; }
.sm-step { border-left:3px solid #60a5fa; padding:3px 0 3px 14px; margin:7px 0; }
hr { border-color:#26364f !important; }
</style>
""", unsafe_allow_html=True)

# --- Session state for a genuinely guided, replayable demo ---
for key, default in {
    "tutorial_step": 0, "xp": 0, "completed_steps": [], "last_incident": None,
    "last_triage": None, "last_diagnosis": None, "last_remediation": None,
    "last_verification": None, "centrality_results": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

with st.sidebar:
    st.markdown("## 🛡️ SentinelMesh")
    st.caption("INCIDENT OPERATIONS · TRACK 02")
    st.markdown("---")
    tutorial = st.toggle("🎮 Guided mission mode", value=True, help="Turn this on for the judge-friendly walkthrough.")
    tenant = st.selectbox("Workspace / tenant", ["tenant_fintech_prod", "tenant_healthcare_cloud", "tenant_retail_eu"], format_func=lambda x: {"tenant_fintech_prod":"Fintech · Production", "tenant_healthcare_cloud":"Healthcare · Cloud", "tenant_retail_eu":"Retail · EU"}[x])
    if "memory" not in st.session_state or st.session_state.get("current_tenant") != tenant:
        st.session_state.memory = IncidentMemoryManager(host=os.getenv("FALKORDB_HOST", "localhost"), port=int(os.getenv("FALKORDB_PORT", "6379")), tenant_id=tenant)
        st.session_state.current_tenant = tenant
        st.session_state.last_incident = None
        st.session_state.last_triage = None
        st.session_state.last_diagnosis = None
        st.session_state.last_remediation = None
        st.session_state.last_verification = None
    memory = st.session_state.memory
    st.markdown("<div class='sm-muted'>Graph memory is isolated by selected tenant. This demo never runs shell commands.</div>", unsafe_allow_html=True)
    st.markdown("---")
    if st.button("🌱 Prepare demo environment", use_container_width=True, type="primary"):
        try:
            memory.seed_environment(reset=False)
            st.session_state["environment_seeded"] = True
            st.success("Topology ready. Existing tenant data was preserved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not seed graph: {exc}")
    with st.expander("Danger zone · tenant reset"):
        st.warning("Permanently deletes graph data for the selected tenant.")
        confirm = st.checkbox("I understand this deletes tenant graph data", key="confirm_reset_checkbox")
        if st.button("Reset selected tenant", disabled=not confirm, use_container_width=True):
            try:
                memory.seed_environment(reset=True)
                st.session_state.last_incident = None
                st.session_state.last_triage = None
                st.session_state.last_diagnosis = None
                st.session_state.last_remediation = None
                st.session_state.last_verification = None
                st.success("Tenant graph reset and reseeded.")
                st.rerun()
            except Exception as exc:
                st.error(f"Reset failed: {exc}")
    st.markdown("---")
    st.metric("Mission XP", st.session_state.xp)
    st.progress(min(len(st.session_state.completed_steps) / 4, 1.0), text=f"{len(st.session_state.completed_steps)}/4 mission objectives")
    if st.button("↻ Replay mission", use_container_width=True):
        st.session_state.tutorial_step = 0
        st.session_state.completed_steps = []
        st.session_state.xp = 0
        st.session_state.last_incident = None
        st.session_state.last_triage = None
        st.session_state.last_diagnosis = None
        st.session_state.last_remediation = None
        st.session_state.last_verification = None
        st.rerun()

# Hero
st.markdown("""
<div class="sm-hero">
  <div class="sm-eyebrow">Autonomous operations · Human-governed recovery</div>
  <h1 style="margin:.35rem 0 .4rem 0; font-size:2.45rem; letter-spacing:-.04em;">Resolve incidents with memory.</h1>
  <p style="color:#b8c7dc; max-width:850px; margin-bottom:1rem;">SentinelMesh coordinates specialized SRE agents over a shared graph memory—connecting incident symptoms, service dependencies, prior procedures, and auditable recovery evidence.</p>
  <span class="sm-pill">● SANDBOX</span> &nbsp; <span class="sm-pill">FALKORDB GRAPH MEMORY</span> &nbsp; <span class="sm-pill">HUMAN APPROVAL REQUIRED</span>
</div>
""", unsafe_allow_html=True)

# A compact operational header
m1, m2, m3, m4 = st.columns(4)
with m1: st.metric("Agent roles", "03", "Triage · Diagnosis · Remediation")
with m2: st.metric("Tenant", "Isolated", tenant.replace("tenant_", "").replace("_", " ").title())
with m3: st.metric("Incident status", "Investigating" if st.session_state.last_incident else "Standby", "Simulated environment")
with m4: st.metric("Recovery policy", "Human-gated", "No shell execution")

if tutorial:
    st.markdown("### 🎮 Mission briefing")
    st.caption("Complete the four objectives to finish the walkthrough. Each objective teaches one core capability; the score is for demo engagement, not a production reliability metric.")
    steps = ["Prepare graph", "Launch incident", "Review the plan", "Record verification"]
    current = min(st.session_state.tutorial_step, 3)
    st.progress(len(st.session_state.completed_steps)/4, text=f"Objective {min(current+1,4)} of 4 · {steps[current]}")
    bcols = st.columns(4)
    for i, label in enumerate(steps):
        with bcols[i]:
            done = i in st.session_state.completed_steps
            st.markdown(f"<div class='sm-card'><div class='sm-eyebrow'>OBJECTIVE {i+1}</div><h4 style='margin:.45rem 0'>{'✓ ' if done else ''}{label}</h4><div class='sm-muted'>{'Completed' if done else ('Current objective' if i == current else 'Unlocks as you progress')}</div></div>", unsafe_allow_html=True)

st.markdown("### Incident workbench")
incident_tab, memory_tab, audit_tab = st.tabs(["🚨 Incident response", "🧠 Graph intelligence", "📜 Audit & evidence"])

with incident_tab:
    left, right = st.columns([1.08, .92], gap="large")
    with left:
        st.markdown("#### 01 / Trigger a scenario")
        st.caption("Choose a synthetic failure. The agents will share incident state through graph memory.")
        incident_id = st.text_input("Incident reference", value=st.session_state.last_incident or "INC-2026-901")
        entry_service = st.selectbox("Affected entry service", ["api-gateway", "payment-processor"])
        issue_type = st.selectbox("Failure signature", ["CONNECTION_POOL_EXHAUSTION", "DEADLOCK_ON_SHARD_04", "UNKNOWN_FAILURE"])
        symptom = st.text_input("Observed telemetry", value="HTTP 504 Gateway Timeout spike · p99 > 4500ms")
        launch = st.button("▶ Run agent investigation", type="primary", use_container_width=True)
        if tutorial and 0 not in st.session_state.completed_steps:
            st.info("Mission tip: prepare the demo topology from the left sidebar before launching the scenario.")
    with right:
        st.markdown("#### Live service topology")
        st.caption("Conceptual view of the demo's service relationships. Diagnosis output remains a candidate, not proof of causation.")
        try:
            st.graphviz_chart('''digraph { graph [bgcolor="transparent", rankdir=TB, nodesep="0.42", ranksep="0.48"]; node [shape=box, style="rounded,filled", fontname="Arial", fontsize=10, color="#395577", fontcolor="#e5eefb", fillcolor="#172943", margin="0.16,0.10"]; edge [color="#607d9e", penwidth=1.6, arrowsize=.7]; api [label="API Gateway\\nENTRY / ALERT", fillcolor="#713f32", color="#fb923c"]; auth [label="Auth Service"]; pay [label="Payment Processor"]; ledger [label="Ledger Worker"]; redis [label="Redis Cluster\\nDATA DEPENDENCY", fillcolor="#263b67", color="#60a5fa"]; api -> auth; api -> pay; auth -> redis; pay -> ledger; ledger -> redis; }''', use_container_width=True)
        except Exception:
            st.info("Service topology visualization is unavailable in this Streamlit version.")

    if launch:
        try:
            with st.status("Coordinating agents…", expanded=True) as status_box:
                st.write("Triage Agent · classifying alert and writing handoff")
                triage = TriageAgent(memory).run(incident_id, symptom, entry_service)
                st.write("Diagnosis Agent · tracing graph dependencies")
                diagnosis = DiagnosisAgent(memory).run(incident_id)
                st.write("Remediation Agent · proposing a guarded playbook")
                if diagnosis.get("error"):
                    remediation = None
                else:
                    root = diagnosis["root_cause_trace"]["selected"]["root_service"]
                    remediation = RemediationAgent(memory).run(incident_id, root, issue_type)
                status_box.update(label="Investigation finished", state="complete", expanded=False)
            st.session_state.last_incident = incident_id
            st.session_state.last_triage = triage
            st.session_state.last_diagnosis = diagnosis
            st.session_state.last_remediation = remediation
            st.session_state.last_verification = None
            if 1 not in st.session_state.completed_steps:
                st.session_state.completed_steps.append(1); st.session_state.xp += 100
            st.session_state.tutorial_step = 2
            st.rerun()
        except Exception as exc:
            st.error(f"Agent investigation failed: {exc}")

    triage = st.session_state.last_triage
    diagnosis = st.session_state.last_diagnosis
    remediation = st.session_state.last_remediation
    if triage:
        st.markdown("---")
        st.markdown("#### 02 / What the agents found")
        a, b, c = st.columns(3, gap="medium")
        with a:
            with st.container(border=True):
                st.markdown("**🕵️ Triage Agent**")
                st.success("Handoff recorded")
                st.caption(f"Incident: {st.session_state.last_incident}")
                st.write("Priority candidate")
                if triage.get("priority_candidate"):
                    pc = triage["priority_candidate"]
                    st.metric(str(pc.get("service", "Service")), f"{pc.get('score', 0):.4f}" if isinstance(pc.get("score"), (float,int)) else str(pc.get("score", "—")), str(pc.get("tier", "")))
                with st.expander("Technical handoff details"):
                    st.code(triage.get("handoff_query", "No handoff query returned"), language="cypher")
                    st.caption(f"Handoff ID: {triage.get('handoff_id', '—')}")
        with b:
            with st.container(border=True):
                st.markdown("**🔎 Diagnosis Agent**")
                if diagnosis and not diagnosis.get("error"):
                    selected = diagnosis["root_cause_trace"]["selected"]
                    st.warning("Candidate root cause")
                    st.markdown(f"### `{selected.get('root_service', 'Unknown')}`")
                    st.caption(f"Entry service: {selected.get('entry_service', '—')}")
                    st.info("Evidence-based hypothesis, not confirmed causation.")
                    with st.expander("Inspect dependency path & evidence"):
                        st.json(selected)
                        st.json(diagnosis.get("shortest_path_algo", {}))
                else:
                    st.error(diagnosis.get("error", "Diagnosis unavailable") if diagnosis else "Diagnosis has not run")
        with c:
            with st.container(border=True):
                st.markdown("**🛡️ Remediation Agent**")
                if remediation:
                    st.warning("PROPOSED · approval required")
                    resolution = remediation.get("resolution", {})
                    st.markdown(f"### {resolution.get('playbook_id', 'Playbook proposed')}")
                    st.caption("No host commands executed. Review before any real-world action.")
                    with st.expander("Review proposed playbook", expanded=True):
                        st.json(resolution)
                else:
                    st.info("A remediation proposal could not be generated for this scenario.")
        if tutorial and 2 not in st.session_state.completed_steps:
            st.info("Mission tip: open the proposed playbook and explain to the judge why human approval and explicit verification matter.")
            if st.button("✓ Mark plan reviewed · +100 XP"):
                st.session_state.completed_steps.append(2)
                st.session_state.xp += 100
                st.session_state.tutorial_step = 3
                st.rerun()
        st.markdown("#### 03 / Recovery verification")
        st.caption("This is a simulated evidence record. It does not probe or alter real infrastructure.")
        with st.form("verify_recovery"):
            outcome = st.radio("Synthetic health-check outcome", ["Failed", "Passed"], horizontal=True, help="Choose the outcome for this demo run.")
            evidence = st.text_input("Evidence note", value="Synthetic health check: p99 latency returned below threshold" if outcome == "Passed" else "Synthetic health check: p99 latency remains above threshold")
            verify = st.form_submit_button("Record verification evidence", type="primary")
        if verify:
            try:
                result = memory.record_recovery_verification(st.session_state.last_incident, outcome == "Passed", evidence)
                st.session_state.last_verification = {"result": result, "outcome": outcome, "evidence": evidence}
                if result.get("verified"):
                    st.success("Simulated recovery marked VERIFIED. This is not a real infrastructure health check.")
                    if 3 not in st.session_state.completed_steps:
                        st.session_state.completed_steps.append(3); st.session_state.xp += 150
                else:
                    st.error("Simulated recovery failed. The incident must remain unresolved.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not record verification: {exc}")
        if st.session_state.last_verification:
            v = st.session_state.last_verification
            st.success(f"Last recorded outcome: {v['outcome']} · {v['evidence']}") if v["outcome"] == "Passed" else st.error(f"Last recorded outcome: {v['outcome']} · {v['evidence']}")

with memory_tab:
    st.markdown("#### Graph intelligence")
    st.write("Use graph algorithms to rank structurally important services. Centrality helps prioritize investigation; it does not by itself identify a root cause.")
    if st.button("Calculate service centrality", type="primary"):
        try:
            result = memory.run_pagerank_centrality()
            st.session_state.centrality_results = result
        except Exception as exc:
            st.error(f"Graph algorithm failed: {exc}")
    result = st.session_state.centrality_results
    if result:
        if result.get("results"):
            df = pd.DataFrame(result["results"])
            st.dataframe(df, use_container_width=True, hide_index=True)
            if "score" in df.columns and "service" in df.columns:
                st.bar_chart(df.set_index("service")["score"])
        elif result.get("error"):
            st.warning(result["error"])
        else:
            st.info("No centrality results. Prepare the demo topology first.")
    st.markdown("---")
    st.markdown("#### Memory principles")
    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown("<div class='sm-card'><h4>📚 Episodic</h4><div class='sm-muted'>What happened in a prior incident and what evidence was recorded.</div></div>", unsafe_allow_html=True)
    with p2:
        st.markdown("<div class='sm-card'><h4>🧭 Semantic</h4><div class='sm-muted'>How services and dependencies relate in the tenant graph.</div></div>", unsafe_allow_html=True)
    with p3:
        st.markdown("<div class='sm-card'><h4>🛠️ Procedural</h4><div class='sm-muted'>Reusable playbook knowledge, proposed for review rather than silently executed.</div></div>", unsafe_allow_html=True)

with audit_tab:
    st.markdown("#### Verifiable incident history")
    st.caption("Inspect persisted events for the selected tenant. Audit results depend on the data actually stored in FalkorDB.")
    audit_id = st.text_input("Incident reference to inspect", value=st.session_state.last_incident or "INC-2026-901", key="audit_id")
    if st.button("Load audit trail", type="primary"):
        try:
            rows = memory.get_verifiable_audit_trail(audit_id)
            st.session_state.audit_rows = rows
        except Exception as exc:
            st.error(f"Audit query failed: {exc}")
    if "audit_rows" in st.session_state:
        rows = st.session_state.audit_rows
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.download_button("Export audit trail CSV", pd.DataFrame(rows).to_csv(index=False).encode("utf-8"), file_name=f"{audit_id}_audit.csv", mime="text/csv")
        else:
            st.info("No audit events found for this incident in the selected tenant.")

st.markdown("---")
st.markdown("<div class='sm-muted'>SentinelMesh demo · All incident telemetry and recovery outcomes are synthetic unless independently connected to real observability systems. Never present a simulated verification as a production recovery.</div>", unsafe_allow_html=True)
