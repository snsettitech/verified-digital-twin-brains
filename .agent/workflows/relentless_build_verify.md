---
description: Relentless Build–Verify Loop (Always On) - Mandatory Execution Loop
---

# Relentless Build–Verify Loop (Mandatory)

**Global Rule:** Assume the system is broken until proven working end-to-end.

## 1. Mandatory Execution Loop (Non-Optional)
For every task or fix, you MUST follow this loop until completion criteria are met:

### **A. Reproduce**
*   **Reproduce the issue** or target behavior in a real environment.
*   **Identify the exact failure point** (UI, API, auth, DB, background job, retrieval, cache, deployment).

### **B. Diagnose**
*   **Generate and rank root-cause hypotheses** by likelihood.
*   **Use evidence**: logs, traces, browser dev tools, network inspection.

### **C. Fix**
*   **Implement the smallest correct fix** tied to a validated cause.
*   **Do NOT implement speculative or cosmetic changes.**

### **D. Verify**
Verify end-to-end:
1.  **UI behavior**
2.  **Network requests/responses**
3.  **Backend logic**
4.  **Database state**
5.  **Async/background processes**
6.  **Final user-visible outcome**

### **E. Loop**
*   If the target functionality is not fully working, **return to step B (Diagnose)**.
*   Continue looping until success is proven.

---

## 2. Definition of “Done” (Hard Rule)
A task is **NOT complete** unless:
1.  The focused functionality works in a real execution.
2.  Acceptance criteria are explicitly met.
3.  Behavior is repeatable across refreshes/sessions.
4.  No blocking errors remain in logs or network calls.

---

## 3. Tooling Requirements
**Use Browser Tools and Developer Tools by default** when UI or integrations are involved.
*   **Inspect**:
    *   Network
    *   Console
    *   Auth/session
    *   Storage (local/session)
    *   API payloads
*   **Add temporary instrumentation** if visibility is insufficient.

---

## 4. “Stuck” Protocol (Required)
If progress stalls:
1.  **Generate 10 distinct debugging strategies** across layers: frontend, auth, API, DB, background jobs, cache, env, deployment, third-party services, architecture.
2.  **Select the best strategy** and execute it decisively.

---

## 5. External Reference Rule
When unsure:
1.  **Research at least 10 GitHub repositories** implementing similar functionality.
2.  **Extract best patterns** (architecture, edge-case handling, tests).
3.  **Adapt the best implementation**, not the first.

---

## 6. Escalation Rule
If blocked after exhaustive attempts:
1.  **Ask the user precise, high-signal questions** with evidence: logs, errors, screenshots, remaining hypotheses.
2.  **Do NOT guess silently.**

---

## 7. Behavioral Expectations
*   Operate like a **principal engineer** owning a production incident.
*   Avoid optimism bias (“this should work”).
*   **Do not stop early.** Prove correctness.
