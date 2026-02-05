# Digital Brain Architecture

> A Delphi-level Digital Brain MVP that learns day by day with multi-tenant isolation.

## System Overview

```mermaid
flowchart TB
    subgraph "Frontend - Vercel"
        FE[Next.js App]
        Auth_UI[Auth Components]
        Twin_UI[Twin Dashboard]
        Chat_UI[Chat Interface]
        Onboard_UI[Onboarding Flow]
    end
    
    subgraph "Backend - Render"
        API[FastAPI Server]
        subgraph "Services"
            Auth_Svc[Auth Service]
            Twin_Svc[Twin Service]
            Chat_Svc[Chat Service]
            Ingest_Svc[Ingestion Service]
            Graph_Svc[Graph Memory Service]
            Escal_Svc[Escalation Service]
        end
        subgraph "Orchestration"
            Retriever[Hybrid Retriever]
            Scribe[Memory Scribe]
            LlamaIdx[LlamaIndex PropertyGraph]
        end
    end
    
    subgraph "Data Layer"
        Supabase[(Supabase Postgres)]
        Pinecone[(Pinecone Vectors)]
    end
    
    subgraph "External Services"
        OpenAI[OpenAI GPT-4o]
        Langfuse[Langfuse Tracing]
    end
    
    FE --> API
    API --> Supabase
    API --> Pinecone
    API --> OpenAI
    API --> Langfuse
```

## Multi-Tenant Isolation Model

```mermaid
flowchart LR
    subgraph "Tenant A"
        UA[User A] --> TA1[Twin A1]
        UA --> TA2[Twin A2]
    end
    
    subgraph "Tenant B"  
        UB[User B] --> TB1[Twin B1]
    end
    
    subgraph "Supabase RLS"
        RLS[Row Level Security]
        RLS --> |tenant_id = jwt.tenant_id| Tables
    end
    
    subgraph "Pinecone"
        NS_A1[Namespace: tenant_a:twin_a1]
        NS_A2[Namespace: tenant_a:twin_a2]
        NS_B1[Namespace: tenant_b:twin_b1]
    end
    
    TA1 --> NS_A1
    TA2 --> NS_A2
    TB1 --> NS_B1
```

## Database Schema

```mermaid
erDiagram
    tenants ||--o{ users : has
    users ||--o{ twins : owns
    twins ||--o{ documents : contains
    twins ||--o{ conversations : has
    twins ||--o{ graph_nodes : has
    twins ||--o{ memory_candidates : has
    twins ||--o{ escalations : has
    conversations ||--o{ messages : contains
    graph_nodes ||--o{ graph_edges : from
    graph_nodes ||--o{ graph_edges : to
    
    tenants {
        uuid id PK
        text name
        jsonb settings
        timestamp created_at
    }
    
    users {
        uuid id PK
        uuid tenant_id FK
        text email
        text role
        timestamp created_at
    }
    
    twins {
        uuid id PK
        uuid tenant_id FK
        uuid owner_id FK
        text name
        text description
        text specialization
        jsonb personality
        text onboarding_status
        timestamp created_at
    }
    
    documents {
        uuid id PK
        uuid twin_id FK
        uuid tenant_id FK
        text title
        text content
        text source_type
        jsonb metadata
        text processing_status
        timestamp created_at
    }
    
    conversations {
        uuid id PK
        uuid twin_id FK
        uuid tenant_id FK
        uuid user_id FK
        text mode
        jsonb context
        timestamp created_at
    }
    
    messages {
        uuid id PK
        uuid conversation_id FK
        uuid tenant_id FK
        text role
        text content
        jsonb tool_calls
        jsonb metadata
        timestamp created_at
    }
    
    graph_nodes {
        uuid id PK
        uuid twin_id FK
        uuid tenant_id FK
        text node_type
        text name
        text description
        jsonb properties
        float[] embedding
        timestamp created_at
    }
    
    graph_edges {
        uuid id PK
        uuid from_node_id FK
        uuid to_node_id FK
        uuid tenant_id FK
        text relationship_type
        float weight
        jsonb properties
        timestamp created_at
    }
    
    memory_candidates {
        uuid id PK
        uuid twin_id FK
        uuid tenant_id FK
        uuid source_message_id FK
        text content
        text memory_type
        text status
        jsonb extracted_entities
        timestamp created_at
        timestamp reviewed_at
    }
    
    escalations {
        uuid id PK
        uuid twin_id FK
        uuid tenant_id FK
        uuid source_conversation_id FK
        text question
        text context
        text status
        text owner_response
        boolean add_to_brain
        timestamp created_at
        timestamp resolved_at
    }
```

## API Architecture

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as FastAPI
    participant Auth as Supabase Auth
    participant DB as Supabase DB
    participant PC as Pinecone
    participant LLM as OpenAI
    participant LF as Langfuse
    
    FE->>Auth: Sign In
    Auth-->>FE: JWT Token
    
    FE->>API: Chat Request + JWT
    API->>Auth: Verify JWT
    Auth-->>API: User Claims (tenant_id)
    
    API->>LF: Start Trace
    
    par Hybrid Retrieval
        API->>PC: Vector Search (namespace=twin_id)
        API->>DB: Graph Query (RLS enforced)
        API->>DB: Recent Conversations (RLS)
    end
    
    PC-->>API: Relevant Docs
    DB-->>API: Graph Context
    DB-->>API: Conversation History
    
    API->>LLM: Generate Response
    LLM-->>API: Response + Confidence
    
    alt Low Confidence
        API->>DB: Create Escalation
    end
    
    API->>DB: Extract Memory Candidates
    API->>LF: End Trace
    
    API-->>FE: Chat Response
```

## Chat Retrieval Pipeline

```mermaid
flowchart TB
    Query[User Query]
    
    subgraph "Hybrid Retrieval"
        VecSearch[Vector Search - Pinecone]
        GraphQuery[Graph Traversal - Postgres]
        ConvHist[Conversation History]
    end
    
    Query --> VecSearch
    Query --> GraphQuery
    Query --> ConvHist
    
    subgraph "Context Assembly"
        DocContext[Document Chunks]
        GraphBrief[Graph Brief]
        HistContext[Recent Messages]
    end
    
    VecSearch --> DocContext
    GraphQuery --> GraphBrief
    ConvHist --> HistContext
    
    subgraph "LLM Generation"
        Prompt[System Prompt + Context]
        GPT4[GPT-4o]
        Response[Structured Response]
    end
    
    DocContext --> Prompt
    GraphBrief --> Prompt
    HistContext --> Prompt
    Prompt --> GPT4
    GPT4 --> Response
    
    subgraph "Post-Processing"
        ConfCheck{Confidence Check}
        MemExtract[Memory Extraction]
        Escalate[Create Escalation]
    end
    
    Response --> ConfCheck
    Response --> MemExtract
    ConfCheck -->|Low| Escalate
```

## Memory Write Pipeline

```mermaid
flowchart TB
    Msg[New Message]
    
    subgraph "Scribe Extraction"
        Scribe[Memory Scribe - GPT-4o]
        Struct[Structured Output]
    end
    
    Msg --> Scribe
    Scribe --> Struct
    
    subgraph "Extracted Data"
        Entities[Named Entities]
        Facts[Facts & Preferences]
        Relations[Relationships]
    end
    
    Struct --> Entities
    Struct --> Facts
    Struct --> Relations
    
    subgraph "Storage"
        Candidates[memory_candidates table]
        PendingNodes[Pending Graph Nodes]
    end
    
    Entities --> Candidates
    Facts --> Candidates
    Relations --> PendingNodes
    
    subgraph "Owner Review"
        Review[Approval Queue]
        Approve{Approve?}
    end
    
    Candidates --> Review
    PendingNodes --> Review
    Review --> Approve
    
    Approve -->|Yes| GraphNodes[graph_nodes]
    Approve -->|Yes| GraphEdges[graph_edges]
    Approve -->|Yes| Embeddings[Pinecone Vectors]
    Approve -->|No| Archive[Archived]
```

## Security Model

| Layer | Mechanism | Enforcement |
|-------|-----------|-------------|
| Auth | Supabase Auth JWT | Every API request |
| API | FastAPI Depends | Route middleware |
| Database | Supabase RLS | Policy per table |
| Vectors | Pinecone Namespace | `tenant_id:twin_id` |
| LLM | No PII in prompts | Input sanitization |

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Frontend | Next.js 14 | SSR, React, TypeScript |
| Backend | FastAPI | Async API, Pydantic |
| Auth | Supabase Auth | JWT, Social logins |
| Database | Supabase Postgres | RLS, real-time |
| Vectors | Pinecone | Semantic search |
| Graph | Postgres + LlamaIndex | Property graph |
| LLM | GPT-4o | Generation, extraction |
| Tracing | Langfuse | Observability |
| Eval | RAGAS | RAG quality metrics |

## Directory Structure

```
deep-kuiper/
├── frontend/                  # Next.js application
│   ├── app/                   # App router pages
│   ├── components/            # React components
│   ├── lib/                   # Utilities, API client
│   └── styles/                # CSS modules
│
├── backend/                   # FastAPI application
│   ├── app/
│   │   ├── api/              # Route handlers
│   │   │   ├── auth.py
│   │   │   ├── twins.py
│   │   │   ├── chat.py
│   │   │   ├── documents.py
│   │   │   ├── memory.py
│   │   │   └── escalations.py
│   │   ├── core/             # Core utilities
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── dependencies.py
│   │   ├── services/         # Business logic
│   │   │   ├── retrieval.py
│   │   │   ├── scribe.py
│   │   │   ├── graph.py
│   │   │   └── llm.py
│   │   ├── models/           # Pydantic models
│   │   └── db/               # Database utilities
│   ├── tests/                # Pytest tests
│   └── requirements.txt
│
├── supabase/                  # Supabase config
│   ├── migrations/           # SQL migrations
│   └── seed.sql              # Test data
│
├── docs/                      # Documentation
│   ├── architecture.md
│   ├── api_contracts.md
│   ├── security.md
│   └── e2e_tests.md
│
├── scripts/                   # Utility scripts
│
└── .env.example              # Environment template
```
