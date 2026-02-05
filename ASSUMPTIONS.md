# Assumptions

This document tracks assumptions made during development when information was not explicitly provided.

## Infrastructure Assumptions

1. **Supabase Project**: A Supabase project exists or will be created with:
   - Auth enabled with email/password
   - Postgres database with RLS capabilities
   - Service role key and anon key available

2. **Pinecone Index**: A Pinecone index exists or will be created with:
   - Dimension: 1536 (OpenAI ada-002 embeddings)
   - Metric: cosine similarity
   - Namespace support enabled

3. **OpenAI Access**: OpenAI API access with:
   - GPT-4o model access
   - text-embedding-ada-002 access
   - Sufficient quota for development/testing

4. **Langfuse Account**: Langfuse cloud or self-hosted instance available

## Technical Assumptions

1. **Tenant Model**: Single-tenant users (one tenant per user account for MVP)
   - In future: support organizational tenants with multiple users

2. **Twin Ownership**: Each twin has exactly one owner (the creator)
   - Owner can grant read access to others (post-MVP)

3. **Embedding Model**: Using OpenAI text-embedding-ada-002 (1536 dimensions)
   - Future: support custom embedding models

4. **Graph Implementation**: Using Postgres tables for graph storage
   - Nodes and edges stored relationally
   - LlamaIndex PropertyGraphIndex for querying orchestration
   - No separate graph database (Neo4j) for MVP

5. **Memory Approval Flow**: All extracted memories require owner approval
   - Automated approval can be enabled per-twin (post-MVP)

6. **Escalation Response**: Owner responds via web UI
   - Email/Slack notifications are post-MVP

## API Assumptions

1. **JWT Claims**: Supabase JWT contains:
   - `sub`: user_id
   - `email`: user email
   - Custom claims for tenant_id after tenant creation

2. **Rate Limiting**: API rate limiting handled by Render/Vercel
   - Custom rate limiting per twin is post-MVP

3. **File Upload**: Documents uploaded via signed URLs to Supabase Storage
   - Backend processes asynchronously

## Security Assumptions

1. **RLS Policies**: All user-facing queries go through Supabase client with anon key
   - Service role key only for:
     - User sync from auth.users
     - Background jobs
     - Admin operations

2. **Namespace Format**: Pinecone namespace = `{tenant_id}:{twin_id}`
   - Ensures no cross-tenant vector access

3. **Input Sanitization**: All user inputs sanitized before:
   - LLM prompts (prevent injection)
   - Database queries (prevent SQL injection via RLS)

## UI/UX Assumptions

1. **Onboarding Flow**:
   - Step 1: Create twin (name, description, specialization)
   - Step 2: Interview mode OR document upload
   - Step 3: Begin chatting

2. **"Brain Learned Today"**: Daily digest email/notification
   - MVP: In-app notification only
   - Shows approved memories from last 24h

3. **Confidence Threshold**: 0.7 confidence score for "I don't know" responses
   - Configurable per twin (post-MVP)
