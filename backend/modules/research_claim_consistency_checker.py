"""
Research Claim Consistency Checker (Phase 10)

Detects contradictions, duplicates, and conflicts across claims in a research run.
Uses lightweight rule-based heuristics (MVP - no deep semantic reasoning).

Usage:
    checker = ConsistencyChecker()
    issues = checker.check_consistency(finalized_claims)
"""

import hashlib
import re
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

from modules.research_claim_extractor import ResearchClaim, ClaimType
from modules.research_claim_finalization_engine import FinalClaimStatus

logger = logging.getLogger(__name__)


class IssueType(str, Enum):
    """Types of consistency issues."""
    CONTRADICTION = "contradiction"
    DUPLICATE = "duplicate"
    CONFIDENCE_MISMATCH = "confidence_mismatch"
    STATUS_CONFLICT = "status_conflict"


class Severity(str, Enum):
    """Severity levels for issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class FinalizedClaim:
    """Claim with finalization data for consistency checking."""
    claim: ResearchClaim
    final_status: FinalClaimStatus
    final_confidence: float
    local_status: Optional[str] = None
    web_status: Optional[str] = None


@dataclass
class ConsistencyIssue:
    """A consistency issue between claims."""
    issue_type: IssueType
    severity: Severity
    claim_ids: List[str]
    title: str
    description: str
    detection_rule: str
    confidence: float
    issue_hash: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "issue_type": self.issue_type.value,
            "severity": self.severity.value,
            "claim_ids": self.claim_ids,
            "title": self.title,
            "description": self.description,
            "detection_rule": self.detection_rule,
            "confidence": self.confidence,
            "issue_hash": self.issue_hash,
        }


class ConsistencyChecker:
    """
    Detects consistency issues across finalized claims.
    
    Detection heuristics:
    1. Contradictions: Opposite statements (prefer vs dislike)
    2. Duplicates: Near-identical claims with different IDs
    3. Confidence mismatches: High vs low confidence on similar claims
    4. Status conflicts: Same claim with different final statuses
    """
    
    # Keywords that indicate opposite meanings
    OPPOSITE_PATTERNS = {
        "preference": {
            "positive": ["prefer", "like", "love", "enjoy", "favor"],
            "negative": ["dislike", "hate", "avoid", "disprefer", "don't like", "do not like"],
        },
        "belief": {
            "positive": ["believe", "think", "consider", "view as"],
            "negative": ["don't believe", "do not believe", "doubt", "reject", "dispute"],
        },
        "boundary": {
            "positive": ["always", "definitely", "must", "never avoid"],
            "negative": ["never", "avoid", "don't", "won't", "wouldn't"],
        },
    }
    
    def __init__(self):
        """Initialize the consistency checker."""
        self.issues_found = 0
    
    def check_consistency(
        self,
        claims: List[FinalizedClaim]
    ) -> List[ConsistencyIssue]:
        """
        Run all consistency checks on a list of claims.
        
        Args:
            claims: List of finalized claims to check
            
        Returns:
            List of consistency issues found
        """
        issues: List[ConsistencyIssue] = []
        seen_hashes: Set[str] = set()
        
        # Run each detector
        detectors = [
            self._detect_contradictions,
            self._detect_duplicates,
            self._detect_confidence_mismatches,
            self._detect_status_conflicts,
        ]
        
        for detector in detectors:
            try:
                found_issues = detector(claims)
                for issue in found_issues:
                    # Deduplicate by hash
                    if issue.issue_hash not in seen_hashes:
                        issues.append(issue)
                        seen_hashes.add(issue.issue_hash)
            except Exception as e:
                logger.error(f"Error in {detector.__name__}: {e}")
        
        self.issues_found = len(issues)
        logger.info(f"Consistency check found {len(issues)} issues")
        
        return issues
    
    def _detect_contradictions(self, claims: List[FinalizedClaim]) -> List[ConsistencyIssue]:
        """
        Detect contradictory claims.
        
        Looks for:
        - Opposite preferences (prefer X vs dislike X)
        - Opposite beliefs (believe X vs don't believe X)
        - Boundary conflicts (always do X vs never do X)
        """
        issues = []
        
        # Group claims by type for efficient comparison
        by_type: Dict[ClaimType, List[FinalizedClaim]] = {}
        for fc in claims:
            ct = fc.claim.claim_type
            if ct not in by_type:
                by_type[ct] = []
            by_type[ct].append(fc)
        
        # Check each claim type for contradictions
        for claim_type, type_claims in by_type.items():
            patterns = self.OPPOSITE_PATTERNS.get(claim_type.value, None)
            if not patterns:
                continue
            
            positive_claims = []
            negative_claims = []
            
            # Categorize claims
            for fc in type_claims:
                text_lower = fc.claim.claim_text.lower()
                
                # Check for negative patterns first (more specific)
                has_negative = any(
                    re.search(r'\b' + re.escape(n) + r'\b', text_lower)
                    for n in patterns["negative"]
                )
                
                # Check for positive patterns only if no negative found
                if not has_negative:
                    has_positive = any(
                        re.search(r'\b' + re.escape(p) + r'\b', text_lower)
                        for p in patterns["positive"]
                    )
                else:
                    has_positive = False
                
                # Categorize
                if has_negative:
                    negative_claims.append(fc)
                elif has_positive:
                    positive_claims.append(fc)
            
            # Create issues for potential contradictions
            for pos in positive_claims:
                for neg in negative_claims:
                    # Check if they refer to the same subject (simplified)
                    if self._same_subject(pos.claim.claim_text, neg.claim.claim_text):
                        issue = ConsistencyIssue(
                            issue_type=IssueType.CONTRADICTION,
                            severity=Severity.HIGH,
                            claim_ids=[pos.claim.id or "", neg.claim.id or ""],
                            title="Contradictory Statements Detected",
                            description=f"Claim A: '{pos.claim.claim_text}' contradicts Claim B: '{neg.claim.claim_text}'",
                            detection_rule="opposite_keywords_same_subject",
                            confidence=0.8,
                            issue_hash=self._compute_issue_hash(
                                IssueType.CONTRADICTION,
                                [pos.claim.id or "", neg.claim.id or ""],
                                pos.claim.claim_text
                            )
                        )
                        issues.append(issue)
        
        return issues
    
    def _detect_duplicates(self, claims: List[FinalizedClaim]) -> List[ConsistencyIssue]:
        """
        Detect duplicate or near-duplicate claims.
        
        Looks for:
        - Same claim_text from different sources
        - Similar text (>80% similarity) with different statuses
        """
        issues = []
        
        # Group by normalized text
        text_groups: Dict[str, List[FinalizedClaim]] = {}
        for fc in claims:
            normalized = self._normalize_text(fc.claim.claim_text)
            if normalized not in text_groups:
                text_groups[normalized] = []
            text_groups[normalized].append(fc)
        
        # Find groups with multiple claims
        for text, group in text_groups.items():
            if len(group) > 1:
                claim_ids = [fc.claim.id or "" for fc in group]
                statuses = set(fc.final_status.value for fc in group)
                
                # Different statuses = higher severity
                severity = Severity.HIGH if len(statuses) > 1 else Severity.LOW
                
                issue = ConsistencyIssue(
                    issue_type=IssueType.DUPLICATE,
                    severity=severity,
                    claim_ids=claim_ids,
                    title="Duplicate Claims Detected",
                    description=f"Found {len(group)} claims with similar text but different IDs",
                    detection_rule="same_normalized_text",
                    confidence=0.9,
                    issue_hash=self._compute_issue_hash(
                        IssueType.DUPLICATE,
                        sorted(claim_ids),
                        text
                    )
                )
                issues.append(issue)
        
        # Check for similar text using simple word overlap
        for i, fc1 in enumerate(claims):
            for fc2 in claims[i+1:]:
                similarity = self._text_similarity(
                    fc1.claim.claim_text,
                    fc2.claim.claim_text
                )
                
                if similarity > 0.8 and fc1.claim.id != fc2.claim.id:
                    # Check if not already caught by exact match
                    norm1 = self._normalize_text(fc1.claim.claim_text)
                    norm2 = self._normalize_text(fc2.claim.claim_text)
                    
                    if norm1 != norm2:
                        issue = ConsistencyIssue(
                            issue_type=IssueType.DUPLICATE,
                            severity=Severity.MEDIUM,
                            claim_ids=[fc1.claim.id or "", fc2.claim.id or ""],
                            title="Similar Claims Detected",
                            description=f"Claims have {similarity:.0%} text similarity",
                            detection_rule="high_text_similarity",
                            confidence=similarity,
                            issue_hash=self._compute_issue_hash(
                                IssueType.DUPLICATE,
                                sorted([fc1.claim.id or "", fc2.claim.id or ""]),
                                norm1
                            )
                        )
                        issues.append(issue)
        
        return issues
    
    def _detect_confidence_mismatches(self, claims: List[FinalizedClaim]) -> List[ConsistencyIssue]:
        """
        Detect confidence mismatches.
        
        Looks for:
        - Similar claims with very different confidence scores
        - High confidence accepted vs low confidence rejected on similar topics
        """
        issues = []
        
        # Group by claim type
        by_type: Dict[ClaimType, List[FinalizedClaim]] = {}
        for fc in claims:
            ct = fc.claim.claim_type
            if ct not in by_type:
                by_type[ct] = []
            by_type[ct].append(fc)
        
        # Check within each type
        for claim_type, type_claims in by_type.items():
            accepted_high = [fc for fc in type_claims 
                           if fc.final_status == FinalClaimStatus.ACCEPTED 
                           and fc.final_confidence >= 0.8]
            rejected_low = [fc for fc in type_claims 
                          if fc.final_status == FinalClaimStatus.REJECTED 
                          and fc.final_confidence <= 0.4]
            
            # Check for mismatched pairs
            for acc in accepted_high:
                for rej in rejected_low:
                    if self._same_subject(acc.claim.claim_text, rej.claim.claim_text):
                        issue = ConsistencyIssue(
                            issue_type=IssueType.CONFIDENCE_MISMATCH,
                            severity=Severity.MEDIUM,
                            claim_ids=[acc.claim.id or "", rej.claim.id or ""],
                            title="Confidence Mismatch",
                            description=(f"Similar claims have conflicting outcomes: "
                                       f"Accepted with {acc.final_confidence:.0%} confidence vs "
                                       f"Rejected with {rej.final_confidence:.0%} confidence"),
                            detection_rule="high_vs_low_confidence_same_subject",
                            confidence=0.7,
                            issue_hash=self._compute_issue_hash(
                                IssueType.CONFIDENCE_MISMATCH,
                                sorted([acc.claim.id or "", rej.claim.id or ""]),
                                "confidence_mismatch"
                            )
                        )
                        issues.append(issue)
        
        return issues
    
    def _detect_status_conflicts(self, claims: List[FinalizedClaim]) -> List[ConsistencyIssue]:
        """
        Detect status conflicts.
        
        Looks for:
        - Same source with different final statuses
        - Claims that reference the same fact but have different outcomes
        """
        issues = []
        
        # Group by source
        by_source: Dict[str, List[FinalizedClaim]] = {}
        for fc in claims:
            source_id = fc.claim.source_id or "unknown"
            if source_id not in by_source:
                by_source[source_id] = []
            by_source[source_id].append(fc)
        
        # Find sources with conflicting statuses
        for source_id, source_claims in by_source.items():
            if source_id == "unknown" or len(source_claims) < 2:
                continue
            
            statuses = set(fc.final_status for fc in source_claims)
            if len(statuses) > 1:
                claim_ids = [fc.claim.id or "" for fc in source_claims]
                status_list = ", ".join(s.value for s in statuses)
                
                issue = ConsistencyIssue(
                    issue_type=IssueType.STATUS_CONFLICT,
                    severity=Severity.HIGH,
                    claim_ids=claim_ids,
                    title="Status Conflict from Same Source",
                    description=f"Claims from the same source have conflicting final statuses: {status_list}",
                    detection_rule="same_source_different_status",
                    confidence=0.85,
                    issue_hash=self._compute_issue_hash(
                        IssueType.STATUS_CONFLICT,
                        sorted(claim_ids),
                        source_id
                    )
                )
                issues.append(issue)
        
        return issues
    
    def _same_subject(self, text1: str, text2: str) -> bool:
        """
        Check if two claim texts refer to the same subject (simplified).
        
        Uses keyword overlap as a heuristic.
        """
        # Extract nouns and key terms (simplified: words > 3 chars)
        words1 = set(w.lower() for w in re.findall(r'\b\w{4,}\b', text1))
        words2 = set(w.lower() for w in re.findall(r'\b\w{4,}\b', text2))
        
        if not words1 or not words2:
            return False
        
        # Check overlap
        overlap = words1 & words2
        total = words1 | words2
        
        if not total:
            return False
        
        similarity = len(overlap) / len(total)
        return similarity > 0.3  # 30% word overlap threshold
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for duplicate detection.
        
        - Lowercase
        - Remove punctuation
        - Remove extra whitespace
        """
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate simple word-based similarity between two texts.
        
        Returns:
            Similarity score 0.0-1.0
        """
        words1 = set(self._normalize_text(text1).split())
        words2 = set(self._normalize_text(text2).split())
        
        if not words1 or not words2:
            return 0.0
        
        overlap = words1 & words2
        total = words1 | words2
        
        return len(overlap) / len(total)
    
    def _compute_issue_hash(
        self,
        issue_type: IssueType,
        claim_ids: List[str],
        content: str
    ) -> str:
        """
        Compute a hash for issue deduplication.
        
        Args:
            issue_type: Type of issue
            claim_ids: IDs of claims involved
            content: Content to hash
            
        Returns:
            Hex hash string
        """
        # Sort claim IDs for consistency
        sorted_ids = sorted(claim_ids)
        hash_input = f"{issue_type.value}:{','.join(sorted_ids)}:{content}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


# =============================================================================
# Convenience Functions
# =============================================================================

def check_claim_consistency(claims: List[FinalizedClaim]) -> List[ConsistencyIssue]:
    """
    Convenience function to check consistency of claims.
    
    Args:
        claims: List of finalized claims
        
    Returns:
        List of consistency issues
    """
    checker = ConsistencyChecker()
    return checker.check_consistency(claims)


def get_issue_summary(issues: List[ConsistencyIssue]) -> Dict[str, Any]:
    """
    Get a summary of consistency issues.
    
    Args:
        issues: List of issues
        
    Returns:
        Summary dictionary with counts by type and severity
    """
    by_type: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    
    for issue in issues:
        t = issue.issue_type.value
        s = issue.severity.value
        by_type[t] = by_type.get(t, 0) + 1
        by_severity[s] = by_severity.get(s, 0) + 1
    
    return {
        "total_issues": len(issues),
        "by_type": by_type,
        "by_severity": by_severity,
        "has_critical": by_severity.get("high", 0) > 0,
    }
