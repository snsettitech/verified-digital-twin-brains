# Immediate Actions: Delphi.ai Architecture Upgrade

## Critical Finding: Neo4j Demo is READ-ONLY

The Neo4j demo credentials (`neo4j+s://demo.neo4jlabs.com:7687`) only allow reads. CodeGraphContext needs write access to create code graphs.

---

## Action 1: Set Up Working Neo4j (This Week)

### Option A: Neo4j AuraDB (Recommended - Free)

1. **Sign up:** https://neo4j.com/cloud/aura/
2. **Create free instance:**
   - 1GB RAM
   - 2GB storage
   - Always free
3. **Get credentials:**
   - Connection URI: `neo4j+s://xxxxx.databases.neo4j.io`
   - Username: `neo4j`
   - Password: (generated)

4. **Update MCP config:**
```toml
# ~/.codex/config.toml
[mcp_servers.CodeGraphContext.env]
DEFAULT_DATABASE = "neo4j"
NEO4J_URI = "neo4j+s://YOUR_INSTANCE.databases.neo4j.io"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "YOUR_PASSWORD"
```

### Option B: Local Neo4j (Development Only)

```bash
# Install Docker first, then:
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  -v $HOME/neo4j/data:/data \
  neo4j:5.26.0-community

# Access at http://localhost:7474
```

---

## Action 2: Sign Up for API Keys (This Week)

### Required for Phase 2 (Inference)
- [ ] **Cerebras:** https://cloud.cerebras.net/
  - Free tier: $10 credit
  - Llama 3.3 70B access
  - Fastest inference speeds

### Required for Phase 3 (Real-time Ingestion)
- [ ] **AssemblyAI:** https://www.assemblyai.com/
  - Free tier: 50 hours/month
  - Real-time transcription
  - Speaker diarization

### Required for Phase 5 (Caching)
- [ ] **Redis:** https://upstash.com/ (serverless) or local
  - Free tier: 10GB
  - Global replication

### Existing (Verify Access)
- [x] **OpenAI API:** Verify quota for hybrid routing
- [x] **Pinecone:** Ready for serverless migration
- [x] **Supabase:** Already configured
- [x] **ElevenLabs:** Voice cloning active

---

## Action 3: Create Pinecone Serverless Index (Week 2)

```python
# test_serverless.py
from pinecone import Pinecone, ServerlessSpec
import os

pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])

# Create serverless index
index_name = "digital-twin-serverless"

if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=3072,  # text-embedding-3-large
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )
    print(f"Created index: {index_name}")
else:
    print(f"Index {index_name} already exists")

# Test
index = pc.Index(index_name)
print(index.describe_index_stats())
```

---

## Action 4: Test Cerebras Integration (Week 4)

```python
# test_cerebras.py
from cerebras.cloud.sdk import Cerebras

client = Cerebras(api_key=os.environ['CEREBRAS_API_KEY'])

response = client.chat.completions.create(
    model="llama-3.3-70b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"}
    ]
)

print(response.choices[0].message.content)
print(f"Latency: {response.response_ms}ms")
```

---

## Action 5: CodeGraphContext Usage (After Neo4j Setup)

Once Neo4j is configured:

```bash
# Index the entire codebase
python -m codegraphcontext index D:\verified-digital-twin-brains

# Get statistics
python -m codegraphcontext stats

# Find dependencies for a module
python -m codegraphcontext find "modules/retrieval.py"

# Analyze architecture
python -m codegraphcontext analyze --path D:\verified-digital-twin-brains
```

---

## Quick Reference: Environment Variables

Add to `.env`:

```bash
# Neo4j (from AuraDB or local)
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password

# Cerebras
CEREBRAS_API_KEY=your_cerebras_key

# AssemblyAI
ASSEMBLYAI_API_KEY=your_assemblyai_key

# Redis (Upstash)
REDIS_URL=rediss://default:password@host:6379

# Pinecone Serverless (new index)
PINECONE_SERVERLESS_INDEX=digital-twin-serverless
```

---

## Decision Points

### 1. Self-Hosted vs Managed Services?
| Component | Self-Hosted | Managed | Recommendation |
|-----------|-------------|---------|----------------|
| Neo4j | Local Docker | AuraDB | **AuraDB** (zero ops) |
| Redis | Local install | Upstash | **Upstash** (serverless) |
| Pinecone | Pod-based | Serverless | **Serverless** (Delphi uses this) |
| Inference | Self-hosted | Cerebras API | **Cerebras API** (wafer-scale) |

### 2. Migration Strategy?
- **Big Bang:** High risk, fast completion
- **Strangler Fig:** Low risk, gradual migration ✅ **Recommended**
- **Parallel:** Medium risk, dual-running costs

### 3. Rollback Plan?
- Keep existing Pinecone index during migration
- Feature flags for new inference providers
- Circuit breakers for external services

---

## Cost Estimate (Monthly)

| Phase | Services | Est. Cost |
|-------|----------|-----------|
| 0-1 | Neo4j Aura + Pinecone Serverless | ~$50 |
| 2 | Cerebras + OpenAI | ~$1,000 |
| 3 | AssemblyAI | ~$150 |
| 4 | ElevenLabs (enhanced) | ~$200 |
| 5 | Redis + optimizations | ~$50 |
| **Total** | | **~$1,450** |

*Savings vs current: ~$400/month + 10x performance*

---

## Verification Checklist

- [ ] Neo4j AuraDB instance created
- [ ] CodeGraphContext MCP working with writes
- [ ] Cerebras API key obtained
- [ ] AssemblyAI API key obtained
- [ ] Pinecone Serverless index created
- [ ] Redis instance provisioned
- [ ] All env vars configured
- [ ] Test scripts passing

---

**Next:** Proceed to Phase 1 (Vector DB migration) once all checkboxes complete.
