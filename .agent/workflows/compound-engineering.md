---
description: Compound engineering loop for critical path stability
---

# Compound Engineering Workflow

Purpose: compound reliability by looping minimal fixes with proofs and distilled context.

## 1. Reproduce
- [ ] Capture baseline with `python scripts/run_api_proof.py` when API is involved.
- [ ] Capture UI baseline with `node frontend/scripts/critical_path_smoke.mjs` when UI is involved.

## 2. Diagnose
- [ ] Form 2–3 hypotheses.
- [ ] Prove or eliminate each with logs, contract docs, or targeted file inspection.

## 3. Minimal Fix
- [ ] Apply the smallest possible change.
- [ ] Preserve tenant and twin scoping.
- [ ] Never clear user state on transient errors.

## 4. Prove Again
- [ ] Re-run the same proof that failed.
- [ ] Capture updated artifacts in `proof/`.

## 5. Distill & Store
- [ ] Update `INGESTION_PROOF_PACKET.md` or `PUBLIC_RETRIEVAL_PROOF_PACKET.md`.
- [ ] Update `PHASE_D_FINAL_PROOF.md` if proofs changed.
- [ ] Regenerate `artifacts/context/context_pack.md`.

## 6. Scope Hygiene
- [ ] If a fix reduces complexity, record it in `SIMPLIFICATION_CHANGELOG.md`.
- [ ] If a new drift is found, record it in `FE_BE_DRIFT_REPORT.md`.
