# Verified Digital Twin

Build an AI clone of yourself — trained on your documents, speaking in your voice, grounded in your actual knowledge.

Upload your docs, set a persona prompt, and get a chat interface that answers like you would. Every response is traceable to source material.

## What It Does

- You upload documents (PDFs, DOCX, links) and write a system prompt describing who the twin is
- Users chat with the twin and get answers grounded in the uploaded knowledge
- If the answer exists in the documents, it cites the source. If not, the persona prompt handles it
- Each twin is isolated — separate vector namespace, separate permissions, separate knowledge base

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 16, TypeScript, Tailwind |
| Backend | FastAPI, Python 3.13, LangGraph |
| Database | Supabase (Postgres + Auth + RLS) |
| Vectors | Pinecone (3072-dim, `text-embedding-3-large`) |
| LLM | OpenAI GPT-4o (primary), Claude/Cerebras (fallback) |
| Voice | ElevenLabs |
| Observability | Langfuse |

## Local Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- API keys: OpenAI, Supabase, Pinecone

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # Fill in: OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, PINECONE_API_KEY
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # Set NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
npm run dev
```

Open `http://localhost:3000`. Sign up, and a twin is auto-created for your account.

## Creating a Digital Twin (UI)

### Step 1: Configure the Persona

Go to **Settings** (`/dashboard/settings`) > **Twin Settings** tab:

- **Twin Name**: The display name (e.g., "Shambhavi Mishra")
- **Handle**: Short identifier (e.g., "shambhavi")
- **Tagline**: One-liner description
- **Personality**: Tone (professional/friendly/casual), response length, first-person toggle
- **System Prompt**: The core instruction set that defines how the twin talks, thinks, and behaves. This is the most important field — it controls the twin's entire personality, boundaries, and communication style

You can also use **Studio** (`/dashboard/studio`) for a focused persona editing experience.

### Step 2: Upload Knowledge

Go to **Knowledge** (`/dashboard/knowledge`):

- Drag and drop files (PDF, DOCX, TXT, XLSX, CSV, MD) or paste URLs
- Documents are automatically chunked, embedded, and indexed into Pinecone
- Each source shows its status: processing → live
- You can view, inspect, and delete sources from this page

Supported sources:
- **Files**: PDF, DOCX, TXT, XLSX, CSV, Markdown, JSON
- **URLs**: YouTube videos, podcast RSS feeds, X/Twitter threads, web pages

### Step 3: Test

Go to **Simulator** (`/dashboard/simulator/owner`):

- Chat with your twin to verify it responds correctly
- Ask questions about the uploaded documents to check retrieval
- Ask persona questions to check the system prompt behavior

### How It Works

```
User asks a question
    ↓
Retrieval: search Pinecone for relevant document chunks
    ↓
If documents found → answer grounded in sources (with citations)
If no documents match → fall back to persona system prompt
    ↓
Response streamed to user
```

## Creating a Digital Twin (CLI)

For bulk setup or automation, you can use the CLI tools:

```bash
# 1. Create a persona config JSON
cat > backend/persona_configs/my_twin.json << 'EOF'
{
  "name": "Your Name",
  "description": "Short description",
  "settings": {
    "system_prompt": "You are the AI digital twin of [Name]...",
    "personality": { "tone": "friendly", "responseLength": "balanced" }
  }
}
EOF

# 2. Load it into your twin
cd backend
python persona_configs/load_persona.py <twin_id> persona_configs/my_twin.json

# 3. Upload a document
curl -X POST http://localhost:8000/ingest/file/<twin_id> \
  -H "Authorization: Bearer <token>" \
  -F "file=@document.pdf"
```

## Project Structure

```
backend/
├── main.py                 # FastAPI entry point
├── modules/
│   ├── agent.py            # LangGraph pipeline (router → retrieve → gate → plan → realize)
│   ├── retrieval.py        # Hybrid RAG: verified QnA → vector search → persona fallback
│   ├── ingestion.py        # Document chunking, embedding, Pinecone indexing
│   ├── inference_router.py # Multi-provider LLM routing (OpenAI/Claude/Cerebras)
│   ├── answerability.py    # Evidence sufficiency evaluation
│   └── tools.py            # Retrieval tool with conversation-aware query expansion
├── routers/
│   ├── chat.py             # SSE streaming chat endpoint
│   ├── ingestion.py        # File/URL upload and processing
│   └── auth.py             # User sync, twin management
├── persona_configs/        # Persona JSON configs + loader script
└── worker.py               # Background job processor (optional)

frontend/
├── app/dashboard/
│   ├── settings/           # Twin config, system prompt, personality
│   ├── knowledge/          # Document upload and source management
│   ├── studio/             # Persona editing
│   ├── simulator/          # Chat testing (owner/public/training modes)
│   ├── brain/              # Knowledge graph visualization
│   └── share/              # Public sharing, widget embed
├── components/
│   ├── Chat/               # ChatInterface, MessageList, CitationsDrawer
│   └── ingestion/          # UnifiedIngestion upload component
└── lib/
    ├── context/            # TwinContext (auth + active twin state)
    └── ingestionApi.ts     # File upload API client
```

## Key Dashboard Pages

| Page | URL | Purpose |
|------|-----|---------|
| Settings | `/dashboard/settings` | Twin name, system prompt, personality, billing |
| Knowledge | `/dashboard/knowledge` | Upload docs, manage sources, view health |
| Studio | `/dashboard/studio` | Persona editing, style profile |
| Simulator | `/dashboard/simulator/owner` | Chat testing |
| Brain | `/dashboard/brain` | Knowledge graph visualization |
| Share | `/dashboard/share` | Public link, widget embed |
| Metrics | `/dashboard/metrics` | Usage analytics |

## Architecture

- **Multi-tenant**: Each user has a tenant, each tenant can have multiple twins
- **Twin isolation**: Separate Pinecone namespace per twin (`creator_{id}_twin_{id}`), Supabase RLS, ownership verification on every API call
- **RAG pipeline**: `router_node → retrieve_node → evidence_gate → planner_node → realizer_node`
- **Answerability gate**: LLM evaluates if retrieved evidence can answer the question before generating a response
- **Persona fallback**: When no documents match, the system prompt drives the response

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | LLM and embeddings |
| `SUPABASE_URL` | Yes | Database |
| `SUPABASE_KEY` | Yes | Supabase anon/service key |
| `PINECONE_API_KEY` | Yes | Vector store |
| `PINECONE_INDEX_NAME` | Yes | Pinecone index name |
| `LANGFUSE_PUBLIC_KEY` | No | Observability (optional) |
| `LANGFUSE_SECRET_KEY` | No | Observability (optional) |
| `ELEVENLABS_API_KEY` | No | Voice synthesis (optional) |

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_BACKEND_URL` | Yes | Backend API URL (e.g., `http://localhost:8000`) |
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | Supabase anon key |

## License

Proprietary.
