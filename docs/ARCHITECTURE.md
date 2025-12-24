# System Architecture - Verified Digital Twin Brain

This document outlines the high-level architecture, data flows, and system components of the Verified Digital Twin Brain.

## High-Level Overview

The system is designed as a high-trust RAG (Retrieval-Augmented Generation) engine that enables users to interact with a "Digital Twin" backed by verified knowledge.

```mermaid
graph TD
    subgraph Frontend [Next.js App Router]
        Dashboard[Dashboard UI]
        Chat[Chat Interface]
        Upload[Document Upload]
    end

    subgraph Backend [FastAPI]
        API[FastAPI Endpoints]
        Ingest[Ingestion Module]
        Ret[Retrieval Module]
        Ans[Answering Module]
        Esc[Escalation Module]
    end

    subgraph Storage
        Supabase[(Supabase - Auth/Postgres)]
        Pinecone[(Pinecone - Vector DB)]
        Files[Local/Cloud Storage]
    end

    Chat --> API
    Upload --> API
    API --> Ingest
    API --> Ret
    Ingest --> Files
    Ingest --> Supabase
    Ingest --> Pinecone
    Ret --> Pinecone
    Ret --> Ans
    Ans --> Esc
    Esc --> Supabase
```

## Data Flows

### 1. Ingestion Pipeline
When a document is uploaded, it follows this path:
1. **Extraction**: Text is extracted from the PDF (currently via PyPDF2).
2. **Chunking**: Text is split into smaller, overlapping chunks.
3. **Embedding**: Each chunk is converted into a high-dimensional vector using OpenAI's `text-embedding-3-large`.
4. **Indexing**: Vectors and metadata (source ID, twin ID) are stored in Pinecone.
5. **Persistence**: Metadata about the source is stored in Supabase.

### 2. RAG Chat Flow
1. **Query Embedding**: The user's question is embedded using the same OpenAI model.
2. **Vector Search**: Pinecone retrieves the top-K most similar chunks, filtered by `twin_id`.
3. **Context Construction**: Chunks are assembled into a prompt for the LLM.
4. **Answer Generation**: GPT-4 generates an answer with citations.
5. **Confidence Scoring**: If retrieval scores are below a threshold (e.g., 0.7), an **Escalation** is created in Supabase for human review.

## Database Schema (Supabase)

The system uses the following core tables:
- `twins`: Settings and identity for each digital twin.
- `sources`: Metadata for ingested documents (PDFs, links, etc.).
- `conversations`: Chat sessions.
- `messages`: Individual user/assistant messages with confidence scores and citations.
- `escalations`: Flagged interactions requiring owner verification.

## Vector Schema (Pinecone)

- **Namespace**: Default (or per-twin if scaled).
- **Metadata**:
  - `twin_id`: UUID for multi-tenancy.
  - `source_id`: UUID of the original document.
  - `text`: The raw text chunk.
