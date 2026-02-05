# CLAUDE.md

This file provides guidance to Claude Code and Cursor when working with the **Verified Digital Twin Brain** repository.

## Workspace Overview

This project consists of a FastAPI backend and a Next.js frontend, integrated with Supabase (Postgres/Auth), Pinecone (Vector DB), and OpenAI (LLMs).

## Common Commands

### Backend (FastAPI)
Navigate to project: `cd backend`

**Setup:**
```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Development:**
```bash
# Run the FastAPI server
python main.py
# OR
uvicorn main:app --reload
```

**Testing:**
```bash
python test_system.py
```

### Frontend (Next.js)
Navigate to project: `cd frontend`

**Development:**
```bash
npm install
npm run dev
```

## Architecture & Project Structure

- `backend/`: FastAPI application.
  - `main.py`: Application entry point.
  - `modules/`: Core logic modules (ingestion, retrieval, answering, escalation).
  - `modules/clients.py`: Centralized client initialization for OpenAI and Pinecone.
  - `modules/schemas.py`: Pydantic models for API validation.
- `frontend/`: Next.js 14 application using Tailwind CSS.
- `supabase_schema.sql`: Database schema for Supabase.

## System Dependencies

### Supabase Tables
- `twins`: (id, tenant_id, name, description, settings, created_at)
- `sources`: (id, twin_id, filename, file_size, status, created_at)
- `conversations`: (id, twin_id, user_id, created_at)
- `messages`: (id, conversation_id, role, content, confidence_score, citations, created_at)
- `escalations`: (id, message_id, status, resolved_by, resolved_at)
- `verified_qna`: (id, twin_id, question, answer, question_embedding, visibility, created_by, created_at, updated_at, is_active)
- `answer_patches`: (id, verified_qna_id, previous_answer, new_answer, reason, patched_by, patched_at)
- `citations`: (id, verified_qna_id, source_id, chunk_id, citation_url, created_at)
- `access_groups`: (Phase 5 - audience segmentation)
- `group_memberships`: (Phase 5)
- `content_permissions`: (Phase 5)
- `group_limits`: (Phase 5)
- `group_overrides`: (Phase 5)
- `twin_api_keys`: (Phase 7 - API key management)
- `sessions`: (Phase 7 - anonymous session tracking)
- `rate_limit_tracking`: (Phase 7)
- `user_invitations`: (Phase 7)
- `events`: (Phase 8 - event logging for triggers)
- `tool_connectors`: (Phase 8 - external service configs)
- `action_triggers`: (Phase 8 - automation rules)
- `action_drafts`: (Phase 8 - pending approvals)
- `action_executions`: (Phase 8 - execution audit logs)

### Pinecone Configuration
- **Metric**: Cosine
- **Dimension**: 3072 (for `text-embedding-3-large`)
- **Metadata Filtering**: Must filter by `twin_id`.

## Phase Completion Status

| Phase | Name | Status |
|-------|------|--------|
| 1 | MVP - Grounded Answers | ✅ Complete |
| 2 | Cloud Agents & Verified Memory | ✅ Complete |
| 3 | Digital Persona & Multi-Modal Mind | ✅ Complete |
| 4 | Verified-First Knowledge Layer | ✅ Complete |
| 5 | Access Groups | ✅ Complete |
| 6 | Mind Ops Layer | ✅ Complete |
| 7 | Omnichannel Distribution | ✅ Complete |
| 8 | Actions Engine | ✅ Complete |
| 9 | Verification & Governance | ✅ Complete |
| 3.5 | Cognitive Brain Builder | ✅ Complete |
| 10 | Enterprise Scale | 🔲 Vision |

**See:** `PLATFORM_ROADMAP.md` for Gate-by-Gate details of Phase 3.5.

### Phase 3.5 Tables (Cognitive Brain)
- `nodes`: (id, twin_id, type, name, description, properties, source_message_id, created_at)
- `edges`: (id, twin_id, from_node_id, to_node_id, relation_type, strength, created_at)

## Specialization Architecture

The platform supports **specialization variants** (e.g., VC Brain, Legal Brain) via a configuration-first approach. 

### Key Files
- `backend/modules/_core/` - Generic feature base (Host, Scribe, Graph, Guard)
- `backend/modules/specializations/registry.json` - Global specialization registry
- `backend/modules/specializations/vc/manifest.json` - VC specialization definition
- `backend/modules/specializations/vc/ontology/vc_base_pack.json` - VC knowledge structure
- `frontend/src/specializations/vc/ui_clusters.json` - VC UI definitions

### Specialization Selection
Specialization is resolved per-twin at runtime via the `twins.specialization_id` column in the database.
- `GET /twins/{twin_id}/specialization` returns the effective manifest.
- Specializations are **assets-only** (JSON/Prompts); no new core logic.

### Creating New Specializations
Use workflow: `/create-specialization`

## Guidelines

- **Style**: Follow `.agent/CODING_STANDARDS.md` for all code
- **RAG Integrity**: Ensure all answers include citations from the knowledge base.
- **Trust Layer**: High importance on confidence scoring and escalation for low-confidence answers.
- **Security**: Never commit `.env` files. Use `.env.example` for template keys.
- **Specializations**: Never modify core modules - only extend via interfaces.
- **Documentation**: Update CLAUDE.md when adding new modules, endpoints, or tables.
- **Client Management**: All Supabase clients should use `modules.observability.supabase` for consistency. Never create duplicate client instances.
- **Database**: Always use migrations in `backend/database/migrations/` for schema changes. The `supabase_schema.sql` is a reference only.

