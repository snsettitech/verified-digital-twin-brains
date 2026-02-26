"""
Person Completeness Layer v1 - Configuration

Feature flags and configuration for the person completeness pipeline.
"""

import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SourceRegistryConfig(BaseModel):
    """Configuration for source registry building."""
    enabled: bool = Field(default=True)
    min_authority_tier: int = Field(default=3)  # Skip sources below this tier
    max_sources_per_twin: int = Field(default=1000)
    enable_content_hash_dedup: bool = Field(default=True)
    default_source_type: str = Field(default="website_page")
    
    @classmethod
    def from_env(cls) -> "SourceRegistryConfig":
        return cls(
            enabled=os.getenv("PC_SOURCE_REGISTRY_ENABLED", "true").lower() == "true",
            min_authority_tier=int(os.getenv("PC_MIN_AUTHORITY_TIER", "3")),
            max_sources_per_twin=int(os.getenv("PC_MAX_SOURCES", "1000")),
            enable_content_hash_dedup=os.getenv("PC_CONTENT_HASH_DEDUP", "true").lower() == "true",
        )


class ClaimExtractionConfig(BaseModel):
    """Configuration for claim extraction."""
    enabled: bool = Field(default=True)
    model: str = Field(default="gpt-4o-mini")
    min_authority_tier: int = Field(default=3)  # 1 (highest authority) to 7 (lowest)
    max_sources_per_twin: int = Field(default=200)
    max_claims_per_source: int = Field(default=50)
    min_confidence_threshold: float = Field(default=0.5)
    enable_deduplication: bool = Field(default=True)
    extract_temporal_info: bool = Field(default=True)
    
    # Claim types to extract
    enabled_claim_types: List[str] = Field(default_factory=lambda: [
        "identity", "work_experience", "education", "credential", "project",
        "achievement", "preference", "belief", "goal", "bio_fact", "skill",
        "media_appearance", "expertise"
    ])
    
    @classmethod
    def from_env(cls) -> "ClaimExtractionConfig":
        enabled_types = os.getenv("PC_CLAIM_TYPES", "")
        return cls(
            enabled=os.getenv("PC_CLAIM_EXTRACTION_ENABLED", "true").lower() == "true",
            model=os.getenv("PC_CLAIM_MODEL", "gpt-4o-mini"),
            min_authority_tier=int(os.getenv("PC_CLAIM_MIN_AUTHORITY_TIER", "3")),
            max_sources_per_twin=int(os.getenv("PC_CLAIM_MAX_SOURCES", "200")),
            max_claims_per_source=int(os.getenv("PC_MAX_CLAIMS_PER_SOURCE", "50")),
            min_confidence_threshold=float(os.getenv("PC_MIN_CLAIM_CONFIDENCE", "0.5")),
            enabled_claim_types=[t.strip() for t in enabled_types.split(",") if t.strip()] if enabled_types else cls().enabled_claim_types,
        )


class TimelineBuilderConfig(BaseModel):
    """Configuration for timeline building."""
    enabled: bool = Field(default=True)
    enable_date_normalization: bool = Field(default=True)
    enable_duplicate_detection: bool = Field(default=True)
    enable_conflict_flagging: bool = Field(default=True)
    default_date_precision: str = Field(default="month")
    
    @classmethod
    def from_env(cls) -> "TimelineBuilderConfig":
        return cls(
            enabled=os.getenv("PC_TIMELINE_ENABLED", "true").lower() == "true",
            enable_date_normalization=os.getenv("PC_DATE_NORMALIZATION", "true").lower() == "true",
            enable_duplicate_detection=os.getenv("PC_TIMELINE_DEDUP", "true").lower() == "true",
        )


class TopicGraphConfig(BaseModel):
    """Configuration for topic graph building."""
    enabled: bool = Field(default=True)
    model: str = Field(default="gpt-4o-mini")
    max_topics_per_twin: int = Field(default=100)
    enable_hierarchy: bool = Field(default=True)
    min_evidence_count: int = Field(default=2)
    
    # Scoring weights (should sum to 1.0)
    coverage_weight: float = Field(default=0.25)
    verification_weight: float = Field(default=0.25)
    recency_weight: float = Field(default=0.20)
    consistency_weight: float = Field(default=0.20)
    style_weight: float = Field(default=0.10)
    
    @classmethod
    def from_env(cls) -> "TopicGraphConfig":
        return cls(
            enabled=os.getenv("PC_TOPIC_GRAPH_ENABLED", "true").lower() == "true",
            max_topics_per_twin=int(os.getenv("PC_MAX_TOPICS", "100")),
            enable_hierarchy=os.getenv("PC_TOPIC_HIERARCHY", "true").lower() == "true",
            min_evidence_count=int(os.getenv("PC_MIN_TOPIC_EVIDENCE", "2")),
        )


class StyleProfileConfig(BaseModel):
    """Configuration for style profile building."""
    enabled: bool = Field(default=True)
    model: str = Field(default="gpt-4o-mini")
    min_content_chars: int = Field(default=1000)
    max_phrases_to_extract: int = Field(default=20)
    
    @classmethod
    def from_env(cls) -> "StyleProfileConfig":
        return cls(
            enabled=os.getenv("PC_STYLE_PROFILE_ENABLED", "true").lower() == "true",
            min_content_chars=int(os.getenv("PC_STYLE_MIN_CONTENT", "1000")),
        )


class ContradictionDetectionConfig(BaseModel):
    """Configuration for contradiction detection."""
    enabled: bool = Field(default=True)
    model: str = Field(default="gpt-4o-mini")
    min_confidence_for_detection: float = Field(default=0.7)
    enable_timeline_conflicts: bool = Field(default=True)
    enable_role_conflicts: bool = Field(default=True)
    enable_factual_conflicts: bool = Field(default=True)
    enable_preference_conflicts: bool = Field(default=False)  # Off by default - high false positive
    
    @classmethod
    def from_env(cls) -> "ContradictionDetectionConfig":
        return cls(
            enabled=os.getenv("PC_CONTRADICTION_ENABLED", "true").lower() == "true",
            min_confidence_for_detection=float(os.getenv("PC_CONTRA_CONFIDENCE", "0.7")),
            enable_preference_conflicts=os.getenv("PC_PREFERENCE_CONTRA", "false").lower() == "true",
        )


class AnswerabilityScoringConfig(BaseModel):
    """Configuration for answerability scoring."""
    enabled: bool = Field(default=True)
    enable_global_score: bool = Field(default=True)
    enable_topic_scores: bool = Field(default=True)
    enable_audience_scores: bool = Field(default=False)
    recalculation_interval_hours: int = Field(default=24)
    
    @classmethod
    def from_env(cls) -> "AnswerabilityScoringConfig":
        return cls(
            enabled=os.getenv("PC_ANSWERABILITY_ENABLED", "true").lower() == "true",
            recalculation_interval_hours=int(os.getenv("PC_ANSWERABILITY_INTERVAL", "24")),
        )


class PersonCompletenessConfig(BaseModel):
    """Main Person Completeness Layer configuration."""
    
    # Master enable flag
    enabled: bool = Field(default=True)
    
    # Per-twin enable (for gradual rollout)
    enabled_twin_ids: List[str] = Field(default_factory=list)
    disabled_twin_ids: List[str] = Field(default_factory=list)
    rollout_percentage: int = Field(default=100)  # 0-100
    
    # Stage configs
    source_registry: SourceRegistryConfig = Field(default_factory=SourceRegistryConfig.from_env)
    claim_extraction: ClaimExtractionConfig = Field(default_factory=ClaimExtractionConfig.from_env)
    timeline_builder: TimelineBuilderConfig = Field(default_factory=TimelineBuilderConfig.from_env)
    topic_graph: TopicGraphConfig = Field(default_factory=TopicGraphConfig.from_env)
    style_profile: StyleProfileConfig = Field(default_factory=StyleProfileConfig.from_env)
    contradiction_detection: ContradictionDetectionConfig = Field(default_factory=ContradictionDetectionConfig.from_env)
    answerability_scoring: AnswerabilityScoringConfig = Field(default_factory=AnswerabilityScoringConfig.from_env)
    
    # Pipeline behavior
    fail_fast: bool = Field(default=False)  # If True, stop on first error
    continue_on_stage_failure: bool = Field(default=True)
    enable_metrics: bool = Field(default=True)
    
    @classmethod
    def from_env(cls) -> "PersonCompletenessConfig":
        """Load configuration from environment variables."""
        enabled_twins = os.getenv("PC_ENABLED_TWIN_IDS", "")
        disabled_twins = os.getenv("PC_DISABLED_TWIN_IDS", "")
        
        return cls(
            enabled=os.getenv("PERSON_COMPLETENESS_ENABLED", "true").lower() == "true",
            enabled_twin_ids=enabled_twins.split(",") if enabled_twins else [],
            disabled_twin_ids=disabled_twins.split(",") if disabled_twins else [],
            rollout_percentage=int(os.getenv("PC_ROLLOUT_PCT", "100")),
            fail_fast=os.getenv("PC_FAIL_FAST", "false").lower() == "true",
            continue_on_stage_failure=os.getenv("PC_CONTINUE_ON_FAILURE", "true").lower() == "true",
        )
    
    def is_enabled_for_twin(self, twin_id: str) -> bool:
        """Check if person completeness is enabled for a specific twin."""
        if not self.enabled:
            return False
        
        # Explicit enable list takes precedence
        if self.enabled_twin_ids:
            return twin_id in self.enabled_twin_ids
        
        # Explicit disable list
        if twin_id in self.disabled_twin_ids:
            return False
        
        # Rollout percentage (use hash for deterministic)
        if self.rollout_percentage < 100:
            import hashlib
            hash_val = int(hashlib.md5(twin_id.encode()).hexdigest(), 16)
            return (hash_val % 100) < self.rollout_percentage
        
        return True
    
    def get_enabled_stages(self) -> List[str]:
        """Get list of enabled pipeline stages."""
        stages = []
        if self.source_registry.enabled:
            stages.append("source_registry_built")
        if self.claim_extraction.enabled:
            stages.append("claims_extracted")
        if self.timeline_builder.enabled:
            stages.append("timeline_built")
        if self.topic_graph.enabled:
            stages.append("topic_graph_built")
        if self.style_profile.enabled:
            stages.append("style_profile_built")
        if self.contradiction_detection.enabled:
            stages.append("contradictions_detected")
        if self.answerability_scoring.enabled:
            stages.append("answerability_scored")
        return stages


# Global config instance
_config: PersonCompletenessConfig | None = None


def get_config() -> PersonCompletenessConfig:
    """Get the global Person Completeness configuration."""
    global _config
    if _config is None:
        _config = PersonCompletenessConfig.from_env()
    return _config


def reset_config() -> None:
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None
