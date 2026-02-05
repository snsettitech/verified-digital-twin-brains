# Context Engineering Playbook

Last updated: 2026-02-04

Purpose: minimize tokens and maximize correctness by making a small, reusable context pack and a repeatable workflow for loading it.

## Core Principles
- Context is a product: smaller, fresher, and task-shaped.
- Always prefer deterministic sources over conversational memory.
- Every task starts from the same minimal pack; expand only if necessary.
- Track drift and prove relevance before widening scope.

## Standard Context Pack (Required)
Produce a single pack with:
- Critical path map
- Canonical contracts and drift report
- Proof artifacts summary
- Working set of files
- Open questions and hypotheses
- Commands to reproduce

## Context Pack Inputs (Project-Specific)
- `CRITICAL_PATH_CALL_GRAPH.md`
- `CRITICAL_PATH_CONTRACT_MATRIX.md`
- `FE_BE_DRIFT_REPORT.md`
- `INGESTION_PROOF_PACKET.md`
- `PUBLIC_RETRIEVAL_PROOF_PACKET.md`
- `PHASE_D_FINAL_PROOF.md`
- `docs/CDR-001-canonical-contracts.md`
- `SCOPE_CUT_PROPOSAL.md`
- `SIMPLIFICATION_CHANGELOG.md`
- `proof/PROOF_README.md`

## Minimal Expansion Ladder
1. Read the context pack.
2. Add only the files referenced in the pack.
3. Add the exact handler/component for the failing route.
4. Add only the module the handler depends on.
5. Stop and summarize before expanding further.

## Working Set Template
- Backend routers and modules for the affected path
- Frontend call sites only
- Database schema or migration only if touched by the route

## Output Contract
Every task output must include:
- What changed
- What to verify in UI
- Acceptance checks (pass/fail)

## Automation
Use `scripts/context_pack.py` to regenerate `artifacts/context/context_pack.md`.
Use `scripts/repo_map.py` to generate `artifacts/context/repo_map.txt`.

## Evidence-First Behavior
When labeling a module as unused or non-critical, provide evidence references from the repo and critical path contract.
