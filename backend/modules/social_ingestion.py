# backend/modules/social_ingestion.py
"""Social Media Ingestion: Extract content from LinkedIn, Twitter/X, and RSS feeds.

Provides functions to ingest user's social media presence for Twin training.
Uses existing twikit for Twitter and adds LinkedIn scraping.
"""

import os
import re
import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

import feedparser

from modules.observability import supabase, log_ingestion_event
from modules.health_checks import calculate_content_hash
from modules.governance import AuditLogger

logger = logging.getLogger(__name__)


class RSSFetcher:
    """Fetch and parse RSS/Atom feeds for content ingestion."""
    
    @staticmethod
    async def fetch_feed(url: str, max_entries: int = 10) -> Dict[str, Any]:
        """
        Fetch and parse an RSS/Atom feed.
        
        Args:
            url: Feed URL
            max_entries: Maximum number of entries to return
        
        Returns:
            Dict with feed info and entries
        """
        try:
            feed = feedparser.parse(url)
            
            if feed.bozo and not feed.entries:
                return {
                    "success": False,
                    "error": f"Invalid feed: {feed.bozo_exception}"
                }
            
            entries = []
            for entry in feed.entries[:max_entries]:
                # Extract content
                content = ""
                if hasattr(entry, 'content'):
                    content = entry.content[0].value if entry.content else ""
                elif hasattr(entry, 'summary'):
                    content = entry.summary
                elif hasattr(entry, 'description'):
                    content = entry.description
                
                # Clean HTML tags for plain text
                clean_content = re.sub(r'<[^>]+>', '', content)
                
                entries.append({
                    "title": getattr(entry, 'title', 'Untitled'),
                    "link": getattr(entry, 'link', ''),
                    "published": getattr(entry, 'published', ''),
                    "content": clean_content,
                    "author": getattr(entry, 'author', '')
                })
            
            return {
                "success": True,
                "feed_title": feed.feed.get('title', 'Unknown Feed'),
                "feed_link": feed.feed.get('link', url),
                "entries": entries,
                "entry_count": len(entries)
            }
            
        except Exception as e:
            logger.error(f"Error fetching RSS feed {url}: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def ingest_feed(
        url: str,
        twin_id: str,
        max_entries: int = 10,
        source_id: str = None
    ) -> Dict[str, Any]:
        """
        Ingest an RSS feed into a Twin's knowledge base.
        
        Args:
            url: Feed URL
            twin_id: Twin ID
            max_entries: Maximum entries to ingest
            source_id: Optional source ID
        
        Returns:
            Dict with ingestion results
        """
        if not source_id:
            source_id = str(uuid.uuid4())
        
        # Fetch feed
        feed_data = await RSSFetcher.fetch_feed(url, max_entries)
        
        if not feed_data.get("success"):
            return feed_data
        
        try:
            # Create source record
            feed_title = feed_data.get("feed_title", "RSS Feed")
            
            supabase.table("sources").insert({
                "id": source_id,
                "twin_id": twin_id,
                "filename": f"RSS: {feed_title}",
                "file_size": 0,
                "content_text": "",
                "status": "processing",
                "staging_status": "processing"
            }).execute()
            
            log_ingestion_event(source_id, twin_id, "info", f"Ingesting RSS feed: {feed_title}")
            
            # Combine entries into content
            content_parts = []
            for entry in feed_data.get("entries", []):
                entry_text = f"## {entry['title']}\n\n"
                if entry.get('published'):
                    entry_text += f"*Published: {entry['published']}*\n\n"
                entry_text += entry.get('content', '')
                content_parts.append(entry_text)
            
            combined_content = "\n\n---\n\n".join(content_parts)
            content_hash = calculate_content_hash(combined_content)
            
            # Update source
            supabase.table("sources").update({
                "content_text": combined_content,
                "content_hash": content_hash,
                "file_size": len(combined_content),
                "status": "indexed",
                "staging_status": "approved",
                "extracted_text_length": len(combined_content)
            }).eq("id", source_id).execute()
            
            # Index content
            from modules.ingestion import process_and_index_text
            num_chunks = await process_and_index_text(
                source_id, twin_id, combined_content,
                metadata_override={
                    "filename": f"RSS: {feed_title}",
                    "type": "rss_feed",
                    "feed_url": url,
                    "entry_count": len(feed_data.get("entries", []))
                }
            )
            
            log_ingestion_event(
                source_id, twin_id, "info",
                f"RSS feed indexed: {num_chunks} chunks from {len(feed_data.get('entries', []))} entries"
            )
            
            # Fetch tenant_id
            tenant_id = None
            try:
                res = supabase.table("twins").select("tenant_id").eq("id", twin_id).single().execute()
                tenant_id = res.data.get("tenant_id") if res.data else None
            except Exception:
                pass

            # Audit log
            AuditLogger.log(
                tenant_id=tenant_id,
                twin_id=twin_id, 
                event_type="KNOWLEDGE_UPDATE", 
                action="SOURCE_INDEXED",
                metadata={
                    "source_id": source_id,
                    "filename": f"RSS: {feed_title}",
                    "type": "rss_feed",
                    "chunks": num_chunks
                }
            )

            
            return {
                "success": True,
                "source_id": source_id,
                "feed_title": feed_title,
                "entries_ingested": len(feed_data.get("entries", [])),
                "chunks_indexed": num_chunks,
                "total_content_length": len(combined_content)
            }
            
        except Exception as e:
            logger.error(f"Error ingesting RSS feed {url}: {e}")
            
            try:
                supabase.table("sources").update({
                    "status": "error",
                    "health_status": "failed"
                }).eq("id", source_id).execute()
                
                log_ingestion_event(source_id, twin_id, "error", f"RSS ingestion failed: {e}")
            except Exception:
                pass
            
            return {"success": False, "error": str(e), "source_id": source_id}


class LinkedInScraper:
    """
    LinkedIn profile scraper using public data.
    
    Note: LinkedIn aggressively blocks scraping. This implementation
    uses the public profile endpoint which may have limitations.
    For production, consider:
    - LinkedIn API (requires partnership)
    - Proxycurl or similar services
    - User-provided profile export
    """
    
    @staticmethod
    async def scrape_profile(linkedin_url: str) -> Dict[str, Any]:
        """
        Attempt to scrape a LinkedIn profile.
        
        Due to LinkedIn's restrictions, this uses a combination of:
        1. Public profile page (limited data)
        2. User can provide their own profile data
        
        Args:
            linkedin_url: LinkedIn profile URL
        
        Returns:
            Dict with profile data or error
        """
        # Validate URL
        if 'linkedin.com' not in linkedin_url:
            return {"success": False, "error": "Invalid LinkedIn URL"}
        
        try:
            import httpx
            
            # Try fetching public profile
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(linkedin_url, headers=headers, follow_redirects=True)
                
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"LinkedIn returned status {response.status_code}. Profile may be private or LinkedIn is blocking access."
                    }
                
                html = response.text
                
                # Extract basic info from meta tags (more reliable than parsing)
                title_match = re.search(r'<title>([^<]+)</title>', html)
                description_match = re.search(r'<meta name="description" content="([^"]+)"', html)
                
                name = ""
                if title_match:
                    # LinkedIn titles are usually "Name - Title | LinkedIn"
                    title = title_match.group(1)
                    name = title.split(' - ')[0].strip() if ' - ' in title else title.split(' | ')[0].strip()
                
                description = ""
                if description_match:
                    description = description_match.group(1)
                
                if not name and not description:
                    return {
                        "success": False,
                        "error": "Could not extract profile data. LinkedIn may be blocking access."
                    }
                
                return {
                    "success": True,
                    "name": name,
                    "headline": description,
                    "profile_url": linkedin_url,
                    "note": "Limited data available from public profile. For full profile, use LinkedIn data export."
                }
                
        except Exception as e:
            logger.error(f"Error scraping LinkedIn profile: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def ingest_linkedin_export(
        twin_id: str,
        profile_data: Dict[str, Any],
        source_id: str = None
    ) -> Dict[str, Any]:
        """
        Ingest LinkedIn profile from user-provided export data.
        
        LinkedIn allows users to export their data, which includes:
        - Profile summary
        - Positions
        - Education
        - Skills
        - Recommendations
        
        Args:
            twin_id: Twin ID
            profile_data: Dict with LinkedIn export data
            source_id: Optional source ID
        
        Returns:
            Dict with ingestion results
        """
        if not source_id:
            source_id = str(uuid.uuid4())
        
        try:
            # Build content from profile data
            content_parts = []
            
            name = profile_data.get('name', 'Unknown')
            
            # Summary
            if profile_data.get('summary'):
                content_parts.append(f"## About {name}\n\n{profile_data['summary']}")
            
            # Headline
            if profile_data.get('headline'):
                content_parts.append(f"**Current Role:** {profile_data['headline']}")
            
            # Positions
            if profile_data.get('positions'):
                positions_text = "## Experience\n\n"
                for pos in profile_data['positions']:
                    positions_text += f"### {pos.get('title', 'Role')} at {pos.get('company', 'Company')}\n"
                    if pos.get('dates'):
                        positions_text += f"*{pos['dates']}*\n\n"
                    if pos.get('description'):
                        positions_text += f"{pos['description']}\n\n"
                content_parts.append(positions_text)
            
            # Skills
            if profile_data.get('skills'):
                skills_text = "## Skills\n\n" + ", ".join(profile_data['skills'])
                content_parts.append(skills_text)
            
            combined_content = "\n\n".join(content_parts)
            
            if not combined_content:
                return {"success": False, "error": "No content to ingest from profile data"}
            
            # Create source
            supabase.table("sources").insert({
                "id": source_id,
                "twin_id": twin_id,
                "filename": f"LinkedIn: {name}",
                "file_size": len(combined_content),
                "content_text": combined_content,
                "content_hash": calculate_content_hash(combined_content),
                "status": "indexed",
                "staging_status": "approved",
                "extracted_text_length": len(combined_content)
            }).execute()
            
            # Index
            from modules.ingestion import process_and_index_text
            num_chunks = await process_and_index_text(
                source_id, twin_id, combined_content,
                metadata_override={
                    "filename": f"LinkedIn: {name}",
                    "type": "linkedin_profile",
                    "profile_name": name
                }
            )
            
            log_ingestion_event(
                source_id, twin_id, "info",
                f"LinkedIn profile indexed: {num_chunks} chunks"
            )
            
            return {
                "success": True,
                "source_id": source_id,
                "profile_name": name,
                "chunks_indexed": num_chunks,
                "content_length": len(combined_content)
            }
            
        except Exception as e:
            logger.error(f"Error ingesting LinkedIn export: {e}")
            return {"success": False, "error": str(e)}


class TwitterScraper:
    """
    Twitter/X content scraper.
    
    Uses the existing twikit integration for thread scraping.
    This class extends it with profile-level ingestion.
    """
    
    @staticmethod
    async def get_user_tweets(username: str, count: int = 20) -> Dict[str, Any]:
        """
        Get recent tweets from a user.
        
        Note: Twitter API access is increasingly restricted.
        This uses the syndication endpoint as a fallback.
        
        Args:
            username: Twitter username (without @)
            count: Number of tweets to fetch
        
        Returns:
            Dict with tweets or error
        """
        try:
            import httpx
            
            # Use syndication timeline (limited but doesn't require auth)
            syndication_url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(syndication_url)
                
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Could not fetch tweets. Status: {response.status_code}"
                    }
                
                html = response.text
                
                # Extract tweet texts from the HTML response
                # This is a simplified extraction
                tweet_texts = re.findall(r'<p[^>]*class="[^"]*timeline-Tweet-text[^"]*"[^>]*>([^<]+)</p>', html)
                
                if not tweet_texts:
                    # Try alternate pattern
                    tweet_texts = re.findall(r'"text":"([^"]+)"', html)
                
                return {
                    "success": True,
                    "username": username,
                    "tweets": tweet_texts[:count],
                    "count": len(tweet_texts[:count])
                }
                
        except Exception as e:
            logger.error(f"Error fetching tweets for {username}: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def ingest_user_tweets(
        username: str,
        twin_id: str,
        count: int = 20,
        source_id: str = None
    ) -> Dict[str, Any]:
        """
        Ingest a user's recent tweets into their Twin.
        
        Args:
            username: Twitter username
            twin_id: Twin ID
            count: Number of tweets to ingest
            source_id: Optional source ID
        
        Returns:
            Dict with ingestion results
        """
        if not source_id:
            source_id = str(uuid.uuid4())
        
        tweet_data = await TwitterScraper.get_user_tweets(username, count)
        
        if not tweet_data.get("success"):
            return tweet_data
        
        tweets = tweet_data.get("tweets", [])
        
        if not tweets:
            return {"success": False, "error": "No tweets found"}
        
        try:
            # Combine tweets
            combined_content = f"# Tweets by @{username}\n\n"
            for i, tweet in enumerate(tweets, 1):
                combined_content += f"## Tweet {i}\n{tweet}\n\n"
            
            # Create source
            supabase.table("sources").insert({
                "id": source_id,
                "twin_id": twin_id,
                "filename": f"Twitter: @{username}",
                "file_size": len(combined_content),
                "content_text": combined_content,
                "content_hash": calculate_content_hash(combined_content),
                "status": "indexed",
                "staging_status": "approved",
                "extracted_text_length": len(combined_content)
            }).execute()
            
            # Index
            from modules.ingestion import process_and_index_text
            num_chunks = await process_and_index_text(
                source_id, twin_id, combined_content,
                metadata_override={
                    "filename": f"Twitter: @{username}",
                    "type": "twitter_profile",
                    "username": username,
                    "tweet_count": len(tweets)
                }
            )
            
            log_ingestion_event(
                source_id, twin_id, "info",
                f"Twitter profile indexed: {num_chunks} chunks from {len(tweets)} tweets"
            )
            
            return {
                "success": True,
                "source_id": source_id,
                "username": username,
                "tweets_ingested": len(tweets),
                "chunks_indexed": num_chunks
            }
            
        except Exception as e:
            logger.error(f"Error ingesting Twitter profile: {e}")
            return {"success": False, "error": str(e)}
