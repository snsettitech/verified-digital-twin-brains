# Phase 3.4: Research Orchestrator (State Machine + Checkpointing)

## Summary

Phase 3.4 implements the coordination layer that manages research run lifecycle, pauses at confirmation gates, and resumes when all confirmations are resolved. The orchestrator explicitly stops at `ready_for_ingestion` state (Phase 3.5 will handle actual ingestion continuation).

## Files Created

### Core Module
- **`backend/modules/research_orchestrator.py`** - Main orchestrator implementation with state machine and checkpointing

### Database Migration
- **`backend/database/migrations/migration_phase_3_4_research_orchestrator.sql`** - Adds columns to `research_runs` table for state machine support

### Tests
- **`backend/tests/test_research_orchestrator.py`** - Comprehensive tests for state machine, checkpoint data, and transition logic

### API Updates
- **`backend/routers/crawl.py`** - Updated with orchestrator integration and new endpoints

## State Machine

```
planning -> queued -> crawling -> awaiting_confirmation -> ready_for_ingestion
                                          |                     |
                                          v                     v
                                    timed_out (on timeout)   completed (Phase 3.5+)
```

### Valid Transitions

| From | To | Condition |
|------|-----|-----------|
| planning | queued | Run created from onboarding |
| queued | crawling | Crawl job started |
| crawling | awaiting_confirmation | Unresolved confirmations exist |
| crawling | ready_for_ingestion | All confirmations auto-resolved |
| awaiting_confirmation | awaiting_confirmation | Self-transition (refresh) |
| awaiting_confirmation | ready_for_ingestion | All confirmations resolved |
| awaiting_confirmation | timed_out | 24h timeout expired |
| timed_out | ready_for_ingestion | Proceed after timeout |
| ready_for_ingestion | completed | Phase 3.5 (ingestion complete) |
| * | failed | Error handling |

### Terminal States
- `completed` - Full research workflow finished
- `failed` - Error occurred, workflow halted
- `ready_for_ingestion` - Phase 3.4 terminal (Phase 3.5 continues)

## Key Components

### ResearchOrchestrator

Main class coordinating the research run lifecycle:

```python
orchestrator = ResearchOrchestrator(
    confirmation_timeout_hours=24  # Configurable timeout
)

# Create research run from onboarding
run = await orchestrator.create_research_run(
    twin_id="twin-123",
    actor_user_id="user-456",
    claimed_identity={"full_name": "Test User", ...},
    seed_urls=["https://example.com"]
)

# After crawl completes
result = await orchestrator.on_crawl_completed(
    research_run_id=run.research_run_id,
    twin_id="twin-123",
    crawl_id="crawl-789"
)

# After user confirms/rejects
result = await orchestrator.on_confirmations_updated(
    research_run_id=run.research_run_id,
    twin_id="twin-123"
)
```

### Checkpoint Data

Stored in `research_runs.checkpoint_data` as JSON:

```python
{
    "phase": "awaiting_confirmation",
    "last_transition_at": "2026-02-23T23:00:00Z",
    "crawl_id": "crawl-789",
    "confirmation": {
        "total": 10,
        "pending": 3,
        "manual_review": 1,
        "auto_confirmed": 4,
        "auto_rejected": 2,
        "confirmed": 0,
        "rejected": 0,
        "all_resolved": false,
        "resolution_percent": 70.0
    },
    "claimed_identity": {"full_name": "Test User", ...},
    "seed_urls_count": 2,
    "timeout_at": "2026-02-24T23:00:00Z",
    "warnings": ["Some items unresolved"]
}
```

## API Endpoints

### New Phase 3.4 Endpoints

#### Create Research Run
```http
POST /twins/{twin_id}/research
```
Creates a new research run from onboarding input.

**Request:**
```json
{
    "claimed_identity": {"full_name": "Test User", ...},
    "seed_urls": ["https://example.com"],
    "onboarding_session_id": "optional-session-id",
    "metadata": {}
}
```

#### Get Research Run Status
```http
GET /twins/{twin_id}/research/{research_run_id}
```
Returns full status including checkpoint data and confirmation summary.

**Response:**
```json
{
    "research_run_id": "...",
    "status": "awaiting_confirmation",
    "crawl_id": "crawl-789",
    "checkpoint_data": {...},
    "confirmation_summary": {...},
    "next_action": "wait_for_confirmation",
    "warnings": []
}
```

#### Force Status Transition (Admin/Debug)
```http
POST /twins/{twin_id}/research/{research_run_id}/transition/{new_status}
```

### Updated Phase 3.3 Endpoints

The following endpoints now trigger orchestrator state transitions:

#### Resolve Single Confirmation
```http
POST /twins/{twin_id}/research/{research_run_id}/confirmations/{confirmation_id}
```
Now includes orchestrator response:
```json
{
    "confirmation_id": "...",
    "previous_status": "pending",
    "new_status": "confirmed",
    "run_status": "ready_for_ingestion",
    "run_transition": "All confirmations resolved by user"
}
```

#### Bulk Resolve Confirmations
```http
POST /twins/{twin_id}/research/{research_run_id}/bulk-confirm
```
Also includes orchestrator state transition feedback.

## Behavior Contracts

### Phase 3.4 Stops at `ready_for_ingestion`

Phase 3.4 does NOT continue to ingestion. The orchestrator:
1. Creates research run → `planning`
2. Transitions → `queued`
3. Marks crawl started → `crawling`
4. On crawl completion:
   - If unresolved confirmations → `awaiting_confirmation`
   - If all auto-resolved → `ready_for_ingestion`
5. On confirmation resolution:
   - If all resolved → `ready_for_ingestion`
   - Else remain in `awaiting_confirmation`
6. On timeout → `timed_out` → `ready_for_ingestion`
7. **STOPS** at `ready_for_ingestion`

Phase 3.5 will handle:
- Ingestion continuation from `ready_for_ingestion`
- Transition to `completed`

### Timeout Policy

- Default timeout: 24 hours after entering `awaiting_confirmation`
- On timeout:
  1. Transition to `timed_out` status
  2. Preserve unresolved counts in checkpoint warnings
  3. Transition to `ready_for_ingestion`
  4. Do NOT ingest in Phase 3.4

### User Override Policy

Users CAN override:
- `auto_confirmed` → `rejected`
- `auto_rejected` → `confirmed`

Users CANNOT change:
- `confirmed` → anything (terminal)
- `rejected` → anything (terminal)

`manual_review` MUST be resolved by user (no auto-transition).

## Integration Points

### Phase 3.3 Confirmation System

Option A was implemented (non-invasive): `on_confirmations_updated()` is called from existing resolve/bulk_resolve endpoints.

```python
# In resolve_confirmation_endpoint:
result = await manager.resolve_confirmation(...)

# Notify orchestrator
orchestrator = ResearchOrchestrator()
transition_result = await orchestrator.on_confirmations_updated(
    research_run_id=research_run_id,
    twin_id=twin_id,
)
```

### Phase 3.5 Ingestion Bridge

Deferred to Phase 3.5:
- `crawl_ingestion_bridge.py` confirmation gate behavior modification
- Ingestion continuation when research run reaches `ready_for_ingestion`

### Phase 4+ Bio Generation

Deferred to Phase 4+:
- Bio generation trigger
- Mind score updates

## Testing

```bash
# Run Phase 3.4 tests
pytest backend/tests/test_research_orchestrator.py -v

# All 22 tests pass
# - 8 state machine transition tests
# - 3 checkpoint data tests
# - 5 phase contract tests
# - 1 repository test
# - 3 error handling tests
# - 1 integration summary test
```

## Migration

Run the migration to add required columns:

```bash
# Add crawl_id, onboarding_session_id, started_at to research_runs
psql -f backend/database/migrations/migration_phase_3_4_research_orchestrator.sql
```

## Feature Flags

- `DEEP_RESEARCH_ENABLED` - Master feature flag
- `DEEP_RESEARCH_GLOBAL_DISABLE` - Global kill switch
- Phase-specific flags available in `deep_research_config.py`

## Next Steps

Phase 3.5 will:
1. Modify `crawl_ingestion_bridge.py` to check research run status
2. Only ingest confirmed sources when in `ready_for_ingestion` state
3. Transition from `ready_for_ingestion` to `completed`
4. Trigger bio generation and mind score updates
