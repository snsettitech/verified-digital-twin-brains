# DeepAgents Telemetry And Rollout Alerts

## Overview
This runbook covers DeepAgents telemetry counters and rollout gating for owner, widget, and public chat surfaces.

Counter model:
- Every counter is emitted as per-turn `0|1`.
- "Rate" means `sum(counter) / total_turns` in the selected window.

Code references:
- Counter extraction and trace/log emission: `backend/routers/chat.py:336`
- Counter payload in owner metadata: `backend/routers/chat.py:2000`
- Counter payload in widget metadata: `backend/routers/chat.py:2553`
- Public guard flag assignment: `backend/routers/chat.py:3028`
- Allowlist parsing and enforcement: `backend/modules/deepagents_executor.py:26`, `backend/modules/deepagents_executor.py:126`

## Field Dictionary
| Field | Type | Emits `1` when | Route Scope | Code Reference |
|---|---|---|---|---|
| `deepagents_route_rate` | int (`0|1`) | Query ran through DeepAgents execution lane | owner, widget | `backend/modules/agent.py:907` |
| `deepagents_forbidden_context_rate` | int (`0|1`) | DeepAgents denied due to public/anonymous context | owner, widget (from planner telemetry) | `backend/modules/agent.py:909` |
| `deepagents_missing_params_rate` | int (`0|1`) | DeepAgents returned missing params | owner, widget | `backend/modules/agent.py:912` |
| `deepagents_needs_approval_rate` | int (`0|1`) | DeepAgents produced pending approval plan | owner, widget | `backend/modules/agent.py:913` |
| `deepagents_executed_rate` | int (`0|1`) | DeepAgents executed action directly | owner, widget | `backend/modules/agent.py:914` |
| `public_action_query_guarded_rate` | int (`0|1`) | Public action-like query was guard-blocked from action lane | public | `backend/routers/chat.py:3028` |
| `selection_recovery_failure_rate` | int (`0|1`) | Selection reply detected but prior intent could not be recovered | owner, widget | `backend/modules/agent.py:1478`, `backend/modules/agent.py:1708` |

Notes:
- `deepagents_forbidden_context_rate` tracks context-forbidden only (`DEEPAGENTS_FORBIDDEN_CONTEXT`) and does not include allowlist-forbidden (`DEEPAGENTS_NOT_ALLOWLISTED`).
- Public/share/widget are always execution-forbidden before allowlist evaluation.

## Emission Surfaces
- Langfuse metadata:
  - `update_current_observation(metadata=payload)` and `update_current_trace(metadata=payload)` at `backend/routers/chat.py:378`
- Server logs:
  - JSON line: `{"component":"chat_telemetry","event":"turn_counters",...}` at `backend/routers/chat.py:374`
- Metadata to UI:
  - owner stream metadata includes `turn_counters` at `backend/routers/chat.py:2000`
  - widget stream metadata includes `turn_counters` at `backend/routers/chat.py:2553`

## Aggregation Guidance
Recommended defaults:
- Window: 10m for paging, 30m for trend analysis.
- Minimum sample size before alerting:
  - owner/widget counters: at least 100 turns/window
  - public guard counters: at least 50 public turns/window

Rate formulas:
- `deepagents_missing_params_pct = sum(deepagents_missing_params_rate) / count(*)`
- `public_action_guarded_pct = sum(public_action_query_guarded_rate) / count(*)`

Anti-noise safeguards:
- Require threshold breach for 2 consecutive windows.
- Ignore windows below minimum sample size.
- For P1, require both rate breach and absolute count floor (for example `>= 10` events).

## Alert Thresholds
### P1 Pager
- `selection_recovery_failure_rate > 0.08` for 2x 10m windows and `>= 10` failures
  - Risk: follow-up loops and degraded conversational recovery.
- `deepagents_forbidden_context_rate > 0.05` on owner/widget traffic for 2x 10m windows
  - Risk: auth/context regression routing owner requests as forbidden context.

### P2 Ticket
- `deepagents_missing_params_rate > 0.35` for 30m
  - Risk: action parsing/parameter extraction quality drop.
- `deepagents_needs_approval_rate < 0.60` while `DEEPAGENTS_REQUIRE_APPROVAL=true` for 30m
  - Risk: approval path drift or lane mis-routing.
- `deepagents_executed_rate > 0` while `DEEPAGENTS_REQUIRE_APPROVAL=true` for 10m
  - Risk: unexpected direct execution.

### Informational Monitors
- `deepagents_route_rate` by twin and tenant.
- `public_action_query_guarded_rate` by public endpoint.

## Example Queries
Adapt to your telemetry backend.

Counter totals:
```sql
SELECT
  date_trunc('minute', ts) AS minute_bucket,
  sum((payload->>'deepagents_route_rate')::int) AS deepagents_route_count,
  sum((payload->>'deepagents_forbidden_context_rate')::int) AS deepagents_forbidden_context_count,
  sum((payload->>'deepagents_missing_params_rate')::int) AS deepagents_missing_params_count,
  sum((payload->>'deepagents_needs_approval_rate')::int) AS deepagents_needs_approval_count,
  sum((payload->>'deepagents_executed_rate')::int) AS deepagents_executed_count,
  sum((payload->>'public_action_query_guarded_rate')::int) AS public_action_guarded_count,
  sum((payload->>'selection_recovery_failure_rate')::int) AS selection_recovery_failure_count,
  count(*) AS total_turns
FROM logs
WHERE component = 'chat_telemetry'
  AND event = 'turn_counters'
  AND ts >= now() - interval '60 minutes'
GROUP BY 1
ORDER BY 1 DESC;
```

Public guard percentage:
```sql
SELECT
  100.0 * sum((payload->>'public_action_query_guarded_rate')::int) / nullif(count(*), 0) AS guarded_pct
FROM logs
WHERE component = 'chat_telemetry'
  AND event = 'turn_counters'
  AND ts >= now() - interval '10 minutes';
```

## Rollout Gating
Environment variables:
- `DEEPAGENTS_ENABLED`
- `DEEPAGENTS_REQUIRE_APPROVAL`
- `DEEPAGENTS_MAX_STEPS`
- `DEEPAGENTS_TIMEOUT_SECONDS`
- `DEEPAGENTS_ALLOWLIST_TWIN_IDS`
- `DEEPAGENTS_ALLOWLIST_TENANT_IDS`

Allowlist semantics:
- If both allowlists are empty, owner contexts are eligible (subject to other flags).
- If either allowlist is non-empty, only matching twin or tenant IDs are eligible.
- Public/share/widget contexts are always forbidden regardless of allowlist (`backend/modules/deepagents_executor.py:114`).

Examples:
- Single twin: `DEEPAGENTS_ALLOWLIST_TWIN_IDS=twin_abc123`
- Multiple twins: `DEEPAGENTS_ALLOWLIST_TWIN_IDS=twin_a,twin_b,twin_c`
- Tenant rollout: `DEEPAGENTS_ALLOWLIST_TENANT_IDS=tenant_prod_1,tenant_prod_2`

## Runbook
1. Check deploy flags and allowlists.
2. Verify counters are arriving:
   - Langfuse trace metadata contains `turn_counters`.
   - Logs contain `component=chat_telemetry event=turn_counters`.
3. If `selection_recovery_failure_rate` spikes:
   - Replay founder clarifier sequence.
   - Check recent planner telemetry for `planner.intent_recovered`.
4. If `deepagents_forbidden_context_rate` spikes on owner traffic:
   - Inspect interaction context classification and auth identity payloads.
5. If `deepagents_missing_params_rate` spikes:
   - Sample recent action prompts and missing params returned by lane.

## Deploy Validation Checklist
- Owner chat:
  - action prompt emits `deepagents_route_rate=1`
  - approval path emits `deepagents_needs_approval_rate=1`
- Public/share:
  - action-like prompt yields `public_action_query_guarded_rate=1`
  - no action execution metadata in public payload
- Logs:
  - grep for `\"component\":\"chat_telemetry\",\"event\":\"turn_counters\"`
- Langfuse:
  - verify turn metadata includes all seven counter fields
