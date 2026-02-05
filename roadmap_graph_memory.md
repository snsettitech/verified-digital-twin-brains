# Roadmap: Graph Memory (Epic D)

> Cognitive graph that captures entities, relationships, and facts from conversations.

## Overview

Implement a property graph in Postgres that stores extracted knowledge from conversations. The Memory Scribe extracts entities and relationships, stores them as candidates for approval, and integrates them into the graph upon owner approval.

## Dependencies

- ✅ Epic A (Auth + Multi-Tenancy)
- ✅ Epic B (Twin Creation)

## Tasks

### D1: Graph Database Schema
**Status**: Not Started
**Estimated**: 3 hours

- [ ] Create migration: 006_graph_nodes.sql
- [ ] Create migration: 007_graph_edges.sql
- [ ] Create migration: 008_memory_candidates.sql
- [ ] Add RLS policies for all tables
- [ ] Add indexes for graph traversal

**Schema**:
```sql
-- Graph Nodes
CREATE TABLE graph_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    node_type TEXT NOT NULL, -- 'person', 'company', 'concept', 'preference', 'fact'
    name TEXT NOT NULL,
    description TEXT,
    properties JSONB DEFAULT '{}',
    embedding VECTOR(1536), -- pgvector for similarity search
    source_id UUID, -- link to memory_candidate or document
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(twin_id, node_type, name) -- prevent duplicates
);

-- Graph Edges
CREATE TABLE graph_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_node_id UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    to_node_id UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    relationship_type TEXT NOT NULL, -- 'works_at', 'invested_in', 'prefers', etc.
    weight FLOAT DEFAULT 1.0,
    properties JSONB DEFAULT '{}',
    source_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(from_node_id, to_node_id, relationship_type)
);

-- Memory Candidates
CREATE TABLE memory_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    source_message_id UUID, -- link to messages table
    source_conversation_id UUID,
    content TEXT NOT NULL, -- human-readable summary
    memory_type TEXT NOT NULL, -- 'entity', 'fact', 'preference', 'relationship'
    extracted_data JSONB NOT NULL, -- structured extraction
    status TEXT DEFAULT 'pending', -- pending, approved, rejected
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ
);

-- Indexes for graph traversal
CREATE INDEX idx_graph_nodes_twin ON graph_nodes(twin_id);
CREATE INDEX idx_graph_nodes_type ON graph_nodes(twin_id, node_type);
CREATE INDEX idx_graph_edges_from ON graph_edges(from_node_id);
CREATE INDEX idx_graph_edges_to ON graph_edges(to_node_id);
CREATE INDEX idx_memory_candidates_status ON memory_candidates(twin_id, status);
```

**Acceptance Criteria**:
- All tables created with RLS
- Indexes in place for performance
- pgvector extension enabled

---

### D2: Memory Scribe Service
**Status**: Not Started
**Estimated**: 5 hours
**Dependencies**: D1

- [ ] Create GPT-4o extraction prompt
- [ ] Use Structured Outputs for consistent format
- [ ] Extract entities, facts, preferences
- [ ] Identify relationships between entities
- [ ] Store as memory candidates

**Extraction Schema**:
```python
class ExtractedMemory(BaseModel):
    entities: List[Entity]
    facts: List[Fact]
    preferences: List[Preference]
    relationships: List[Relationship]

class Entity(BaseModel):
    name: str
    type: str  # person, company, concept
    description: Optional[str]
    properties: Dict[str, Any]

class Fact(BaseModel):
    subject: str
    predicate: str
    object: str
    confidence: float

class Preference(BaseModel):
    category: str
    preference: str
    strength: float  # -1 to 1

class Relationship(BaseModel):
    from_entity: str
    to_entity: str
    relationship_type: str
    context: Optional[str]
```

**GPT-4o Prompt**:
```
You are a Memory Scribe. Extract structured knowledge from the conversation.
Focus on:
1. Named entities (people, companies, concepts)
2. Facts and preferences expressed
3. Relationships between entities

Return structured JSON matching the schema.
```

**Acceptance Criteria**:
- Accurate extraction from conversations
- Structured output matches schema
- Handles edge cases (no knowledge to extract)

**Test Plan**:
```python
def test_scribe_extracts_entities():
    message = "I usually invest in B2B SaaS companies like Stripe and Figma"

    result = await scribe.extract(message)

    assert "Stripe" in [e.name for e in result.entities]
    assert "Figma" in [e.name for e in result.entities]
    assert any(p.category == "investment" for p in result.preferences)
```

---

### D3: Memory Candidates API
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: D1, D2

- [ ] GET /api/twins/{id}/memory-candidates - List pending
- [ ] POST /api/twins/{id}/memory-candidates/{id}/approve
- [ ] POST /api/twins/{id}/memory-candidates/{id}/reject
- [ ] GET /api/twins/{id}/memory-candidates/stats

**Acceptance Criteria**:
- Owner can view pending candidates
- Approve integrates into graph
- Reject archives candidate
- Stats show daily learning

---

### D4: Memory Approval UI
**Status**: Not Started
**Estimated**: 4 hours
**Dependencies**: D3

- [ ] Create MemoryQueue component
- [ ] Show pending memories with context
- [ ] Quick approve/reject buttons
- [ ] Batch actions
- [ ] Show graph impact preview

**Acceptance Criteria**:
- Clear presentation of memories
- Easy approve/reject flow
- Context helps decision making

---

### D5: Graph Integration on Approval
**Status**: Not Started
**Estimated**: 4 hours
**Dependencies**: D1, D3

- [ ] Create graph integration service
- [ ] Insert nodes with deduplication
- [ ] Insert edges with weight updates
- [ ] Generate embeddings for new nodes
- [ ] Store embeddings in pgvector

**Node Deduplication**:
```python
async def upsert_node(twin_id: UUID, entity: Entity):
    existing = await find_node(twin_id, entity.type, entity.name)
    if existing:
        # Merge properties, update description
        return await update_node(existing.id, entity)
    else:
        return await create_node(twin_id, entity)
```

**Acceptance Criteria**:
- Approved memories become graph nodes
- Duplicates are merged intelligently
- Relationships create edges

---

### D6: Graph Query Service
**Status**: Not Started
**Estimated**: 4 hours
**Dependencies**: D5

- [ ] Implement traversal queries
- [ ] Get related entities (1-hop, 2-hop)
- [ ] Get facts about entity
- [ ] Full-text search on nodes
- [ ] Vector similarity search on nodes

**Query Types**:
```python
async def get_related_entities(twin_id: UUID, entity_name: str, hops: int = 2):
    """Get entities within N hops of given entity"""

async def get_entity_facts(twin_id: UUID, entity_name: str):
    """Get all facts where entity is subject or object"""

async def search_graph(twin_id: UUID, query: str, top_k: int = 10):
    """Vector similarity search over node embeddings"""
```

**Acceptance Criteria**:
- Traversal queries work correctly
- Performance is acceptable (< 100ms for 2-hop)
- Vector search finds relevant nodes

---

### D7: Graph Brief Generator
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: D6

- [ ] Generate context brief from graph
- [ ] Include relevant entities and relationships
- [ ] Format for LLM consumption
- [ ] Limit to reasonable context size

**Brief Format**:
```
## Known Entities (relevant to query)
- John Smith (Person): CEO of Acme Corp, connected since 2020
- Acme Corp (Company): B2B SaaS, Series B, $20M revenue

## Key Facts
- John prefers email over phone calls
- Acme Corp uses our competitor's product currently

## Relationships
- John Smith → works_at → Acme Corp
- Acme Corp → competes_with → Competitor Inc
```

**Acceptance Criteria**:
- Brief is concise and relevant
- Includes most important context
- Formatted for LLM understanding

---

### D8: "Brain Learned Today" Digest
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: D3

- [ ] Create daily digest endpoint
- [ ] Summarize approved memories
- [ ] Count by category
- [ ] Create DigestCard component
- [ ] Show on dashboard

**Digest Content**:
```python
class DailyDigest(BaseModel):
    date: date
    new_entities: int
    new_facts: int
    new_relationships: int
    highlights: List[str]  # Top 3 learnings
```

**Acceptance Criteria**:
- Digest shows daily learning
- Highlights are meaningful
- Visible on dashboard

---

## Progress

| Task | Status | Date | Notes |
|------|--------|------|-------|
| D1 | Not Started | | |
| D2 | Not Started | | |
| D3 | Not Started | | |
| D4 | Not Started | | |
| D5 | Not Started | | |
| D6 | Not Started | | |
| D7 | Not Started | | |
| D8 | Not Started | | |
