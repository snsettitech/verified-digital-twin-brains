import os
import uuid
import asyncio
import re
import json
import feedparser
import yt_dlp
import time
import httpx
import html
import html as html_lib
import asyncio
from typing import List, Dict, Optional, Any, Tuple
from modules.transcription import transcribe_audio_multi
from modules.embeddings import get_embedding
from PyPDF2 import PdfReader
from youtube_transcript_api import YouTubeTranscriptApi
from modules.clients import get_openai_client, get_pinecone_index
from modules.observability import supabase, log_ingestion_event
from modules.health_checks import run_all_health_checks, calculate_content_hash
from modules.training_jobs import create_training_job
from modules.governance import AuditLogger


# ============================================================================
# Enterprise Configuration & Utilities
# ============================================================================

class YouTubeConfig:
    """Enterprise-grade YouTube ingestion configuration."""
    MAX_RETRIES = int(os.getenv("YOUTUBE_MAX_RETRIES", "5"))
    ASR_MODEL = os.getenv("YOUTUBE_ASR_MODEL", "whisper-large-v3")
    ASR_PROVIDER = os.getenv("YOUTUBE_ASR_PROVIDER", "openai")
    LANGUAGE_DETECTION = os.getenv("YOUTUBE_LANGUAGE_DETECTION", "true").lower() == "true"
    PII_SCRUB = os.getenv("YOUTUBE_PII_SCRUB", "true").lower() == "true"
    VERBOSE_LOGGING = os.getenv("YOUTUBE_VERBOSE_LOGGING", "false").lower() == "true"
    COOKIES_FILE = os.getenv("YOUTUBE_COOKIES_FILE")
    PROXY = os.getenv("YOUTUBE_PROXY")


class ErrorClassifier:
    """Classify YouTube/yt-dlp errors for better handling and telemetry."""
    
    @staticmethod
    def classify(error_msg: str) -> Tuple[str, str, bool]:
        """
        Classify error and return (category, user_message, is_retryable).
        
        Categories:
        - auth: Authentication/login required
        - rate_limit: HTTP 429, quota exceeded
        - gating: Age/region/access restrictions
        - unavailable: Video deleted/private
        - network: Connection/timeout issues
        - unknown: Unclassified
        """
        error_lower = error_msg.lower()
        
        # Rate limiting
        if "429" in error_msg or "rate" in error_lower or "quota" in error_lower or "too many requests" in error_lower:
            return "rate_limit", "YouTube rate limit reached. Retrying with backoff...", True
        
        # Authentication required
        if "403" in error_msg or "sign in" in error_lower or "unauthorized" in error_lower:
            return "auth", "This video requires authentication or is age-restricted.", False
        
        # Gating (region, age, etc.)
        if "geo" in error_lower or "region" in error_lower or "not available" in error_lower:
            return "gating", "This video is not available in your region.", False
        
        # Video unavailable
        if "unavailable" in error_lower or "deleted" in error_lower or "not found" in error_lower:
            return "unavailable", "This video is unavailable (deleted, private, or not found).", False
        
        # Network issues
        if "timeout" in error_lower or "connection" in error_lower or "socket" in error_lower:
            return "network", "Network connection issue. Retrying...", True
        
        return "unknown", f"Unexpected error: {error_msg}", False


class LanguageDetector:
    """Lightweight language detection for transcripts."""
    
    # Simple heuristics for common languages (word counts and patterns)
    LANGUAGE_PATTERNS = {
        "en": [r"\b(the|and|a|to|of|in|is|that|it)\b"],
        "es": [r"\b(el|la|de|que|y|a|en|un|es)\b"],
        "fr": [r"\b(le|la|de|et|a|en|un|est|c'est)\b"],
        "de": [r"\b(der|die|und|in|den|von|zu|das)\b"],
        "ja": [r"[ぁ-ん]|[ァ-ヴー]|[一-龥]"],
        "zh": [r"[\u4e00-\u9fff]"],
    }
    
    @staticmethod
    def detect(text: str) -> str:
        """Detect language of text. Returns language code (e.g., 'en', 'es')."""
        if not text or len(text) < 10:
            return "en"  # Default
        
        text_lower = text.lower()
        scores = {}
        
        for lang, patterns in LanguageDetector.LANGUAGE_PATTERNS.items():
            count = 0
            for pattern in patterns:
                count += len(re.findall(pattern, text_lower))
            scores[lang] = count
        
        if scores:
            return max(scores, key=scores.get)
        return "en"


class PIIScrubber:
    """Lightweight PII detection and redaction."""
    
    # Regex patterns for common PII (very permissive, for flagging)
    PATTERNS = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"(?:\+1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b",  # Matches multiple formats
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
        "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    }
    
    @staticmethod
    def detect_pii(text: str) -> Dict[str, List[str]]:
        """Detect PII in text. Returns dict of pii_type -> [matches]."""
        detected = {}
        for pii_type, pattern in PIIScrubber.PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                detected[pii_type] = matches
        return detected
    
    @staticmethod
    def has_pii(text: str) -> bool:
        """Check if text contains any PII."""
        return bool(PIIScrubber.detect_pii(text))
    
    @staticmethod
    def scrub(text: str) -> str:
        """Redact PII from text."""
        for pii_type, pattern in PIIScrubber.PATTERNS.items():
            placeholder = f"[{pii_type.upper()}]"
            text = re.sub(pattern, placeholder, text)
        return text


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





def _build_yt_dlp_opts(video_id: str, source_id: str, twin_id: str) -> dict:
    """
    Build yt-dlp options with enterprise-grade toggles:
    - Multiple client emulation strategies (Android, web, iOS)
    - Optional cookies (file only) for age/region-gated videos
    - Optional proxy for IP reputation routing
    - Browser headers to avoid bot detection
    """
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    temp_filename = f"yt_{video_id}"

    cookie_file = os.getenv("YOUTUBE_COOKIES_FILE")
    proxy_url = os.getenv("YOUTUBE_PROXY")

    # Start with Android client emulation (most reliable for containers)
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
        # Multiple client strategies (try Android first, then web)
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web', 'ios'],  # Try multiple clients
                'player_skip': ['webpage', 'configs', 'js'],
                'include_live_dash': [True]
            }
        },
        'nocheckcertificate': True,
        'socket_timeout': 30,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        },
        'retries': 5,
        'fragment_retries': 5,
        'skip_unavailable_fragments': True,
    }

    if proxy_url:
        ydl_opts['proxy'] = proxy_url
        log_ingestion_event(source_id, twin_id, "info", "Using YOUTUBE_PROXY for YouTube download")

    # Only use file-based cookies (cookiesfrombrowser doesn't work in containers)
    if cookie_file and os.path.exists(cookie_file):
        ydl_opts['cookiefile'] = cookie_file
        log_ingestion_event(source_id, twin_id, "info", "Using YOUTUBE_COOKIES_FILE for YouTube download")
    else:
        if YouTubeConfig.VERBOSE_LOGGING:
            log_ingestion_event(source_id, twin_id, "info", "No cookie file found; using client emulation only")

    # Log configuration for telemetry
    log_ingestion_event(source_id, twin_id, "info", 
        f"YouTube config: ASR={YouTubeConfig.ASR_PROVIDER}:{YouTubeConfig.ASR_MODEL}, "
        f"MaxRetries={YouTubeConfig.MAX_RETRIES}, LanguageDetection={YouTubeConfig.LANGUAGE_DETECTION}, "
        f"PIIScrub={YouTubeConfig.PII_SCRUB}")

    return ydl_opts, temp_dir, temp_filename


async def ingest_youtube_transcript(source_id: str, twin_id: str, url: str):
    """
    Ingest YouTube video transcript using robust multi-strategy approach.
    """
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL")

    # -------------------------------------------------------------
    # Step 0: Ensure Source Record exists
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
            
            # Brief wait to ensure DB propagation (especially with replica lag if any)
            await asyncio.sleep(1)
    except Exception as e:
        print(f"[YouTube] Error or duplicate during source record creation: {e}")

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

    # Strategy 1.5: List Transcripts (all languages)
    if not text:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi as YTA
            transcript_list = YTA.list_transcripts(video_id)
            
            # Try manual transcripts first (usually more complete)
            for transcript in transcript_list.manually_created_transcripts:
                try:
                    fetched = transcript.fetch()
                    text = " ".join([item['text'] for item in fetched])
                    log_ingestion_event(source_id, twin_id, "info", f"Fetched manual {transcript.language} transcript")
                    break
                except:
                    continue
            
            # Then try auto-generated transcripts
            if not text:
                for transcript in transcript_list.generated_transcripts:
                    try:
                        fetched = transcript.fetch()
                        text = " ".join([item['text'] for item in fetched])
                        log_ingestion_event(source_id, twin_id, "info", f"Fetched auto-generated {transcript.language} transcript")
                        break
                    except:
                        continue
        except Exception as e:
            print(f"[YouTube] List transcripts failed: {e}")

    # -------------------------------------------------------------
    # Strategy 1.6: Direct HTTP fetch with browser headers (bypasses library blocks)
    # -------------------------------------------------------------
    if not text:
        try:
            print(f"[YouTube] Trying direct HTTP transcript fetch for {video_id}")
            log_ingestion_event(source_id, twin_id, "info", "Attempting direct HTTP transcript fetch")
            
            # Use Chrome-like headers to appear as a real browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            
            # Fetch the video page
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
                response = await client.get(video_url)
                
                if response.status_code == 200:
                    page_content = response.text
                    
                    # Extract caption track URLs from the page
                    # Strategy 1.6.a: Main Player Response
                    caption_match = re.search(r'"captionTracks":\s*(\[.*?\])', page_content)
                    
                    # Strategy 1.6.b: Escaped JSON (mobile/older formats)
                    if not caption_match:
                        caption_match = re.search(r'captionTracks\\":(\[.*?\])', page_content)
                    
                    # Strategy 1.6.c: Alternative escaped format
                    if not caption_match:
                        caption_match = re.search(r'\\u0022captionTracks\\u0022:\\s*(\\\[.*?\\\])', page_content)

                    if caption_match:
                        print(f"[YouTube] Found caption tracks on page")
                        try:
                            raw_json = caption_match.group(1).replace('\\"', '"').replace('\\\\', '\\').replace('\\u0022', '"')
                            # Ensure we handle double brackets from some escaped formats
                            if raw_json.startswith('\\['): raw_json = json.loads(f'"{raw_json}"')
                            caption_tracks = json.loads(raw_json)
                            
                            # Find English or first available caption
                            caption_url = None
                            for track in caption_tracks:
                                lang = track.get("languageCode", "")
                                if lang.startswith("en"):
                                    caption_url = track.get("baseUrl")
                                    break
                            
                            # Fallback to first track if no English
                            if not caption_url and caption_tracks:
                                caption_url = caption_tracks[0].get("baseUrl")
                            
                            if caption_url:
                                # Fetch the actual captions
                                caption_response = await client.get(caption_url)
                                if caption_response.status_code == 200:
                                    # Parse XML captions
                                    caption_xml = caption_response.text
                                    caption_texts = re.findall(r'<text[^>]*>(.*?)</text>', caption_xml, re.DOTALL)
                                    
                                    if caption_texts:
                                        # Unescape HTML entities and join
                                        text = " ".join([html.unescape(t.strip()) for t in caption_texts])
                                        text = re.sub(r'\s+', ' ', text).strip()
                                        log_ingestion_event(source_id, twin_id, "info", f"Direct HTTP transcript fetch successful ({len(text)} chars)")
                                        print(f"[YouTube] Direct HTTP fetch succeeded: {len(text)} characters")
                        except json.JSONDecodeError:
                            print(f"[YouTube] Could not parse caption tracks JSON")
        except Exception as e:
            print(f"[YouTube] Direct HTTP fetch failed: {e}")

    # -------------------------------------------------------------
    # Strategy 2: yt-dlp with Multiple Client Emulation & Better Error Handling
    # Using YouTubeRetryStrategy for enterprise-grade retry logic
    # -------------------------------------------------------------
    if not text:
        print("[YouTube] No captions found. Starting robust audio download...")
        log_ingestion_event(source_id, twin_id, "warning", "Attempting robust audio download (yt-dlp with multiple clients)")

        from modules.youtube_retry_strategy import YouTubeRetryStrategy
        from modules.ingestion import ErrorClassifier
        
        ydl_opts, temp_dir, temp_filename = _build_yt_dlp_opts(video_id, source_id, twin_id)
        
        # Initialize retry strategy with configured max_retries
        config = YouTubeConfig()
        strategy = YouTubeRetryStrategy(
            source_id=source_id,
            twin_id=twin_id,
            max_retries=config.MAX_RETRIES,
            verbose=config.VERBOSE_LOGGING
        )
        
        temp_audio_path = None
        
        while strategy.attempts < strategy.max_retries and not text:
            try:
                strategy.attempts += 1
                print(f"[YouTube] Download attempt {strategy.attempts}/{strategy.max_retries} for {video_id}")
                
                # Download audio
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                temp_audio_path = os.path.join(temp_dir, f"{temp_filename}.mp3")
                
                if not os.path.exists(temp_audio_path):
                    raise FileNotFoundError(f"Audio file not created at {temp_audio_path}")

                # Transcribe
                print(f"[YouTube] Transcribing audio for {video_id}")
                text = transcribe_audio_multi(temp_audio_path)
                
                # Language detection
                language = LanguageDetector.detect(text)
                
                # PII detection
                pii_detected = PIIScrubber.has_pii(text) if config.PII_SCRUB else False
                detected_pii = PIIScrubber.detect_pii(text) if pii_detected else []
                
                # Log success with metadata
                strategy.log_success(
                    content_length=len(text),
                    metadata={
                        "language": language,
                        "has_pii": pii_detected,
                        "pii_count": len(detected_pii)
                    }
                )
                
                log_ingestion_event(
                    source_id, twin_id, "info",
                    f"Audio transcribed via Gemini/Whisper ({len(text)} chars, lang={language}, pii={pii_detected})"
                )
                
                print(f"[YouTube] Successfully transcribed {video_id}: {len(text)} characters, language={language}")
                
            except Exception as download_error:
                error_msg = str(download_error)
                error_category, user_msg, retryable = ErrorClassifier.classify(error_msg)
                
                strategy.log_attempt(error_msg)
                
                print(f"[YouTube] Attempt {strategy.attempts} failed [{error_category}]: {error_msg}")
                log_ingestion_event(
                    source_id, twin_id, "warning",
                    f"Download attempt {strategy.attempts} failed [{error_category}]: {error_msg}"
                )
                
                # Determine if we should retry
                if not strategy.should_retry(error_category):
                    print(f"[YouTube] Error category '{error_category}' is non-retryable, stopping attempts")
                    break
                
                if strategy.attempts < strategy.max_retries:
                    wait_time = strategy.wait_for_retry()
                    print(f"[YouTube] Waiting {wait_time}s before retry...")
                else:
                    break

        # Cleanup temp file
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except:
                pass

        if not text:
            # Get final error message with classification
            final_error = strategy.get_final_error_message(strategy.last_error or "Unknown error")
            metrics = strategy.get_metrics()
            
            log_ingestion_event(
                source_id, twin_id, "error",
                f"YouTube ingestion failed after {strategy.attempts} attempts. Metrics: {metrics}"
            )
            
            raise ValueError(final_error)

    if not text:
        raise ValueError(
            "No transcript could be extracted. This video may not have captions. "
            "Try a different video with closed captions (CC) enabled."
        )

    try:
        # Phase 6: Direct indexing - extract, index, and approve immediately
        content_hash = calculate_content_hash(text)

        # Record source in Supabase with indexed status
        supabase.table("sources").insert({
            "id": source_id,
            "twin_id": twin_id,
            "filename": f"YouTube: {video_id}",
            "file_size": len(text),
            "content_text": text,
            "content_hash": content_hash,
            "status": "processed",
            "staging_status": "approved",
            "extracted_text_length": len(text)
        }).execute()

        log_ingestion_event(source_id, twin_id, "info", f"YouTube transcript extracted: {len(text)} characters")

        # Phase 7: Direct indexing (skip staging approval)
        num_chunks = await process_and_index_text(source_id, twin_id, text, metadata_override={
            "filename": f"YouTube: {video_id}",
            "type": "youtube",
            "video_id": video_id
        })

        # Fetch tenant_id
        tenant_id = None
        try:
            twin_res = supabase.table("twins").select("tenant_id").eq("id", twin_id).single().execute()
            tenant_id = twin_res.data.get("tenant_id") if twin_res.data else None
        except Exception:
            pass

        # Phase 8: Log the action
        AuditLogger.log(
            tenant_id=tenant_id,
            twin_id=twin_id, 
            event_type="KNOWLEDGE_UPDATE", 
            action="SOURCE_INDEXED", 
            metadata={"source_id": source_id, "filename": f"YouTube: {video_id}", "type": "youtube", "chunks": num_chunks}
        )


        log_ingestion_event(source_id, twin_id, "info", f"YouTube content indexed: {num_chunks} chunks")

        return num_chunks
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
    Ingests an X (Twitter) thread using multiple fallback strategies.
    """
    tweet_id_match = re.search(r'status/(\d+)', url)
    if not tweet_id_match:
        raise ValueError("Invalid X (Twitter) URL")

    tweet_id = tweet_id_match.group(1)
    text = ""
    user = "Unknown"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    # -------------------------------------------------------------
    # Strategy 1: cdn.syndication.twimg.com (legacy, often fails)
    # -------------------------------------------------------------
    try:
        syndication_url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&token=0"
        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            response = await client.get(syndication_url)
            if response.status_code == 200:
                data = response.json()
                text = data.get("text", "")
                user = data.get("user", {}).get("name", "Unknown")
                if text:
                    print(f"[X Thread] Syndication API returned {len(text)} chars")
    except Exception as e:
        print(f"[X Thread] Syndication API failed: {e}")

    # -------------------------------------------------------------
    # Strategy 2: Nitter instances (public Twitter readers)
    # -------------------------------------------------------------
    if not text:
        nitter_instances = [
            "nitter.privacydev.net",
            "nitter.poast.org", 
            "nitter.1d4.us",
        ]
        for instance in nitter_instances:
            try:
                nitter_url = f"https://{instance}/i/status/{tweet_id}"
                async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True) as client:
                    response = await client.get(nitter_url)
                    if response.status_code == 200:
                        page = response.text
                        # Extract tweet content from nitter HTML
                        content_match = re.search(r'<div class="tweet-content[^"]*"[^>]*>(.*?)</div>', page, re.DOTALL)
                        if content_match:
                            raw_text = content_match.group(1)
                            # Clean HTML tags and entities
                            text = re.sub(r'<[^>]+>', ' ', raw_text)
                            text = html_lib.unescape(text)
                            text = re.sub(r'\s+', ' ', text).strip()
                            
                            # Extract username
                            user_match = re.search(r'<a class="fullname"[^>]*>([^<]+)</a>', page)
                            if user_match:
                                user = user_match.group(1).strip()
                            
                            if text:
                                print(f"[X Thread] Nitter {instance} returned {len(text)} chars")
                                break
            except Exception as e:
                print(f"[X Thread] Nitter {instance} failed: {e}")
                continue

    # -------------------------------------------------------------
    # Strategy 3: FxTwitter API (embed generator)
    # -------------------------------------------------------------
    if not text:
        try:
            fx_url = f"https://api.fxtwitter.com/status/{tweet_id}"
            async with httpx.AsyncClient(timeout=15, headers=headers) as client:
                response = await client.get(fx_url)
                if response.status_code == 200:
                    data = response.json()
                    tweet = data.get("tweet", {})
                    text = tweet.get("text", "")
                    user = tweet.get("author", {}).get("name", "Unknown")
                    if text:
                        print(f"[X Thread] FxTwitter API returned {len(text)} chars")
        except Exception as e:
            print(f"[X Thread] FxTwitter API failed: {e}")

    # -------------------------------------------------------------
    # Strategy 4: VxTwitter API (another embed generator)
    # -------------------------------------------------------------
    if not text:
        try:
            vx_url = f"https://api.vxtwitter.com/status/{tweet_id}"
            async with httpx.AsyncClient(timeout=15, headers=headers) as client:
                response = await client.get(vx_url)
                if response.status_code == 200:
                    data = response.json()
                    text = data.get("text", "")
                    user = data.get("user_name", "Unknown")
                    if text:
                        print(f"[X Thread] VxTwitter API returned {len(text)} chars")
        except Exception as e:
            print(f"[X Thread] VxTwitter API failed: {e}")

    # -------------------------------------------------------------
    # Final: Handle result
    # -------------------------------------------------------------
    if not text:
        log_ingestion_event(source_id, twin_id, "error", "All X thread extraction methods failed")
        raise ValueError(
            "Could not extract X thread content. All methods failed. "
            "X/Twitter may be blocking requests from this server. "
            "Try copying the tweet text manually and pasting it as a text file."
        )

    try:
        content_hash = calculate_content_hash(text)

        # Record source in Supabase - use upsert to be safe
        supabase.table("sources").upsert({
            "id": source_id,
            "twin_id": twin_id,
            "filename": f"X Thread: {tweet_id} by {user}",
            "file_size": len(text),
            "content_text": text,
            "content_hash": content_hash,
            "status": "processed",
            "staging_status": "approved",
            "extracted_text_length": len(text)
        }).execute()

        # Small verification wait to settle FK
        await asyncio.sleep(1)

        log_ingestion_event(source_id, twin_id, "info", f"X thread extracted: {len(text)} characters")

        # Direct indexing
        num_chunks = await process_and_index_text(source_id, twin_id, text, metadata_override={
            "filename": f"X Thread: {tweet_id} by {user}",
            "type": "x_thread",
            "tweet_id": tweet_id
        })

        # Fetch tenant_id
        tenant_id = None
        try:
            twin_res = supabase.table("twins").select("tenant_id").eq("id", twin_id).single().execute()
            tenant_id = twin_res.data.get("tenant_id") if twin_res.data else None
        except Exception:
            pass

        AuditLogger.log(
            tenant_id=tenant_id,
            twin_id=twin_id, 
            event_type="KNOWLEDGE_UPDATE", 
            action="SOURCE_INDEXED", 
            metadata={"source_id": source_id, "filename": f"X Thread: {tweet_id} by {user}", "type": "x_thread", "chunks": num_chunks}
        )


        log_ingestion_event(source_id, twin_id, "info", f"X thread indexed: {num_chunks} chunks")

        return num_chunks
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

    # Phase 8: Emit event for Action Engine
    from modules.actions_engine import EventEmitter
    EventEmitter.emit(
        twin_id=twin_id,
        event_type="source_ingested",
        payload={
            "source_id": source_id,
            "filename": metadata_override.get("filename") if metadata_override else "Document",
            "type": metadata_override.get("type", "file") if metadata_override else "file",
            "chunks_indexed": len(vectors),
            "content_preview": text[:1000] # For trigger matching (keywords)
        },
        source_context={
            "source": "ingestion_engine",
            "method": "process_and_index_text"
        }
    )

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


async def ingest_x_thread_wrapper(twin_id: str, url: str) -> str:
    """Wrapper that creates source_id and calls ingest_x_thread"""
    source_id = str(uuid.uuid4())
    await ingest_x_thread(source_id, twin_id, url)
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
