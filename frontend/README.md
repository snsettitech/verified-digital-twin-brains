# Frontend

Next.js 16 App Router frontend for the Verified Digital Twin Brains dashboard and public share flows.

## Local Run

```bash
cd frontend
npm ci
copy .env.example .env.local
npm run dev
```

## Important Files

- `app/`: route entrypoints
- `proxy.ts`: auth/session gate
- `lib/`: API, auth, feature flags, shared state
- `components/`: UI building blocks
- `tests/e2e/`: Playwright coverage

Use [`../DEBUG_RUNBOOK.md`](../DEBUG_RUNBOOK.md) for the end-to-end local startup and smoke test.
