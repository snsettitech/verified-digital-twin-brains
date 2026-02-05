# Verified Digital Twin Brains

A high-fidelity Digital Twin system designed to replicate a user's voice, knowledge, and reasoning capabilities. This system enables users to scale their presence by having an AI agent that can converse, reason, and act on their behalf.

## 🌟 Key Features

### 1. **Voice Integration** (`modules/audio_generator.py`)
- **ElevenLabs Integration**: Generates lifelike speech using your cloned voice.
- **REST API**: `/audio/tts/{twin_id}` endpoint for generating audio.

### 2. **Enhanced Ingestion** (`modules/enhanced_ingestion.py`)
- **Deep Web Crawling**: Uses [Firecrawl](https://firecrawl.dev) to scrape entire websites and documentation.
- **Social Media**: Ingests content from Twitter/X, LinkedIn exports, and RSS feeds.
- **Auto-Update Scheduler**: Keeps your Twin's knowledge fresh by periodically re-crawling sources.

### 3. **Advisor Mode (Reasoning Engine)** (`modules/reasoning_engine.py`)
- **Hypothetical Reasoning**: Answers "Would I..." questions by traversing the cognitive graph (Values/Beliefs/Principles).
- **Decision Trace**: Provides a transparent logic chain explaining *why* the Twin took a specific stance.

### 4. **Cognitive Graph**
- **Structured Knowledge**: Stores data not just as text chunks, but as connected nodes (Entities, Concepts, Values).
- **Context Retrieval**: intelligently retrieves relevant graph subsets for chat context.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- [Supabase](https://supabase.com) project (for Vector content & Graph)
- [OpenAI](https://openai.com) API Key
- [ElevenLabs](https://elevenlabs.io) API Key (for Voice)
- [Firecrawl](https://firecrawl.dev) API Key (for Web Crawling)

### Installation
1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd verified-digital-twin-brains
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure Environment Variables:
   Create a `.env` file in the `backend/` directory:
   ```env
   OPENAI_API_KEY=sk-...
   SUPABASE_URL=https://...
   SUPABASE_KEY=ey...
   ELEVENLABS_API_KEY=...
   FIRECRAWL_API_KEY=...
   ```

4. Run the Backend:
   ```bash
   cd backend
   uvicorn main:app --reload
   ```

---

## 🛠️ Usage

### Chatting with your Twin
**Endpoint**: `POST /chat/{twin_id}`
```json
{
  "query": "What do I think about remote work?",
  "conversation_id": "optional-uuid"
}
```

### Ingesting Data
**Endpoint**: `POST /ingest/website/{twin_id}`
```json
{
  "url": "https://my-blog.com",
  "max_pages": 10
}
```

### Asking for Advice (Advisor Mode)
**Endpoint**: `POST /reason/predict/{twin_id}`
```json
{
  "topic": "Investing in crypto startups"
}
```

---

## 🧪 Testing

Run strict triple-loop verification tests:
```bash
# Unit Tests
pytest backend/tests/test_reasoning_engine.py

# Integration Tests
pytest backend/tests/test_reasoning_integration.py

# Full Suite
pytest backend/tests/
```

---

## 📂 Project Structure

```
backend/
├── modules/
│   ├── reasoning_engine.py   # Logic & Deduction
│   ├── web_crawler.py        # Firecrawl integration
│   ├── social_ingestion.py   # Twitter/LinkedIn/RSS
│   ├── audio_generator.py    # ElevenLabs TTS
│   └── graph_context.py      # Graph retrieval
├── routers/
│   ├── chat.py               # Main chat endpoint
│   ├── reasoning.py          # Reasoning endpoints
│   └── enhanced_ingestion.py # Ingestion endpoints
└── tests/                    # Comprehensive test suite
```

## License
Proprietary.
