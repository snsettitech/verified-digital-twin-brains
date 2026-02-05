# API Contracts

> Complete API specification for the Digital Brain MVP.

## Base URL

- **Development**: `http://localhost:8000/api`
- **Production**: `https://api.digitalbrain.app/api`

## Authentication

All endpoints (except health) require a valid Supabase JWT token.

```
Authorization: Bearer <jwt_token>
```

The JWT contains:
- `sub`: User ID
- `email`: User email
- `tenant_id`: Tenant ID (custom claim)

---

## Auth Endpoints

### GET /api/auth/me
Get current authenticated user.

**Response 200**:
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "tenant_id": "uuid",
  "role": "owner",
  "created_at": "2024-12-24T00:00:00Z"
}
```

**Response 401**: Invalid or missing token

---

## Twin Endpoints

### POST /api/twins
Create a new twin.

**Request**:
```json
{
  "name": "My VC Brain",
  "description": "Digital twin for venture capital decisions",
  "specialization": "vc_brain"
}
```

**Response 201**:
```json
{
  "id": "uuid",
  "name": "My VC Brain",
  "description": "Digital twin for venture capital decisions",
  "specialization": "vc_brain",
  "onboarding_status": "pending",
  "personality": {},
  "created_at": "2024-12-24T00:00:00Z"
}
```

### GET /api/twins
List twins for current tenant.

**Query Parameters**:
- `limit` (int, default 20): Max results
- `offset` (int, default 0): Pagination offset

**Response 200**:
```json
{
  "twins": [...],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

### GET /api/twins/{twin_id}
Get a specific twin.

**Response 200**: Twin object
**Response 404**: Twin not found (or not accessible)

### PATCH /api/twins/{twin_id}
Update a twin.

**Request**:
```json
{
  "name": "Updated Name",
  "personality": {
    "tone": "professional",
    "verbosity": "concise"
  }
}
```

### DELETE /api/twins/{twin_id}
Delete a twin and all associated data.

**Response 204**: Deleted successfully

---

## Chat Endpoints

### POST /api/twins/{twin_id}/conversations
Create a new conversation.

**Request**:
```json
{
  "mode": "chat"
}
```

**Response 201**:
```json
{
  "id": "uuid",
  "twin_id": "uuid",
  "mode": "chat",
  "created_at": "2024-12-24T00:00:00Z"
}
```

### GET /api/twins/{twin_id}/conversations
List conversations for a twin.

**Query Parameters**:
- `limit` (int, default 20)
- `offset` (int, default 0)

### GET /api/twins/{twin_id}/conversations/{conversation_id}
Get conversation with messages.

**Query Parameters**:
- `include_messages` (bool, default true)
- `message_limit` (int, default 50)

**Response 200**:
```json
{
  "id": "uuid",
  "twin_id": "uuid",
  "mode": "chat",
  "messages": [
    {
      "id": "uuid",
      "role": "user",
      "content": "Hello!",
      "created_at": "2024-12-24T00:00:00Z"
    },
    {
      "id": "uuid",
      "role": "assistant",
      "content": "Hello! How can I help?",
      "metadata": {
        "confidence": 0.95,
        "sources": []
      },
      "created_at": "2024-12-24T00:00:01Z"
    }
  ],
  "created_at": "2024-12-24T00:00:00Z"
}
```

### POST /api/twins/{twin_id}/chat
Send a chat message.

**Request**:
```json
{
  "conversation_id": "uuid",  // Optional, creates new if omitted
  "message": "What's our investment thesis?"
}
```

**Response 200**:
```json
{
  "conversation_id": "uuid",
  "message_id": "uuid",
  "response": "Our investment thesis focuses on...",
  "confidence": 0.87,
  "sources": [
    {
      "type": "document",
      "title": "Investment Memo",
      "chunk": "We invest in B2B SaaS..."
    }
  ],
  "escalated": false
}
```

**Response with Escalation**:
```json
{
  "conversation_id": "uuid",
  "message_id": "uuid",
  "response": "I don't have specific information about that. I've flagged this for the owner to review.",
  "confidence": 0.35,
  "sources": [],
  "escalated": true,
  "escalation_id": "uuid"
}
```

---

## Document Endpoints

### POST /api/twins/{twin_id}/documents/upload
Get signed upload URL.

**Request**:
```json
{
  "filename": "investment_thesis.pdf",
  "content_type": "application/pdf"
}
```

**Response 200**:
```json
{
  "upload_url": "https://storage.supabase.co/...",
  "document_id": "uuid",
  "expires_at": "2024-12-24T01:00:00Z"
}
```

### POST /api/twins/{twin_id}/documents/{document_id}/process
Trigger processing after upload.

**Response 202**:
```json
{
  "status": "processing",
  "document_id": "uuid"
}
```

### GET /api/twins/{twin_id}/documents
List documents.

**Response 200**:
```json
{
  "documents": [
    {
      "id": "uuid",
      "title": "Investment Thesis",
      "source_type": "upload",
      "processing_status": "completed",
      "chunk_count": 15,
      "created_at": "2024-12-24T00:00:00Z"
    }
  ],
  "total": 1
}
```

### GET /api/twins/{twin_id}/documents/{document_id}
Get document details.

### DELETE /api/twins/{twin_id}/documents/{document_id}
Delete document and vectors.

---

## Memory Endpoints

### GET /api/twins/{twin_id}/memory-candidates
List pending memory candidates.

**Query Parameters**:
- `status` (string): "pending", "approved", "rejected"
- `limit` (int, default 20)

**Response 200**:
```json
{
  "candidates": [
    {
      "id": "uuid",
      "content": "Prefers B2B SaaS investments",
      "memory_type": "preference",
      "extracted_data": {
        "category": "investment",
        "preference": "B2B SaaS",
        "strength": 0.8
      },
      "status": "pending",
      "created_at": "2024-12-24T00:00:00Z"
    }
  ],
  "total": 5
}
```

### POST /api/twins/{twin_id}/memory-candidates/{candidate_id}/approve
Approve a memory candidate.

**Response 200**:
```json
{
  "status": "approved",
  "graph_node_id": "uuid"
}
```

### POST /api/twins/{twin_id}/memory-candidates/{candidate_id}/reject
Reject a memory candidate.

**Response 200**:
```json
{
  "status": "rejected"
}
```

### GET /api/twins/{twin_id}/graph
Get graph summary.

**Response 200**:
```json
{
  "nodes_count": 45,
  "edges_count": 78,
  "node_types": {
    "person": 12,
    "company": 8,
    "concept": 15,
    "preference": 10
  },
  "recent_nodes": [...],
  "important_entities": [...]
}
```

---

## Escalation Endpoints

### GET /api/twins/{twin_id}/escalations
List escalations.

**Query Parameters**:
- `status` (string): "pending", "responded", "dismissed"
- `limit` (int, default 20)

**Response 200**:
```json
{
  "escalations": [
    {
      "id": "uuid",
      "question": "What's our minimum check size?",
      "context": "User was asking about investment criteria...",
      "ai_attempt": "I'm not certain, but typically...",
      "confidence_score": 0.45,
      "status": "pending",
      "created_at": "2024-12-24T00:00:00Z"
    }
  ],
  "total": 3
}
```

### POST /api/twins/{twin_id}/escalations/{escalation_id}/respond
Respond to an escalation.

**Request**:
```json
{
  "response": "Our minimum check is $500K for Series A.",
  "add_to_brain": true
}
```

**Response 200**:
```json
{
  "id": "uuid",
  "status": "responded",
  "knowledge_added": true,
  "graph_node_id": "uuid"
}
```

### POST /api/twins/{twin_id}/escalations/{escalation_id}/dismiss
Dismiss an escalation.

**Response 200**:
```json
{
  "id": "uuid",
  "status": "dismissed"
}
```

---

## Metrics Endpoints

### GET /api/twins/{twin_id}/metrics
Get twin metrics.

**Response 200**:
```json
{
  "total_conversations": 150,
  "total_messages": 890,
  "avg_confidence": 0.82,
  "escalation_count": 12,
  "escalation_rate": 0.05,
  "memory_candidates_pending": 8,
  "memory_candidates_approved": 45,
  "graph_nodes_count": 78,
  "documents_count": 5
}
```

### GET /api/twins/{twin_id}/digest
Get daily learning digest.

**Query Parameters**:
- `date` (string, default today): YYYY-MM-DD

**Response 200**:
```json
{
  "date": "2024-12-24",
  "new_entities": 3,
  "new_facts": 7,
  "new_relationships": 2,
  "highlights": [
    "Learned about Acme Corp's Series B funding",
    "Added John Smith as key contact",
    "Updated investment preferences for AI"
  ]
}
```

---

## Health Endpoint

### GET /health
Health check (no auth required).

**Response 200**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "database": "ok",
    "pinecone": "ok",
    "openai": "ok"
  }
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  }
}
```

**Common Error Codes**:
- `UNAUTHORIZED`: 401 - Missing or invalid token
- `FORBIDDEN`: 403 - Valid token but no access
- `NOT_FOUND`: 404 - Resource not found
- `VALIDATION_ERROR`: 422 - Invalid request body
- `RATE_LIMITED`: 429 - Too many requests
- `INTERNAL_ERROR`: 500 - Server error
