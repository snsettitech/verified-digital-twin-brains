---
description: Mandatory preload for Antigravity entries to ensure platform alignment.
---

To ensure alignment with the Digital Brains platform model, governance rules, and system invariants, follow these steps immediately upon entering the workspace:

1. **Load Core Context**:
   Use `view_file` on all files in `/docs/core/`:
   - `architecture.md`: Understand the Twin lifecycle and RAG tiers.
   - `invariants.md`: Internalize the non-negotiable isolation and ownership rules.
   - `governance.md`: Understand security guards and the AI safety gate.
   - `flows.mmd`: Visualize the request and escalation paths.

2. **Verify Environment**:
   - Check `scripts/ai-stop-hook.py` presence.
   - Run a quick `python scripts/ai-verify-governance.py` to ensure current compliance.

3. **Identify Work Area**:
   - Locate the relevant `backend/routers` or `frontend/app` paths.
   - Verify if the task touches Twins, Memory, or Actions.

4. **Planning Mode**:
   - Always enter PLANNING mode first for any logic changes.
   - Reference `/docs/core/invariants.md` in every implementation plan.
