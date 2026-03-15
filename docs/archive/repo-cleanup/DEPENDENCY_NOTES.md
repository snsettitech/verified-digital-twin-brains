# Dependency Hygiene Notes

Review of project dependencies for potential cleanup opportunities.

---

## Backend Dependencies (requirements.txt)

### Runtime Dependencies (Appear Legitimate)

| Package | Purpose | Status |
|---------|---------|--------|
| fastapi | Web framework | ✅ Keep |
| uvicorn | ASGI server | ✅ Keep |
| supabase | Database client | ✅ Keep |
| pinecone | Vector DB client | ✅ Keep |
| openai | AI/ML API | ✅ Keep |
| flashrank | Reranking | ✅ Keep (starter plan safe) |
| cohere | Reranking | ✅ Keep |
| cerebras-cloud-sdk | Fast inference | ✅ Keep |
| pydantic | Data validation | ✅ Keep |
| python-dotenv | Environment loading | ✅ Keep |
| python-multipart | Form parsing | ✅ Keep |
| langchain | LLM framework | ✅ Keep |
| langchain-openai | OpenAI integration | ✅ Keep |
| langchain-community | Community extensions | ✅ Keep |
| langgraph | Agent framework | ✅ Keep |
| langgraph-checkpoint-postgres | Graph persistence | ✅ Keep |
| asyncpg | Async PostgreSQL | ✅ Keep |
| PyPDF2 | PDF processing | ✅ Keep |
| python-jose[cryptography] | JWT handling | ✅ Keep |
| passlib[bcrypt] | Password hashing | ✅ Keep |
| composio-langchain | Tool integrations | ✅ Keep |
| httpx | HTTP client | ✅ Keep |
| yt-dlp | YouTube downloads | ✅ Keep |
| feedparser | RSS parsing | ✅ Keep |
| twikit | Twitter/X client | ✅ Keep |
| youtube-transcript-api | YouTube transcripts | ✅ Keep |
| google-genai | Google AI | ✅ Keep |
| google-api-python-client | Google APIs | ✅ Keep |
| beautifulsoup4 | HTML parsing | ✅ Keep |
| elevenlabs | Voice synthesis | ✅ Keep |
| firecrawl-py | Web scraping | ✅ Keep |
| exa-py | Search API | ✅ Keep |
| apscheduler | Job scheduling | ✅ Keep |
| graphiti-core | Graph memory | ✅ Keep |
| neo4j | Neo4j client | ✅ Keep |
| python-docx | Word documents | ✅ Keep |
| openpyxl | Excel files | ✅ Keep |
| pydub | Audio processing | ✅ Keep |
| imageio-ffmpeg | Video processing | ✅ Keep |
| redis | Redis client | ✅ Keep |
| langfuse | Observability | ✅ Keep |

### Assessment

All backend dependencies appear to serve specific purposes in the application. No obviously unused packages were identified.

---

## Frontend Dependencies (package.json)

### Dependencies (Runtime)

| Package | Purpose | Status | Notes |
|---------|---------|--------|-------|
| @playwright/test | E2E testing | ⚠️ Move to devDeps | Test-only |
| @supabase/auth-helpers-nextjs | Auth | ✅ Keep | Runtime |
| @supabase/supabase-js | Database | ✅ Keep | Runtime |
| next | Framework | ✅ Keep | Runtime |
| react | UI library | ✅ Keep | Runtime |
| react-dom | UI library | ✅ Keep | Runtime |
| react-markdown | Markdown rendering | ✅ Keep | Runtime |
| remark-gfm | Markdown extensions | ✅ Keep | Runtime |
| zod | Validation | ✅ Keep | Runtime |

### Dev Dependencies

| Package | Purpose | Status |
|---------|---------|--------|
| @tailwindcss/postcss | CSS framework | ✅ Keep |
| @types/node | TypeScript types | ✅ Keep |
| @types/react | TypeScript types | ✅ Keep |
| @types/react-dom | TypeScript types | ✅ Keep |
| eslint | Linting | ✅ Keep |
| eslint-config-next | Next.js linting | ✅ Keep |
| eslint-plugin-react-compiler | React linting | ✅ Keep |
| husky | Git hooks | ✅ Keep |
| lint-staged | Pre-commit linting | ✅ Keep |
| tailwindcss | CSS framework | ✅ Keep |
| typescript | TypeScript | ✅ Keep |

### Recommended Action

**Move @playwright/test to devDependencies:**

```bash
cd frontend
npm uninstall @playwright/test
npm install --save-dev @playwright/test
```

This is a safe change that improves dependency organization.

---

## Potential Future Optimizations

### Backend

1. **Split requirements files**
   - Consider `requirements.txt` (minimal runtime)
   - `requirements-dev.txt` (development)
   - `requirements-ml.txt` (ML heavy dependencies)
   
   This would improve deployment times for services that don't need all features.

2. **Audit for optional dependencies**
   - Some packages may be optional for certain deployment modes
   - Document which are required vs optional

### Frontend

1. **Bundle analysis**
   - Run `npm run build` with bundle analyzer
   - Identify large dependencies that may be tree-shakeable

2. **Update check**
   - Some dependencies may have updates available
   - Review changelogs before updating

---

## Security Considerations

All dependencies should be regularly audited:

```bash
# Backend
pip install safety
safety check -r requirements.txt

# Frontend
cd frontend
npm audit
```

---

## Summary

| Category | Finding | Action |
|----------|---------|--------|
| Backend | All deps appear legitimate | None needed |
| Frontend | Playwright in wrong section | Move to devDeps |
| Both | Regular audit recommended | Schedule quarterly |
