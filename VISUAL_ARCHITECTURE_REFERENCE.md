# Visual Architecture Reference

**For visual learners and presentations**

---

## 🏗️ System Architecture (Layered)

```
┌─────────────────────────────────────────────────────────────┐
│ PRESENTATION LAYER (User-Facing)                            │
├─────────────────────────────────────────────────────────────┤
│ Next.js 16 Frontend (Vercel)                               │
│ ├─ Authentication UI (OAuth, JWT)                          │
│ ├─ Dashboard (20 sections)                                 │
│ ├─ Chat Interface                                          │
│ ├─ Knowledge Upload                                        │
│ ├─ Graph Visualization                                     │
│ ├─ Metrics Dashboard                                       │
│ ├─ Settings & Governance                                   │
│ └─ Admin Panels                                            │
└──────────────────┬──────────────────────────────────────────┘
                   │ REST API + JSON
┌──────────────────▼──────────────────────────────────────────┐
│ APPLICATION LAYER (API Router)                              │
├─────────────────────────────────────────────────────────────┤
│ FastAPI Backend (Render/Railway)                           │
│ ├─ auth.py           (JWT, OAuth, user sync)              │
│ ├─ chat.py           (3 chat endpoints)                    │
│ ├─ twins.py          (Twin CRUD)                           │
│ ├─ cognitive.py      (Interview, graph, builder)           │
│ ├─ ingestion.py      (Document upload)                     │
│ ├─ knowledge.py      (Sources, chunks, QnA)              │
│ ├─ actions.py        (Triggers, drafts)                    │
│ ├─ governance.py     (Audit logging)                       │
│ ├─ escalations.py    (Low-confidence queue)                │
│ ├─ graph.py          (Nodes, edges)                        │
│ ├─ metrics.py        (Observability)                       │
│ ├─ jobs.py           (Job management)                      │
│ ├─ specializations.py (Manifest, ontology)                │
│ └─ observability.py  (Health checks)                      │
│ [+ 4 more routers]                                          │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ BUSINESS LOGIC LAYER (Modules)                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ COGNITIVE ENGINE (_core/)                                  │
│ ├─ host_engine.py          (Interview orchestration)      │
│ ├─ scribe_engine.py        (Memory extraction)            │
│ ├─ interview_controller.py (State management)             │
│ ├─ versioning.py           (Profile snapshots)            │
│ ├─ artifact_pipeline.py    (Output generation)            │
│ ├─ tenant_guard.py         (Security)                     │
│ └─ ontology_loader.py      (Knowledge structure)          │
│                                                              │
│ RAG PIPELINE (Retrieval)                                   │
│ ├─ retrieval.py            (Verified → Vector → Tools)    │
│ ├─ verified_qna.py         (Exact matches)                │
│ ├─ embeddings.py           (Vector operations)            │
│ └─ tools.py                (Composio integrations)        │
│                                                              │
│ ORCHESTRATION                                              │
│ ├─ agent.py                (LangGraph FSM)                │
│ ├─ answering.py            (Response generation)          │
│ ├─ memory.py               (Conversation state)           │
│ ├─ memory_events.py        (Event logging)                │
│ └─ graph_context.py        (Graph state)                  │
│                                                              │
│ GOVERNANCE (Security, Audit, Compliance)                   │
│ ├─ auth_guard.py           (JWT, ownership)               │
│ ├─ governance.py           (Audit logging)                │
│ ├─ safety.py               (Content moderation)           │
│ ├─ rate_limiting.py        (Quota enforcement)            │
│ ├─ access_groups.py        (Audience segmentation)        │
│ └─ escalation.py           (Low-confidence routing)       │
│                                                              │
│ INFRASTRUCTURE                                             │
│ ├─ clients.py              (OpenAI, Pinecone)            │
│ ├─ observability.py        (Supabase client)              │
│ ├─ langfuse_client.py      (Tracing)                      │
│ ├─ health_checks.py        (Service health)               │
│ ├─ metrics_collector.py    (Timing, tokens)              │
│ ├─ sessions.py             (Session management)           │
│ ├─ job_queue.py            (Background jobs)              │
│ ├─ ingestion.py            (Document processing)          │
│ ├─ specializations/        (17 domain templates)          │
│ └─ schemas.py              (Pydantic models)              │
│                                                              │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ DATA LAYER (Storage & Processing)                           │
├─────────────────────────────────────────────────────────────┤
│ ┌─ Supabase PostgreSQL              ┌─ Pinecone         │
│ │ ├─ users (auth)                   │ ├─ Vectors        │
│ │ ├─ twins (digital personalities)  │ ├─ 3072-dim       │
│ │ ├─ sources (documents)            │ ├─ Namespaced     │
│ │ ├─ conversations (chat history)   │ │  per twin       │
│ │ ├─ messages (content)             │ └─ Cosine metric  │
│ │ ├─ graph_nodes (concepts)         │                   │
│ │ ├─ graph_edges (relationships)    ├─ OpenAI          │
│ │ ├─ verified_qna (trusted answers) │ ├─ GPT-4o         │
│ │ ├─ escalations (reviews)          │ ├─ Embeddings     │
│ │ ├─ jobs (background tasks)        │ └─ Completions    │
│ │ ├─ audit_logs (compliance)        │                   │
│ │ ├─ metrics (observability)        ├─ Langfuse        │
│ │ ├─ sessions (API tracking)        │ ├─ Traces         │
│ │ ├─ events (automation)            │ ├─ Metrics        │
│ │ └─ [+10 more tables]              │ └─ Evaluation     │
│ └─────────────────────────────────   └─ ─ ─ ─ ─ ─ ─ ─ ─┘
│
└──────────────────────────────────────────────────────────────┘
```

---

## 🔄 Request Flow Diagram

```
USER REQUEST
    │
    ▼
┌─────────────────────┐
│ Frontend (Browser)  │
│ ├─ Input validation │
│ ├─ OAuth redirect   │
│ └─ Send REST call   │
└──────────┬──────────┘
           │ (HTTPS)
           ▼
┌─────────────────────┐
│ Backend (FastAPI)   │
├─────────────────────┤
│ 1. CORS Middleware  │ ← Check origin
│ 2. Auth Middleware  │ ← Validate JWT
│ 3. Router           │ ← Route request
│ 4. Dependency Inj.  │ ← Get current user
│ 5. Business Logic   │ ← Execute endpoint
│ 6. Response Format  │ ← Serialize response
└──────────┬──────────┘
           │
    ┌──────┴──────┬──────────┬──────────┐
    ▼             ▼          ▼          ▼
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐
│Supabase │  │Pinecone │  │ OpenAI  │  │Langfuse  │
│PostgreSQL  │ Vectors │  │  LLM    │  │ Tracing  │
└────┬────┘  └────┬────┘  └────┬────┘  └──────────┘
     │            │            │
     │ (RLS)      │ (Namespace)│ (API)
     │            │            │
     └────┬───────┴────┬───────┘
          ▼            ▼
      [Database]  [External APIs]
      [Computed]  [Background Jobs]
      │
      ▼
   RESPONSE
   ├─ Status code
   ├─ JSON data
   └─ Headers
      │
      ▼
   Browser renders
   User sees result
```

---

## 🧠 Chat Flow (Detailed)

```
User Types: "What's my business strategy?"
    │
    ▼
POST /chat/{twin_id}
    │
    ├─ 1. Auth Check
    │  └─ Verify JWT token
    │
    ├─ 2. Twin Ownership Verify
    │  └─ Check user owns twin
    │
    ├─ 3. Load Context
    │  ├─ Twin persona/settings
    │  ├─ Conversation history
    │  └─ Graph nodes (memory)
    │
    ├─ 4. Process Query
    │  └─ Call LangGraph Agent
    │
    │   [Inside Agent]
    │   ├─ Parse intent
    │   ├─ Check verified_qna
    │   │  └─ If exact match → Return immediately
    │   ├─ Query Pinecone (semantic search)
    │   │  └─ Retrieve relevant chunks
    │   ├─ Rerank results (Cohere)
    │   │  └─ Filter top-3
    │   ├─ Generate with context
    │   │  └─ Call OpenAI GPT-4o
    │   ├─ Extract confidence score
    │   │  └─ If < threshold → Escalate
    │   └─ Extract graph updates
    │       └─ Enqueue graph extraction job
    │
    ├─ 5. Save Message
    │  ├─ Insert into messages table
    │  ├─ Store embeddings
    │  └─ Save citations
    │
    ├─ 6. Send Response
    │  └─ JSON with citations
    │
    └─ 7. Background Processing
       ├─ Extract memory (Scribe engine)
       ├─ Update graph nodes
       └─ Log metrics/tracing

    ▼
Browser shows response with citations
```

---

## 🛡️ Security Layers

```
INCOMING REQUEST
    │
    ▼
┌─────────────────────────────────────┐
│ 1. CORS Middleware                  │
│ └─ Check origin allowed             │
└─────────────┬───────────────────────┘
              │ (continues if valid)
              ▼
┌─────────────────────────────────────┐
│ 2. JWT Validation                   │
│ ├─ Decode JWT token                 │
│ ├─ Verify signature                 │
│ ├─ Check expiration                 │
│ └─ Extract user info                │
└─────────────┬───────────────────────┘
              │ (continues if valid)
              ▼
┌─────────────────────────────────────┐
│ 3. Resource Ownership               │
│ ├─ Verify user owns resource        │
│ ├─ Check tenant_id matches         │
│ └─ Deny if mismatched              │
└─────────────┬───────────────────────┘
              │ (continues if valid)
              ▼
┌─────────────────────────────────────┐
│ 4. Database RLS Policies            │
│ ├─ Filter by tenant_id              │
│ ├─ Filter by ownership              │
│ └─ Additional policy checks         │
└─────────────┬───────────────────────┘
              │ (continues if valid)
              ▼
┌─────────────────────────────────────┐
│ 5. Rate Limiting (Optional)         │
│ ├─ Check quotas                     │
│ ├─ Enforce limits                   │
│ └─ Block if exceeded                │
└─────────────┬───────────────────────┘
              │ (continues if valid)
              ▼
        EXECUTE LOGIC
              │
              ▼
        STORE IN DB
   (RLS enforced again)
```

---

## 📊 Data Flow: Document Ingestion

```
USER UPLOADS: business-plan.pdf
    │
    ▼
┌─────────────────────────┐
│ Frontend               │
│ ├─ File selection      │
│ ├─ Multipart upload    │
│ └─ Progress indicator  │
└────────────┬───────────┘
             │
             ▼
┌─────────────────────────┐
│ POST /ingestion/upload  │
├─────────────────────────┤
│ 1. Auth check           │
│ 2. File validation      │
│ 3. Create source record │
│ 4. Trigger processing   │
└────────────┬───────────┘
             │
             ├─ ASYNC: Extract text
             │ ├─ PyPDF2 extracts pages
             │ ├─ Split into chunks
             │ └─ Store in sources table
             │
             ├─ Create embeddings
             │ ├─ Call OpenAI API
             │ ├─ Get 3072-dim vectors
             │ └─ Upsert to Pinecone
             │
             ├─ Extract metadata
             │ ├─ Title, date, author
             │ └─ Store in sources table
             │
             └─ Update status
               ├─ sources.status = "indexed"
               └─ Notify frontend

             ▼
     DOCUMENT READY
     ├─ Appears in knowledge list
     ├─ Available for retrieval
     └─ Indexed for search
```

---

## 🧠 Graph Extraction Pipeline

```
CHAT INTERACTION (User + Twin)
    │
    ├─ User: "Tell me about your background"
    │ Twin: "I grew up in Silicon Valley, worked at..."
    │
    ▼
┌─────────────────────────────┐
│ Scribe Engine               │
│ ├─ Extract entities         │
│ ├─ Identify relationships   │
│ └─ Create graph updates     │
└────────────┬────────────────┘
             │
             ├─ ENTITY: "Silicon Valley"
             │  └─ Type: Location
             │
             ├─ ENTITY: "Tech Industry"
             │  └─ Type: Industry
             │
             ├─ RELATIONSHIP
             │  └─ "User → lived in → Silicon Valley"
             │
             └─ RELATIONSHIP
                └─ "User → works in → Tech"

             ▼
┌─────────────────────────────┐
│ Job Queue                   │
│ ├─ Job type: graph_extraction
│ ├─ Status: pending          │
│ └─ Retry count: 0           │
└────────────┬────────────────┘
             │ (async)
             ▼
     ┌─────────────────────────┐
     │ Worker Process          │
     ├─ Dequeue job            │
     ├─ Extract graph updates  │
     ├─ Create nodes           │
     ├─ Create edges           │
     └─ Mark complete          │
     └────────────┬────────────┘
                  │
         ┌────────┴──────────┐
         ▼                   ▼
    ┌─────────┐         ┌──────────┐
    │ Nodes   │         │ Edges    │
    ├─────────┤         ├──────────┤
    │silicon  │         │lived_in  │
    │valley   │         │works_in  │
    │tech_ind │         │educated  │
    └─────────┘         └──────────┘
         │                   │
         └─────────┬─────────┘
                   │
                   ▼
          GRAPH UPDATED
          │
          ├─ Nodes appear in visualization
          ├─ Relationships show connections
          └─ Better context for next query
```

---

## 📈 Performance Metrics Tracking

```
REQUEST COMES IN
    │
    ▼
START_TIME = now()
    │
    ├─ Auth: +50ms
    ├─ Retrieval: +400ms
    ├─ Generation: +2000ms
    ├─ Saving: +100ms
    └─ Total: ~2550ms

    ▼
┌─────────────────────────┐
│ Metrics Collector       │
├─────────────────────────┤
│ ├─ Latency: 2550ms     │
│ ├─ Tokens: 1,250       │
│ ├─ Confidence: 0.92    │
│ ├─ Retrieved items: 3  │
│ └─ Status: success     │
└────────────┬────────────┘
             │
    ┌────────┴─────────┐
    ▼                  ▼
┌─────────┐      ┌──────────────┐
│Supabase │      │Langfuse      │
│metrics  │      │tracing       │
│table    │      │(optional)    │
└─────────┘      └──────────────┘
    │                 │
    ▼                 ▼
Dashboard       Analysis
shows           tools
metrics         track
                performance
```

---

## 🎯 Deployment Architecture

```
┌──────────────────────────────────────────┐
│ CODE REPOSITORY (GitHub)                 │
│ └─ main branch                           │
└──────────┬───────────────────────────────┘
           │ (git push)
           ▼
┌──────────────────────────────────────────┐
│ CI/CD Pipeline (GitHub Actions)          │
│ ├─ Lint backend                          │
│ ├─ Test backend                          │
│ ├─ Lint frontend                         │
│ ├─ Type-check frontend                   │
│ ├─ Build frontend                        │
│ └─ All pass → Auto-deploy                │
└──────┬───────────────────────┬───────────┘
       │                       │
       ▼                       ▼
┌──────────────┐      ┌────────────────┐
│ Vercel       │      │ Render/Railway │
│ (Frontend)   │      │ (Backend)      │
│              │      │                │
│ Next.js 16   │      │ FastAPI        │
│ ├─ Build     │      │ ├─ Build       │
│ ├─ Deploy    │      │ ├─ Deploy      │
│ ├─ SSL       │      │ ├─ Worker      │
│ └─ CDN       │      │ └─ Health      │
└──────┬───────┘      └────────┬───────┘
       │                       │
       │        ┌──────────────┘
       │        │
       ▼        ▼
   ┌─────────────────────┐
   │ Supabase (Database) │
   │ ├─ PostgreSQL       │
   │ ├─ Auth             │
   │ ├─ RLS              │
   │ └─ Backups          │
   └─────────────────────┘

   ┌─────────────────────┐
   │ Pinecone (Vectors)  │
   │ └─ 3072-dim index   │
   └─────────────────────┘

   ┌─────────────────────┐
   │ OpenAI (LLM)        │
   │ └─ GPT-4o models    │
   └─────────────────────┘
```

---

## 🔀 Multi-Tenant Isolation Pattern

```
INCOMING REQUEST
├─ JWT contains tenant_id = "acme-corp"
└─ User ID = "user-123"

    ▼

BACKEND LOGIC
├─ Extract tenant_id from JWT
├─ Pass to all database queries
└─ Supabase enforces RLS:

   IF user_id = 'user-123'
   AND tenant_id = 'acme-corp'
   THEN allow
   ELSE deny

    ▼

DATABASE QUERIES
├─ SELECT * FROM twins
│  WHERE tenant_id = 'acme-corp'
│  │
│  └─ Returns only ACME twins
│
├─ SELECT * FROM twins
│  WHERE tenant_id = 'other-corp'
│  │
│  └─ Returns EMPTY (denied by RLS)
│
└─ UPDATE messages
   WHERE id = 'msg-999'
   AND twin_id NOT IN (
     SELECT id FROM twins
     WHERE tenant_id = 'acme-corp'
   )
   │
   └─ UPDATE DENIED (RLS prevents)

    ▼

VECTOR QUERIES
├─ Pinecone namespace = 'acme-corp:twin-001'
├─ Search within namespace only
└─ No cross-tenant data leakage

    ▼

RESULT
├─ User sees ONLY their data
├─ Other tenants invisible
└─ Enforced at database level
```

---

## ⚠️ Failure Scenarios & Recovery

```
SCENARIO 1: Database Down
    │
    ├─ /health returns error
    ├─ Alert sent to team
    ├─ UI shows "We're experiencing issues"
    └─ Auto-retry after 5 minutes

    Recovery:
    ├─ Check Supabase status
    ├─ Verify connection string
    └─ Restart backend service

SCENARIO 2: OpenAI Rate Limited
    │
    ├─ Chat returns error
    ├─ Escalation triggered
    ├─ Fallback to simple response
    └─ Retry with exponential backoff

    Recovery:
    ├─ Check OpenAI status
    ├─ Verify API key valid
    └─ Wait or upgrade account

SCENARIO 3: Pinecone Connection Lost
    │
    ├─ Vector search fails
    ├─ Fall back to keyword search
    ├─ Response quality degrades
    └─ Alert sent to ops

    Recovery:
    ├─ Check network connection
    ├─ Restart Pinecone client
    └─ Reindex if needed

SCENARIO 4: JWT Secret Wrong
    │
    ├─ All auth requests fail
    ├─ Users can't login
    ├─ Alert: Auth system down
    └─ Immediate page shows error

    Recovery:
    ├─ Get correct secret from Supabase
    ├─ Update environment variable
    ├─ Restart backend
    └─ Users can login again

SCENARIO 5: Database Query Slow
    │
    ├─ P95 latency > 5 seconds
    ├─ Alert sent to team
    ├─ Slow query logs checked
    └─ Index analysis performed

    Recovery:
    ├─ Add missing index
    ├─ Optimize query
    ├─ Implement caching
    └─ Performance restored
```

---

## 🎓 Technology Stack Visualization

```
┌─────────────────────────────┐
│ FRONTEND STACK              │
├─────────────────────────────┤
│ React 19 (UI framework)     │
│ Next.js 16 (SSR, routing)   │
│ TypeScript (type safety)    │
│ Tailwind CSS (styling)      │
│ Supabase Auth (JWT)         │
│ Playwright (testing)        │
└─────────────────────────────┘

┌─────────────────────────────┐
│ BACKEND STACK               │
├─────────────────────────────┤
│ Python 3.12 (runtime)       │
│ FastAPI (API framework)     │
│ LangGraph (agent/FSM)       │
│ LangChain (LLM abstraction) │
│ Pydantic (validation)       │
│ pytest (testing)            │
│ Uvicorn (ASGI server)       │
└─────────────────────────────┘

┌─────────────────────────────┐
│ DATA & INFRASTRUCTURE       │
├─────────────────────────────┤
│ PostgreSQL (relational DB)  │
│ Pinecone (vector DB)        │
│ OpenAI (LLM)                │
│ Cohere (reranking)          │
│ Composio (tool integration) │
│ Langfuse (tracing)          │
│ Redis (optional, caching)   │
├─────────────────────────────┤
│ Vercel (frontend hosting)   │
│ Render/Railway (backend)    │
│ Supabase (database)         │
│ GitHub (version control)    │
│ GitHub Actions (CI/CD)      │
└─────────────────────────────┘
```

---

## 📊 Comparison: Current vs Target

```
METRIC              CURRENT    MONTH 3    MONTH 6
────────────────────────────────────────────────
P95 Latency         2.5s       500ms      250ms
                    ████░░░    ██░░░░░    █░░░░░░

Database Load       HIGH       MEDIUM     LOW
                    ███░░░░    ██░░░░░    █░░░░░░

Test Coverage       40%        70%        80%
                    ████░░░░░░ ███████░░░ ████████░░

Uptime              95%        99.5%      99.9%
                    ███████░░░░ █████████░ ██████████

Concurrent Users    100        1,000      10,000
                    █░░░░░░░░░ ██░░░░░░░░ ██████████

Code Quality        ✅         ✅✅       ✅✅✅
                    Good       Better     Excellent

Team Productivity   ✅         ✅✅       ✅✅✅
                    Good       Better     Excellent
```

---

**Use these visual references during:**
- Onboarding new team members
- Presenting to stakeholders
- Architecture reviews
- Debugging sessions
- Documentation

All diagrams are text-based and can be copied to presentations!
