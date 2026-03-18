"""Deterministic persona artifact materialization."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List

from adk_core.schemas.artifacts import PersonaArtifact, PersonaQuote, ResearchArtifact, VoiceDna

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "he",
    "her",
    "his",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "she",
    "that",
    "the",
    "their",
    "they",
    "to",
    "was",
    "were",
    "with",
}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _top_terms(texts: List[str], limit: int = 8) -> List[str]:
    tokens: Counter[str] = Counter()
    for text in texts:
        for token in re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", text.lower()):
            if token in _STOPWORDS:
                continue
            tokens[token] += 1
    return [term for term, _count in tokens.most_common(limit)]


def _signature_phrases(quotes: List[str], limit: int = 6) -> List[str]:
    phrases: List[str] = []
    for quote in quotes:
        clean = _normalize_text(quote)
        if not clean:
            continue
        if len(clean.split()) <= 12:
            phrases.append(clean)
        else:
            phrases.append(" ".join(clean.split()[:12]))
    deduped: List[str] = []
    seen = set()
    for phrase in phrases:
        lowered = phrase.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(phrase)
        if len(deduped) >= limit:
            break
    return deduped


def _derive_voice_dna(research: ResearchArtifact) -> VoiceDna:
    quotes = [item.quote for item in research.verified_quote_candidates if item.quote]
    claim_texts = [item.text for item in research.extracted_claims if item.text]
    all_texts = quotes + claim_texts

    sentence_lengths = [len(_normalize_text(text).split()) for text in quotes if text]
    avg_sentence_length = sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0.0

    sentence_style: List[str] = []
    if avg_sentence_length >= 26:
        sentence_style.append("long-form sentences with layered clauses")
    elif avg_sentence_length >= 15:
        sentence_style.append("medium-length sentences with balanced pacing")
    else:
        sentence_style.append("short sentences with direct cadence")

    tonal_traits = []
    summary = _normalize_text(research.synthesis_summary).lower()
    if any(token in summary for token in ("builder", "operator", "execution", "ship")):
        tonal_traits.append("operator-minded and execution oriented")
    if any(token in summary for token in ("research", "evidence", "prove", "data")):
        tonal_traits.append("evidence first and analytical")
    if any(token in summary for token in ("mentor", "coach", "teach", "help")):
        tonal_traits.append("teacherly and generous")
    if not tonal_traits:
        tonal_traits.append("measured and grounded")

    return VoiceDna(
        tonal_traits=tonal_traits,
        sentence_style=sentence_style,
        lexical_preferences=_top_terms(all_texts, limit=10),
        signature_phrases=_signature_phrases(quotes),
    )


def _build_public_profile(research: ResearchArtifact, subject_name: str) -> Dict[str, object]:
    identity = research.subject_identity or {}
    return {
        "name": identity.get("canonical_name") or subject_name,
        "bio": _normalize_text(research.synthesis_summary),
        "headline": ", ".join(identity.get("public_roles") or [])[:240],
        "locations": identity.get("locations") or [],
        "organizations": identity.get("organizations") or [],
        "expertise_topics": identity.get("expertise_topics") or [],
    }


def _build_identity_pack(public_profile: Dict[str, object], voice_dna: VoiceDna) -> Dict[str, object]:
    return {
        "name": public_profile.get("name"),
        "headline": public_profile.get("headline"),
        "bio": public_profile.get("bio"),
        "signature_phrases": voice_dna.signature_phrases,
        "tonal_traits": voice_dna.tonal_traits,
        "lexical_preferences": voice_dna.lexical_preferences,
    }


def _build_thinking_style(research: ResearchArtifact) -> Dict[str, object]:
    claim_types = Counter(item.claim_type for item in research.extracted_claims if item.claim_type)
    dominant = [name for name, _count in claim_types.most_common(3)]
    if not dominant:
        dominant = ["operator"]
    return {
        "dominant_modes": dominant,
        "summary": _normalize_text(research.synthesis_summary),
    }


def _build_values(research: ResearchArtifact) -> List[str]:
    values: List[str] = []
    summary = _normalize_text(research.synthesis_summary).lower()
    if "trust" in summary or "credibility" in summary:
        values.append("opt for credibility over performative certainty")
    if "product" in summary or "builder" in summary:
        values.append("prefer shipping and iteration over abstract posturing")
    if "research" in summary or "evidence" in summary:
        values.append("show the evidence behind the conclusion")
    if not values:
        values.append("prefer clear evidence and concrete language")
    return values


def _build_communication_rules(research: ResearchArtifact, voice_dna: VoiceDna) -> List[str]:
    rules = [
        "Stay in the first-person voice of the subject.",
        "Sound like the subject, not like a generic assistant.",
        "Prefer grounded specifics over generic reassurance.",
    ]
    if voice_dna.signature_phrases:
        rules.append("Echo the subject's signature phrasing when it feels natural.")
    if research.verified_quote_candidates:
        rules.append("Use verified quotes as texture, not as constant direct quotation.")
    return rules


def materialize_persona_artifact(
    *,
    twin_id: str,
    research_artifact: ResearchArtifact,
) -> PersonaArtifact:
    subject_identity = research_artifact.subject_identity or {}
    subject_name = subject_identity.get("canonical_name") or subject_identity.get("name") or twin_id
    voice_dna = _derive_voice_dna(research_artifact)

    quote_pack = [
        PersonaQuote(
            quote=item.quote,
            source_id=item.source_id,
            confidence=item.confidence,
            context=item.context,
        )
        for item in research_artifact.verified_quote_candidates[:12]
    ]

    public_profile = _build_public_profile(research_artifact, subject_name)
    persona_identity_pack = _build_identity_pack(public_profile, voice_dna)

    retrieval_seeds = []
    retrieval_seeds.extend(
        [item.text for item in research_artifact.extracted_claims[:20] if _normalize_text(item.text)]
    )
    retrieval_seeds.extend(
        [item.event for item in research_artifact.timeline[:12] if _normalize_text(item.event)]
    )
    retrieval_seeds.extend(subject_identity.get("expertise_topics") or [])

    version = datetime.now(timezone.utc).strftime("adk-%Y%m%dT%H%M%SZ")

    return PersonaArtifact(
        twin_id=twin_id,
        version=version,
        subject_name=subject_name,
        identity_frame=subject_identity,
        thinking_style=_build_thinking_style(research_artifact),
        values_and_decision_heuristics=_build_values(research_artifact),
        communication_rules=_build_communication_rules(research_artifact, voice_dna),
        voice_dna=voice_dna,
        quote_pack=quote_pack,
        retrieval_seeds=[seed for seed in retrieval_seeds if _normalize_text(seed)],
        claims=research_artifact.extracted_claims,
        timeline=research_artifact.timeline,
        public_profile=public_profile,
        persona_identity_pack=persona_identity_pack,
        provenance={
            "research_summary": research_artifact.synthesis_summary,
            "source_count": len(research_artifact.source_registry),
            "claim_count": len(research_artifact.extracted_claims),
            "timeline_count": len(research_artifact.timeline),
            "quote_count": len(research_artifact.verified_quote_candidates),
            "compile_metadata": research_artifact.compile_metadata,
        },
    )
