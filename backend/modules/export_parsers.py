"""
export_parsers.py

Phase 1 Component: Parsers for export uploads (Mode A).
Handles LinkedIn exports, Twitter/X archives, and other export formats.
"""

import os
import re
import json
import zipfile
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path


# =============================================================================
# LinkedIn Export Parser
# =============================================================================

class LinkedInExportParser:
    """Parse LinkedIn 'Download your data' exports."""
    
    SUPPORTED_FORMATS = {".zip", ".csv", ".html"}
    
    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Parse LinkedIn export file.
        
        Returns list of content items with metadata.
        """
        ext = Path(file_path).suffix.lower()
        
        if ext == ".zip":
            return self._parse_zip(file_path)
        elif ext == ".csv":
            return self._parse_csv(file_path)
        elif ext == ".html":
            return self._parse_html(file_path)
        else:
            raise ValueError(f"Unsupported LinkedIn export format: {ext}")
    
    def _parse_zip(self, zip_path: str) -> List[Dict[str, Any]]:
        """Parse LinkedIn ZIP export."""
        items = []
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Look for messages, posts, and profile data
            for name in zf.namelist():
                if name.endswith('.csv'):
                    content = zf.read(name).decode('utf-8', errors='ignore')
                    csv_items = self._parse_csv_content(content, filename=name)
                    items.extend(csv_items)
                
                elif name.endswith('.html') and 'messages' in name.lower():
                    content = zf.read(name).decode('utf-8', errors='ignore')
                    html_items = self._parse_html_content(content, filename=name)
                    items.extend(html_items)
        
        return items
    
    def _parse_csv(self, csv_path: str) -> List[Dict[str, Any]]:
        """Parse LinkedIn CSV export."""
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return self._parse_csv_content(content, filename=csv_path)
    
    def _parse_csv_content(self, content: str, filename: str) -> List[Dict[str, Any]]:
        """Parse CSV content."""
        items = []
        lines = content.strip().split('\n')
        
        if len(lines) < 2:
            return items
        
        # Simple CSV parsing (header + rows)
        headers = lines[0].split(',')
        
        for line in lines[1:]:
            values = line.split(',')
            row = dict(zip(headers, values))
            
            # Extract content based on column names
            text_content = ""
            timestamp = None
            
            for key, value in row.items():
                key_lower = key.lower()
                if any(k in key_lower for k in ['content', 'message', 'body', 'text']):
                    text_content = value.strip('"')
                elif any(k in key_lower for k in ['date', 'timestamp', 'created']):
                    try:
                        timestamp = datetime.fromisoformat(value.strip('"'))
                    except:
                        pass
            
            if text_content:
                items.append({
                    "content": text_content,
                    "source_type": "linkedin_export",
                    "source_file": filename,
                    "timestamp": timestamp.isoformat() if timestamp else None,
                    "metadata": row,
                })
        
        return items
    
    def _parse_html(self, html_path: str) -> List[Dict[str, Any]]:
        """Parse LinkedIn HTML export."""
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return self._parse_html_content(content, filename=html_path)
    
    def _parse_html_content(self, content: str, filename: str) -> List[Dict[str, Any]]:
        """Parse HTML content (simplified)."""
        items = []
        
        # Simple regex extraction for message-like content
        # This is a basic implementation - production would use BeautifulSoup
        text_pattern = r'<p[^>]*>(.*?)</p>'
        matches = re.findall(text_pattern, content, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            # Clean HTML tags
            clean_text = re.sub(r'<[^>]+>', '', match)
            clean_text = clean_text.strip()
            
            if len(clean_text) > 20:  # Filter short fragments
                items.append({
                    "content": clean_text,
                    "source_type": "linkedin_export",
                    "source_file": filename,
                    "timestamp": None,
                    "metadata": {},
                })
        
        return items


# =============================================================================
# Twitter/X Archive Parser
# =============================================================================

class TwitterArchiveParser:
    """Parse Twitter/X archive exports (tweets.js format)."""
    
    def parse(self, archive_path: str) -> List[Dict[str, Any]]:
        """
        Parse Twitter/X ZIP archive.
        
        Returns list of tweets with metadata.
        """
        items = []
        
        with zipfile.ZipFile(archive_path, 'r') as zf:
            # Look for tweets.js or tweets.json
            tweet_files = [n for n in zf.namelist() 
                          if 'tweet' in n.lower() and (n.endswith('.js') or n.endswith('.json'))]
            
            for tweet_file in tweet_files:
                content = zf.read(tweet_file).decode('utf-8', errors='ignore')
                tweets = self._parse_tweets_js(content)
                items.extend(tweets)
        
        return items
    
    def _parse_tweets_js(self, content: str) -> List[Dict[str, Any]]:
        """Parse tweets.js content."""
        items = []
        
        # Twitter archives often have "window.YTD.tweets.part0 = [ ... ]" format
        # Try to extract JSON array
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        
        if json_match:
            try:
                tweets = json.loads(json_match.group())
            except json.JSONDecodeError:
                # Try without the window assignment
                try:
                    tweets = json.loads(content)
                except:
                    return items
        else:
            try:
                tweets = json.loads(content)
            except:
                return items
        
        for tweet_data in tweets:
            # Handle different archive formats
            if isinstance(tweet_data, dict):
                tweet = tweet_data.get('tweet', tweet_data)
                
                text = tweet.get('full_text') or tweet.get('text', '')
                created_at = tweet.get('created_at')
                tweet_id = tweet.get('id_str') or tweet.get('id')
                
                if text:
                    items.append({
                        "content": text,
                        "source_type": "twitter_archive",
                        "source_id": tweet_id,
                        "timestamp": self._parse_twitter_date(created_at),
                        "metadata": {
                            "retweet_count": tweet.get('retweet_count', 0),
                            "favorite_count": tweet.get('favorite_count', 0),
                        },
                    })
        
        return items
    
    def _parse_twitter_date(self, date_str: Optional[str]) -> Optional[str]:
        """Parse Twitter date format."""
        if not date_str:
            return None
        
        try:
            # Twitter format: "Mon Sep 01 12:00:00 +0000 2020"
            dt = datetime.strptime(date_str, '%a %b %d %H:%M:%S +0000 %Y')
            return dt.isoformat()
        except:
            return None


# =============================================================================
# Slack Export Parser
# =============================================================================

class SlackExportParser:
    """Parse Slack export JSON files."""
    
    def parse(self, export_path: str) -> List[Dict[str, Any]]:
        """Parse Slack export (ZIP or directory)."""
        items = []
        
        if zipfile.is_zipfile(export_path):
            with zipfile.ZipFile(export_path, 'r') as zf:
                json_files = [n for n in zf.namelist() if n.endswith('.json')]
                
                for json_file in json_files:
                    if 'channel' in json_file.lower() or 'messages' in json_file.lower():
                        content = zf.read(json_file).decode('utf-8', errors='ignore')
                        messages = self._parse_slack_json(content, json_file)
                        items.extend(messages)
        
        return items
    
    def _parse_slack_json(self, content: str, filename: str) -> List[Dict[str, Any]]:
        """Parse Slack JSON messages."""
        items = []
        
        try:
            messages = json.loads(content)
            
            if not isinstance(messages, list):
                return items
            
            for msg in messages:
                text = msg.get('text', '')
                user = msg.get('user', 'unknown')
                ts = msg.get('ts')
                
                # Skip system messages
                if msg.get('subtype') in ['channel_join', 'channel_leave', 'bot_message']:
                    continue
                
                if text and not text.startswith('<'):  # Skip command-like messages
                    # Convert timestamp
                    timestamp = None
                    if ts:
                        try:
                            timestamp = datetime.fromtimestamp(float(ts)).isoformat()
                        except:
                            pass
                    
                    items.append({
                        "content": text,
                        "source_type": "slack_export",
                        "source_file": filename,
                        "timestamp": timestamp,
                        "metadata": {
                            "user": user,
                            "channel": filename.split('/')[-2] if '/' in filename else 'unknown',
                        },
                    })
        
        except json.JSONDecodeError:
            pass
        
        return items


# =============================================================================
# Generic HTML Parser
# =============================================================================

class HTMLContentParser:
    """Parse generic HTML content."""
    
    def parse(self, html_path: str) -> List[Dict[str, Any]]:
        """Parse HTML file and extract readable text."""
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return self._extract_text_from_html(content, html_path)
    
    def _extract_text_from_html(self, html: str, source: str) -> List[Dict[str, Any]]:
        """Extract readable text blocks from HTML."""
        items = []
        
        # Remove script and style tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Extract text from common content tags
        content_tags = ['p', 'div', 'article', 'section', 'li', 'h1', 'h2', 'h3', 'h4']
        
        for tag in content_tags:
            pattern = f'<{tag}[^>]*>(.*?)</{tag}>'
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                # Clean HTML
                text = re.sub(r'<[^>]+>', '', match)
                text = text.strip()
                
                # Filter meaningful content
                if len(text) > 50 and not text.startswith('http'):
                    items.append({
                        "content": text,
                        "source_type": "html_export",
                        "source_file": source,
                        "timestamp": None,
                        "metadata": {"tag": tag},
                    })
        
        return items


# =============================================================================
# Main Parser Factory
# =============================================================================

def parse_export_file(file_path: str, source_hint: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parse an export file based on format.
    
    Args:
        file_path: Path to export file
        source_hint: Optional hint ('linkedin', 'twitter', 'slack')
    
    Returns:
        List of content items with metadata
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    filename = path.name.lower()
    
    # Auto-detect source type
    if source_hint == 'linkedin' or 'linkedin' in filename:
        parser = LinkedInExportParser()
    elif source_hint == 'twitter' or any(x in filename for x in ['twitter', 'tweet', 'x_archive']):
        parser = TwitterArchiveParser()
    elif source_hint == 'slack' or 'slack' in filename:
        parser = SlackExportParser()
    elif ext == '.html' or ext == '.htm':
        parser = HTMLContentParser()
    else:
        # Default to HTML parser
        parser = HTMLContentParser()
    
    return parser.parse(file_path)


# =============================================================================
# Content Aggregation
# =============================================================================

def aggregate_export_content(file_paths: List[str], twin_id: str) -> Dict[str, Any]:
    """
    Aggregate content from multiple export files.
    
    Returns:
        {
            "total_items": int,
            "sources": List[str],
            "content_text": str,  # Combined text for processing
            "items": List[Dict],  # Individual items with metadata
        }
    """
    all_items = []
    sources = []
    
    for file_path in file_paths:
        try:
            items = parse_export_file(file_path)
            all_items.extend(items)
            sources.append(file_path)
        except Exception as e:
            print(f"[ExportParser] Error parsing {file_path}: {e}")
    
    # Combine content text
    content_parts = []
    for item in all_items:
        content_parts.append(f"[{item['source_type']}] {item['content']}")
    
    return {
        "total_items": len(all_items),
        "sources": sources,
        "content_text": "\n\n".join(content_parts),
        "items": all_items,
        "twin_id": twin_id,
    }
