# DeepAgents Telemetry And Rollout Alerts

## Scope
This document defines production telemetry counters, alert thresholds, and staged rollout checks for the DeepAgents execution lane and public safety guards.

## Counters
These counters are emitted per turn in trace metadata and server logs (`component=chat_telemetry`, `event=turn_counters`):

- `deepagents_route_rate`
- `deepagents_forbidden_context_rate`
- `deepagents_missing_params_rate`
- `deepagents_needs_approval_rate`
- `deepagents_executed_rate`
- `public_action_query_guarded_rate`
- `selection_recovery_failure_rate`

All counters are `0|1` at turn granularity.

## Emission Points
- Owner and widget metadata payloads expose counters under `turn_counters`.
- Public action-like prompts are guarded and counted via `public_action_query_guarded_rate`.
- Trace metadata is updated on each turn via `langfuse_context.update_current_trace`.
- Server logs emit JSON lines for aggregation.

## Alert Thresholds
Use a 10-minute rolling window unless specified otherwise.

### P1 Pager
- `deepagents_forbidden_context_rate` > 5% of owner traffic for 10m
  - Indicates owner traffic misclassified as public/anonymous or identity/auth regression.
- `selection_recovery_failure_rate` > 8% for 10m
  - Indicates clarification follow-up regression and loop risk.

### P2 Ticket
- `deepagents_missing_params_rate` > 35% for 30m
  - Signals degraded parameter extraction quality.
- `deepagents_needs_approval_rate` drops below 60% while `DEEPAGENTS_REQUIRE_APPROVAL=true` for 30m
  - Indicates approval gate bypass risk.
- `deepagents_executed_rate` > 0 while `DEEPAGENTS_REQUIRE_APPROVAL=true` for 10m
  - Should be zero in approval-gated mode.

### Info Monitors
- `deepagents_route_rate` trend by twin and tenant.
- `public_action_query_guarded_rate` trend on public/share endpoints.

## Example Queries
Adjust syntax to your log backend.

### Counter sum by 10m bucket
```sql
SELECT
  date_trunc('minute', ts) AS minute_bucket,
  sum((payload->>'deepagents_route_rate')::int) AS deepagents_route_count,
  sum((payload->>'deepagents_forbidden_context_rate')::int) AS deepagents_forbidden_count,
  sum((payload->>'selection_recovery_failure_rate')::int) AS selection_recovery_fail_count
FROM logs
WHERE component = 'chat_telemetry'
  AND event = 'turn_counters'
  AND ts >= now() - interval '60 minutes'
GROUP BY 1
ORDER BY 1 DESC;
```

### Public action guard hit rate
```sql
SELECT
  100.0 * sum((payload->>'public_action_query_guarded_rate')::int) / nullif(count(*), 0) AS guarded_pct
FROM logs
WHERE component = 'chat_telemetry'
  AND event = 'turn_counters'
  AND ts >= now() - interval '10 minutes';
```

## Rollout Allowlist
DeepAgents rollout allowlist is controlled by:

- `DEEPAGENTS_ALLOWLIST_TWIN_IDS` (comma-separated)
- `DEEPAGENTS_ALLOWLIST_TENANT_IDS` (comma-separated)

Behavior:
- If both allowlists are empty, DeepAgents runs for all owner contexts.
- If either allowlist is non-empty, only matching twin or tenant IDs are allowed.
- Public/share/widget contexts are always forbidden regardless of allowlist.

## Runbook Checks
1. Confirm `DEEPAGENTS_ENABLED=true` in target environment.
2. Start with a small allowlist in production.
3. Track `deepagents_route_rate` and `deepagents_forbidden_context_rate` for 30 minutes.
4. Confirm `public_action_query_guarded_rate` is non-zero on public traffic with action-like prompts.
5. Expand allowlist in controlled batches.
