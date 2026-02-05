# backend/routers/enhanced_ingestion.py
"""Enhanced Ingestion API endpoints.

Provides endpoints for:
- Website deep crawling (Firecrawl)
- RSS feed subscription
- Social media ingestion (Twitter, LinkedIn)
- Ingestion pipeline management
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any

from modules.auth_guard import get_current_user, verify_twin_ownership

router = APIRouter(tags=["enhanced-ingestion"])


# ============================================================================
# Request/Response Models
# ============================================================================

class WebsiteCrawlRequest(BaseModel):
    """Request for website crawling."""
    url: str
    max_pages: int = 10
    max_depth: int = 2
    include_patterns: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None


class RSSIngestRequest(BaseModel):
    """Request for RSS feed ingestion."""
    url: str
    max_entries: int = 10


class TwitterIngestRequest(BaseModel):
    """Request for Twitter profile ingestion."""
    username: str
    tweet_count: int = 20


class LinkedInIngestRequest(BaseModel):
    """Request for LinkedIn profile ingestion."""
    profile_url: Optional[str] = None
    profile_data: Optional[Dict[str, Any]] = None


class PipelineCreateRequest(BaseModel):
    """Request for creating an ingestion pipeline."""
    source_url: str
    source_type: str  # 'website', 'rss', 'twitter', 'youtube'
    schedule_hours: int = 24
    crawl_depth: int = 2
    max_pages: int = 10
    metadata: Optional[Dict[str, Any]] = None


class PipelineUpdateRequest(BaseModel):
    """Request for updating a pipeline."""
    schedule_hours: Optional[int] = None
    crawl_depth: Optional[int] = None
    max_pages: Optional[int] = None
    status: Optional[str] = None  # 'active', 'paused'


# ============================================================================
# Website Crawling Endpoints
# ============================================================================

@router.post("/ingest/website/{twin_id}")
async def crawl_website_endpoint(
    twin_id: str,
    request: WebsiteCrawlRequest,
    user=Depends(get_current_user)
):
    """
    Deep crawl a website using Firecrawl.
    
    This will:
    1. Start from the provided URL
    2. Crawl up to max_pages pages
    3. Extract content as markdown
    4. Index all content into the Twin's knowledge base
    """
    verify_twin_ownership(twin_id, user)
    
    from modules.web_crawler import crawl_website
    
    result = await crawl_website(
        url=request.url,
        twin_id=twin_id,
        max_pages=request.max_pages,
        max_depth=request.max_depth,
        include_patterns=request.include_patterns,
        exclude_patterns=request.exclude_patterns
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Crawl failed"))
    
    return result


@router.post("/ingest/website/{twin_id}/single")
async def scrape_single_page_endpoint(
    twin_id: str,
    request: WebsiteCrawlRequest,
    user=Depends(get_current_user)
):
    """
    Scrape a single page (no crawling).
    Faster than deep crawl, useful for specific pages.
    """
    verify_twin_ownership(twin_id, user)
    
    from modules.web_crawler import scrape_single_page
    
    result = await scrape_single_page(request.url)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Scrape failed"))
    
    # If successful, index the content
    if result.get("content"):
        from modules.ingestion import process_and_index_text
        from modules.health_checks import calculate_content_hash
        from modules.observability import supabase
        import uuid
        
        source_id = str(uuid.uuid4())
        content = result["content"]
        metadata = result.get("metadata", {})
        
        # Create source record
        supabase.table("sources").insert({
            "id": source_id,
            "twin_id": twin_id,
            "filename": f"Page: {metadata.get('title', request.url)[:50]}",
            "file_size": len(content),
            "content_text": content,
            "content_hash": calculate_content_hash(content),
            "status": "indexed",
            "staging_status": "live",
            "extracted_text_length": len(content)
        }).execute()
        
        num_chunks = await process_and_index_text(
            source_id, twin_id, content,
            metadata_override={
                "filename": f"Page: {metadata.get('title', 'Unknown')}",
                "type": "single_page",
                "url": request.url
            }
        )
        
        result["source_id"] = source_id
        result["chunks_indexed"] = num_chunks
    
    return result


# ============================================================================
# Social Media Endpoints
# ============================================================================

@router.post("/ingest/rss/{twin_id}")
async def ingest_rss_feed(
    twin_id: str,
    request: RSSIngestRequest,
    user=Depends(get_current_user)
):
    """
    Ingest content from an RSS/Atom feed.
    
    Useful for:
    - Blog posts
    - Newsletters
    - Podcast show notes
    """
    verify_twin_ownership(twin_id, user)
    
    from modules.social_ingestion import RSSFetcher
    
    result = await RSSFetcher.ingest_feed(
        url=request.url,
        twin_id=twin_id,
        max_entries=request.max_entries
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "RSS ingestion failed"))
    
    return result


@router.post("/ingest/twitter/{twin_id}")
async def ingest_twitter_profile(
    twin_id: str,
    request: TwitterIngestRequest,
    user=Depends(get_current_user)
):
    """
    Ingest recent tweets from a Twitter/X profile.
    
    Note: Limited by Twitter's public API restrictions.
    For full access, consider Twitter API integration.
    """
    verify_twin_ownership(twin_id, user)
    
    from modules.social_ingestion import TwitterScraper
    
    result = await TwitterScraper.ingest_user_tweets(
        username=request.username,
        twin_id=twin_id,
        count=request.tweet_count
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Twitter ingestion failed"))
    
    return result


@router.post("/ingest/linkedin/{twin_id}")
async def ingest_linkedin_profile(
    twin_id: str,
    request: LinkedInIngestRequest,
    user=Depends(get_current_user)
):
    """
    Ingest LinkedIn profile data.
    
    Due to LinkedIn's restrictions, this works best with:
    - User-provided profile export (profile_data field)
    - Public profile URL (limited data)
    
    For full LinkedIn data, recommend using LinkedIn's data export feature.
    """
    verify_twin_ownership(twin_id, user)
    
    from modules.social_ingestion import LinkedInScraper
    
    if request.profile_data:
        # User provided their own export data
        result = await LinkedInScraper.ingest_linkedin_export(
            twin_id=twin_id,
            profile_data=request.profile_data
        )
    elif request.profile_url:
        # Try to scrape public profile
        scrape_result = await LinkedInScraper.scrape_profile(request.profile_url)
        
        if not scrape_result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=f"Could not scrape LinkedIn profile: {scrape_result.get('error')}. "
                       "Consider using LinkedIn's data export feature."
            )
        
        # Convert scraped data to profile format
        profile_data = {
            "name": scrape_result.get("name", ""),
            "headline": scrape_result.get("headline", ""),
            "summary": scrape_result.get("headline", "")  # Limited data
        }
        
        result = await LinkedInScraper.ingest_linkedin_export(
            twin_id=twin_id,
            profile_data=profile_data
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Either profile_url or profile_data must be provided"
        )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "LinkedIn ingestion failed"))
    
    return result


from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel

class YoutubeIngestRequest(BaseModel):
    """Request for YouTube video ingestion."""
    url: str

from fastapi import Request

@router.post("/ingest/youtube/{twin_id}")
async def ingest_youtube_video(
    twin_id: str,
    payload: YoutubeIngestRequest,
    user=Depends(get_current_user)
):
    """
    Ingest a YouTube video (audio only).
    
    Features:
    - Audio download via yt-dlp
    - Transcription via Whisper
    - Speaker Diarization (Twin vs Guest)
    """
    # P0: Verify user has access to this twin
    verify_twin_ownership(twin_id, user)
    
    from modules.media_ingestion import MediaIngester
    
    ingester = MediaIngester(twin_id)
    result = await ingester.ingest_youtube_video(payload.url)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "YouTube ingestion failed"))
        
    return result


# ============================================================================
# Pipeline Management Endpoints
# ============================================================================

@router.post("/pipelines/{twin_id}")
async def create_pipeline(
    twin_id: str,
    request: PipelineCreateRequest,
    user=Depends(get_current_user)
):
    """
    Create an automated ingestion pipeline.
    
    The pipeline will automatically re-crawl the source
    at the specified interval (schedule_hours).
    """
    verify_twin_ownership(twin_id, user)
    
    from modules.auto_updater import PipelineManager
    
    result = PipelineManager.create_pipeline(
        twin_id=twin_id,
        source_url=request.source_url,
        source_type=request.source_type,
        schedule_hours=request.schedule_hours,
        crawl_depth=request.crawl_depth,
        max_pages=request.max_pages,
        metadata=request.metadata
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Pipeline creation failed"))
    
    return result


@router.get("/pipelines/{twin_id}")
async def list_pipelines(
    twin_id: str,
    include_paused: bool = False,
    user=Depends(get_current_user)
):
    """List all ingestion pipelines for a twin."""
    verify_twin_ownership(twin_id, user)
    
    from modules.auto_updater import PipelineManager
    
    pipelines = PipelineManager.list_pipelines(twin_id, include_paused)
    
    return {"pipelines": pipelines, "count": len(pipelines)}


@router.get("/pipelines/{twin_id}/{pipeline_id}")
async def get_pipeline(
    twin_id: str,
    pipeline_id: str,
    user=Depends(get_current_user)
):
    """Get details of a specific pipeline."""
    verify_twin_ownership(twin_id, user)
    
    from modules.auto_updater import PipelineManager
    
    pipeline = PipelineManager.get_pipeline(pipeline_id)
    
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    if pipeline.get("twin_id") != twin_id:
        raise HTTPException(status_code=403, detail="Pipeline belongs to different twin")
    
    return pipeline


@router.put("/pipelines/{twin_id}/{pipeline_id}")
async def update_pipeline(
    twin_id: str,
    pipeline_id: str,
    request: PipelineUpdateRequest,
    user=Depends(get_current_user)
):
    """Update pipeline settings."""
    verify_twin_ownership(twin_id, user)
    
    from modules.auto_updater import PipelineManager
    
    # Verify ownership
    pipeline = PipelineManager.get_pipeline(pipeline_id)
    if not pipeline or pipeline.get("twin_id") != twin_id:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    updates = {}
    if request.schedule_hours is not None:
        updates["schedule_hours"] = request.schedule_hours
    if request.crawl_depth is not None:
        updates["crawl_depth"] = request.crawl_depth
    if request.max_pages is not None:
        updates["max_pages"] = request.max_pages
    if request.status is not None:
        updates["status"] = request.status
    
    result = PipelineManager.update_pipeline(pipeline_id, updates)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Update failed"))
    
    return result


@router.delete("/pipelines/{twin_id}/{pipeline_id}")
async def delete_pipeline(
    twin_id: str,
    pipeline_id: str,
    user=Depends(get_current_user)
):
    """Delete (deactivate) a pipeline."""
    verify_twin_ownership(twin_id, user)
    
    from modules.auto_updater import PipelineManager
    
    # Verify ownership
    pipeline = PipelineManager.get_pipeline(pipeline_id)
    if not pipeline or pipeline.get("twin_id") != twin_id:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    result = PipelineManager.delete_pipeline(pipeline_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Delete failed"))
    
    return result


@router.post("/pipelines/{twin_id}/{pipeline_id}/run")
async def run_pipeline_now(
    twin_id: str,
    pipeline_id: str,
    user=Depends(get_current_user)
):
    """Manually trigger a pipeline execution."""
    verify_twin_ownership(twin_id, user)
    
    from modules.auto_updater import PipelineManager, PipelineExecutor
    
    # Verify ownership
    pipeline = PipelineManager.get_pipeline(pipeline_id)
    if not pipeline or pipeline.get("twin_id") != twin_id:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    result = await PipelineExecutor.execute_pipeline(pipeline_id)
    
    return result
