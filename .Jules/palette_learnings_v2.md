## 2026-02-05 - [Mocking Pydantic Models and Clients]
**Learning:** When mocking DB responses that populate Pydantic models, ensure *all* required fields (including `created_at`, `updated_at`, `status`) are present in the mock data, or validation will fail. Also, remember to mock both synchronous and asynchronous clients if the code uses both (e.g., `get_openai_client` vs `get_async_openai_client`).
**Action:** Review mock setup in tests to match Pydantic schemas exactly. Use `pnpm` setup actions in CI/CD for frontend if using `pnpm-lock.yaml`.
