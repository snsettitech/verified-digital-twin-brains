# Digital Brain MVP - Master Roadmap

> Delphi-level Digital Brain that learns day by day with enterprise-grade multi-tenant isolation.

## Epic Overview

| Epic | Name | Priority | Status | Dependencies |
|------|------|----------|--------|--------------|
| A | Auth + Multi-Tenancy | P0 | Not Started | None |
| B | Twin Creation + Onboarding | P0 | Not Started | Epic A |
| C | Document Ingestion + RAG | P1 | Not Started | Epic A, B |
| D | Graph Memory Write | P0 | Not Started | Epic A, B |
| E | Hybrid Chat Retrieval | P0 | Not Started | Epic A, B, D |
| F | Escalations Loop | P0 | Not Started | Epic A, B, E |
| G | Observability + Eval | P1 | Not Started | Epic E |

## Implementation Order

Based on dependencies and user flow requirements:

```
Epic A (Auth + Tenancy)
    ↓
Epic B (Twin + Onboarding)
    ↓
Epic E (Hybrid Chat) ←── Epic D (Graph Memory)
    ↓
Epic F (Escalations)
    ↓
Epic G (Observability)
    ↓
Epic C (Full Ingestion)
```

## Detailed Roadmaps

Each epic has a detailed roadmap:

1. [Auth + Multi-Tenancy](roadmap_auth_tenancy.md)
2. [Twin + Onboarding](roadmap_twin_onboarding.md)
3. [Document Ingestion + RAG](roadmap_ingestion_rag.md)
4. [Graph Memory](roadmap_graph_memory.md)
5. [Escalations](roadmap_escalations.md)
6. [Observability + Eval](roadmap_observability_eval.md)

## Milestones

### Milestone 1: Foundation (Epics A + B)
**Target**: User can sign up, create a twin, and access dashboard

- [ ] Supabase project setup with RLS
- [ ] FastAPI backend with auth middleware
- [ ] Next.js frontend with auth flow
- [ ] Twin CRUD with tenant isolation
- [ ] Basic onboarding UI

### Milestone 2: Chat MVP (Epic E + D)
**Target**: User can chat with twin and see memory extraction

- [ ] Basic chat interface
- [ ] Vector retrieval from Pinecone
- [ ] Graph memory write pipeline
- [ ] Memory candidates queue
- [ ] Owner approval flow

### Milestone 3: Learning Loop (Epic F)
**Target**: Escalation → Owner response → Improved answers

- [ ] "I don't know" responses
- [ ] Escalation creation
- [ ] Owner response UI
- [ ] Add to brain flow
- [ ] "Brain learned today" digest

### Milestone 4: Production Ready (Epics C + G)
**Target**: Full document ingestion, observability, quality metrics

- [ ] Document upload + processing
- [ ] Langfuse tracing integration
- [ ] RAGAS evaluation baseline
- [ ] E2E test suite
- [ ] Security audit complete

## Progress Tracking

| Date | Epic | Task | Status | Notes |
|------|------|------|--------|-------|
| 2024-12-24 | - | Initial planning | ✅ | Architecture defined |

## Test Strategy

### Unit Tests
- All services have pytest unit tests
- Mock external dependencies (Supabase, Pinecone, OpenAI)
- Target: 80% coverage

### Integration Tests
- API endpoint tests with test database
- Cross-tenant isolation tests
- RLS policy validation

### E2E Tests
- Playwright tests for critical flows
- Sign up → Twin → Chat → Memory → Escalation

### Security Tests
- Cross-tenant access attempts (must fail)
- RLS bypass attempts (must fail)
- API auth bypass attempts (must fail)

## Definition of Done

Each task is done when:

1. ✅ Code implemented and reviewed
2. ✅ Unit tests passing
3. ✅ Integration tests passing (if applicable)
4. ✅ Security requirements validated
5. ✅ Documentation updated
6. ✅ Roadmap progress updated
7. ✅ devlog.md entry added
