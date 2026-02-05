# Roadmap: Escalations (Epic F)

> When the system doesn't know, it asks the owner and learns from the response.

## Overview

Implement the escalation loop: detect low confidence → create escalation → owner responds → optionally add to brain → improve future responses.

## Dependencies

- ✅ Epic A (Auth + Multi-Tenancy)
- ✅ Epic B (Twin Creation)
- ✅ Epic E (Hybrid Chat) - for confidence detection

## Tasks

### F1: Escalations Database Schema
**Status**: Not Started
**Estimated**: 2 hours

- [ ] Create migration: 010_escalations.sql
- [ ] Add RLS policies
- [ ] Add indexes for queries

**Schema**:
```sql
CREATE TABLE escalations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    source_conversation_id UUID REFERENCES conversations(id),
    source_message_id UUID REFERENCES messages(id),

    question TEXT NOT NULL,          -- What the user asked
    context TEXT,                     -- Relevant context from conversation
    ai_attempt TEXT,                  -- What the AI tried to answer (if anything)
    confidence_score FLOAT,           -- Why it escalated

    status TEXT DEFAULT 'pending',    -- pending, responded, dismissed
    owner_response TEXT,              -- Owner's answer
    add_to_brain BOOLEAN DEFAULT FALSE, -- Should this become knowledge

    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,

    CONSTRAINT valid_status CHECK (status IN ('pending', 'responded', 'dismissed'))
);

-- RLS
ALTER TABLE escalations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own tenant escalations"
ON escalations FOR ALL
USING (tenant_id = auth.jwt() ->> 'tenant_id');

-- Index for pending escalations
CREATE INDEX idx_escalations_pending ON escalations(twin_id, status) WHERE status = 'pending';
```

**Acceptance Criteria**:
- Migration runs successfully
- RLS prevents cross-tenant access
- Efficient queries for pending escalations

---

### F2: Confidence Detection
**Status**: Not Started
**Estimated**: 4 hours
**Dependencies**: F1

- [ ] Add confidence scoring to chat response
- [ ] Use GPT-4o structured output for confidence
- [ ] Define confidence threshold (default 0.7)
- [ ] Detect "I don't know" conditions:
  - No relevant documents found
  - Graph has no information
  - Query is out of scope

**Confidence Response Schema**:
```python
class ChatResponseWithConfidence(BaseModel):
    response: str
    confidence: float  # 0.0 to 1.0
    reasoning: str     # Why this confidence level
    sources_used: List[str]
```

**Confidence Triggers**:
```python
LOW_CONFIDENCE_CONDITIONS = [
    "retrieval_score < 0.5",  # Poor vector match
    "graph_nodes_found == 0",  # No graph context
    "query_type == 'specific_fact'",  # Needs exact knowledge
]
```

**Acceptance Criteria**:
- Confidence score in every response
- Low confidence triggers "I don't know"
- Reasoning is accurate

**Test Plan**:
```python
def test_low_confidence_on_unknown_topic():
    # Ask about something not in the brain
    response = chat(twin_id, "What's John's favorite restaurant?")

    assert response.confidence < 0.7
    assert "I don't know" in response.response or "not sure" in response.response
```

---

### F3: Escalation Creation
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: F1, F2

- [ ] Create escalation when confidence < threshold
- [ ] Store question, context, and AI attempt
- [ ] Link to source conversation
- [ ] Notify owner (in-app for MVP)

**Creation Flow**:
```python
async def maybe_escalate(
    twin_id: UUID,
    conversation_id: UUID,
    message: str,
    response: ChatResponseWithConfidence
):
    if response.confidence < CONFIDENCE_THRESHOLD:
        await create_escalation(
            twin_id=twin_id,
            source_conversation_id=conversation_id,
            question=message,
            context=get_conversation_context(conversation_id),
            ai_attempt=response.response if response.confidence > 0.3 else None,
            confidence_score=response.confidence
        )

        # Modify response to indicate uncertainty
        return modify_response_with_uncertainty(response)

    return response
```

**Acceptance Criteria**:
- Escalations created automatically
- Context preserved for owner
- Response indicates uncertainty

---

### F4: Escalations API
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: F1, F3

- [ ] GET /api/twins/{id}/escalations - List escalations
- [ ] GET /api/twins/{id}/escalations/{id} - Get escalation
- [ ] POST /api/twins/{id}/escalations/{id}/respond - Owner responds
- [ ] POST /api/twins/{id}/escalations/{id}/dismiss - Dismiss

**Response Payload**:
```python
class EscalationResponse(BaseModel):
    response: str                # Owner's answer
    add_to_brain: bool = False   # Whether to add as knowledge
    memory_type: Optional[str]   # 'fact', 'preference', 'knowledge'
```

**Acceptance Criteria**:
- Owner can view pending escalations
- Owner can respond or dismiss
- Response triggers knowledge integration

---

### F5: Escalation UI
**Status**: Not Started
**Estimated**: 4 hours
**Dependencies**: F4

- [ ] Create EscalationQueue component
- [ ] Show question with context
- [ ] Show AI's uncertain attempt (if any)
- [ ] Response textarea
- [ ] "Add to brain" checkbox
- [ ] Quick dismiss option

**UI Flow**:
```
┌─────────────────────────────────────────────┐
│ 🤔 Escalation #23              Dec 24, 3pm  │
├─────────────────────────────────────────────┤
│ Someone asked:                               │
│ "What's our investment thesis for AI?"       │
│                                              │
│ Context:                                     │
│ User was asking about AI investments...      │
│                                              │
│ I attempted:                                 │
│ "I'm not certain, but you might focus on..." │
│ (Confidence: 45%)                            │
├─────────────────────────────────────────────┤
│ Your response:                               │
│ ┌─────────────────────────────────────────┐ │
│ │ We invest in AI infrastructure...       │ │
│ └─────────────────────────────────────────┘ │
│                                              │
│ ☑ Add to brain as permanent knowledge        │
│                                              │
│ [Dismiss]                     [Send Response]│
└─────────────────────────────────────────────┘
```

**Acceptance Criteria**:
- Clear presentation of escalation
- Context helps owner understand
- Easy to respond or dismiss

---

### F6: Knowledge Integration from Response
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: F4, D2 (Memory Scribe)

- [ ] Extract knowledge from owner response
- [ ] Use Memory Scribe for extraction
- [ ] Auto-approve if add_to_brain is true
- [ ] Create graph nodes/edges
- [ ] Store in Pinecone

**Integration Flow**:
```python
async def integrate_escalation_response(escalation_id: UUID, response: str, add_to_brain: bool):
    escalation = await get_escalation(escalation_id)

    await update_escalation(escalation_id,
        status='responded',
        owner_response=response,
        add_to_brain=add_to_brain
    )

    if add_to_brain:
        # Extract and integrate
        extraction = await scribe.extract(f"Q: {escalation.question}\nA: {response}")
        for entity in extraction.entities:
            await upsert_node(escalation.twin_id, entity)
        for fact in extraction.facts:
            await upsert_fact_node(escalation.twin_id, fact)

        # Also store as document chunk for RAG
        await store_qa_pair(escalation.twin_id, escalation.question, response)
```

**Acceptance Criteria**:
- Owner responses become knowledge
- Knowledge available in future chats
- Q&A pairs searchable via RAG

**Test Plan**:
```python
def test_escalation_response_improves_future_chat():
    # Create escalation
    response1 = chat(twin_id, "What's our min check size?")
    assert response1.confidence < 0.7

    # Owner responds
    respond_to_escalation(escalation_id, "Our minimum check is $500K", add_to_brain=True)

    # Future chat should know
    response2 = chat(twin_id, "What's the minimum investment you make?")
    assert "$500K" in response2.response
    assert response2.confidence > 0.7
```

---

### F7: Escalation Badge/Notifications
**Status**: Not Started
**Estimated**: 2 hours
**Dependencies**: F4

- [ ] Add escalation count badge to nav
- [ ] Show pending count on dashboard
- [ ] Real-time updates (optional)

**Acceptance Criteria**:
- Owner sees pending escalation count
- Badge updates on resolution

---

### F8: "I Don't Know" Response Templates
**Status**: Not Started
**Estimated**: 2 hours
**Dependencies**: F2

- [ ] Create response templates for uncertainty
- [ ] Vary by confidence level
- [ ] Include what AI does know
- [ ] Mention escalation was created

**Templates**:
```python
UNCERTAINTY_TEMPLATES = {
    "no_info": "I don't have information about {topic}. I've flagged this for {owner} to review.",
    "partial_info": "I have some context but I'm not confident about {specific}. {owner} will be notified to clarify.",
    "out_of_scope": "This seems outside my knowledge area. I've escalated this to {owner}.",
}
```

**Acceptance Criteria**:
- Responses feel natural
- User knows escalation was created
- Partial knowledge is shared

---

## Progress

| Task | Status | Date | Notes |
|------|--------|------|-------|
| F1 | Not Started | | |
| F2 | Not Started | | |
| F3 | Not Started | | |
| F4 | Not Started | | |
| F5 | Not Started | | |
| F6 | Not Started | | |
| F7 | Not Started | | |
| F8 | Not Started | | |
