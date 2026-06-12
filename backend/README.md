# Digital Twin Brain - Backend

FastAPI application providing the RAG engine and management APIs for the Verified Digital Twin Brain.

## Core Services
- **FastAPI**: REST API framework.
- **Pinecone**: Vector database for knowledge retrieval (vector + integrated modes).
- **OpenAI**: Embeddings (`text-embedding-3-large`) plus primary JSON/text inference (`gpt-4o`, `gpt-4o-mini`).
- **Gemini**: Optional text-generation provider for conversational realizer flows (`gemini-2.0-flash`).
- **Supabase**: PostgreSQL for relational data and Auth.
- **Deep Research**: Core deep-research routes are always mounted; the name-only JSON flow is gated by `NAME_ONLY_DEEP_RESEARCH_ENABLED`.

## Project Structure
- `main.py`: Entry point and API route definitions.
- `modules/`:
  - `clients.py`: Centralized singleton-style clients for external services.
  - `ingestion.py`: Document processing, chunking, and vectorization.
  - `retrieval.py`: Context retrieval from Pinecone.
  - `agent.py`: Authoritative LangGraph chat/runtime orchestration.
  - `inference_router.py`: Active multi-provider text/JSON inference routing.
  - `answering.py`: Legacy compatibility answer generation surface.
  - `auth_guard.py`: JWT verification and role-based access control.
  - `escalation.py`: Logic for flagging unsupported or review-required responses.

## API Endpoints

### Health & System
- `GET /health`: Checks connectivity to Pinecone and OpenAI.

### Knowledge Management
- `POST /ingest/{twin_id}`: Upload a PDF to a specific twin's knowledge base.

### Chat & Reasoning
- `POST /chat/{twin_id}`: Query the digital twin.
  - Returns grounded answer with citations.
  - Automatically creates an escalation when a response is unsupported or marked for review.

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   Optional production-safe ML features (HF API embeddings, FlashRank, Cohere reranker):
   ```bash
   pip install -r requirements-ml.txt
   ```

   Optional local HF embeddings (heavier: sentence-transformers/torch):
   ```bash
   pip install -r requirements-ml-local.txt
   ```

   Developer/test tooling:
   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Environment Variables**:
   Create a `.env` file based on `.env.example`:
   ```env
   OPENAI_API_KEY=...
   PINECONE_API_KEY=...
   PINECONE_INDEX_NAME=digitalminds
   PINECONE_HOST=digitalminds-nrnzovv.svc.aped-4627-b74a.pinecone.io
   PINECONE_INDEX_MODE=integrated
   PINECONE_TEXT_FIELD=chunk_text
   SUPABASE_URL=...
   SUPABASE_SERVICE_KEY=...
   JWT_SECRET=...
   LANGFUSE_PUBLIC_KEY=...
   LANGFUSE_SECRET_KEY=...
   LANGFUSE_HOST=https://cloud.langfuse.com
   INFERENCE_PROVIDER=openai
   OPENAI_MODEL=gpt-4o
   OPENAI_JSON_MODEL=gpt-4o-mini
   GEMINI_MODEL=gemini-2.0-flash
   GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
   CONVERSATIONAL_REALIZER_ENABLED=false
   QUERY_REWRITE_ENABLED=true
   QUERY_REWRITING_ENABLED=true
   RUNTIME_SUPPORT_POLICY_ENABLED=false
   GOOGLE_API_KEY=...
   RETRIEVAL_HYDE_ENABLED=true
   # Reranking
   ENABLE_FLASHRANK=true
   ENABLE_COHERE_RERANK=true
   COHERE_RERANK_MODEL=rerank-v3.5
   COHERE_API_KEY=...
   COHERE_RERANK_STRICT=false
   ```

### Pinecone Index Modes
- `vector` (default): Uses external embeddings and Pinecone `upsert/query`.
- `integrated`: Uses Pinecone hosted embedding model and `upsert_records/search_records`.
- Current production target:
  - `PINECONE_HOST=digitalminds-nrnzovv.svc.aped-4627-b74a.pinecone.io`
  - `PINECONE_INDEX_NAME=digitalminds`
  - `PINECONE_INDEX_MODE=integrated`
  - `PINECONE_TEXT_FIELD=chunk_text`

3. **Run Application**:
   ```bash
   python main.py
   ```

