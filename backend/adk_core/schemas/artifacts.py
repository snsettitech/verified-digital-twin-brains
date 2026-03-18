"""Canonical artifact contracts for the ADK runtime."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ResearchSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    url: str
    title: str = ""
    snippet: str = ""
    extracted_text: str = ""
    provider: str = ""
    quality: str = "unknown"
    published_at: Optional[str] = None


class ResearchClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    text: str
    claim_type: str = "other"
    confidence: float = 0.0
    source_ids: List[str] = Field(default_factory=list)


class ResearchTimelineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_or_range: str
    event: str
    confidence: float = 0.0
    source_ids: List[str] = Field(default_factory=list)


class ResearchQuoteCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quote: str
    source_id: str
    confidence: float = 0.0
    speaker: Optional[str] = None
    context: str = ""


class ResearchArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_identity: Dict[str, Any] = Field(default_factory=dict)
    source_registry: List[ResearchSource] = Field(default_factory=list)
    extracted_claims: List[ResearchClaim] = Field(default_factory=list)
    timeline: List[ResearchTimelineItem] = Field(default_factory=list)
    verified_quote_candidates: List[ResearchQuoteCandidate] = Field(default_factory=list)
    synthesis_summary: str = ""
    compile_metadata: Dict[str, Any] = Field(default_factory=dict)


class VoiceDna(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tonal_traits: List[str] = Field(default_factory=list)
    sentence_style: List[str] = Field(default_factory=list)
    lexical_preferences: List[str] = Field(default_factory=list)
    signature_phrases: List[str] = Field(default_factory=list)


class PersonaQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quote: str
    source_id: str
    confidence: float = 0.0
    context: str = ""


class PersonaArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    twin_id: str
    version: str
    subject_name: str
    status: Literal["draft", "active", "archived"] = "active"
    identity_frame: Dict[str, Any] = Field(default_factory=dict)
    thinking_style: Dict[str, Any] = Field(default_factory=dict)
    values_and_decision_heuristics: List[str] = Field(default_factory=list)
    communication_rules: List[str] = Field(default_factory=list)
    voice_dna: VoiceDna = Field(default_factory=VoiceDna)
    quote_pack: List[PersonaQuote] = Field(default_factory=list)
    retrieval_seeds: List[str] = Field(default_factory=list)
    claims: List[ResearchClaim] = Field(default_factory=list)
    timeline: List[ResearchTimelineItem] = Field(default_factory=list)
    public_profile: Dict[str, Any] = Field(default_factory=dict)
    persona_identity_pack: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
