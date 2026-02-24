"""
Identity Confidence Scorer Module (Phase 3.1)

Scores how likely a crawled page belongs to the user who submitted links
during onboarding. Uses weighted, interpretable signals (no opaque LLM calls).

Usage:
    scorer = IdentityConfidenceScorer()
    result = scorer.score_page(
        page_content="Renee Sferrazza is a wine expert...",
        page_metadata={"title": "About Renee Sferrazza", "url": "..."},
        claimed_identity={
            "full_name": "Renee Sferrazza",
            "location": "Toronto, Ontario, Canada",
            "submitted_links": ["https://linkedin.com/in/renee-sferrazza"]
        },
        content_quality="full"
    )
    
    if result.is_auto_confirm():
        # Auto-confirm this source
    elif result.is_auto_reject():
        # Auto-reject this source
    else:
        # Pending user confirmation
"""

import re
import unicodedata
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from modules.firecrawl_client import ContentQuality


class ConfidenceLevel(str, Enum):
    """Confidence level based on score thresholds."""
    HIGH = "high"      # >= 0.80
    MEDIUM = "medium"  # >= 0.50 and < 0.80
    LOW = "low"        # < 0.50


@dataclass
class IdentityScoreResult:
    """
    Result of identity confidence scoring.
    
    Attributes:
        score: Float score from 0.0 to 1.0
        confidence_level: High/medium/low classification
        details: Component scores and boolean flags
        matched_signals: List of signals that matched
        unmatched_signals: List of signals that didn't match
        reasons: Human-readable explanations for auditability
        normalized_identity: Normalized identity info used in scoring
    """
    score: float
    confidence_level: ConfidenceLevel
    details: Dict[str, Any] = field(default_factory=dict)
    matched_signals: List[str] = field(default_factory=list)
    unmatched_signals: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    normalized_identity: Dict[str, Any] = field(default_factory=dict)
    
    # Threshold constants (configurable via env in future)
    AUTO_CONFIRM_THRESHOLD: float = field(default=0.8, repr=False)
    AUTO_REJECT_THRESHOLD: float = field(default=0.5, repr=False)
    
    def is_auto_confirm(self) -> bool:
        """Returns True if score is high enough for auto-confirmation."""
        return self.score >= self.AUTO_CONFIRM_THRESHOLD
    
    def is_auto_reject(self) -> bool:
        """Returns True if score is low enough for auto-rejection."""
        return self.score < self.AUTO_REJECT_THRESHOLD
    
    def is_pending_confirmation(self) -> bool:
        """Returns True if score is in medium range requiring user confirmation."""
        return self.AUTO_REJECT_THRESHOLD <= self.score < self.AUTO_CONFIRM_THRESHOLD


@dataclass
class ScoringWeights:
    """Configurable weights for identity scoring signals."""
    name_in_title: float = 0.25
    name_in_content: float = 0.20
    location_match: float = 0.15
    url_slug_match: float = 0.15
    social_handle_match: float = 0.15
    profile_indicators: float = 0.10
    
    def __post_init__(self):
        """Ensure weights sum to approximately 1.0."""
        total = (
            self.name_in_title +
            self.name_in_content +
            self.location_match +
            self.url_slug_match +
            self.social_handle_match +
            self.profile_indicators
        )
        if not 0.99 <= total <= 1.01:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")


class IdentityConfidenceScorer:
    """
    Scores identity confidence for crawled pages.
    
    Uses interpretable weighted scoring based on:
    - Name presence in title/metadata
    - Name presence in content
    - Location matching
    - URL slug matching
    - Social handle extraction and matching
    - Profile indicator keywords
    """
    
    def __init__(self, weights: Optional[ScoringWeights] = None):
        self.weights = weights or ScoringWeights()
        # Validation happens in ScoringWeights.__post_init__
    
    def score_page(
        self,
        page_content: str,
        page_metadata: Dict[str, Any],
        claimed_identity: Dict[str, Any],
        content_quality: Optional[str] = None,
    ) -> IdentityScoreResult:
        """
        Score a page for identity confidence.
        
        Args:
            page_content: Extracted page content text
            page_metadata: Page metadata (title, description, url, author, etc.)
            claimed_identity: User's claimed identity info
                - full_name: str
                - location: str (optional)
                - submitted_links: List[str] (optional)
            content_quality: Content quality from Phase 3.0 (full/partial/blocked/manual_needed)
        
        Returns:
            IdentityScoreResult with score, confidence level, and details
        """
        # Normalize inputs
        normalized = self._normalize_identity(claimed_identity)
        content_lower = page_content.lower()
        title = (page_metadata.get("title") or "").lower()
        description = (page_metadata.get("description") or "").lower()
        url = (page_metadata.get("url") or page_metadata.get("sourceURL") or "").lower()
        author = (page_metadata.get("author") or "").lower()
        
        # Initialize tracking
        component_scores: Dict[str, float] = {}
        matched_signals: List[str] = []
        unmatched_signals: List[str] = []
        reasons: List[str] = []
        
        # Parse content quality
        quality = self._parse_content_quality(content_quality)
        quality_penalty = self._get_quality_penalty(quality)
        
        # Extract handles from submitted links
        submitted_handles = self._extract_handles_from_links(
            claimed_identity.get("submitted_links", [])
        )
        
        # Score components
        name_parts = normalized.get("name_parts", [])
        full_name = normalized.get("full_name", "")
        location = normalized.get("location", "")
        
        # 1. Name in title/meta (weight: 0.25)
        name_in_title_score = self._score_name_in_title(
            title, description, author, name_parts, full_name
        )
        component_scores["name_in_title"] = name_in_title_score
        if name_in_title_score > 0:
            matched_signals.append("name_in_title")
            reasons.append(f"Name found in title/metadata (score: {name_in_title_score:.2f})")
        else:
            unmatched_signals.append("name_in_title")
        
        # 2. Name in content (weight: 0.20)
        name_in_content_score = self._score_name_in_content(
            content_lower, name_parts, full_name
        )
        component_scores["name_in_content"] = name_in_content_score
        if name_in_content_score > 0:
            matched_signals.append("name_in_content")
            reasons.append(f"Name found in content (score: {name_in_content_score:.2f})")
        else:
            unmatched_signals.append("name_in_content")
        
        # 3. Location match (weight: 0.15)
        location_score = self._score_location(content_lower, title, location)
        component_scores["location_match"] = location_score
        if location_score > 0:
            matched_signals.append("location_match")
            reasons.append(f"Location match (score: {location_score:.2f})")
        else:
            unmatched_signals.append("location_match")
        
        # 4. URL slug match (weight: 0.15)
        slug_score = self._score_url_slug(url, name_parts, full_name)
        component_scores["url_slug_match"] = slug_score
        if slug_score > 0:
            matched_signals.append("url_slug_match")
            reasons.append(f"URL slug matches name (score: {slug_score:.2f})")
        else:
            unmatched_signals.append("url_slug_match")
        
        # 5. Social handle match (weight: 0.15)
        handle_score = self._score_social_handles(
            content_lower, title, url, submitted_handles
        )
        component_scores["social_handle_match"] = handle_score
        if handle_score > 0:
            matched_signals.append("social_handle_match")
            reasons.append(f"Social handle match (score: {handle_score:.2f})")
        else:
            unmatched_signals.append("social_handle_match")
        
        # 6. Profile indicators (weight: 0.10)
        indicator_score = self._score_profile_indicators(content_lower, title)
        component_scores["profile_indicators"] = indicator_score
        if indicator_score > 0:
            matched_signals.append("profile_indicators")
            reasons.append(f"Profile indicator keywords found (score: {indicator_score:.2f})")
        else:
            unmatched_signals.append("profile_indicators")
        
        # Check for strong mismatches (penalties)
        mismatch_penalty = self._calculate_mismatch_penalty(
            content_lower, title, name_parts, location
        )
        
        # Calculate weighted score
        raw_score = (
            name_in_title_score * self.weights.name_in_title +
            name_in_content_score * self.weights.name_in_content +
            location_score * self.weights.location_match +
            slug_score * self.weights.url_slug_match +
            handle_score * self.weights.social_handle_match +
            indicator_score * self.weights.profile_indicators
        )
        
        # Apply penalties
        final_score = max(0.0, min(1.0, raw_score - mismatch_penalty - quality_penalty))
        
        # Determine confidence level
        if final_score >= 0.80:
            confidence_level = ConfidenceLevel.HIGH
        elif final_score >= 0.50:
            confidence_level = ConfidenceLevel.MEDIUM
        else:
            confidence_level = ConfidenceLevel.LOW
        
        # Add quality/mismatch reasons
        if quality_penalty > 0:
            reasons.append(f"Content quality '{quality.value}' reduced confidence")
        if mismatch_penalty > 0:
            reasons.append(f"Potential mismatch signals detected (penalty: {mismatch_penalty:.2f})")
        
        return IdentityScoreResult(
            score=round(final_score, 3),
            confidence_level=confidence_level,
            details={
                "component_scores": component_scores,
                "raw_score": round(raw_score, 3),
                "quality_penalty": round(quality_penalty, 3),
                "mismatch_penalty": round(mismatch_penalty, 3),
                "content_quality": quality.value,
            },
            matched_signals=matched_signals,
            unmatched_signals=unmatched_signals,
            reasons=reasons,
            normalized_identity=normalized,
        )
    
    # ========================================================================
    # Normalization Utilities
    # ========================================================================
    
    def _normalize_identity(self, claimed_identity: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize identity fields for consistent matching."""
        full_name = self._normalize_text(claimed_identity.get("full_name", ""))
        location = self._normalize_text(claimed_identity.get("location", ""))
        
        # Split name into parts
        name_parts = [p for p in full_name.split() if len(p) >= 2]
        
        # Extract first/last name
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[-1] if len(name_parts) > 1 else ""
        
        return {
            "full_name": full_name,
            "name_parts": name_parts,
            "first_name": first_name,
            "last_name": last_name,
            "location": location,
            "location_parts": [p for p in location.split() if len(p) >= 2],
        }
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for matching:
        - Unicode normalization (NFKD)
        - Lowercase
        - Remove accents
        - Remove extra punctuation
        - Normalize whitespace
        """
        if not text:
            return ""
        
        # Unicode normalization
        text = unicodedata.normalize("NFKD", text)
        
        # Remove accents (combine with following character and filter)
        text = "".join(c for c in text if not unicodedata.combining(c))
        
        # Lowercase
        text = text.lower()
        
        # Replace common punctuation with spaces
        text = re.sub(r"[.,;:!?&|\-\_\/\@\#\$\%\^\&\*\(\)\[\]\{\}\\]", " ", text)
        
        # Normalize whitespace
        text = " ".join(text.split())
        
        return text.strip()
    
    def _normalize_url_slug(self, slug: str) -> str:
        """Normalize URL slug (e.g., 'john-doe' -> 'john doe')."""
        # Replace common slug separators with spaces
        slug = re.sub(r"[-_\.+]", " ", slug)
        return self._normalize_text(slug)
    
    # ========================================================================
    # Signal Scoring Methods
    # ========================================================================
    
    def _score_name_in_title(
        self,
        title: str,
        description: str,
        author: str,
        name_parts: List[str],
        full_name: str
    ) -> float:
        """Score name presence in title, description, or author fields."""
        if not name_parts:
            return 0.0
        
        score = 0.0
        combined_text = f"{title} {description} {author}"
        
        # Full name match (highest value)
        if full_name and full_name in combined_text:
            score = 1.0
        # All name parts match
        elif len(name_parts) >= 2 and all(part in combined_text for part in name_parts):
            score = 0.9
        # Last name match (common for professional pages)
        elif len(name_parts) >= 2 and name_parts[-1] in combined_text:
            score = 0.6
        # First name match only (weak signal)
        elif name_parts and name_parts[0] in combined_text:
            score = 0.3
        
        return score
    
    def _score_name_in_content(
        self,
        content: str,
        name_parts: List[str],
        full_name: str
    ) -> float:
        """Score name presence in content body."""
        if not name_parts or not content:
            return 0.0
        
        # Full name match
        if full_name and full_name in content:
            # Count occurrences for confidence
            count = content.count(full_name)
            return min(1.0, 0.5 + (count - 1) * 0.1)
        
        # All name parts match
        if len(name_parts) >= 2 and all(part in content for part in name_parts):
            count = min(content.count(p) for p in name_parts)
            return min(0.9, 0.4 + (count - 1) * 0.1)
        
        # Last name only
        if len(name_parts) >= 2 and name_parts[-1] in content:
            return 0.4
        
        # First name only (weak)
        if name_parts and name_parts[0] in content:
            return 0.2
        
        return 0.0
    
    def _score_location(
        self,
        content: str,
        title: str,
        location: str
    ) -> float:
        """Score location match with fuzzy matching support."""
        if not location:
            return 0.0
        
        combined_text = f"{title} {content}"
        location_parts = [p for p in location.split() if len(p) >= 3]
        
        # Full location match
        if location in combined_text:
            return 1.0
        
        # City/region match (major part of location)
        if location_parts:
            # Match major location parts (city, state, country)
            matches = sum(1 for part in location_parts if part in combined_text)
            if matches == len(location_parts):
                return 0.8
            elif matches >= len(location_parts) / 2:
                return 0.5
            elif matches > 0:
                return 0.2
        
        return 0.0
    
    def _score_url_slug(
        self,
        url: str,
        name_parts: List[str],
        full_name: str
    ) -> float:
        """Score URL slug matching name."""
        if not url or not name_parts:
            return 0.0
        
        # Extract path from URL
        path_match = re.search(r"\/([^\/\?#]+)(?:[\/\?#]|$)", url)
        if not path_match:
            return 0.0
        
        slug = path_match.group(1)
        normalized_slug = self._normalize_url_slug(slug)
        
        # Full name in slug
        if full_name and full_name in normalized_slug:
            return 1.0
        
        # All name parts in slug
        if len(name_parts) >= 2 and all(part in normalized_slug for part in name_parts):
            return 0.9
        
        # Last name in slug (common for professional sites)
        if len(name_parts) >= 2 and name_parts[-1] in normalized_slug:
            return 0.7
        
        # First name in slug
        if name_parts and name_parts[0] in normalized_slug:
            return 0.4
        
        return 0.0
    
    def _extract_handles_from_links(self, links: List[str]) -> Set[str]:
        """Extract social handles from submitted links."""
        handles = set()
        
        for link in links:
            link_lower = link.lower()
            
            # LinkedIn: /in/username
            li_match = re.search(r"linkedin\.com\/in\/([^\/\?#]+)", link_lower)
            if li_match:
                # Keep hyphens for handle matching, just lowercase
                handles.add(li_match.group(1).lower())
            
            # Twitter/X: /@username or /username
            tw_match = re.search(r"(?:twitter|x)\.com\/(?:@)?([^\/\?#]+)", link_lower)
            if tw_match:
                handles.add(tw_match.group(1).lower())
            
            # Instagram: /@username or /username
            ig_match = re.search(r"instagram\.com\/(?:@)?([^\/\?#]+)", link_lower)
            if ig_match:
                handles.add(ig_match.group(1).lower())
            
            # YouTube: /@channel or /c/channel or /user/username
            yt_match = re.search(r"youtube\.com\/(?:@|c\/|user\/)([^\/\?#]+)", link_lower)
            if yt_match:
                handles.add(yt_match.group(1).lower())
            
            # Generic: /@handle pattern
            generic_match = re.search(r"\/@([^\/\?#]+)", link_lower)
            if generic_match:
                handles.add(generic_match.group(1).lower())
        
        return handles
    
    def _score_social_handles(
        self,
        content: str,
        title: str,
        url: str,
        submitted_handles: Set[str]
    ) -> float:
        """Score social handle matches."""
        if not submitted_handles:
            return 0.0
        
        combined_text = f"{title} {content} {url}"
        
        # Check for exact handle matches
        matched = [h for h in submitted_handles if h in combined_text]
        
        if not matched:
            return 0.0
        
        # Score based on number of matches and specificity
        score = min(1.0, len(matched) * 0.5 + 0.2)
        
        return score
    
    def _score_profile_indicators(self, content: str, title: str) -> float:
        """Score profile indicator keywords."""
        # Use word boundaries to avoid substring matches
        indicators = [
            r"\babout\b", r"\bbio\b", r"\bprofile\b", r"\bfounder\b", 
            r"\bco-founder\b", r"\bceo\b", r"\bcto\b",
            r"\bspeaker\b", r"\bauthor\b", r"\bwriter\b", 
            r"\bconsultant\b", r"\bexpert\b", r"\bprofessional\b",
            r"\bportfolio\b", r"\bresume\b", r"\bcv\b", 
            r"\bbackground\b", r"\bexperience\b", r"\bcontact\b"
        ]
        
        combined_text = f"{title} {content}"
        
        # Count matching indicators using word boundaries
        matches = sum(1 for ind in indicators if re.search(ind, combined_text))
        
        # Score based on match count (diminishing returns)
        if matches >= 3:
            return 1.0
        elif matches == 2:
            return 0.7
        elif matches == 1:
            return 0.4
        
        return 0.0
    
    def _calculate_mismatch_penalty(
        self,
        content: str,
        title: str,
        name_parts: List[str],
        location: str
    ) -> float:
        """
        Detect strong mismatch signals and apply penalty.
        
        Looks for:
        - Different full names that aren't the claimed identity
        - Clear indicators this is about someone else
        """
        penalty = 0.0
        combined_text = f"{title} {content[:2000]}"  # Check beginning of content
        
        # Look for other proper names that might indicate different person
        # Pattern: "Name is a" or "Name, " or "Name's"
        name_patterns = re.findall(r"\b([a-z]+ [a-z]+)\s+(?:is a|is an|was a|,|')", combined_text)
        
        other_names_found = []
        for name in name_patterns:
            name_lower = name.lower()
            # Skip if it's the claimed identity
            if any(part == name_lower for part in name_parts):
                continue
            # Skip common non-name words
            if name_lower in ("this is", "there is", "it is", "he is", "she is"):
                continue
            # If it looks like a name (2+ parts, reasonable length)
            if len(name_lower) > 5 and " " in name_lower:
                other_names_found.append(name_lower)
        
        # If we found other prominent names without the claimed identity
        if other_names_found and not any(part in combined_text for part in name_parts):
            penalty += 0.3
        
        return min(0.5, penalty)  # Cap penalty at 0.5
    
    def _parse_content_quality(self, quality: Optional[str]) -> ContentQuality:
        """Parse content quality string to enum."""
        if not quality:
            return ContentQuality.FULL
        try:
            return ContentQuality(quality.lower())
        except ValueError:
            return ContentQuality.FULL
    
    def _get_quality_penalty(self, quality: ContentQuality) -> float:
        """Get penalty based on content quality."""
        penalties = {
            ContentQuality.FULL: 0.0,
            ContentQuality.PARTIAL: 0.1,
            ContentQuality.BLOCKED: 0.3,
            ContentQuality.MANUAL_NEEDED: 0.2,
        }
        return penalties.get(quality, 0.0)


# Convenience function for easy use
def score_identity_confidence(
    page_content: str,
    page_metadata: Dict[str, Any],
    claimed_identity: Dict[str, Any],
    content_quality: Optional[str] = None,
    weights: Optional[ScoringWeights] = None,
) -> IdentityScoreResult:
    """
    Convenience function to score identity confidence without instantiating scorer.
    
    Args:
        page_content: Extracted page content text
        page_metadata: Page metadata dict
        claimed_identity: User's claimed identity info
        content_quality: Optional content quality from Phase 3.0
        weights: Optional custom scoring weights
    
    Returns:
        IdentityScoreResult
    """
    scorer = IdentityConfidenceScorer(weights=weights)
    return scorer.score_page(page_content, page_metadata, claimed_identity, content_quality)
