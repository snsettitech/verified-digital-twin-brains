# Roadmap: Hybrid Chat Retrieval (Epic E)

> Combine vectors + graph + conversation history for rich context.

## Overview

Implement the chat endpoint with hybrid retrieval: vector search from Pinecone, graph context from Postgres, and recent conversation history. The retrieval pipeline feeds context to GPT-4o for response generation.

## Dependencies

- ✅ Epic A (Auth + Multi-Tenancy)
- ✅ Epic B (Twin Creation)
- ⚠️ Epic D (Graph Memory) - for graph context
- ⚠️ Epic C (Ingestion) - for vector context

Note: Can start with basic chat before full ingestion/graph are complete.

## Tasks

### E1: Conversations Database Schema
**Status**: Not Started
**Estimated**: 2 hours

- [ ] Create migration: 009_conversations.sql
- [ ] Create messages table
- [ ] Add RLS policies
- [ ] Add indexes

**Schema**:
```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID NOT NULL REFERENCES users(id),
    mode TEXT DEFAULT 'chat', -- 'chat', 'interview', 'onboarding'
    title TEXT,
    context JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    role TEXT NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    tool_calls JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can access own tenant conversations"
ON conversations FOR ALL
USING (tenant_id = auth.jwt() ->> 'tenant_id');

CREATE POLICY "Users can access own tenant messages"
ON messages FOR ALL
USING (tenant_id = auth.jwt() ->> 'tenant_id');

-- Indexes
CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX idx_conversations_twin ON conversations(twin_id, created_at DESC);
```

**Acceptance Criteria**:
- Tables created with RLS
- Efficient message retrieval

---

### E2: Chat API Endpoint
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: E1

- [ ] POST /api/twins/{id}/chat - Send message
- [ ] GET /api/twins/{id}/conversations - List conversations
- [ ] GET /api/twins/{id}/conversations/{id} - Get conversation
- [ ] POST /api/twins/{id}/conversations - Create conversation

**Chat Request/Response**:
```python
class ChatRequest(BaseModel):
    conversation_id: Optional[UUID]  # Continue existing or create new
    message: str

class ChatResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    response: str
    sources: List[Source]
    confidence: float
```

**Acceptance Criteria**:
- Can send and receive messages
- Conversations persist
- Response includes sources

---

### E3: Vector Retrieval Service
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: E2, C6 (Pinecone)

- [ ] Query Pinecone with user message
- [ ] Use namespace: `{tenant_id}:{twin_id}`
- [ ] Return top-k results with metadata
- [ ] Format for LLM context

**Retrieval Flow**:
```python
async def vector_retrieve(twin_id: UUID, tenant_id: UUID, query: str, top_k: int = 5):
    namespace = f"{tenant_id}:{twin_id}"

    query_embedding = await embed(query)

    results = pinecone_index.query(
        vector=query_embedding,
        namespace=namespace,
        top_k=top_k,
        include_metadata=True
    )

    return [
        RetrievalResult(
            content=r.metadata["text"],
            source=r.metadata["source"],
            score=r.score
        )
        for r in results.matches
    ]
```

**Acceptance Criteria**:
- Retrieval uses correct namespace
- Results are relevant
- Metadata included

---

### E4: Graph Retrieval Service
**Status**: Not Started
**Estimated**: 4 hours
**Dependencies**: E2, D6 (Graph Query)

- [ ] Extract entities from query
- [ ] Find related nodes in graph
- [ ] Get facts about entities
- [ ] Format as graph brief

**Graph Retrieval Flow**:
```python
async def graph_retrieve(twin_id: UUID, query: str):
    # Extract entities from query using NER or LLM
    entities = await extract_entities(query)

    brief_parts = []
    for entity in entities:
        # Find node
        node = await find_node(twin_id, entity)
        if node:
            # Get related nodes
            related = await get_related(twin_id, node.id, hops=1)
            # Get facts
            facts = await get_facts(twin_id, node.id)

            brief_parts.append(format_node_context(node, related, facts))

    return "\n".join(brief_parts)
```

**Acceptance Criteria**:
- Entities extracted from query
- Graph context retrieved when relevant
- Brief is concise and informative

---

### E5: Conversation History Retrieval
**Status**: Not Started
**Estimated**: 2 hours
**Dependencies**: E1

- [ ] Get recent messages from conversation
- [ ] Limit to last N messages (default 10)
- [ ] Format for LLM context

**History Format**:
```python
async def get_conversation_context(conversation_id: UUID, limit: int = 10):
    messages = await get_recent_messages(conversation_id, limit)

    return [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]
```

**Acceptance Criteria**:
- Recent history retrieved
- Truncated to reasonable size

---

### E6: Hybrid Retriever Orchestrator
**Status**: Not Started
**Estimated**: 4 hours
**Dependencies**: E3, E4, E5

- [ ] Combine vector, graph, and history retrieval
- [ ] Run retrievals in parallel
- [ ] Assemble context with priorities
- [ ] Respect token limits

**Orchestration**:
```python
async def hybrid_retrieve(
    twin_id: UUID,
    tenant_id: UUID,
    conversation_id: UUID,
    query: str
) -> RetrievalContext:
    # Run retrievals in parallel
    vector_results, graph_brief, history = await asyncio.gather(
        vector_retrieve(twin_id, tenant_id, query),
        graph_retrieve(twin_id, query),
        get_conversation_context(conversation_id)
    )

    return RetrievalContext(
        documents=vector_results,
        graph_brief=graph_brief,
        conversation_history=history,
        total_tokens=count_tokens(...)
    )
```

**Acceptance Criteria**:
- All sources combined
- Parallel execution for speed
- Token limits respected

---

### E7: LLM Generation Service
**Status**: Not Started
**Estimated**: 4 hours
**Dependencies**: E6

- [ ] Create system prompt with twin personality
- [ ] Inject retrieval context
- [ ] Use GPT-4o with structured output
- [ ] Stream response (optional)
- [ ] Track token usage

**System Prompt Template**:
```python
SYSTEM_PROMPT = """
You are {twin_name}, a {specialization} digital twin.

Personality: {personality_description}

Use the following context to answer:

## Documents
{document_context}

## Known Facts & Relationships
{graph_brief}

## Recent Conversation
{conversation_history}

Guidelines:
- Be {tone} and {verbosity}
- If you don't know, say so
- Cite sources when possible
"""
```

**Acceptance Criteria**:
- Responses match personality
- Context is used appropriately
- Token usage tracked

---

### E8: Chat UI
**Status**: Not Started
**Estimated**: 5 hours
**Dependencies**: E2

- [ ] Create ChatInterface component
- [ ] Message input with send button
- [ ] Message list with bubbles
- [ ] Loading states
- [ ] Error handling
- [ ] Sources panel (expandable)

**UI Components**:
- ChatContainer
- MessageList
- MessageBubble (user/assistant variants)
- ChatInput
- SourcesPanel
- TypingIndicator

**Acceptance Criteria**:
- Clean, responsive chat UI
- Messages render correctly
- Sources are accessible

---

### E9: Memory Extraction on Chat
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: E7, D2 (Memory Scribe)

- [ ] Run Memory Scribe after each response
- [ ] Extract from user message + context
- [ ] Create memory candidates
- [ ] Link to source message

**Post-Chat Pipeline**:
```python
async def post_chat_processing(conversation_id: UUID, user_message: str, assistant_response: str):
    # Extract memories from the exchange
    extraction = await scribe.extract(
        f"User: {user_message}\nAssistant: {assistant_response}"
    )

    # Create candidates for approval
    for entity in extraction.entities:
        await create_memory_candidate(
            twin_id=...,
            content=f"Entity: {entity.name} ({entity.type})",
            memory_type="entity",
            extracted_data=entity.dict(),
            source_conversation_id=conversation_id
        )

    # Similar for facts and preferences
```

**Acceptance Criteria**:
- Memories extracted from chat
- Candidates created for approval
- No blocking of chat response

---

## Progress

| Task | Status | Date | Notes |
|------|--------|------|-------|
| E1 | Not Started | | |
| E2 | Not Started | | |
| E3 | Not Started | | |
| E4 | Not Started | | |
| E5 | Not Started | | |
| E6 | Not Started | | |
| E7 | Not Started | | |
| E8 | Not Started | | |
| E9 | Not Started | | |
