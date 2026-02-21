"""
persona_claim_inference.py

Phase 3 Component: Build PersonaSpecV2 from claims with inference honesty.
Links claims to persona layers and generates clarification interview.
"""

import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from modules.persona_spec_v2 import (
    PersonaSpecV2,
    CognitiveHeuristic,
    CognitiveHeuristics,
    ValueItem,
    ValueHierarchy,
)
from modules.persona_claim_extractor import ClaimStore


# =============================================================================
# Layer Item with Evidence
# =============================================================================

@dataclass
class LayerItemWithEvidence:
    """A persona layer item with supporting evidence claims."""
    item_id: str
    name: str
    description: str
    claim_ids: List[str]
    verification_required: bool
    confidence: float  # Aggregated from claims


# =============================================================================
# Clarification Question Generator
# =============================================================================

CLARIFICATION_QUESTION_TEMPLATES = {
    "heuristic": [
        "When evaluating {topic}, what specific criteria do you look for first?",
        "Can you walk me through how you think through {topic} decisions?",
        "What red flags do you watch for with {topic}?",
    ],
    "value": [
        "When forced to choose between {value_a} and {value_b}, which wins?",
        "How do you apply {value} in practice?",
        "What does {value} mean to you specifically?",
    ],
    "preference": [
        "Do you have a strong preference regarding {topic}?",
        "What do you look for in {topic}?",
    ],
    "belief": [
        "What do you believe about {topic}?",
        "How did you form your perspective on {topic}?",
    ],
}


class ClarificationInterviewGenerator:
    """Generate clarification questions for low-confidence Layer 2/3 items."""
    
    def __init__(self, min_confidence_threshold: float = 0.6):
        self.min_confidence = min_confidence_threshold
    
    def generate_questions(
        self,
        cognitive_items: List[LayerItemWithEvidence],
        value_items: List[LayerItemWithEvidence],
    ) -> List[Dict[str, Any]]:
        """
        Generate clarification questions for low-confidence items.
        
        Returns list of questions with metadata.
        """
        questions = []
        
        # Filter to low-confidence Layer 2 (Cognitive) items
        for item in cognitive_items:
            if item.confidence < self.min_confidence and item.verification_required:
                templates = CLARIFICATION_QUESTION_TEMPLATES.get("heuristic", [])
                for template in templates[:2]:  # Top 2 questions per item
                    questions.append({
                        "target_layer": "cognitive",
                        "target_item_id": item.item_id,
                        "question": template.format(topic=item.name),
                        "current_confidence": item.confidence,
                        "purpose": "clarify_heuristic",
                    })
        
        # Filter to low-confidence Layer 3 (Values) items
        for item in value_items:
            if item.confidence < self.min_confidence and item.verification_required:
                templates = CLARIFICATION_QUESTION_TEMPLATES.get("value", [])
                for template in templates[:2]:
                    questions.append({
                        "target_layer": "values",
                        "target_item_id": item.item_id,
                        "question": template.format(value=item.name),
                        "current_confidence": item.confidence,
                        "purpose": "clarify_value",
                    })
        
        # Sort by confidence (lowest first) and limit to 10
        questions.sort(key=lambda q: q["current_confidence"])
        
        return questions[:10]


# =============================================================================
# Persona Compiler from Claims
# =============================================================================

class PersonaFromClaimsCompiler:
    """Compile PersonaSpecV2 from extracted claims."""
    
    def __init__(self, supabase_client):
        self.db = supabase_client
        self.claim_store = ClaimStore(supabase_client)
    
    def _aggregate_claims_by_type(
        self,
        claims: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group claims by type."""
        grouped = {
            "heuristic": [],
            "value": [],
            "preference": [],
            "belief": [],
            "experience": [],
            "boundary": [],
        }
        
        for claim in claims:
            claim_type = claim.get("claim_type", "uncertain")
            if claim_type in grouped:
                grouped[claim_type].append(claim)
        
        return grouped
    
    def _build_cognitive_heuristics(
        self,
        heuristic_claims: List[Dict[str, Any]],
    ) -> CognitiveHeuristics:
        """
        Build Layer 2: Cognitive Heuristics from claims.
        
        RULE: verification_required defaults to True unless:
        - Multiple supporting claims exist (confidence > 0.7)
        - Owner_direct authority claims present
        """
        heuristics = []
        
        # Group similar heuristics (simple approach: by keywords)
        heuristic_groups: Dict[str, List[Dict]] = {}
        
        for claim in heuristic_claims:
            claim_text = claim.get("claim_text", "").lower()
            
            # Extract topic keywords
            keywords = self._extract_keywords(claim_text)
            group_key = "_".join(sorted(keywords[:3])) if keywords else "general"
            
            if group_key not in heuristic_groups:
                heuristic_groups[group_key] = []
            heuristic_groups[group_key].append(claim)
        
        # Build heuristics from groups
        for idx, (group_key, group_claims) in enumerate(heuristic_groups.items()):
            # Calculate confidence
            avg_confidence = sum(c.get("confidence", 0.5) for c in group_claims) / len(group_claims)
            
            # Check for owner_direct authority
            has_owner_direct = any(
                c.get("authority") == "owner_direct" for c in group_claims
            )
            
            # Determine verification_required
            # DEFAULT: True (inference honesty)
            # EXCEPTION: High confidence + owner_direct OR multiple strong claims
            if has_owner_direct and avg_confidence > 0.8:
                verification_required = False
            elif len(group_claims) >= 3 and avg_confidence > 0.75:
                verification_required = False
            else:
                verification_required = True
            
            # Build heuristic description from claims
            claim_texts = [c.get("claim_text", "") for c in group_claims[:3]]
            description = " ".join(claim_texts)
            
            heuristic = CognitiveHeuristic(
                id=f"heuristic_{idx}_{group_key[:20]}",
                name=self._generate_heuristic_name(group_key),
                description=description[:500],
                applicable_query_types=["evaluation", "analysis"],
                steps=claim_texts[:5],
                priority=50,
                active=True,
                verification_required=verification_required,
                evidence_claim_ids=[c.get("id") for c in group_claims],
                confidence=round(avg_confidence, 2),
            )
            
            heuristics.append(heuristic)
        
        return CognitiveHeuristics(
            default_framework="evidence_based",
            heuristics=heuristics,
            evidence_evaluation_criteria=[
                "source_credibility",
                "recency",
                "relevance",
                "corroboration",
            ],
        )
    
    def _build_value_hierarchy(
        self,
        value_claims: List[Dict[str, Any]],
    ) -> ValueHierarchy:
        """
        Build Layer 3: Value Hierarchy from claims.
        
        RULE: verification_required defaults to True unless:
        - Explicit owner_direct value statement
        - Multiple corroborating claims
        """
        values = []
        
        # Group value claims by value name (extracted from claim text)
        value_groups: Dict[str, List[Dict]] = {}
        
        for claim in value_claims:
            claim_text = claim.get("claim_text", "")
            
            # Extract value name (simplified: first noun phrase)
            value_name = self._extract_value_name(claim_text)
            
            if value_name not in value_groups:
                value_groups[value_name] = []
            value_groups[value_name].append(claim)
        
        # Sort by frequency (most mentioned = higher priority)
        sorted_values = sorted(
            value_groups.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )
        
        for priority, (value_name, group_claims) in enumerate(sorted_values[:10], 1):
            # Calculate confidence
            avg_confidence = sum(c.get("confidence", 0.5) for c in group_claims) / len(group_claims)
            
            # Check authorities
            has_owner_direct = any(c.get("authority") == "owner_direct" for c in group_claims)
            
            # Determine verification_required
            # DEFAULT: True (inference honesty)
            if has_owner_direct and avg_confidence > 0.85:
                verification_required = False
            elif len(group_claims) >= 2 and avg_confidence > 0.8:
                verification_required = False
            else:
                verification_required = True
            
            # Build description
            descriptions = [c.get("claim_text", "") for c in group_claims[:2]]
            description = " ".join(descriptions)
            
            value_item = ValueItem(
                name=value_name,
                priority=priority,
                description=description[:300],
                applicable_contexts=["general"],
                verification_required=verification_required,
                evidence_claim_ids=[c.get("id") for c in group_claims],
                confidence=round(avg_confidence, 2),
            )
            
            values.append(value_item)
        
        return ValueHierarchy(
            values=values,
            conflict_rules=[],  # TODO: Generate from boundary claims
        )
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract topic keywords from text."""
        # Simple keyword extraction
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        words = text.lower().split()
        keywords = [w.strip(".,!?;:") for w in words if len(w) > 3 and w not in stop_words]
        return list(dict.fromkeys(keywords))[:5]  # Deduplicate and limit
    
    def _extract_value_name(self, claim_text: str) -> str:
        """Extract value name from claim text."""
        # Look for patterns like "X is important" or "I value X"
        patterns = [
            r"I value ([^.,]+)",
            r"([^.,]+) is (?:important|critical|essential)",
            r"priority is ([^.,]+)",
        ]
        
        import re
        for pattern in patterns:
            match = re.search(pattern, claim_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:50]
        
        # Fallback: return first few words
        words = claim_text.split()[:3]
        return " ".join(words)[:50]
    
    def _generate_heuristic_name(self, group_key: str) -> str:
        """Generate human-readable heuristic name."""
        words = group_key.replace("_", " ").split()
        return " ".join(words[:3]).title()[:50] or "General Evaluation"
    
    async def compile_persona(
        self,
        twin_id: str,
        existing_spec: Optional[PersonaSpecV2] = None,
    ) -> Dict[str, Any]:
        """
        Compile PersonaSpecV2 from claims for a twin.
        
        Returns:
            {
                "persona_spec": PersonaSpecV2,
                "cognitive_items": List[LayerItemWithEvidence],
                "value_items": List[LayerItemWithEvidence],
                "clarification_questions": List[Dict],
            }
        """
        # Fetch all active claims
        claims = await self.claim_store.get_claims_for_twin(
            twin_id=twin_id,
            min_confidence=0.3,
        )
        
        if not claims:
            return {
                "persona_spec": existing_spec or PersonaSpecV2(),
                "cognitive_items": [],
                "value_items": [],
                "clarification_questions": [],
            }
        
        # Group by type
        grouped = self._aggregate_claims_by_type(claims)
        
        # Build Layer 2: Cognitive Heuristics
        cognitive = self._build_cognitive_heuristics(grouped.get("heuristic", []))
        
        # Build Layer 3: Value Hierarchy
        values = self._build_value_hierarchy(grouped.get("value", []))
        
        # Build Layer Item summaries for clarification
        cognitive_items = [
            LayerItemWithEvidence(
                item_id=h.id,
                name=h.name,
                description=h.description,
                claim_ids=h.evidence_claim_ids,
                verification_required=h.verification_required,
                confidence=h.confidence,
            )
            for h in cognitive.heuristics
        ]
        
        value_items = [
            LayerItemWithEvidence(
                item_id=f"value_{v.name}",
                name=v.name,
                description=v.description,
                claim_ids=v.evidence_claim_ids,
                verification_required=v.verification_required,
                confidence=v.confidence,
            )
            for v in values.values
        ]
        
        # Generate clarification questions
        interview_gen = ClarificationInterviewGenerator(min_confidence_threshold=0.6)
        questions = interview_gen.generate_questions(cognitive_items, value_items)
        
        # Build full persona spec
        if existing_spec:
            # Merge with existing
            persona_spec = existing_spec
            persona_spec.cognitive_heuristics = cognitive
            persona_spec.value_hierarchy = values
        else:
            from modules.persona_spec_v2 import IdentityFrame, CommunicationPatterns, MemoryAnchors
            
            persona_spec = PersonaSpecV2(
                version="2.0.0-link-first",
                name="Link-First Persona",
                identity_frame=IdentityFrame(),
                cognitive_heuristics=cognitive,
                value_hierarchy=values,
                communication_patterns=CommunicationPatterns(),
                memory_anchors=MemoryAnchors(),
            )
        
        return {
            "persona_spec": persona_spec,
            "cognitive_items": cognitive_items,
            "value_items": value_items,
            "clarification_questions": questions,
        }


# =============================================================================
# Clarification Answer Handler
# =============================================================================

async def handle_clarification_answer(
    twin_id: str,
    question: Dict[str, Any],
    answer: str,
    supabase_client,
) -> Dict[str, Any]:
    """
    Process owner clarification answer and create owner_direct claim.
    
    Args:
        twin_id: Twin ID
        question: Clarification question metadata
        answer: Owner's answer text
        supabase_client: Database client
    
    Returns:
        {
            "claim_id": str,
            "updated_layer": str,
            "new_confidence": float,
        }
    """
    from modules.persona_claim_extractor import ClaimExtractor, ClaimCitation
    
    # Extract claim from answer
    extractor = ClaimExtractor()
    
    # Create a synthetic source for the clarification
    source_id = f"clarification_{datetime.utcnow().isoformat()}"
    
    # For clarification answers, we store them directly as owner_direct claims
    # without requiring span validation (since there's no external source)
    claim = PersonaClaim(
        twin_id=twin_id,
        claim_text=answer,
        claim_type=question.get("target_layer", "belief"),
        citation=ClaimCitation(
            source_id=source_id,
            span_start=0,
            span_end=len(answer),
            quote=answer,
            content_hash=hashlib.sha256(answer.encode()).hexdigest(),
        ),
        authority="owner_direct",
        confidence=0.95,  # High confidence for direct owner input
        extractor_model="owner_clarification",
    )
    
    # Store claim
    store = ClaimStore(supabase_client)
    claim_ids = await store.save_claims([claim])
    
    # Update the linked layer item
    if claim_ids:
        claim_id = claim_ids[0]
        
        # Update verification status
        target_item_id = question.get("target_item_id")
        target_layer = question.get("target_layer")
        
        # Link claim to layer
        link_data = {
            "claim_id": claim_id,
            "twin_id": twin_id,
            "layer_name": target_layer,
            "layer_item_id": target_item_id,
            "link_type": "primary",
            "verification_required": False,  # Owner direct = no verification needed
        }
        
        try:
            supabase_client.table("persona_claim_links").insert(link_data).execute()
        except Exception as e:
            print(f"[Clarification] Failed to link claim: {e}")
        
        return {
            "claim_id": claim_id,
            "updated_layer": target_layer,
            "new_confidence": 0.95,
        }
    
    return {"error": "Failed to store clarification claim"}
