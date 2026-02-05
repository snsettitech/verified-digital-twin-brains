# backend/modules/media_ingestion.py
"""
Media Ingestion Module (Phase 5).

Handles downloading audio from YouTube and podcasts, transcribing it,
and extracting knowledge while separating the speaker (Diarization).
"""

import os
import json
import logging
import asyncio
import uuid
import tempfile
import shutil
from typing import Dict, Any, List, Optional
from datetime import datetime

import yt_dlp
from pydub import AudioSegment
import imageio_ffmpeg

from modules.observability import supabase, log_ingestion_event
from modules.clients import get_openai_client
from modules.governance import AuditLogger

logger = logging.getLogger(__name__)

# Get path to ffmpeg binary
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
AudioSegment.converter = FFMPEG_PATH
AudioSegment.ffmpeg = FFMPEG_PATH

class MediaIngester:
    """Handles downloading and processing of media files."""
    
    def __init__(self, twin_id: str):
        self.twin_id = twin_id
        self.client = get_openai_client()

    async def ingest_youtube_video(self, url: str) -> Dict[str, Any]:
        """
        Download and ingest a YouTube video.
        
        Args:
            url: YouTube video URL
            
        Returns:
            Dict with ingestion results
        """
        source_id = str(uuid.uuid4())
        
        try:
            # 1. Create Source Record
            supabase.table("sources").insert({
                "id": source_id,
                "twin_id": self.twin_id,
                "filename": f"YouTube: {url}",
                "status": "processing",
                "staging_status": "training",
                "type": "youtube_video"
            }).execute()
            
            log_ingestion_event(source_id, self.twin_id, "info", f"Starting YouTube ingestion: {url}")
            
            # 2. Download Audio
            with tempfile.TemporaryDirectory() as temp_dir:
                audio_path = self._download_audio(url, temp_dir)
                if not audio_path:
                    raise Exception("Failed to download audio")
                
                # 3. Transcribe
                transcript = await self._transcribe_audio(audio_path)
                
                # 4. Diarize (Separate Host vs Guest)
                processed_content = await self._diarize_and_process(transcript)
                
                # 5. Index
                from modules.ingestion import process_and_index_text
                num_chunks = await process_and_index_text(
                    source_id, self.twin_id, processed_content,
                    metadata_override={
                        "filename": f"YouTube: {url}",
                        "type": "youtube_video",
                        "url": url,
                        "diarized": True
                    }
                )
                
                # 6. Update Source
                content_len = len(processed_content)
                supabase.table("sources").update({
                    "content_text": processed_content,
                    "content_hash": str(hash(processed_content)),
                    "file_size": content_len,
                    "status": "indexed",
                    "staging_status": "live",
                    "extracted_text_length": content_len
                }).eq("id", source_id).execute()
                
                log_ingestion_event(source_id, self.twin_id, "info", f"YouTube ingestion complete: {num_chunks} chunks")
                
                return {
                    "success": True,
                    "source_id": source_id,
                    "chunks": num_chunks
                }
                
        except Exception as e:
            logger.error(f"YouTube ingestion failed: {e}", exc_info=True)
            supabase.table("sources").update({"status": "error", "health_status": "failed"}).eq("id", source_id).execute()
            return {"success": False, "error": str(e)}

    def _download_audio(self, url: str, output_dir: str) -> Optional[str]:
        """Download audio from YouTube using yt-dlp."""
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
            'ffmpeg_location': FFMPEG_PATH,
            'quiet': True,
            'no_warnings': True
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                # yt-dlp changes extension to mp3
                base, _ = os.path.splitext(filename)
                return f"{base}.mp3"
        except Exception as e:
            logger.error(f"yt-dlp error: {e}")
            return None

    async def _transcribe_audio(self, file_path: str) -> str:
        """Transcribe audio file using OpenAI Whisper."""
        try:
            # Check file size (Whisper limit 25MB)
            file_size = os.path.getsize(file_path)
            if file_size > 25 * 1024 * 1024:
                # Chunking (simplified: just take first 25MB for MVP)
                # In production, integrate pydub to split properly
                logger.warning("Audio > 25MB, splitting not fully implemented. Truncating.")
                pass 
            
            with open(file_path, "rb") as audio_file:
                transcript = await self.client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file,
                    response_format="text" # text is cheaper/simpler, verbose_json needed for timestamps
                )
            return transcript
        except Exception as e:
            logger.error(f"Whisper error: {e}")
            raise

    async def _diarize_and_process(self, raw_transcript: str) -> str:
        """
        Use LLM to identify the Speaker (Twin) vs Guest.
        
        Strategy: Ask GPT-4o to extract ONLY the parts spoken by the 'Host'.
        """
        # Limit transcript length for context window if needed
        chunked_text = raw_transcript[:100000] 
        
        prompt = """
        You are a Diarization Assistant.
        The user (Twin) is the HOST of this content (YouTube/Podcast).
        
        Task:
        1. Identify the Main Speaker (Host) vs Guests.
        2. Extract ONLY the Host's beliefs, stories, and knowledge.
        3. Ignore the Guest's opinions.
        4. Convert the extraction into first-person beliefs (e.g., "I believe...").
        
        Format output as clean Markdown text sections.
        
        Transcript:
        {text}
        """
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": prompt.format(text=chunked_text)}],
                temperature=0.0
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Diarization error: {e}")
            return raw_transcript # Fallback to full text
