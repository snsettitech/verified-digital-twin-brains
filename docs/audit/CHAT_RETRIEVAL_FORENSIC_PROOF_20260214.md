# Chat Retrieval Forensic Proof (2026-02-14)

## Scope
Validate and fix chat retrieval quality regressions, then verify deployment status and runtime configuration.

## 1) Code Changes Applied
Commit: `8234d56` (`main`)

Changed files:
- `backend/modules/agent.py`
- `backend/modules/retrieval.py`
- `backend/modules/tools.py`
- `backend/modules/training_sessions.py`
- `backend/routers/chat.py`
- `backend/tests/test_agent_evidence_gate.py`
- `backend/tests/test_agent_realizer.py`
- `backend/tests/test_agent_router_policy.py`
- `backend/tests/test_agent_smalltalk_planner.py`
- `backend/tests/test_chat_grounding_policy.py`
- `backend/tests/test_retrieval_pipeline.py`
- `backend/tests/test_training_sessions_expiry.py`

### Key behavior fixes
- Off-topic vector chunks are filtered before planning using anchor overlap + strong-score keep floor.
  - `backend/modules/retrieval.py:51`
  - `backend/modules/retrieval.py:98`
  - `backend/modules/retrieval.py:1118`
- Owner chat is no longer forced into teaching/uncertainty for generic coaching prompts.
  - `backend/modules/agent.py:392`
  - `backend/modules/agent.py:527`
  - `backend/modules/agent.py:765`
  - `backend/modules/agent.py:799`
- Strict grounding no longer hijacks conversational greetings/identity prompts.
  - `backend/routers/chat.py:62`
  - `backend/routers/chat.py:740`
- Group filtering can be disabled intentionally for owner chat path (prevents accidental over-restriction).
  - `backend/modules/tools.py:11`
  - `backend/modules/retrieval.py:822`
  - `backend/modules/agent.py:1005`
- Training session expiry TTL is enforced.
  - `backend/modules/training_sessions.py:17`
  - `backend/modules/training_sessions.py:42`

## 2) Test Evidence
Executed:
```bash
cd backend
python -m pytest tests/test_retrieval_pipeline.py tests/test_agent_smalltalk_planner.py tests/test_agent_router_policy.py tests/test_agent_evidence_gate.py tests/test_chat_grounding_policy.py tests/test_agent_realizer.py tests/test_training_sessions_expiry.py -q
```
Result: `59 passed`

## 3) Local Runtime Behavior Evidence
Ran multi-turn founder coaching simulation through `run_agent_stream` (same backend logic path).
Artifact:
- `artifacts/local_roleplay_transcript_20260214.txt`

Observed:
- `hi` and `who are you` route to `SMALLTALK` and return coherent responses.
- Generic founder coaching prompts route to non-owner evidence path (no hallucinated citations, no training-question leakage).
- Owner-specific prompts without evidence route to uncertainty response.

## 4) Production Deploy Evidence (Render)
### Web service
- Service: `srv-d55qmb95pdvs73cagk60`
- Deploy: `dep-d67v0094tr6s73daevt0`
- Status: `live`
- Finished: `2026-02-14T04:00:28Z`

### Worker service
- Service: `srv-d5ht2763jp1c73evn1dg`
- Deploy: `dep-d67v0094tr6s73daf0dg`
- Status: `live`
- Finished: `2026-02-14T03:58:52Z`

Render logs confirm rollout:
- `==> Your service is live ??`
- New instances started and old ones gracefully shutdown.

## 5) Production Retrieval Health Evidence
Unauthenticated endpoint:
```bash
GET /debug/retrieval/health?twin_id=c3cd4ad0-d4cc-4e82-a020-82b48de72d42
```
Observed:
- Pinecone connected
- namespaces discovered (Delphi + legacy candidate)
- vectors present in Delphi namespace
- `delphi_dual_read: true`
- `flashrank_enabled: false`

## 6) Provider Usage: What is Actually Active
### Inference provider selection
- `backend/modules/answering.py:30` defaults to `openai`
- Cerebras used only if `INFERENCE_PROVIDER=cerebras`
  - `backend/modules/answering.py:138`

### Embeddings provider selection
- `backend/modules/embeddings.py:37` defaults to `openai`
- HuggingFace used only if `EMBEDDING_PROVIDER=huggingface`
  - `backend/modules/embeddings.py:284`

### GraphRAG switch
- Off unless enabled via env:
  - `backend/modules/agent.py:1151`

### FlashRank reranker
- Off unless `ENABLE_FLASHRANK=true`:
  - `backend/modules/retrieval.py:213`

### Cohere client
- Cohere client creation depends on `COHERE_API_KEY`:
  - `backend/modules/clients.py:15`

## 7) Why behavior degraded previously (root causes)
- Generic prompts were incorrectly forced through owner-specific/strict-grounding lanes.
- Low-score nearest-neighbor chunks could still influence planner when off-topic.
- Teaching-mode phrasing leaked into owner-chat when verifier/gate failed.
- Group filtering could over-constrain owner chat retrieval unintentionally.

## 8) Note on `/version`
`/version` currently returns `git_sha: 14061e0` even after live deploy.
This endpoint reads env-based `GIT_SHA` first, so it can drift from actual deployed commit metadata.
Deploy status should be verified from Render deploy records for truth.

## 9) External Reference Baselines (for architecture comparison)
- OpenAI Cookbook: retrieval + reranking pipeline pattern
  - https://cookbook.openai.com/examples/file_search_responses
- OpenAI docs: context quality and retrieval grounding impacts accuracy
  - https://platform.openai.com/docs/guides/optimizing-llm-accuracy
- Pinecone docs: retrieval quality optimization and filtering patterns
  - https://docs.pinecone.io/guides/optimize/decrease-latency
- Pinecone docs: rerank + retrieval pipeline composition
  - https://docs.pinecone.io/guides/search/rerank-results
- Cohere docs: RAG retrieval + rerank workflow
  - https://docs.cohere.com/page/basic-rag
- LangGraph docs: persistence/memory model for long-running state
  - https://langchain-ai.github.io/langgraph/how-tos/persistence/

## 10) Remaining Gaps
- Cannot execute authenticated production chat calls without user JWT/session from this environment.
- Vercel MCP API is currently auth-blocked in this environment; direct Vercel deployment introspection not available.

## 11) Immediate Validation Steps for User (post-deploy)
1. In production, run prompts in this order:
   - `hi`
   - `who are you?`
   - `do you know antler`
   - `I am a B2B SaaS founder. Help me with a 90-day GTM plan`
2. Confirm no teaching-gap prompt appears for generic coaching prompts.
3. If any bad answer appears, provide timestamp + twin id; logs now support precise traceback of route/gate/retrieval behavior.
