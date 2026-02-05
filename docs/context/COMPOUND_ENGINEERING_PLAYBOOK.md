# Compound Engineering Playbook

Last updated: 2026-02-04

Purpose: compound reliability by iterating small fixes with proofs, then distilling the result into reusable context.

## Loop
1. Reproduce
- Capture baseline behavior.
- Identify the exact failure point.

2. Diagnose
- Form 2–3 hypotheses.
- Prove or eliminate each with repo evidence or logs.

3. Minimal Fix
- Apply the smallest change that resolves the root cause.
- Preserve tenant and twin scoping.
- Never clear user state on transient errors.

4. Prove
- Re-run the relevant proof script.
- Capture evidence in `proof/`.

5. Distill
- Update the context pack.
- Update the contract matrix and drift report if changed.
- Add the fix to `SIMPLIFICATION_CHANGELOG.md` if it reduces complexity.

## Phase Targets
- Phase 3: ingestion artifacts are created and verified.
- Phase 4: public share retrieval and widget streaming are proven.
- Phase 6: UI + API smoke proof with artifacts.

## Automation
- API proof: `python scripts/run_api_proof.py`
- UI smoke: `node frontend/scripts/critical_path_smoke.mjs`
- Context pack: `python scripts/context_pack.py`
