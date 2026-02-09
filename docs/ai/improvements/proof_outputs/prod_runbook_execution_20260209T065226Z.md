# Production Runbook Execution Proof (2026-02-09)

## Scope
- Runbook executed: `docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md`
- Objective: fix production blockers first, then execute deployment verification.

## What was fixed
1. Render production CORS policy:
   - `ALLOWED_ORIGINS` updated from wildcard behavior to explicit Vercel allowlist.
2. Redis/runtime consistency:
   - `REDIS_URL` set for both API and worker.
3. Feedback-learning production controls:
   - `FEEDBACK_LEARNING_MIN_EVENTS=5`
   - `FEEDBACK_LEARNING_COOLDOWN_MINUTES=30`
   - `FEEDBACK_LEARNING_AUTO_PUBLISH=false`
   - `FEEDBACK_LEARNING_RUN_REGRESSION_GATE=true`
4. Frontend runtime policy alignment:
   - `frontend/package.json` engine updated from `20.x` to `>=20 <25` to match active Vercel runtime band.

## Deploy evidence
- API deploy:
  - service: `srv-d55qmb95pdvs73cagk60`
  - deploy: `dep-d64o5rsr85hc73c0c5dg`
  - status: `live`
  - finished: `2026-02-09T06:50:39.793402Z`
- Worker deploy:
  - service: `srv-d5ht2763jp1c73evn1dg`
  - deploy: `dep-d64o5sfgi27c73b622lg`
  - status: `live`
  - finished: `2026-02-09T06:50:22.710722Z`

## Runtime verification
- API health:
  - `GET https://verified-digital-twin-brains.onrender.com/health` -> `healthy`
- CORS verification:
  - allowed origin `https://digitalbrains.vercel.app` preflight -> `200`, `Access-Control-Allow-Origin` echoed correctly.
  - blocked origin `https://evil.example.com` preflight -> `400`, no allow-origin header.
- Worker validation:
  - startup log confirms Redis connectivity: `[Worker] Connected to Redis queue`.
- Error window check:
  - Render error logs in `2026-02-09T06:35:00Z..2026-02-09T06:55:00Z`:
    - API: `0`
    - Worker: `0`
- Frontend production domain:
  - `https://digitalbrains.vercel.app` -> `200` (server: `Vercel`).

## Vercel runtime state
- project: `prj_tye8zjjKLvhdjH2pyBXno8JaylYk`
- current Node version: `24.x`
- repository engine policy: `>=20 <25`
- status: aligned (no manual runtime-setting blocker remains)

## Evidence JSON
- `docs/ai/improvements/proof_outputs/prod_runbook_execution_20260209T065226Z.json`
