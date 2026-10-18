# Pre-submission judge checklist

- [ ] `docker compose up -d` succeeds.
- [ ] `pip install -r requirements.txt` succeeds in a clean environment.
- [ ] `pytest -q` passes.
- [ ] Seed is repeatable and does not duplicate seed nodes/relationships.
- [ ] Repeat the same incident ID; no duplicate logical triage event appears.
- [ ] Restart Streamlit without resetting FalkorDB; previous playbook is retrievable.
- [ ] Unknown failure creates a `PROPOSED` playbook, not an approved one.
- [ ] No shell commands execute on the host.
- [ ] Failed verification leaves incident unresolved.
- [ ] Successful verification records `VERIFIED_RECOVERY`.
- [ ] Cross-tenant isolation test passes.
- [ ] Record screenshots and raw results for the evaluation scenarios.
