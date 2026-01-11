import os
import uuid
import re
import json
import feedparser
import yt_dlp
from typing import List, Dict, Optional, Any
from PyPDF2 import PdfReader
from youtube_transcript_api import YouTubeTranscriptApi
from modules.clients import get_openai_client, get_pinecone_index
from modules.observability import supabase, log_ingestion_event
from modules.health_checks import run_all_health_checks, calculate_content_hash
from modules.training_jobs import create_training_job
from modules.governance import AuditLogger


def extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text


def extract_video_id(url: str) -> str:
    """
    Extracts the video ID from a YouTube URL.
    """
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11}).*'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


from modules.transcription import transcribe_audio_multi


async def ingest_youtube_transcript(source_id: str, twin_id: str, url: str):
    """
    Ingest YouTube video transcript using robust multi-strategy approach.
    """
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL")

    # -------------------------------------------------------------
    # Step 0: Create Source Record IMMEDIATELY (Fixes FK Error)
    # -------------------------------------------------------------
    try:
        # Check if exists first to handle updates
        existing = supabase.table("sources").select("id").eq("id", source_id).execute()
        if not existing.data:
            supabase.table("sources").insert({
                "id": source_id,
                "twin_id": twin_id,
                "filename": f"YouTube: {video_id}",  # Placeholder title
                "file_size": 0,
                "content_text": "",
                "status": "processing",
                "staging_status": "processing"
            }).execute()
            print(f"[YouTube] Created processing record for {source_id}")
    except Exception as e:
        print(f"[YouTube] Error creating source record: {e}")
        # Continue anyway, it might stem from a race condition or retry

    text = None
    video_title = None
    transcript_error = None

    # -------------------------------------------------------------
    # Step 1: Validate via YouTube Data API (if key available)
    # -------------------------------------------------------------
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if google_api_key:
        try:
            from googleapiclient.discovery import build
            youtube = build('youtube', 'v3', developerKey=google_api_key)
            request = youtube.videos().list(part="snippet", id=video_id)
            response = request.execute()

            if response["items"]:
                snippet = response["items"][0]["snippet"]
                video_title = snippet["title"]
                # Update filename with real title
                supabase.table("sources").update({
                    "filename": f"YouTube: {video_title}"
                }).eq("id", source_id).execute()
                print(f"[YouTube] Validated video: {video_title}")
        except Exception as e:
            print(f"[YouTube] Data API check failed (non-blocking): {e}")

    # -------------------------------------------------------------
    # Strategy 1: YouTubeTranscriptApi (Official, Fast)
    # -------------------------------------------------------------
    try:
        transcript_snippets = YouTubeTranscriptApi().fetch(video_id)
        text = " ".join([item.text for item in transcript_snippets])
        log_ingestion_event(source_id, twin_id, "info", f"Fetched official YouTube transcript")
    except Exception as e:
        transcript_error = str(e)
        print(f"[YouTube] Transcript API failed: {e}")

    # Strategy 1.5: List Transcripts
    if not text:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi as YTA
            # Note: list_transcripts is a static method
            transcript_list = YTA.list_transcripts(video_id)
            for transcript in transcript_list:
                try:
                    fetched = transcript.fetch()
                    text = " ".join([item['text'] for item in fetched])
                    log_ingestion_event(source_id, twin_id, "info", f"Fetched {transcript.language} transcript")
                    break
                except:
                    continue
        except Exception as e:
             print(f"[YouTube] List transcripts failed: {e}")

    # -------------------------------------------------------------
    # Strategy 2: yt-dlp with Client Emulation (The "Magic" Fix)
    # -------------------------------------------------------------
    if not text:
        print("[YouTube] No captions found. Starting robust audio download...")
        log_ingestion_event(source_id, twin_id, "warning", "Attempting robust audio download (Client Emulation)")

        try:
            temp_dir = "temp_uploads"
            os.makedirs(temp_dir, exist_ok=True)
            temp_filename = f"yt_{video_id}"

            # CRITICAL: Use 'android' client to bypass web-based IP blocking
            ydl_opts = {
                'format': 'm4a/bestaudio/best',
                'outtmpl': os.path.join(temp_dir, f"{temp_filename}.%(ext)s"),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
                # KEY FIX: Emulate Android client to bypass bot checks
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android'],
                        'player_skip': ['webpage', 'configs', 'js'],
                        'include_live_dash': [True] 
                    }
                },
                'nocheckcertificate': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            audio_path = os.path.join(temp_dir, f"{temp_filename}.mp3")

            # Transcribe
            text = transcribe_audio_multi(audio_path)
            log_ingestion_event(source_id, twin_id, "info", "Audio transcribed via Gemini/Whisper")

            # Cleanup
            if os.path.exists(audio_path):
                os.remove(audio_path)

        except Exception as download_error:
            error_str = str(download_error)
            print(f"[YouTube] Robust download failed: {error_str}")

            if "Sign in" in error_str or "bot" in error_str.lower():
                raise ValueError(
                    "YouTube blocked the connection. Try a video with captions."
                )
            raise ValueError(f"Download failed: {download_error}")

    if not text:
        raise ValueError(
            "No transcript could be extracted. This video may not have captions. "
            "Try a different video with closed captions (CC) enabled."
        )

    try:
        # Phase 6: Staging workflow - extract and stage, don't index yet
        content_hash = calculate_content_hash(text)

        # Record source in Supabase with staging status
        supabase.table("sources").insert({
            "id": source_id,
            "twin_id": twin_id,
            "filename": f"YouTube: {video_id}",
            "file_size": len(text),
            "content_text": text,
            "content_hash": content_hash,
            "status": "staged",
            "staging_status": "staged",
            "extracted_text_length": len(text)
        }).execute()

        log_ingestion_event(source_id, twin_id, "info", f"YouTube transcript extracted: {len(text)} characters")

        # Phase 9: Log the action
        AuditLogger.log(twin_id, "KNOWLEDGE_UPDATE", "SOURCE_STAGED", metadata={"source_id": source_id, "filename": f"YouTube: {video_id}", "type": "youtube"})

        # Run health checks
        health_result = run_all_health_checks(source_id, twin_id, text, source_data={
            "filename": f"YouTube: {video_id}",
            "twin_id": twin_id
        })

        # Update source health status
        supabase.table("sources").update({
            "health_status": health_result["overall_status"]
        }).eq("id", source_id).execute()

        log_ingestion_event(source_id, twin_id, "info", f"Health checks completed: {health_result['overall_status']}")

        return 0  # No chunks yet (staged, not indexed)
    except Exception as e:
        print(f"Error staging YouTube content: {e}")
        log_ingestion_event(source_id, twin_id, "error", f"Error staging YouTube content: {e}")
        supabase.table("sources").update({"status": "error", "health_status": "failed"}).eq("id", source_id).execute()
        raise e


async def ingest_podcast_rss(source_id: str, twin_id: str, url: str):
    """
    Ingests the latest episode from a podcast RSS feed.
    """
    try:
        feed = feedparser.parse(url)
        if not feed.entries:
            raise ValueError("No episodes found in RSS feed")

        latest_episode = feed.entries[0]
        audio_url = None
        for enclosure in latest_episode.enclosures:
            if enclosure.type.startswith('audio'):
                audio_url = enclosure.href
                break

        if not audio_url:
            raise ValueError("No audio URL found in the latest episode")

        # Download audio temporarily
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        filename = f"{uuid.uuid4()}.mp3"
        file_path = os.path.join(temp_dir, filename)

        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(audio_url)
            with open(file_path, "wb") as f:
                f.write(response.content)

        # Transcribe and stage (ingest_source now stages instead of indexing)
        num_chunks = await ingest_source(source_id, twin_id, file_path, f"Podcast: {latest_episode.title}")
        return num_chunks
    except Exception as e:
        print(f"Error ingesting podcast: {e}")
        raise e


async def ingest_x_thread(source_id: str, twin_id: str, url: str):
    """
    Ingests an X (Twitter) thread.
    Uses the syndication endpoint for simplicity.
    """
    tweet_id_match = re.search(r'status/(\d+)', url)
    if not tweet_id_match:
        raise ValueError("Invalid X (Twitter) URL")

    tweet_id = tweet_id_match.group(1)

    try:
        import httpx
        # Using the syndication endpoint to get tweet content
        syndication_url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(syndication_url)
            if response.status_code != 200:
                raise ValueError(f"Failed to fetch tweet: {response.status_code}")

            data = response.json()
            text = data.get("text", "")
            user = data.get("user", {}).get("name", "Unknown")

            # Phase 6: Staging workflow
            content_hash = calculate_content_hash(text)

            # Record source in Supabase with staging status
            supabase.table("sources").insert({
                "id": source_id,
                "twin_id": twin_id,
                "filename": f"X Thread: {tweet_id} by {user}",
                "file_size": len(text),
                "content_text": text,
                "content_hash": content_hash,
                "status": "staged",
                "staging_status": "staged",
                "extracted_text_length": len(text)
            }).execute()

            log_ingestion_event(source_id, twin_id, "info", f"X thread extracted: {len(text)} characters")

            # Phase 9: Log the action
            AuditLogger.log(twin_id, "KNOWLEDGE_UPDATE", "SOURCE_STAGED", metadata={"source_id": source_id, "filename": f"X Thread: {tweet_id} by {user}", "type": "x_thread"})

            # Run health checks
            health_result = run_all_health_checks(source_id, twin_id, text, source_data={
                "filename": f"X Thread: {tweet_id} by {user}",
                "twin_id": twin_id
            })

            # Update source health status
            supabase.table("sources").update({
                "health_status": health_result["overall_status"]
            }).eq("id", source_id).execute()

            log_ingestion_event(source_id, twin_id, "info", f"Health checks completed: {health_result['overall_status']}")

            return 0  # No chunks yet (staged, not indexed)
    except Exception as e:
        print(f"Error staging X thread: {e}")
        log_ingestion_event(source_id, twin_id, "error", f"Error staging X thread: {e}")
        supabase.table("sources").update({"status": "error", "health_status": "failed"}).eq("id", source_id).execute()
        raise e


async def transcribe_audio(file_path: str) -> str:
    """
    Transcribes audio using OpenAI Whisper API.
    """
    client = get_openai_client()
    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file
        )
    return transcript.text


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunks.append(text[i:i + chunk_size])
    return chunks

# Embedding generation moved to modules.embeddings
from modules.embeddings import get_embedding


async def analyze_chunk_content(text: str) -> dict:
    """
    Analyzes a chunk to generate synthetic questions, category (Fact/Opinion), and tone.
    """
    client = get_openai_client()
    try:
        # Using gpt-4o-mini for better reasoning with JSON output
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """Analyze the text chunk provided. Return a JSON object with:
                - 'questions': 3 brief questions this text chunk answers.
                - 'category': 'OPINION' if it contains beliefs, values, or personal perspectives. 'FACT' if it is objective information.
                - 'tone': A single word describing the style (e.g., 'Assertive', 'Casual', 'Technical', 'Thoughtful').
                - 'opinion_map': If category is 'OPINION', provide a JSON object with:
                    - 'topic': The main subject of the opinion.
                    - 'stance': A short description of the owner's position.
                    - 'intensity': A score from 1-10 on how strongly this opinion is held.
                  If category is 'FACT', set 'opinion_map' to null."""},
                {"role": "user", "content": text}
            ],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error analyzing chunk: {e}")
        return {"questions": [], "category": "FACT", "tone": "Neutral", "opinion_map": None}


async def process_and_index_text(source_id: str, twin_id: str, text: str, metadata_override: dict = None):
    # 2. Chunk text
    chunks = chunk_text(text)

    # 3. Generate embeddings and upsert to Pinecone
    index = get_pinecone_index()
    vectors = []
    for i, chunk in enumerate(chunks):
        vector_id = str(uuid.uuid4())

        # Analyze chunk for enrichment
        analysis = await analyze_chunk_content(chunk)
        synth_questions = analysis.get("questions", [])

        # Enriched embedding: include synthetic questions to improve retrieval
        enriched_text = f"CONTENT: {chunk}\nQUESTIONS: {', '.join(synth_questions)}"
        embedding = get_embedding(enriched_text)

        metadata = {
            "source_id": source_id,
            "twin_id": twin_id,
            "text": chunk, # Keep original text for grounding
            "synthetic_questions": synth_questions,
            "category": analysis.get("category", "FACT"),
            "tone": analysis.get("tone", "Neutral"),
            "is_verified": False  # Explicitly mark regular sources as not verified
        }

        # Add opinion mapping if present
        opinion_map = analysis.get("opinion_map")
        if opinion_map and isinstance(opinion_map, dict):
            metadata["opinion_topic"] = opinion_map.get("topic")
            metadata["opinion_stance"] = opinion_map.get("stance")
            metadata["opinion_intensity"] = opinion_map.get("intensity")

        if metadata_override:
            metadata.update(metadata_override)

        vectors.append({
            "id": vector_id,
            "values": embedding,
            "metadata": metadata
        })

    # Upsert in batches of 100
    for i in range(0, len(vectors), 100):
        index.upsert(vectors[i:i + 100], namespace=twin_id)

    return len(vectors)


async def ingest_source(source_id: str, twin_id: str, file_path: str, filename: str = None):
    # 0. Check for existing sources with same name to handle "update"
    has_duplicate = False
    if filename:
        existing = supabase.table("sources").select("id").eq("twin_id", twin_id).eq("filename", filename).execute()
        if existing.data:
            print(f"File {filename} already exists. Updating source(s)...")
            has_duplicate = True
            # Delete ALL old versions first to keep knowledge clean
            for record in existing.data:
                old_source_id = record["id"]
                await delete_source(old_source_id, twin_id)
            # We keep the new source_id for the new record

    # 0.1 Record source in Supabase FIRST (before logging - prevents FK error)
    if filename:
        file_size = os.path.getsize(file_path)
        supabase.table("sources").insert({
            "id": source_id,
            "twin_id": twin_id,
            "filename": filename,
            "file_size": file_size,
            "status": "processing"
        }).execute()

    # Log after source record exists (to satisfy FK constraint)
    if has_duplicate:
        log_ingestion_event(source_id, twin_id, "info", f"Duplicate filename detected, removed old sources")


    # 1. Extract text (PDF or Audio)
    if file_path.endswith('.pdf'):
        text = extract_text_from_pdf(file_path)
    elif file_path.endswith(('.mp3', '.wav', '.m4a', '.webm')):
        text = await transcribe_audio(file_path)
    else:
        # Generic text extraction for other types if needed, or error
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()

    # Phase 6: Staging workflow - store text, run health checks, don't index yet
    content_hash = calculate_content_hash(text)

    # Update source with extracted text and staging status
    update_data = {
        "content_text": text,
        "content_hash": content_hash,
        "status": "staged",
        "staging_status": "staged",
        "extracted_text_length": len(text)
    }

    if filename:
        supabase.table("sources").update(update_data).eq("id", source_id).execute()
    else:
        # If no filename, we need to insert the source record
        supabase.table("sources").insert({
            "id": source_id,
            "twin_id": twin_id,
            **update_data
        }).execute()

    log_ingestion_event(source_id, twin_id, "info", f"Text extracted: {len(text)} characters")

    # Phase 9: Log the action
    AuditLogger.log(twin_id, "KNOWLEDGE_UPDATE", "SOURCE_STAGED", metadata={"source_id": source_id, "filename": filename or "unknown", "type": "file_upload"})

    # Run health checks
    health_result = run_all_health_checks(
        source_id, 
        twin_id, 
        text,
        source_data={
            "filename": filename or "unknown",
            "twin_id": twin_id
        }
    )

    # Update source health status
    supabase.table("sources").update({
        "health_status": health_result["overall_status"]
    }).eq("id", source_id).execute()

    log_ingestion_event(source_id, twin_id, "info", f"Health checks completed: {health_result['overall_status']}")

    return 0  # No chunks yet (staged, not indexed)


async def delete_source(source_id: str, twin_id: str):
    """
    Deletes a source from Supabase and its associated vectors from Pinecone.
    """
    # 1. Delete from Pinecone
    index = get_pinecone_index()
    try:
        # Note: Delete by filter requires metadata indexing enabled or serverless index
        index.delete(
            filter={
                "source_id": {"$eq": source_id}
            },
            namespace=twin_id
        )
    except Exception as e:
        print(f"Error deleting from Pinecone: {e}")
        # Continue to delete from Supabase even if Pinecone fails (maybe it was already gone)

    # 2. Delete from Supabase
    supabase.table("sources").delete().eq("id", source_id).eq("twin_id", twin_id).execute()

    # Phase 9: Log the action
    AuditLogger.log(twin_id, "KNOWLEDGE_UPDATE", "SOURCE_DELETED", metadata={"source_id": source_id})

    return True

# Phase 6: Staging workflow functions


async def approve_source(source_id: str) -> str:
    """
    Approves staged source and creates training job.
    
    Args:
        source_id: Source UUID
    
    Returns:
        Training job ID
    """
    # Get source to verify it exists and get twin_id
    source_response = supabase.table("sources").select("twin_id, staging_status").eq("id", source_id).single().execute()
    if not source_response.data:
        raise ValueError(f"Source {source_id} not found")

    twin_id = source_response.data["twin_id"]

    # Update staging status
    supabase.table("sources").update({
        "staging_status": "approved",
        "status": "approved"
    }).eq("id", source_id).execute()

    log_ingestion_event(source_id, twin_id, "info", "Source approved, creating training job")

    # Phase 9: Log the action
    AuditLogger.log(twin_id, "KNOWLEDGE_UPDATE", "SOURCE_APPROVED", metadata={"source_id": source_id})

    # Create training job
    job_id = create_training_job(source_id, twin_id, job_type="ingestion", priority=0)

    return job_id


async def reject_source(source_id: str, reason: str):
    """
    Rejects source with reason.
    
    Args:
        source_id: Source UUID
        reason: Rejection reason
    """
    source_response = supabase.table("sources").select("twin_id").eq("id", source_id).single().execute()
    if not source_response.data:
        raise ValueError(f"Source {source_id} not found")

    twin_id = source_response.data["twin_id"]

    # Update staging status
    supabase.table("sources").update({
        "staging_status": "rejected",
        "status": "rejected"
    }).eq("id", source_id).execute()

    log_ingestion_event(source_id, twin_id, "warning", f"Source rejected: {reason}")

    # Phase 9: Log the action
    AuditLogger.log(twin_id, "KNOWLEDGE_UPDATE", "SOURCE_REJECTED", metadata={"source_id": source_id, "reason": reason})


async def bulk_approve_sources(source_ids: List[str]) -> Dict[str, str]:
    """
    Bulk approve multiple sources.
    
    Args:
        source_ids: List of source UUIDs
    
    Returns:
        Dict mapping source_id to job_id
    """
    results = {}
    for source_id in source_ids:
        try:
            job_id = await approve_source(source_id)
            results[source_id] = job_id
        except Exception as e:
            print(f"Error approving source {source_id}: {e}")
            results[source_id] = None
    return results


async def bulk_update_source_metadata(source_ids: List[str], metadata_updates: Dict[str, Any]):
    """
    Bulk update metadata for sources.
    
    Args:
        source_ids: List of source UUIDs
        metadata_updates: Dict with fields to update (access_group, publish_date, author, citation_url, visibility)
    """
    allowed_fields = ["publish_date", "author", "citation_url"]
    update_data = {k: v for k, v in metadata_updates.items() if k in allowed_fields}

    if not update_data:
        return

    for source_id in source_ids:
        try:
            supabase.table("sources").update(update_data).eq("id", source_id).execute()
        except Exception as e:
            print(f"Error updating source {source_id}: {e}")

# Wrapper functions for router endpoints (create source_id and call actual functions)


async def ingest_youtube_transcript_wrapper(twin_id: str, url: str) -> str:
    """Wrapper that creates source_id and calls ingest_youtube_transcript"""
    source_id = str(uuid.uuid4())
    await ingest_youtube_transcript(source_id, twin_id, url)
    return source_id


async def ingest_podcast_transcript(twin_id: str, url: str) -> str:
    """Wrapper that creates source_id and calls ingest_podcast_rss"""
    source_id = str(uuid.uuid4())
    await ingest_podcast_rss(source_id, twin_id, url)
    return source_id


async def ingest_file(twin_id: str, file) -> str:
    """Wrapper that saves uploaded file and calls ingest_source"""

    source_id = str(uuid.uuid4())
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)

    # Save uploaded file temporarily
    file_extension = os.path.splitext(file.filename)[1] if file.filename else ""
    temp_filename = f"{source_id}{file_extension}"
    file_path = os.path.join(temp_dir, temp_filename)

    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Call ingest_source with the file path
        await ingest_source(source_id, twin_id, file_path, file.filename)

        # Clean up temp file
        if os.path.exists(file_path):
            os.remove(file_path)

        return source_id
    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise e


async def ingest_url(twin_id: str, url: str) -> str:
    """Wrapper that detects URL type and routes to appropriate ingestion function"""
    source_id = str(uuid.uuid4())

    # Detect URL type and route accordingly
    if "youtube.com" in url or "youtu.be" in url:
        await ingest_youtube_transcript(source_id, twin_id, url)
    elif "twitter.com" in url or "x.com" in url:
        await ingest_x_thread(source_id, twin_id, url)
    elif url.endswith(".rss") or "feed" in url.lower() or "podcast" in url.lower():
        await ingest_podcast_rss(source_id, twin_id, url)
    else:
        # Generic URL - try to fetch and extract text
        import httpx
        file_path = None
        text_file_path = None
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()

                # Save content to temp file
                temp_dir = "temp_uploads"
                os.makedirs(temp_dir, exist_ok=True)
                temp_filename = f"{source_id}.html"
                file_path = os.path.join(temp_dir, temp_filename)

                with open(file_path, "wb") as f:
                    f.write(response.content)

                # Extract text from HTML (basic extraction)
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response.text, 'html.parser')
                    text = soup.get_text(separator='\n', strip=True)
                except Exception:
                    # Fallback: use regex to extract text if BeautifulSoup fails or not available
                    import re
                    text = re.sub(r'<[^>]+>', '', response.text)
                    text = re.sub(r'\s+', ' ', text).strip()

                # Save as text file and ingest
                text_file_path = os.path.join(temp_dir, f"{source_id}.txt")
                with open(text_file_path, "w", encoding="utf-8") as f:
                    f.write(text)

                await ingest_source(source_id, twin_id, text_file_path, url)
        except Exception as e:
            raise ValueError(f"Failed to ingest URL: {e}")
        finally:
            # Always clean up temporary files, even if exceptions occur
            for temp_file in [file_path, text_file_path]:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except Exception as cleanup_error:
                        # Log but don't fail on cleanup errors
                        print(f"Warning: Failed to clean up temp file {temp_file}: {cleanup_error}")

    return source_id