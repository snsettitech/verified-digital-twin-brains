"""
Person Completeness Pipeline - Stage 3: Timeline Builder

Builds timeline events from temporal claims.
"""

import hashlib
import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from dateutil import parser as date_parser

from modules.observability import supabase
from modules.person_completeness_config import TimelineBuilderConfig

logger = logging.getLogger(__name__)


@dataclass
class TimelineBuilderResult:
    success: bool
    events_created: int = 0
    events_merged: int = 0
    conflicts_flagged: int = 0
    error_message: Optional[str] = None

    @property
    def item_count(self) -> int:
        """Compatibility count for pipeline metrics."""
        return self.events_created


class TimelineBuilder:
    """Builds timeline from temporal claims."""
    
    def __init__(self, config: Optional[TimelineBuilderConfig] = None):
        self.config = config or TimelineBuilderConfig()
    
    async def run(self, twin_id: str, research_run_id: Optional[str] = None) -> TimelineBuilderResult:
        try:
            logger.info(f"Building timeline for twin {twin_id}")
            
            # Get temporal claims
            claims = await self._get_temporal_claims(twin_id)
            
            events_created = 0
            events_merged = 0
            conflicts_flagged = 0
            seen_fingerprints: set = set()
            
            for claim in claims:
                try:
                    # Convert claim to timeline event
                    event = self._claim_to_event(claim)
                    if not event:
                        continue
                    
                    # Check for duplicates
                    fingerprint = self._compute_event_fingerprint(event)
                    if fingerprint in seen_fingerprints:
                        events_merged += 1
                        continue
                    
                    # Check for conflicts
                    conflict = await self._check_for_conflict(twin_id, event)
                    if conflict:
                        conflicts_flagged += 1
                    
                    # Store event
                    await self._store_event(twin_id, event, fingerprint, claim["id"])
                    seen_fingerprints.add(fingerprint)
                    events_created += 1
                
                except Exception as e:
                    logger.warning(f"Error processing claim {claim.get('id')}: {e}")
                    continue
            
            logger.info(f"Timeline built: {events_created} events, {events_merged} merged, {conflicts_flagged} conflicts")
            return TimelineBuilderResult(
                success=True,
                events_created=events_created,
                events_merged=events_merged,
                conflicts_flagged=conflicts_flagged
            )
        
        except Exception as e:
            logger.exception(f"Error building timeline: {e}")
            return TimelineBuilderResult(success=False, error_message=str(e))
    
    async def _get_temporal_claims(self, twin_id: str) -> List[Dict]:
        """Get claims with temporal information."""
        try:
            # Get work_experience and education claims
            response = supabase.table("person_claims") \
                .select("*") \
                .eq("twin_id", twin_id) \
                .eq("is_active", True) \
                .in_("claim_type", ["work_experience", "education", "project", "timeline_event"]) \
                .execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching claims: {e}")
            return []
    
    def _claim_to_event(self, claim: Dict) -> Optional[Dict]:
        """Convert claim to timeline event."""
        claim_text = claim.get("claim_text", "")
        
        # Detect event type
        event_type = self._detect_event_type(claim.get("claim_type", ""), claim_text)
        
        # Extract dates
        start_date, start_precision = self._extract_date(claim.get("claim_time_start"))
        end_date, end_precision = self._extract_date(claim.get("claim_time_end"))
        
        # If no explicit dates, try to extract from text
        if not start_date:
            start_date, start_precision = self._extract_date_from_text(claim_text)
        
        if not start_date and not end_date:
            return None  # No temporal info
        
        # Extract organization and role
        org, role = self._extract_org_and_role(claim_text)
        
        return {
            "event_type": event_type,
            "title": role or claim_text[:100],
            "description": claim_text[:500],
            "start_date": start_date,
            "start_date_precision": start_precision or "approximate",
            "end_date": end_date,
            "end_date_precision": end_precision,
            "organization": org,
            "role_title": role,
            "confidence": claim.get("extraction_confidence", 0.5),
            "derived_from_claim_ids": [claim["id"]],
        }
    
    def _detect_event_type(self, claim_type: str, text: str) -> str:
        """Detect event type from claim."""
        text_lower = text.lower()
        
        if claim_type == "education" or "degree" in text_lower or "studied" in text_lower:
            return "education_start"
        elif claim_type == "project":
            return "project_start"
        elif "founded" in text_lower or "started" in text_lower or "co-founded" in text_lower:
            return "founded_company"
        elif "award" in text_lower or "won" in text_lower:
            return "award"
        elif "published" in text_lower or "paper" in text_lower:
            return "publication"
        else:
            return "job_start"
    
    def _extract_date(self, date_str: Optional[str]) -> tuple:
        """Extract date and precision from string."""
        if not date_str:
            return None, None
        
        try:
            # Try full ISO date
            dt = date_parser.parse(date_str)
            return dt.strftime("%Y-%m-%d"), "day"
        except:
            pass
        
        # Try year only
        year_match = re.search(r'\b(19|20)\d{2}\b', str(date_str))
        if year_match:
            return f"{year_match.group()}-01-01", "year"
        
        return None, None
    
    def _extract_date_from_text(self, text: str) -> tuple:
        """Try to extract date from claim text."""
        # Look for patterns like "in 2020", "since 2019", "from 2018 to 2020"
        patterns = [
            (r'\b(19|20)\d{2}\b', "year"),
            (r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+(19|20)\d{2}\b', "month"),
        ]
        
        for pattern, precision in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group()
                return self._extract_date(date_str)
        
        return None, None
    
    def _extract_org_and_role(self, text: str) -> tuple:
        """Extract organization and role from text."""
        org = None
        role = None
        
        # Pattern: "ROLE at ORG"
        match = re.search(r'(?:a|an)\s+([^,.]+?)\s+(?:at|with)\s+([^,.]+)', text, re.IGNORECASE)
        if match:
            role = match.group(1).strip()
            org = match.group(2).strip()
        
        return org, role
    
    def _compute_event_fingerprint(self, event: Dict) -> str:
        """Compute fingerprint for event deduplication."""
        key = f"{event.get('event_type')}:{event.get('title')}:{event.get('start_date')}:{event.get('organization')}"
        return hashlib.sha256(key.lower().encode()).hexdigest()[:16]
    
    async def _check_for_conflict(self, twin_id: str, event: Dict) -> bool:
        """Check if event conflicts with existing timeline."""
        try:
            # Simple overlap check for same organization/role
            if not event.get("organization"):
                return False
            
            response = supabase.table("person_timeline_events") \
                .select("*") \
                .eq("twin_id", twin_id) \
                .eq("organization", event["organization"]) \
                .eq("is_active", True) \
                .execute()
            
            for existing in response.data or []:
                # Check for temporal overlap
                if event.get("start_date") and existing.get("start_date"):
                    if event["start_date"] == existing["start_date"]:
                        return True  # Same start date = potential conflict
            
            return False
        except Exception:
            return False
    
    async def _store_event(self, twin_id: str, event: Dict, fingerprint: str, claim_id: str):
        """Store timeline event."""
        try:
            insert_data = {
                "twin_id": twin_id,
                "event_type": event["event_type"],
                "title": event["title"],
                "description": event["description"],
                "start_date": event["start_date"],
                "start_date_precision": event["start_date_precision"],
                "end_date": event.get("end_date"),
                "end_date_precision": event.get("end_date_precision"),
                "organization": event.get("organization"),
                "role_title": event.get("role_title"),
                "confidence": event["confidence"],
                "derived_from_claim_ids": event["derived_from_claim_ids"],
                "event_fingerprint": fingerprint,
            }
            
            supabase.table("person_timeline_events").insert(insert_data).execute()
        except Exception as e:
            logger.warning(f"Error storing event: {e}")
