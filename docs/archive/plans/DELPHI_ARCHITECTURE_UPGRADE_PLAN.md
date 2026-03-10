# Delphi.ai Architecture Upgrade Plan
## Verified Digital Twin Brains → Delphi.ai-Style Architecture

**Date:** February 11, 2026  
**Status:** Research & Planning Phase  
**Objective:** Upgrade architecture to match Delphi.ai capabilities (except monetization)

---

## Executive Summary

Based on research into Delphi.ai's architecture (Pinecone case study, Cerebras partnership, and technical blogs), this plan outlines a phased migration from the current modular microservices architecture to an integrated, high-performance platform similar to Delphi.ai.

### Key Delphi.ai Architectural Insights

| Component | Delphi.ai Implementation | Current System | Gap |
|-----------|------------------------|----------------|-----|
| **Inference** | Cerebras wafer-scale (Llama 3.3 70B) | OpenAI API only | HIGH |
| **Vector DB** | Pinecone Serverless (100M+ vectors, 12K namespaces) | Pinecone self-managed | MEDIUM |
| **Retrieval** | <100ms P95, sub-second end-to-end | ~200-500ms | MEDIUM |
| **Ingestion** | Real-time streaming with AssemblyAI | Async job queue | HIGH |
| **Tenant Isolation** | Namespace-per-creator | Namespace-per-twin | LOW |
| **Voice/Video** | Real-time voice cloning + video | ElevenLabs only | HIGH |
| **Compute** | Hybrid (Cerebras + OpenAI/Anthropic) | OpenAI only | HIGH |

---

## Phase 0: Foundation & Neo4j Setup (Week 1)

### 0.1 Fix CodeGraphContext Database
**Problem:** Neo4j demo is read-only, CodeGraphContext needs write access.

**Solution Options:**

#### Option A: Neo4j AuraDB (Recommended)
```bash
# Sign up at https://neo4j.com/cloud/aura/
# Free tier: 1GB RAM, 2GB storage
# Create instance → Get connection URI
```

**Configuration:**
```toml
# ~/.codex/config.toml
[mcp_servers.CodeGraphContext.env]
DEFAULT_DATABASE = "neo4j"
NEO4J_URI = "neo4j+s://xxxx.databases.neo4j.io"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "<password>"
```

#### Option B: Local Neo4j (Development)
```bash
# Using Docker
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5.26.0-community
```

**Deliverables:**
- [ ] Working CodeGraphContext MCP with write capabilities
- [ ] Indexed codebase graph for analysis
- [ ] CI/CD integration for code analysis

---

## Phase 1: Vector Database Migration (Weeks 2-3)

### 1.1 Migrate to Pinecone Serverless
**Current:** Pod-based Pinecone with self-managed namespaces  
**Target:** Pinecone Serverless with enhanced namespace strategy

**Why Serverless:**
- Separation of storage/compute (cost optimization)
- Dynamic index construction
- Built-in freshness layer
- Zero scaling incidents (Delphi handles 20 QPS globally)
- Supports 5M+ namespaces (Delphi's target)

**Implementation:**

```python
# modules/embeddings.py - Migration
from pinecone import Pinecone, ServerlessSpec

class PineconeServerlessManager:
    def __init__(self):
        self.pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])
        self.index_name = os.environ['PINECONE_INDEX_NAME']
        
    def ensure_serverless_index(self):
        """Create serverless index if not exists"""
        if self.index_name not in self.pc.list_indexes().names():
            self.pc.create_index(
                name=self.index_name,
                dimension=3072,  # text-embedding-3-large
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
    
    def namespace_strategy(self, creator_id: str, twin_id: str = None):
        """
        Delphi-style: namespace-per-creator with optional twin sub-namespace
        Format: creator_{creator_id}[_twin_{twin_id}]
        """
        if twin_id:
            return f"creator_{creator_id}_twin_{twin_id}"
        return f"creator_{creator_id}"
```

**Migration Steps:**
1. Create new serverless index alongside existing
2. Dual-write to both indexes during transition
3. Migrate existing vectors in batches
4. Switch reads to serverless
5. Decommission old index

**Deliverables:**
- [ ] Serverless index created
- [ ] Namespace strategy refactored (creator-centric)
- [ ] Migration script with batch processing
- [ ] Performance benchmarks (<100ms P95 target)

### 1.2 Enhanced RAG Pipeline
**Current:** 3-tier fallback (Verified → Vector → Tools)  
**Target:** Context Engineering + Multi-stage retrieval

```python
# modules/retrieval_v2.py
class DelphiStyleRetrieval:
    """
    Delphi-style retrieval with context engineering
    """
    
    async def retrieve(self, query: str, context: dict) -> RetrievalResult:
        # Stage 1: Query transformation
        transformed = await self.transform_query(query, context)
        
        # Stage 2: Multi-namespace search (if needed)
        namespaces = self.determine_namespaces(context)
        
        # Stage 3: Parallel retrieval across namespaces
        results = await asyncio.gather(*[
            self.search_namespace(ns, transformed) 
            for ns in namespaces
        ])
        
        # Stage 4: Result fusion & reranking
        fused = self.fuse_results(results)
        
        # Stage 5: Context assembly (Delphi-style)
        context_window = self.assemble_context(fused, max_tokens=8000)
        
        return context_window
    
    def determine_namespaces(self, context: dict) -> List[str]:
        """
        Smart namespace selection based on context
        """
        namespaces = []
        
        # Primary: current twin namespace
        if context.get('twin_id'):
            namespaces.append(f"creator_{context['creator_id']}_twin_{context['twin_id']}")
        
        # Secondary: creator-wide knowledge
        namespaces.append(f"creator_{context['creator_id']}")
        
        # Tertiary: public/shared knowledge
        if context.get('include_public'):
            namespaces.append("public")
        
        return namespaces
```

**Deliverables:**
- [ ] Query transformation module
- [ ] Multi-namespace search
- [ ] Result fusion & reranking
- [ ] Context assembly optimization

---

## Phase 2: Inference Layer Upgrade (Weeks 4-6)

### 2.1 Cerebras Integration
**Current:** OpenAI GPT-4o only  
**Target:** Hybrid (Cerebras Llama 3.3 70B + OpenAI/Anthropic)

**Why Cerebras:**
- Fastest inference speeds on earth (per Delphi blog)
- Sub-second end-to-end latency
- Cost-effective at scale
- No rate limiting issues

**Implementation:**

```python
# modules/inference_hybrid.py
from enum import Enum

class ModelProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CEREBRAS = "cerebras"

class HybridInferenceRouter:
    """
    Routes requests to optimal model based on:
    - Latency requirements
    - Token count
    - Complexity
    - Cost optimization
    """
    
    def __init__(self):
        self.openai = AsyncOpenAI()
        self.anthropic = AsyncAnthropic()
        self.cerebras = CerebrasClient(
            api_key=os.environ['CEREBRAS_API_KEY']
        )
        
    async def generate(
        self, 
        messages: List[dict],
        requirements: InferenceRequirements
    ) -> GenerationResult:
        
        # Route selection logic
        provider = self.select_provider(requirements)
        
        if provider == ModelProvider.CEREBRAS:
            # Use Cerebras for high-throughput, low-latency
            return await self.cerebras.chat.completions.create(
                model="llama-3.3-70b",
                messages=messages,
                max_tokens=requirements.max_tokens,
                temperature=requirements.temperature
            )
        elif provider == ModelProvider.ANTHROPIC:
            # Use Claude for complex reasoning
            return await self.anthropic.messages.create(
                model="claude-3-5-sonnet-20241022",
                messages=messages,
                max_tokens=requirements.max_tokens
            )
        else:
            # Default OpenAI
            return await self.openai.chat.completions.create(
                model="gpt-4o",
                messages=messages
            )
    
    def select_provider(self, req: InferenceRequirements) -> ModelProvider:
        """
        Delphi-style model selection:
        - Real-time convos → Cerebras (speed)
        - Complex reasoning → Anthropic (quality)
        - Default → OpenAI (balance)
        """
        if req.latency_target_ms < 500:
            return ModelProvider.CEREBRAS
        elif req.reasoning_complexity > 0.8:
            return ModelProvider.ANTHROPIC
        return ModelProvider.OPENAI
```

**Cerebras Setup:**
```bash
# 1. Get API key from https://cloud.cerebras.net/
# 2. Install client
pip install cerebras-cloud-sdk

# 3. Add to environment
CEREBRAS_API_KEY=your_key_here
```

**Deliverables:**
- [ ] Cerebras client integration
- [ ] Hybrid routing logic
- [ ] Provider fallback mechanisms
- [ ] Latency benchmarking
- [ ] Cost tracking per provider

### 2.2 Real-Time Streaming Infrastructure
**Current:** Blocking API calls  
**Target:** Streaming responses for real-time feel

```python
# modules/streaming.py
class StreamingResponseHandler:
    """
    Handles streaming responses for real-time conversation feel
    """
    
    async def stream_chat_response(
        self,
        twin_id: str,
        messages: List[dict],
        websocket: WebSocket
    ):
        """
        Stream response chunks as they're generated
        """
        provider = self.select_provider_for_twin(twin_id)
        
        if provider == ModelProvider.CEREBRAS:
            # Cerebras fastest streaming
            stream = await self.cerebras.chat.completions.create(
                model="llama-3.3-70b",
                messages=messages,
                stream=True
            )
        else:
            stream = await self.openai.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                stream=True
            )
        
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                await websocket.send_json({
                    "type": "chunk",
                    "content": content,
                    "timestamp": time.time()
                })
```

**Deliverables:**
- [ ] WebSocket infrastructure
- [ ] Streaming response handlers
- [ ] Client-side streaming UI
- [ ] Fallback to non-streaming

---

## Phase 3: Real-Time Ingestion (Weeks 7-9)

### 3.1 AssemblyAI Integration
**Current:** Async job queue with polling  
**Target:** Real-time streaming transcription

**Why AssemblyAI:**
- Real-time streaming transcription
- Speaker diarization
- PII redaction
- Topic detection
- Sentiment analysis

**Implementation:**

```python
# modules/realtime_ingestion.py
import assemblyai as aai

class RealtimeTranscriptionPipeline:
    """
    Real-time audio/video ingestion with AssemblyAI
    """
    
    def __init__(self):
        aai.settings.api_key = os.environ['ASSEMBLYAI_API_KEY']
        self.transcriber = aai.RealtimeTranscriber(
            sample_rate=16_000,
            on_data=self.on_transcript_data,
            on_error=self.on_transcript_error,
        )
        
    async def ingest_audio_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        twin_id: str,
        source_metadata: dict
    ):
        """
        Stream audio for real-time transcription and indexing
        """
        self.transcriber.connect()
        
        try:
            async for chunk in audio_stream:
                self.transcriber.stream(chunk)
                
                # Real-time processing
                await self.process_partial_transcript(twin_id)
                
        finally:
            self.transcriber.close()
            
    def on_transcript_data(self, transcript: aai.RealtimeTranscript):
        """
        Handle incoming transcript chunks in real-time
        """
        if not transcript.text:
            return
            
        # Buffer for chunking
        self.transcript_buffer.append({
            "text": transcript.text,
            "timestamp": transcript.audio_start,
            "confidence": transcript.confidence
        })
        
        # Process when buffer reaches threshold
        if len(self.transcript_buffer) >= 10:  # ~30 seconds
            asyncio.create_task(self.index_buffered_transcript())
    
    async def index_buffered_transcript(self):
        """
        Index transcript chunks in near real-time
        """
        buffer = self.transcript_buffer[:]
        self.transcript_buffer = []
        
        # Combine and chunk
        full_text = " ".join([t["text"] for t in buffer])
        chunks = self.chunk_transcript(full_text)
        
        # Embed and index (async)
        for chunk in chunks:
            embedding = await self.embed(chunk)
            await self.upsert_to_pinecone(chunk, embedding)
```

**Deliverables:**
- [ ] AssemblyAI integration
- [ ] Real-time transcription pipeline
- [ ] Near real-time indexing (<5s lag)
- [ ] Speaker diarization support
- [ ] PII redaction

### 3.2 Streaming Document Processing
**Current:** Batch document processing  
**Target:** Streaming chunk processing

```python
# modules/streaming_ingestion.py
class StreamingDocumentProcessor:
    """
    Process documents as they're uploaded, not after
    """
    
    async def process_document_stream(
        self,
        file_stream: AsyncIterator[bytes],
        filename: str,
        twin_id: str
    ):
        """
        Process document chunks as they arrive
        """
        # Determine file type
        file_type = self.detect_file_type(filename)
        
        if file_type == "pdf":
            async for page in self.stream_pdf_pages(file_stream):
                # Process each page immediately
                chunks = self.chunk_page(page)
                for chunk in chunks:
                    await self.index_chunk(chunk, twin_id)
                    
        elif file_type in ["mp4", "mov", "avi"]:
            # Extract audio and stream to transcription
            audio_stream = self.extract_audio_stream(file_stream)
            await self.realtime_transcription.ingest_audio_stream(
                audio_stream, twin_id, {"source": filename}
            )
```

**Deliverables:**
- [ ] Streaming PDF processing
- [ ] Video/audio streaming extraction
- [ ] Progressive indexing
- [ ] Live progress tracking

---

## Phase 4: Voice & Video (Weeks 10-12)

### 4.1 Advanced Voice Cloning
**Current:** ElevenLabs basic voice cloning  
**Target:** Real-time voice with emotion/intonation

**Implementation:**

```python
# modules/voice_v2.py
class AdvancedVoiceEngine:
    """
    Delphi-style real-time voice generation
    """
    
    def __init__(self):
        self.elevenlabs = ElevenLabs()
        self.cerebras = CerebrasClient()  # For fast LLM inference
        
    async def generate_realtime_voice_response(
        self,
        text: str,
        voice_id: str,
        emotion_context: dict = None
    ) -> AsyncIterator[bytes]:
        """
        Generate voice with emotional intonation
        """
        # Analyze text for emotional cues
        if emotion_context:
            prosody = await self.analyze_prosody(text, emotion_context)
        else:
            prosody = self.default_prosody()
            
        # Stream audio chunks
        stream = self.elevenlabs.generate(
            text=text,
            voice=voice_id,
            stream=True,
            model="eleven_turbo_v2_5",  # Real-time model
            voice_settings={
                "stability": prosody.stability,
                "similarity_boost": prosody.similarity,
                "style": prosody.style,
                "use_speaker_boost": True
            }
        )
        
        async for chunk in stream:
            yield chunk
            
    async def analyze_prosody(self, text: str, context: dict) -> ProsodySettings:
        """
        Use LLM to determine voice prosody based on context
        """
        prompt = f"""
        Analyze this text and determine voice settings:
        Text: {text}
        Context: {context}
        
        Return JSON with:
        - stability (0.0-1.0): voice consistency
        - similarity (0.0-1.0): how similar to original voice
        - style (0.0-1.0): expressiveness
        """
        
        response = await self.cerebras.chat.completions.create(
            model="llama-3.3-70b",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        return ProsodySettings(**json.loads(response.choices[0].message.content))
```

### 4.2 Video Avatar (Future Phase)
**Delphi Feature:** Video chat with digital avatar  
**Implementation:** Hedra, LivePortrait, or similar

**Options:**
1. **Hedra** (https://www.hedra.com/) - Free tier available
2. **LivePortrait** - Open source
3. **D-ID** - Commercial API

**Deliverables:**
- [ ] Enhanced voice cloning
- [ ] Prosody analysis
- [ ] Real-time voice streaming
- [ ] Video avatar research (Phase 5)

---

## Phase 5: Performance & Scale (Weeks 13-15)

### 5.1 Caching Layer
**Current:** No caching  
**Target:** Multi-tier caching

```python
# modules/cache_tier.py
import redis.asyncio as redis
from functools import wraps

class MultiTierCache:
    """
    L1: In-memory (LRU)
    L2: Redis (distributed)
    L3: CDN (static assets)
    """
    
    def __init__(self):
        self.l1_cache = {}  # Simple LRU
        self.l2_redis = redis.Redis(
            host=os.environ['REDIS_HOST'],
            port=6379,
            decode_responses=True
        )
        
    async def get(self, key: str) -> Optional[Any]:
        # L1 check
        if key in self.l1_cache:
            return self.l1_cache[key]
            
        # L2 check
        value = await self.l2_redis.get(key)
        if value:
            # Promote to L1
            self.l1_cache[key] = value
            return value
            
        return None
        
    async def set(self, key: str, value: Any, ttl_seconds: int = 3600):
        # Set L1
        self.l1_cache[key] = value
        
        # Set L2
        await self.l2_redis.setex(key, ttl_seconds, json.dumps(value))

# Usage
cache = MultiTierCache()

@cache.cached(namespace="embeddings", ttl=86400)
async def get_embedding(text: str) -> List[float]:
    """Cache embeddings for 24 hours"""
    return await openai.embeddings.create(...)
```

### 5.2 Connection Pooling & Async Optimization

```python
# modules/connection_pool.py
import aiopg
import aioredis
from contextlib import asynccontextmanager

class ConnectionPools:
    """
    Managed connection pools for all external services
    """
    
    def __init__(self):
        self.supabase_pool = None
        self.redis_pool = None
        self.pinecone_pool = None
        
    async def initialize(self):
        self.supabase_pool = await aiopg.create_pool(
            host=os.environ['SUPABASE_HOST'],
            database='postgres',
            user='postgres',
            password=os.environ['SUPABASE_PASSWORD'],
            minsize=5,
            maxsize=20
        )
        
        self.redis_pool = aioredis.ConnectionPool.from_url(
            os.environ['REDIS_URL'],
            max_connections=50
        )
        
    @asynccontextmanager
    async def get_supabase_conn(self):
        async with self.supabase_pool.acquire() as conn:
            yield conn
```

**Deliverables:**
- [ ] Redis caching layer
- [ ] Connection pooling
- [ ] Query optimization
- [ ] Load testing (>20 QPS target)

---

## Phase 6: Multi-Modal & Advanced Features (Weeks 16-18)

### 6.1 Multi-Modal Understanding
**Current:** Text-only RAG  
**Target:** Image + text understanding

```python
# modules/multimodal.py
class MultimodalRAG:
    """
    RAG with image understanding
    """
    
    async def ingest_image(
        self,
        image_data: bytes,
        twin_id: str,
        metadata: dict
    ):
        """
        Extract text from images and index
        """
        # Use GPT-4V or similar for image understanding
        description = await self.describe_image(image_data)
        
        # Embed and index
        embedding = await self.embed(description)
        await self.upsert_to_pinecone(
            vector=embedding,
            metadata={
                "type": "image",
                "description": description,
                "twin_id": twin_id,
                **metadata
            }
        )
        
    async def describe_image(self, image_data: bytes) -> str:
        """Generate text description of image"""
        response = await self.openai.chat.completions.create(
            model="gpt-4o",  # Vision-capable
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image in detail"},
                        {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image_data}"}
                    ]
                }
            ]
        )
        return response.choices[0].message.content
```

### 6.2 Interview Mode
**Delphi Feature:** Digital Mind interviews creator to fill gaps

```python
# modules/interview_mode.py
class InterviewModeEngine:
    """
    Digital Mind proactively interviews creator
    """
    
    async def conduct_interview_session(
        self,
        twin_id: str,
        topic: str = None
    ):
        """
        Interview creator to fill knowledge gaps
        """
        # Analyze knowledge gaps
        gaps = await self.identify_knowledge_gaps(twin_id, topic)
        
        # Generate interview questions
        questions = await self.generate_questions(gaps)
        
        # Conduct interview (via chat/voice)
        for question in questions:
            response = await self.ask_creator(question, twin_id)
            
            # Index response immediately
            await self.index_interview_response(
                twin_id=twin_id,
                question=question,
                response=response
            )
            
    async def identify_knowledge_gaps(
        self, 
        twin_id: str,
        topic: str = None
    ) -> List[KnowledgeGap]:
        """
        Find topics with insufficient coverage
        """
        # Query pinecone for topic distribution
        distribution = await self.analyze_topic_coverage(twin_id)
        
        # Identify sparse topics
        gaps = [t for t in distribution if t.coverage < 0.3]
        
        return gaps
```

**Deliverables:**
- [ ] Multi-modal ingestion
- [ ] Image understanding
- [ ] Interview mode engine
- [ ] Knowledge gap analysis

---

## Implementation Checklist

### Infrastructure Setup
- [ ] Neo4j AuraDB account
- [ ] Cerebras API key
- [ ] AssemblyAI API key
- [ ] Redis instance (Upstash or self-hosted)
- [ ] Pinecone Serverless migration

### Code Changes
- [ ] Hybrid inference router
- [ ] Streaming response handlers
- [ ] Real-time ingestion pipeline
- [ ] Advanced voice engine
- [ ] Multi-tier caching
- [ ] Connection pooling

### Testing
- [ ] Latency benchmarks (<100ms P95 retrieval)
- [ ] Load testing (20+ QPS)
- [ ] End-to-end streaming tests
- [ ] Failover testing

### Monitoring
- [ ] Latency dashboards
- [ ] Cost tracking per provider
- [ ] Error rate alerting
- [ ] Cache hit rate monitoring

---

## Cost Analysis

### Current Monthly Costs (Estimate)
| Service | Usage | Cost |
|---------|-------|------|
| OpenAI API | 1M tokens/day | ~$1,500 |
| Pinecone (pod) | 10M vectors | ~$200 |
| Supabase | 100GB | ~$50 |
| ElevenLabs | 100K chars | ~$100 |
| **Total** | | **~$1,850** |

### Post-Migration Costs (Estimate)
| Service | Usage | Cost |
|---------|-------|------|
| OpenAI API | 500K tokens/day | ~$750 |
| Cerebras | 500K tokens/day | ~$300 |
| Pinecone Serverless | 10M vectors | ~$150 |
| AssemblyAI | 100 hours audio | ~$150 |
| Redis (Upstash) | 10GB | ~$50 |
| **Total** | | **~$1,400** |

**Savings: ~$450/month (24%)** + significant performance gains

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cerebras API issues | Medium | High | Fallback to OpenAI |
| Pinecone migration failures | Low | High | Dual-write strategy |
| AssemblyAI latency | Low | Medium | Async processing |
| Redis downtime | Low | Medium | Circuit breaker pattern |
| Voice cloning quality | Medium | Medium | A/B testing with users |

---

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Retrieval latency | 200-500ms | <100ms P95 | Pinecone metrics |
| End-to-end chat | 2-5s | <1s | Frontend timing |
| Token cost/1K requests | $0.05 | $0.03 | Billing data |
| Concurrent users | 50 | 500+ | Load testing |
| Ingestion lag | minutes | <5s | Job queue metrics |

---

## Next Steps

1. **Immediate (This Week):**
   - Set up Neo4j AuraDB for CodeGraphContext
   - Sign up for Cerebras API access
   - Create Pinecone Serverless index for testing

2. **Week 2-3:**
   - Begin Phase 1 (Vector DB migration)
   - Set up AssemblyAI account

3. **Week 4-6:**
   - Implement hybrid inference
   - Deploy Cerebras integration

4. **Ongoing:**
   - Monitor metrics
   - Iterate on performance
   - Plan Phase 5+ (Video, Multi-modal)

---

*This plan is based on research into Delphi.ai's published architecture (Pinecone case study, Cerebras blog post) and current system analysis via CodeGraphContext.*
