"""
Dumpling AI Client Module
==========================

Integration with Dumpling AI API for:
- YouTube transcript extraction
- Web page scraping
- Document text extraction
"""

import os
import httpx
from typing import Optional, Dict, Any
from urllib.parse import urlparse


DUMPLING_API_BASE = "https://app.dumplingai.com/api/v1"


def get_dumpling_api_key() -> str:
    """Get Dumpling AI API key from environment."""
    key = os.getenv("DUMPLING_API_KEY", "").strip()
    if not key:
        raise ValueError("DUMPLING_API_KEY environment variable not set")
    return key


def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube video URL."""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    return (
        hostname in ("youtube.com", "www.youtube.com", "youtu.be", "www.youtu.be")
        or hostname.endswith(".youtube.com")
    )


def extract_youtube_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL."""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    
    if hostname in ("youtu.be", "www.youtu.be"):
        # Short URL format: youtu.be/VIDEO_ID
        return parsed.path.lstrip("/").split("/")[0]
    
    if "youtube.com" in hostname:
        # Standard format: youtube.com/watch?v=VIDEO_ID
        from urllib.parse import parse_qs
        query_params = parse_qs(parsed.query)
        if "v" in query_params:
            return query_params["v"][0]
        
        # Shorts format: youtube.com/shorts/VIDEO_ID
        if "/shorts/" in parsed.path:
            return parsed.path.split("/shorts/")[1].split("/")[0]
        
        # Live format: youtube.com/live/VIDEO_ID
        if "/live/" in parsed.path:
            return parsed.path.split("/live/")[1].split("/")[0]
    
    return None


async def get_youtube_transcript(
    video_url: str,
    include_timestamps: bool = True,
    timestamps_to_combine: int = 5,
    preferred_language: str = "en",
) -> Dict[str, Any]:
    """
    Extract transcript from a YouTube video using Dumpling AI.
    
    Args:
        video_url: YouTube video URL
        include_timestamps: Whether to include timestamps in transcript
        timestamps_to_combine: Number of timestamps to combine
        preferred_language: Preferred language code (e.g., "en")
    
    Returns:
        Dict with "transcript" and "language" keys
    
    Raises:
        ValueError: If transcript cannot be extracted
        httpx.HTTPError: If API request fails
    """
    api_key = get_dumpling_api_key()
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    payload = {
        "videoUrl": video_url,
        "includeTimestamps": include_timestamps,
        "timestampsToCombine": timestamps_to_combine,
        "preferredLanguage": preferred_language,
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{DUMPLING_API_BASE}/get-youtube-transcript",
            headers=headers,
            json=payload,
        )
        
        if response.status_code == 404:
            data = response.json()
            raise ValueError(data.get("error", "No subtitles found for this video"))
        
        if response.status_code == 400:
            data = response.json()
            raise ValueError(data.get("error", "Invalid request"))
        
        response.raise_for_status()
        return response.json()


async def scrape_webpage(
    url: str,
    format: str = "markdown",
    cleaned: bool = True,
    render_js: bool = True,
) -> Dict[str, Any]:
    """
    Scrape content from a web page using Dumpling AI.
    
    Args:
        url: Web page URL
        format: Output format ("markdown", "html", "text")
        cleaned: Whether to clean the output
        render_js: Whether to render JavaScript
    
    Returns:
        Dict with scraped content
    """
    api_key = get_dumpling_api_key()
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    payload = {
        "url": url,
        "format": format,
        "cleaned": cleaned,
        "renderJs": render_js,
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{DUMPLING_API_BASE}/scrape",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def extract_webpage_data(
    url: str,
    instructions: str,
    schema: Optional[Dict[str, Any]] = None,
    render_js: bool = True,
) -> Dict[str, Any]:
    """
    Extract structured data from a web page using AI-powered extraction.
    
    Args:
        url: Web page URL
        instructions: Natural language instructions for extraction
        schema: Optional JSON schema for structured output
        render_js: Whether to render JavaScript
    
    Returns:
        Dict with extracted structured data
    """
    api_key = get_dumpling_api_key()
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    payload = {
        "url": url,
        "instructions": instructions,
        "renderJs": render_js,
    }
    
    if schema:
        payload["schema"] = schema
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{DUMPLING_API_BASE}/extract",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def doc_to_text(
    url: str,
    ocr: bool = True,
    language: str = "en",
) -> Dict[str, Any]:
    """
    Convert a document (PDF, DOCX, etc.) to text using Dumpling AI.
    
    Args:
        url: Document URL
        ocr: Whether to use OCR for images/scanned documents
        language: Document language
    
    Returns:
        Dict with extracted text
    """
    api_key = get_dumpling_api_key()
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    payload = {
        "url": url,
        "options": {
            "ocr": ocr,
            "language": language,
        },
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{DUMPLING_API_BASE}/doc-to-text",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()
