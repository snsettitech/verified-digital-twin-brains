# Verified Digital Twin Brains

A high-fidelity Digital Twin system designed to replicate a user's voice, knowledge, and reasoning capabilities. Enterprise-grade AI platform with multi-tenant isolation, governance layers, and auditable reasoning.

## Core Features

- **Personalized Voice** - Clone and generate lifelike speech via ElevenLabs
- **Cognitive Graph** - Structured knowledge retrieval beyond simple RAG
- **Multi-Tenant Isolation** - Enterprise-grade security and permissions
- **Verified Reasoning** - Goal-oriented "Advisor Mode" with decision traces
- **Hybrid RAG** - Verified QnA > Vector Search > Tool Integration > Human Escalation
- **Governance & Audit** - Every answer/action is explainable, permissioned, and reviewable

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 16, TypeScript, Tailwind CSS |
| **Backend** | FastAPI, Python 3.12 |
| **Database** | Supabase (PostgreSQL + Auth + RLS) |
| **Vector Store** | Pinecone (3072-dim, serverless) |
| **LLM** | OpenAI GPT-4o, Claude via LangChain/LangGraph |
| **Observability** | Langfuse |
| **Voice** | ElevenLabs |
| **Deployment** | Vercel (frontend), Render/Railway (backend) |

## Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env  # Fill in keys
python main.py

# Frontend
cd frontend
npm install
npm run dev
```

See [docs/quick-start.md](docs/quick-start.md) for the full setup guide.

## Documentation

### Essential

| Doc | Purpose |
|-----|---------|
| [Quick Start](docs/quick-start.md) | Setup and 1-hour path to production |
| [Vision](docs/VISION.md) | Product principles and strategy |
| [System Overview](docs/architecture/system-overview.md) | Full architecture analysis |
| [API Contracts](docs/architecture/api_contracts.md) | REST API specification |
| [Security Model](docs/architecture/security-model.md) | Auth, RLS, threat model |

### Core Principles

| Doc | Purpose |
|-----|---------|
| [Architecture](docs/core/architecture.md) | Core model: Twin Loop |
| [Governance](docs/core/governance.md) | Security decorators and AI safety gates |
| [Invariants](docs/core/invariants.md) | Non-negotiable system rules |

### Operations

| Doc | Purpose |
|-----|---------|
| [Deployment Runbook](docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md) | Production deployment steps |
| [Troubleshooting](docs/ops/TROUBLESHOOTING_METHODOLOGY.md) | Debugging methodology |
| [Auth Troubleshooting](docs/ops/AUTH_TROUBLESHOOTING.md) | JWT/401/403 debugging |
| [Worker Setup](docs/ops/WORKER_SETUP_GUIDE.md) | Background job processing |
| [Quality Gate](docs/ops/QUALITY_GATE.md) | Pre-merge quality checks |
| [Runbooks](docs/ops/RUNBOOKS.md) | Operational procedures |
| [Known Failures](docs/KNOWN_FAILURES.md) | Setup blockers and fixes |
| [Known Limitations](docs/KNOWN_LIMITATIONS.md) | Feature constraints and workarounds |

### Development

| Doc | Purpose |
|-----|---------|
| [Contributing](CONTRIBUTING.md) | Two-agent workflow, PR rules |
| [Coding Standards](.agent/CODING_STANDARDS.md) | Code quality and style |
| [AI Agent Manual](docs/ai/agent-manual.md) | How AI agents must operate in this repo |
| [Ingestion Runbook](docs/ingestion/INGESTION_RUNBOOK.md) | Document ingestion procedures |
| [Interview Architecture](docs/training/INTERVIEW_MODE_ARCHITECTURE.md) | Interview mode design |

### Diagrams

| Doc | Purpose |
|-----|---------|
| [Twin Lifecycle](docs/diagrams/twin-lifecycle.md) | Twin creation to operation flow |
| [Query Flow](docs/diagrams/query-flow.md) | RAG retrieval pipeline |
| [Action Flow](docs/diagrams/action-flow.md) | Action drafting and approval |
| [Escalation Flow](docs/diagrams/escalation-flow.md) | Low-confidence routing |

### Backlog

Open issues are tracked in [docs/audit/issues/](docs/audit/issues/).

## Project Structure

```
verified-digital-twin-brains/
├── backend/                  # FastAPI Python backend
│   ├── main.py              # Entry point, 17 routers
│   ├── worker.py            # Background job processor
│   ├── routers/             # API endpoints
│   ├── modules/             # Business logic (33 modules)
│   │   ├── _core/           # Core abstractions (DO NOT MODIFY)
│   │   ├── retrieval.py     # Hybrid RAG engine
│   │   ├── auth_guard.py    # JWT + ownership checks
│   │   └── clients.py       # Singleton service clients
│   └── database/            # Migrations and schema
├── frontend/                 # Next.js TypeScript frontend
│   ├── app/                 # App Router pages
│   ├── components/          # React components
│   └── lib/                 # Auth context, API clients
├── docs/                    # Documentation
├── .agent/                  # AI agent workflows and standards
└── .github/                 # CI, PR templates, issue templates
```

## Status

Phase 9/10 of core build. All foundational multi-tenancy, auth, and retrieval paths are verified and production-ready.

## License

Proprietary.
