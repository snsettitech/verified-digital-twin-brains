# Architecture: Digital Brains Platform

The platform is a multi-tenant, governance-first AI system that scales human expertise through "Verified Twins."

## 1. Core Model: The Twin Loop
Verified Twin → Knowledge → Reasoning → Action → Escalation → Audit

- **Verified Twin**: A digital identity tied to an owner (Tenant).
- **Knowledge**: Multi-tier RAG (Supabase QnA -> Pinecone Vector -> Neo4j Graph).
- **Reasoning**: LLM-driven intent extraction and tool selection.
- **Action**: Execution of authorized tasks via integrated tools (Composio).
- **Escalation**: Low-confidence queries are routed to humans; valid answers become memory.
- **Audit**: Every interaction and action is logged in `audit_logs`.

## 2. Technical Stack
- **Backend**: FastAPI (Python), Supabase (Postgres/Auth/Storage).
- **Frontend**: Next.js (TypeScript), Tailwind CSS.
- **Reasoning**: OpenAI/Claude via LangChain/LangGraph.
- **Memory/RAG**: Pinecone (Vector), Neo4j (Graph), Supabase (Relational).

## 3. Data Primitives
- **Tenant**: The isolation unit. Users belong to exactly one tenant.
- **Twin**: Belong to a Tenant. Specialized for a person or function (e.g., Professor Brain, VC Brain).
- **Memory Node**: A discrete piece of knowledge with provenance.
- **Action Draft**: A prepared action awaiting approval.
