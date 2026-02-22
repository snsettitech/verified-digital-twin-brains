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


async def get_linkedin_profile(
    url: str,
) -> Dict[str, Any]:
    """
    Extract comprehensive LinkedIn profile information using Dumpling AI.
    
    This endpoint retrieves public profile information including:
    - Name, image, location, followers, connections
    - About/summary section
    - Recent posts
    - Experience history
    - Education
    - Activity (likes, comments, shares)
    - Articles published
    - Projects
    - Recommendations received
    
    Args:
        url: LinkedIn profile URL (e.g., "https://www.linkedin.com/in/username")
    
    Returns:
        Dict with comprehensive profile data:
        {
            "success": true,
            "name": "Full Name",
            "image": "profile_image_url",
            "location": "City, State, Country",
            "followers": 12847,
            "connections": "500+",
            "about": "Profile summary...",
            "recentPosts": [...],
            "experience": [...],
            "education": [...],
            "activity": [...],
            "articles": [...],
            "projects": [...],
            "recommendations": [...]
        }
    
    Raises:
        ValueError: If URL is not a valid LinkedIn profile URL
        httpx.HTTPError: If API request fails (502 if LinkedIn blocks, 500 for server errors)
    """
    api_key = get_dumpling_api_key()
    
    # Validate URL
    if not url or "linkedin.com/in/" not in url:
        raise ValueError("URL must be a valid LinkedIn profile URL (contains 'linkedin.com/in/')")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    payload = {
        "url": url,
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{DUMPLING_API_BASE}/linkedin/profile",
            headers=headers,
            json=payload,
        )
        
        if response.status_code == 400:
            data = response.json()
            raise ValueError(data.get("error", "Invalid LinkedIn profile URL"))
        
        if response.status_code == 502:
            data = response.json()
            raise ValueError(data.get("error", "LinkedIn profile unavailable or blocked"))
        
        response.raise_for_status()
        return response.json()


def format_linkedin_profile_for_ingestion(profile: Dict[str, Any], url: str) -> str:
    """
    Format a LinkedIn profile into a structured text document for ingestion.
    
    Args:
        profile: The profile data from get_linkedin_profile()
        url: The original LinkedIn profile URL
    
    Returns:
        Formatted text document ready for chunking and indexing
    """
    lines = []
    
    # Header
    name = profile.get("name", "LinkedIn Profile")
    lines.append(f"# LinkedIn Profile: {name}")
    lines.append(f"URL: {url}")
    lines.append("")
    
    # Basic Info
    location = profile.get("location")
    if location:
        lines.append(f"Location: {location}")
    
    followers = profile.get("followers")
    if followers:
        lines.append(f"Followers: {followers}")
    
    connections = profile.get("connections")
    if connections:
        lines.append(f"Connections: {connections}")
    
    lines.append("")
    
    # About/Summary
    about = profile.get("about")
    if about:
        lines.append("## About")
        lines.append(about)
        lines.append("")
    
    # Experience
    experience = profile.get("experience", [])
    if experience:
        lines.append("## Experience")
        for exp in experience:
            org_name = exp.get("name", "Unknown Company")
            org_url = exp.get("url", "")
            location = exp.get("location", "")
            member = exp.get("member", {})
            role_desc = member.get("description", "") if isinstance(member, dict) else ""
            
            lines.append(f"### {org_name}")
            if location:
                lines.append(f"Location: {location}")
            if role_desc:
                lines.append(role_desc)
            lines.append("")
    
    # Education
    education = profile.get("education", [])
    if education:
        lines.append("## Education")
        for edu in education:
            org_name = edu.get("name", "Unknown Institution")
            org_url = edu.get("url", "")
            member = edu.get("member", {})
            if isinstance(member, dict):
                start_date = member.get("startDate", "")
                end_date = member.get("endDate", "Present")
                date_range = f"{start_date} - {end_date}" if start_date else ""
            else:
                date_range = ""
            
            lines.append(f"- {org_name}" + (f" ({date_range})" if date_range else ""))
        lines.append("")
    
    # Recent Posts
    recent_posts = profile.get("recentPosts", [])
    if recent_posts:
        lines.append("## Recent Posts")
        for post in recent_posts[:10]:  # Limit to 10 recent posts
            title = post.get("title", "")
            activity_type = post.get("activityType", "")
            if title:
                lines.append(f"- [{activity_type}] {title}")
        lines.append("")
    
    # Articles
    articles = profile.get("articles", [])
    if articles:
        lines.append("## Published Articles")
        for article in articles[:5]:  # Limit to 5 articles
            headline = article.get("headline", "")
            date = article.get("datePublished", "")
            body = article.get("articleBody", "")
            if headline:
                lines.append(f"### {headline}")
                if date:
                    lines.append(f"Published: {date[:10]}")
                if body:
                    # Truncate long articles
                    body_preview = body[:500] + "..." if len(body) > 500 else body
                    lines.append(body_preview)
                lines.append("")
    
    # Projects
    projects = profile.get("projects", [])
    if projects:
        lines.append("## Projects")
        for project in projects:
            proj_name = project.get("name", "")
            proj_url = project.get("url", "")
            proj_desc = project.get("description", "")
            date_range = project.get("dateRange", "")
            
            if proj_name:
                lines.append(f"### {proj_name}")
                if date_range:
                    lines.append(f"Date: {date_range}")
                if proj_desc:
                    lines.append(proj_desc)
                lines.append("")
    
    # Recommendations
    recommendations = profile.get("recommendations", [])
    if recommendations:
        lines.append("## Recommendations")
        for rec in recommendations[:5]:  # Limit to 5 recommendations
            rec_name = rec.get("name", "")
            rec_text = rec.get("text", "")
            if rec_name and rec_text:
                lines.append(f"> \"{rec_text}\"")
                lines.append(f"> — {rec_name}")
                lines.append("")
    
    return "\n".join(lines)


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
