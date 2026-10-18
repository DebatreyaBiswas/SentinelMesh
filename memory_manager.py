"""FalkorDB-backed graph memory for SentinelMesh.

Safety contract:
- This module never executes shell commands.
- New playbooks are PROPOSED, not learned/verified automatically.
- An incident is RESOLVED only after an explicit successful verification event.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional
from falkordb import FalkorDB


class IncidentMemoryManager:
    def __init__(self, host: str = "localhost", port: int = 6379,
                 tenant_id: str = "tenant_fintech_prod"):
        if not tenant_id.replace("_", "").isalnum():
            raise ValueError("Invalid tenant graph name")
        self.client = FalkorDB(host=host, port=port)
        self.tenant_id = tenant_id
        self.graph = self.client.select_graph(tenant_id)

    def switch_tenant(self, tenant_id: str) -> None:
        if not tenant_id.replace("_", "").isalnum():
            raise ValueError("Invalid tenant graph name")
        self.tenant_id = tenant_id
        self.graph = self.client.select_graph(tenant_id)

    def _query(self, cypher: str, params: Optional[dict] = None):
        return self.graph.query(cypher, params or {})

    def seed_environment(self, reset: bool = False) -> None:
        """Seed deterministic demo data. Destructive reset is opt-in."""
        if reset:
            self.graph.delete()
            self.graph = self.client.select_graph(self.tenant_id)
        cypher = """
        MERGE (api:Service {name:'api-gateway'})
          ON CREATE SET api.tier='edge', api.owner='Platform-Team'
        MERGE (auth:Service {name:'auth-service'})
          ON CREATE SET auth.tier='core', auth.owner='Security-Team'
        MERGE (pay:Service {name:'payment-processor'})
          ON CREATE SET pay.tier='critical', pay.owner='FinOps-Team'
        MERGE (ledger:Service {name:'ledger-worker'})
          ON CREATE SET ledger.tier='backend', ledger.owner='FinOps-Team'
        MERGE (db:Service {name:'redis-cluster-01'})
          ON CREATE SET db.tier='data', db.owner='DBA-Team'
        MERGE (api)-[:DEPENDS_ON {latency_ms:12}]->(auth)
        MERGE (api)-[:DEPENDS_ON {latency_ms:25}]->(pay)
        MERGE (pay)-[:DEPENDS_ON {latency_ms:18}]->(ledger)
        MERGE (ledger)-[:DEPENDS_ON {latency_ms:5}]->(db)
        MERGE (auth)-[:DEPENDS_ON {latency_ms:8}]->(db)
        MERGE (dev:Engineer {name:'Aarav Mehta'})
          ON CREATE SET dev.role='Staff SRE'
        MERGE (commit:Commit {hash:'8f92a1b'})
          ON CREATE SET commit.message='Increase connection pool timeout on redis-cluster-01',
                        commit.timestamp='2026-10-18T14:20:00Z'
        MERGE (dev)-[:AUTHORED]->(commit)
        MERGE (commit)-[:DEPLOYED_TO]->(db)
        MERGE (pb:Playbook {id:'PB-REDIS-POOL'})
          ON CREATE SET pb.target_service='redis-cluster-01',
                        pb.issue_type='CONNECTION_POOL_EXHAUSTION',
                        pb.status='APPROVED',
                        pb.source='seeded_demo',
                        pb.description='Demo playbook; steps are displayed, never run on the host.'
        MERGE (s1:Step {playbook_id:'PB-REDIS-POOL', order:1})
          ON CREATE SET s1.cmd='SIMULATE: inspect Redis connection pool saturation'
        MERGE (s2:Step {playbook_id:'PB-REDIS-POOL', order:2})
          ON CREATE SET s2.cmd='SIMULATE: validate pool limits in an isolated test environment'
        MERGE (pb)-[:HAS_STEP]->(s1)
        MERGE (pb)-[:HAS_STEP]->(s2)
        MERGE (s1)-[:NEXT_STEP]->(s2)
        MERGE (:Agent {name:'TriageAgent', role:'First Responder'})
        MERGE (:Agent {name:'DiagnosisAgent', role:'Root Cause Analyst'})
        MERGE (:Agent {name:'RemediationAgent', role:'Safe Remediation Planner'})
        """
        self._query(cypher)

    def run_pagerank_centrality(self) -> Dict[str, Any]:
        cypher = """CALL algo.pageRank('Service', 'DEPENDS_ON')
        YIELD node, score
        RETURN node.name AS service, node.tier AS tier, score
        ORDER BY score DESC"""
        try:
            res = self._query(cypher)
            rows = [{"service": r[0], "tier": r[1], "score": round(float(r[2]), 5)}
                    for r in res.result_set]
            return {"available": True, "cypher": cypher, "results": rows}
        except Exception as exc:
            # Do not silently invent algorithm results. Keep the UI useful and explicit.
            return {"available": False, "cypher": cypher, "results": [],
                    "error": f"PageRank unavailable in this FalkorDB setup: {exc}"}

    def find_shortest_fault_path(self, failing_edge_service: str,
                                 suspected_core_service: str) -> Dict[str, Any]:
        cypher = """
        MATCH (src:Service {name:$src}), (dst:Service {name:$dst})
        CALL algo.SPpaths({
          sourceNode:src, targetNode:dst,
          relTypes:['DEPENDS_ON'], weightProp:'latency_ms'
        }) YIELD path, pathWeight
        RETURN [n IN nodes(path) | n.name] AS cascade_path, pathWeight
        """
        try:
            res = self._query(cypher, {"src": failing_edge_service,
                                      "dst": suspected_core_service})
            if not res.result_set:
                return {"cypher": cypher, "cascade_path": [],
                        "total_latency_ms": None, "available": True}
            row = res.result_set[0]
            return {"cypher": cypher, "cascade_path": row[0],
                    "total_latency_ms": row[1], "available": True}
        except Exception as exc:
            return {"cypher": cypher, "cascade_path": [],
                    "total_latency_ms": None, "available": False,
                    "error": f"Shortest-path algorithm unavailable: {exc}"}

    def create_incident_and_handoff(self, incident_id: str, symptom: str,
                                    affected_service: str, from_agent: str,
                                    to_agent: str) -> Dict[str, Any]:
        ts = int(time.time())
        event_id = hashlib.sha256(
            f"{self.tenant_id}|{incident_id}|TRIAGE_COMPLETED".encode()
        ).hexdigest()[:20]
        cypher = """
        MATCH (s:Service {name:$service})
        MATCH (a1:Agent {name:$from_agent}), (a2:Agent {name:$to_agent})
        MERGE (i:Incident {id:$incident_id})
        ON CREATE SET i.created_at=$ts
        SET i.symptom=$symptom, i.updated_at=$ts
        WITH i,s,a1,a2
        MERGE (i)-[:AFFECTS]->(s)
        MERGE (m:EpisodicMemory {event_id:$event_id})
        ON CREATE SET m.agent=$from_agent, m.action='TRIAGE_COMPLETED',
                      m.note='Incident linked to service topology; state handed off.',
                      m.timestamp=$ts, m.sequence=1
        MERGE (i)-[:HAS_MEMORY]->(m)
        MERGE (h:Handoff {id:$handoff_id})
        ON CREATE SET h.incident_id=$incident_id, h.from_agent=$from_agent,
                      h.to_agent=$to_agent, h.state='TRIAGED',
                      h.created_at=$ts, h.status='PENDING'
        MERGE (a1)-[:CREATED_HANDOFF]->(h)
        MERGE (h)-[:DELIVERED_TO]->(a2)
        SET i.status=CASE WHEN i.status IN ['RESOLVED','VERIFIED_RECOVERY']
                          THEN i.status ELSE 'TRIAGED' END
        RETURN i.id, s.name, h.id, h.state
        """
        handoff_id = f"{incident_id}:TRIAGE:{to_agent}"
        self._query(cypher, {"service": affected_service, "from_agent": from_agent,
            "to_agent": to_agent, "incident_id": incident_id, "symptom": symptom,
            "ts": ts, "event_id": event_id, "handoff_id": handoff_id})
        return {"cypher": cypher.strip(), "handoff_id": handoff_id, "timestamp": ts}

    def trace_root_cause_across_graph(self, incident_id: str) -> Dict[str, Any]:
        """Return ranked candidates; a recent commit is evidence, not proof of causation."""
        cypher = """
        MATCH (i:Incident {id:$incident_id})-[:AFFECTS]->(entry:Service)
        MATCH p=(entry)-[:DEPENDS_ON*1..4]->(root:Service)
        MATCH (eng:Engineer)-[:AUTHORED]->(c:Commit)-[:DEPLOYED_TO]->(root)
        RETURN entry.name AS entry_service, root.name AS root_service,
               c.hash AS commit_hash, c.message AS commit_msg,
               c.timestamp AS commit_timestamp, eng.name AS engineer,
               [n IN nodes(p) | n.name] AS dependency_path
        ORDER BY c.timestamp DESC
        """
        res = self._query(cypher, {"incident_id": incident_id})
        candidates = []
        for r in res.result_set:
            candidate = {"entry_service": r[0], "root_service": r[1],
                "commit_hash": r[2], "commit_msg": r[3],
                "commit_timestamp": r[4], "engineer": r[5],
                "dependency_path": r[6]}
            if candidate not in candidates:
                candidates.append(candidate)
        if not candidates:
            return {"found": False, "candidates": [], "reason":
                    "No reachable service has linked deployment provenance."}
        return {"found": True, "candidates": candidates,
                "selected": candidates[0],
                "selection_note": "Candidate ranked by deployment timestamp; this is not causal proof."}

    def record_diagnosis_and_handoff(self, incident_id: str, root_service: str,
                                     commit_hash: str, finding: str,
                                     evidence: Optional[dict] = None) -> Dict[str, Any]:
        ts = int(time.time())
        event_id = hashlib.sha256(
            f"{self.tenant_id}|{incident_id}|ROOT_CAUSE_CANDIDATE".encode()
        ).hexdigest()[:20]
        cypher = """
        MATCH (i:Incident {id:$incident_id})
        MATCH (root:Service {name:$root_service})
        MATCH (c:Commit {hash:$commit_hash})
        MATCH (a2:Agent {name:'DiagnosisAgent'}), (a3:Agent {name:'RemediationAgent'})
        SET i.status='DIAGNOSED', i.updated_at=$ts
        MERGE (i)-[:CANDIDATE_CAUSED_BY_SERVICE]->(root)
        MERGE (i)-[:CANDIDATE_CAUSED_BY_COMMIT]->(c)
        MERGE (mem:EpisodicMemory {event_id:$event_id})
        ON CREATE SET mem.agent='DiagnosisAgent', mem.action='ROOT_CAUSE_CANDIDATE',
                      mem.note=$finding, mem.timestamp=$ts, mem.sequence=2,
                      mem.evidence_json=$evidence_json
        MERGE (i)-[:HAS_MEMORY]->(mem)
        MERGE (h:Handoff {id:$handoff_id})
        ON CREATE SET h.incident_id=$incident_id, h.from_agent='DiagnosisAgent',
                      h.to_agent='RemediationAgent', h.state='DIAGNOSED',
                      h.created_at=$ts, h.status='PENDING'
        MERGE (a2)-[:CREATED_HANDOFF]->(h)
        MERGE (h)-[:DELIVERED_TO]->(a3)
        RETURN i.id, i.status
        """
        handoff_id = f"{incident_id}:DIAGNOSIS:RemediationAgent"
        self._query(cypher, {"incident_id": incident_id, "root_service": root_service,
            "commit_hash": commit_hash, "finding": finding, "ts": ts,
            "event_id": event_id, "handoff_id": handoff_id,
            "evidence_json": str(evidence or {})})
        return {"cypher": cypher.strip(), "handoff_id": handoff_id}

    def fetch_or_learn_playbook(self, incident_id: str, root_service: str,
                                issue_type: str) -> Dict[str, Any]:
        """Retrieve approved procedure or persist a proposed safe plan; never execute commands."""
        lookup = """
        MATCH (pb:Playbook {target_service:$service, issue_type:$issue_type})
        OPTIONAL MATCH (pb)-[:HAS_STEP]->(s:Step)
        RETURN pb.id, pb.status, pb.source, s.order, s.cmd
        ORDER BY s.order
        """
        res = self._query(lookup, {"service": root_service, "issue_type": issue_type})
        rows = list(res.result_set)
        if rows:
            pb_id = rows[0][0]
            status = rows[0][1] or "UNKNOWN"
            steps = [{"order": r[3], "description": r[4]} for r in rows if r[4]]
            mode = "RECALLED_FROM_PROCEDURAL_MEMORY"
            pb_status = status
        else:
            digest = hashlib.sha256(
                f"{self.tenant_id}|{root_service}|{issue_type}".encode()
            ).hexdigest()[:10]
            pb_id = f"PB-PROPOSED-{digest}"
            # Safe, human-readable recommendations. No shell execution.
            steps = [
                {"order": 1, "description": f"Collect recent telemetry and logs for {root_service}."},
                {"order": 2, "description": "Compare the incident window with recent deployment events."},
                {"order": 3, "description": "Propose a rollback or mitigation only after operator review."},
                {"order": 4, "description": "Run a health check and record the result before resolving."},
            ]
            create = """
            MERGE (pb:Playbook {id:$pb_id})
            ON CREATE SET pb.target_service=$service, pb.issue_type=$issue_type,
                          pb.status='PROPOSED', pb.source='generated_template',
                          pb.created_at=$ts,
                          pb.description='Unverified plan. Human approval and validation required.'
            """
            self._query(create, {"pb_id": pb_id, "service": root_service,
                                 "issue_type": issue_type, "ts": int(time.time())})
            for step in steps:
                sid = f"{pb_id}-S{step['order']}"
                self._query("""
                MATCH (pb:Playbook {id:$pb_id})
                MERGE (s:Step {id:$step_id})
                ON CREATE SET s.order=$order, s.cmd=$description
                MERGE (pb)-[:HAS_STEP]->(s)
                """, {"pb_id": pb_id, "step_id": sid, "order": step["order"],
                      "description": step["description"]})
            mode = "PROPOSED_AND_PERSISTED"
            pb_status = "PROPOSED"

        event_id = hashlib.sha256(
            f"{self.tenant_id}|{incident_id}|PLAYBOOK_{pb_status}".encode()
        ).hexdigest()[:20]
        note = f"Playbook {pb_id} status={pb_status}; no commands were executed."
        self._query("""
        MATCH (i:Incident {id:$incident_id})
        MERGE (pb:Playbook {id:$pb_id})
        MERGE (i)-[:HAS_PROPOSED_REMEDIATION]->(pb)
        MERGE (m:EpisodicMemory {event_id:$event_id})
        ON CREATE SET m.agent='RemediationAgent', m.action=$action,
                      m.note=$note, m.timestamp=$ts, m.sequence=3
        MERGE (i)-[:HAS_MEMORY]->(m)
        SET i.status=CASE WHEN i.status='VERIFIED_RECOVERY' THEN i.status
                          ELSE 'AWAITING_APPROVAL' END,
            i.updated_at=$ts
        """, {"incident_id": incident_id, "pb_id": pb_id, "event_id": event_id,
              "action": mode, "note": note, "ts": int(time.time())})
        return {"playbook_id": pb_id, "mode": mode, "playbook_status": pb_status,
                "steps": steps, "commands_executed": False,
                "incident_status": "AWAITING_APPROVAL"}

    def record_recovery_verification(self, incident_id: str, success: bool,
                                     evidence: str) -> Dict[str, Any]:
        """Record an external/mock health-check result; only success resolves incident."""
        ts = int(time.time())
        state = "VERIFIED_RECOVERY" if success else "RECOVERY_FAILED"
        event_id = hashlib.sha256(
            f"{self.tenant_id}|{incident_id}|{state}|{evidence}".encode()
        ).hexdigest()[:20]
        self._query("""
        MATCH (i:Incident {id:$incident_id})
        SET i.status=$status, i.updated_at=$ts, i.verification_evidence=$evidence
        MERGE (m:EpisodicMemory {event_id:$event_id})
        ON CREATE SET m.agent='RemediationAgent', m.action=$status,
                      m.note=$evidence, m.timestamp=$ts, m.sequence=4
        MERGE (i)-[:HAS_MEMORY]->(m)
        """, {"incident_id": incident_id, "status": state, "ts": ts,
              "evidence": evidence, "event_id": event_id})
        return {"status": state, "verified": bool(success), "evidence": evidence}

    def get_verifiable_audit_trail(self, incident_id: str) -> List[Dict[str, Any]]:
        cypher = """
        MATCH (i:Incident {id:$incident_id})-[:HAS_MEMORY]->(m:EpisodicMemory)
        RETURN m.timestamp AS ts, m.sequence AS sequence, m.agent AS agent,
               m.action AS action, m.note AS note, m.evidence_json AS evidence
        ORDER BY sequence ASC, ts ASC
        """
        res = self._query(cypher, {"incident_id": incident_id})
        return [{"timestamp": r[0], "sequence": r[1], "agent": r[2],
                 "action": r[3], "reasoning": r[4], "evidence": r[5]}
                for r in res.result_set]
