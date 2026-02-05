---
description: Context Engineering baseline workflow for every task
---

# Context Engineering Workflow

Purpose: minimize tokens while keeping correctness by assembling a small, deterministic context pack before any change.

## 1. Context Pack (Required)
- [ ] Generate `artifacts/context/context_pack.md` with `python scripts/context_pack.py`.
- [ ] Review the pack and confirm the critical path scope.
- [ ] Expand context only if the pack references missing files.

## 2. Working Set Rules
- [ ] Open only files referenced by the pack.
- [ ] If new files are needed, document why in the task output.
- [ ] Avoid scanning unrelated directories.

## 3. Evidence Discipline
- [ ] When declaring anything unused or non-critical, cite evidence from contract/drift docs.
- [ ] Prefer contract truth over memory.

## 4. Pre-Task Checks
- [ ] Confirm backend and frontend endpoints used by the task.
- [ ] Validate twin and tenant scoping inputs.

## 5. End-of-Task Output
- [ ] What changed
- [ ] What to verify in UI
- [ ] Acceptance checks (pass/fail)
- [ ] Update `artifacts/context/context_pack.md` if scope or contracts changed
