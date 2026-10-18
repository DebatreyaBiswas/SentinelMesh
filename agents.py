"""Small, explicit agent roles. No agent executes shell commands."""
from typing import Any, Dict
from memory_manager import IncidentMemoryManager


class TriageAgent:
    def __init__(self, memory: IncidentMemoryManager):
        self.name = "TriageAgent"
        self.memory = memory

    def run(self, incident_id: str, symptom: str, entry_service: str) -> Dict[str, Any]:
        pagerank = self.memory.run_pagerank_centrality()
        handoff = self.memory.create_incident_and_handoff(
            incident_id, symptom, entry_service, self.name, "DiagnosisAgent")
        # Use centrality to surface a candidate priority, but do not treat it as diagnosis.
        ranked = pagerank.get("results", [])
        return {"agent": self.name, "status": "HANDED_OFF_TO_DIAGNOSIS",
                "pagerank_analysis": pagerank,
                "priority_candidate": ranked[0] if ranked else None,
                "handoff_query": handoff["cypher"],
                "handoff_id": handoff["handoff_id"]}


class DiagnosisAgent:
    def __init__(self, memory: IncidentMemoryManager):
        self.name = "DiagnosisAgent"
        self.memory = memory

    def run(self, incident_id: str) -> Dict[str, Any]:
        trace = self.memory.trace_root_cause_across_graph(incident_id)
        if not trace.get("found"):
            return {"agent": self.name, "status": "NEEDS_MORE_EVIDENCE",
                    "error": trace.get("reason", "No supported root-cause candidate found."),
                    "trace": trace}
        candidate = trace["selected"]
        path = self.memory.find_shortest_fault_path(
            candidate["entry_service"], candidate["root_service"])
        finding = (
            f"Candidate root service={candidate['root_service']}; "
            f"commit={candidate['commit_hash']} ({candidate['commit_msg']}); "
            f"author={candidate['engineer']}. This is a candidate, not causal proof."
        )
        self.memory.record_diagnosis_and_handoff(
            incident_id, candidate["root_service"], candidate["commit_hash"],
            finding, evidence={"candidate": candidate, "path": path})
        return {"agent": self.name, "status": "HANDED_OFF_TO_REMEDIATION",
                "root_cause_trace": trace, "shortest_path_algo": path,
                "finding": finding, "requires_operator_review": True}


class RemediationAgent:
    def __init__(self, memory: IncidentMemoryManager):
        self.name = "RemediationAgent"
        self.memory = memory

    def run(self, incident_id: str, root_service: str, issue_type: str) -> Dict[str, Any]:
        result = self.memory.fetch_or_learn_playbook(incident_id, root_service, issue_type)
        return {"agent": self.name, "status": "AWAITING_APPROVAL",
                "resolution": result,
                "message": "Plan persisted for review. No host commands were executed."}
