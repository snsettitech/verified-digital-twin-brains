# Digital Twin Brain - Backend

FastAPI application providing the RAG engine and management APIs for the Verified Digital Twin Brain.

## Core Services
- **FastAPI**: REST API framework.
- **Pinecone**: Vector database for knowledge retrieval (vector + integrated modes).
- **OpenAI**: Embeddings (`text-embedding-3-large`) and Chat (`gpt-4o`).
- **Supabase**: PostgreSQL for relational data and Auth.

## Project Structure
- `main.py`: Entry point and API route definitions.
- `modules/`:
  - `clients.py`: Centralized singleton-style clients for external services.
  - `ingestion.py`: Document processing, chunking, and vectorization.
  - `retrieval.py`: Context retrieval from Pinecone.
  - `answering.py`: Prompt engineering and LLM response generation.
  - `auth_guard.py`: JWT verification and role-based access control.
  - `escalation.py`: Logic for flagging low-confidence responses.

## API Endpoints

### Health & System
- `GET /health`: Checks connectivity to Pinecone and OpenAI.

### Knowledge Management
- `POST /ingest/{twin_id}`: Upload a PDF to a specific twin's knowledge base.

### Chat & Reasoning
- `POST /chat/{twin_id}`: Query the digital twin.
  - Returns grounded answer with citations.
  - Automatically creates an escalation if confidence < 0.7.

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
   SUPABASE_KEY=...
   JWT_SECRET=...
   LANGFUSE_PUBLIC_KEY=...
   LANGFUSE_SECRET_KEY=...
   LANGFUSE_HOST=https://cloud.langfuse.com

   # Reranking
   ENABLE_FLASHRANK=true
   ENABLE_COHERE_RERANK=true
   COHERE_RERANK_MODEL=rerank-v3.5
   COHERE_API_KEY=...
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

