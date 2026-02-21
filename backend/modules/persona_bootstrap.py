"""
Persona Bootstrap Module

Converts onboarding form data into a structured 5-Layer Persona Spec v2.
This is the canonical path for new twin creation - all new twins get a v2 persona.
"""

from typing import Any, Dict, List, Optional
from modules.persona_spec_v2 import (
    PersonaSpecV2,
    IdentityFrame,
    CognitiveHeuristics,
    CognitiveHeuristic,
    ValueHierarchy,
    ValueItem,
    ValueConflictRule,
    CommunicationPatterns,
    ResponseTemplate,
    MemoryAnchors,
    MemoryAnchor,
    SafetyBoundary,
    ScoringDimension,
)


def bootstrap_persona_from_onboarding(onboarding_data: Dict[str, Any]) -> PersonaSpecV2:
    """
    Canonical bootstrap function: Convert onboarding form data to 5-Layer Persona Spec v2.
    
    This is the PRIMARY and ONLY path for new twin persona creation.
    Legacy flattened system_prompt approach is DEPRECATED for new twins.
    
    Args:
        onboarding_data: Structured form data from frontend onboarding
        
    Returns:
        PersonaSpecV2 with all 5 layers populated
    """
    
    # Extract top-level fields
    twin_name = onboarding_data.get("twin_name", "Digital Twin")
    tagline = onboarding_data.get("tagline", "")
    role_definition = onboarding_data.get("role_definition", f"{twin_name} - {tagline}")
    
    # Layer 1: Identity Frame
    identity_frame = _build_identity_frame(onboarding_data)
    
    # Layer 2: Cognitive Heuristics
    cognitive_heuristics = _build_cognitive_heuristics(onboarding_data)
    
    # Layer 3: Value Hierarchy
    value_hierarchy = _build_value_hierarchy(onboarding_data)
    
    # Layer 4: Communication Patterns
    communication_patterns = _build_communication_patterns(onboarding_data)
    
    # Layer 5: Memory Anchors
    memory_anchors = _build_memory_anchors(onboarding_data)
    
    # Safety Boundaries
    safety_boundaries = _build_safety_boundaries(onboarding_data)
    
    return PersonaSpecV2(
        version="2.0.0",
        name=f"{twin_name} Persona",
        description=tagline or f"5-Layer cognitive persona for {twin_name}",
        identity_frame=identity_frame,
        cognitive_heuristics=cognitive_heuristics,
        value_hierarchy=value_hierarchy,
        communication_patterns=communication_patterns,
        memory_anchors=memory_anchors,
        safety_boundaries=safety_boundaries,
        status="active",  # Auto-publish
        source="onboarding_v2",
    )


def _build_identity_frame(data: Dict[str, Any]) -> IdentityFrame:
    """Build Layer 1: Identity Frame from onboarding data."""
    
    twin_name = data.get("twin_name", "Digital Twin")
    tagline = data.get("tagline", "")
    
    # Combine selected and custom expertise
    expertise_domains = [
        *data.get("selected_domains", []),
        *data.get("custom_expertise", [])
    ]
    
    # Determine role from specialization
    specialization = data.get("specialization", "vanilla")
    role_map = {
        "founder": f"Experienced founder and advisor - {twin_name}",
        "creator": f"Content creator and thought leader - {twin_name}",
        "technical": f"Technical expert and advisor - {twin_name}",
        "vanilla": f"Professional advisor - {twin_name}",
    }
    role_definition = data.get("role_definition", role_map.get(specialization, f"Advisor - {twin_name}"))
    
    # Background/success outcomes
    background = data.get("background", "")
    success_outcomes = data.get("success_outcomes", [])
    if success_outcomes:
        background += f"\nSuccess outcomes: {', '.join(success_outcomes)}"
    
    # Reasoning style from explicit selection or specialization default
    reasoning_style = data.get("reasoning_style", "balanced")
    if reasoning_style == "adaptive":
        reasoning_style = "balanced"
    
    # Relationship to user
    relationship = data.get("relationship_type", "advisor")
    
    # Scope and refusals
    scope = data.get("scope", "general")
    refusals = data.get("refusals", [])
    
    # Communication tendencies
    personality = data.get("personality", {})
    communication_tendencies = {
        "directness": _map_tone_to_directness(personality.get("tone", "friendly")),
        "formality": _map_tone_to_formality(personality.get("tone", "friendly")),
        "verbosity": personality.get("response_length", "balanced"),
    }
    
    return IdentityFrame(
        role_definition=role_definition,
        expertise_domains=expertise_domains,
        background_summary=background.strip(),
        reasoning_style=reasoning_style,
        relationship_to_user=relationship,
        scope=scope,
        refusals=refusals,
        communication_tendencies=communication_tendencies,
    )


def _build_cognitive_heuristics(data: Dict[str, Any]) -> CognitiveHeuristics:
    """Build Layer 2: Cognitive Heuristics from onboarding data."""
    
    heuristics: List[CognitiveHeuristic] = []
    
    # Get explicit heuristics or infer from specialization
    explicit_heuristics = data.get("heuristics", [])
    if explicit_heuristics:
        for i, h in enumerate(explicit_heuristics):
            heuristics.append(CognitiveHeuristic(
                id=h.get("id", f"heuristic_{i}"),
                name=h.get("name", "Unnamed Heuristic"),
                description=h.get("description", ""),
                applicable_query_types=h.get("applicable_types", ["evaluation"]),
                steps=h.get("steps", []),
                priority=h.get("priority", 50),
                active=True,
            ))
    else:
        # Infer heuristics from specialization and preferences
        heuristics = _infer_heuristics_from_specialization(data)
    
    # Decision framework
    framework = data.get("decision_framework", "evidence_based")
    
    # Evidence evaluation criteria
    evidence_criteria = data.get("evidence_standards", [
        "source_credibility",
        "recency",
        "relevance",
        "corroboration"
    ])
    
    # Confidence thresholds
    confidence_thresholds = data.get("confidence_thresholds", {
        "factual_question": 0.7,
        "evaluation_request": 0.8,
        "advice_request": 0.6,
    })
    
    # Clarifying behavior
    clarifying_behavior = data.get("clarifying_behavior", "ask")
    if clarifying_behavior == "ask":
        # Add clarify-first heuristic
        heuristics.append(CognitiveHeuristic(
            id="clarify_before_evaluate",
            name="Clarify Before Evaluating",
            description="Ask clarifying questions when information is insufficient for confident evaluation",
            applicable_query_types=["evaluation", "advice"],
            steps=["Assess information completeness", "Identify gaps", "Ask targeted questions"],
            priority=20,
            active=True,
        ))
    
    return CognitiveHeuristics(
        default_framework=framework,
        heuristics=heuristics,
        evidence_evaluation_criteria=evidence_criteria,
        confidence_thresholds=confidence_thresholds,
    )


def _infer_heuristics_from_specialization(data: Dict[str, Any]) -> List[CognitiveHeuristic]:
    """Infer default heuristics based on specialization."""
    
    specialization = data.get("specialization", "vanilla")
    what_i_look_for = data.get("what_i_look_for_first", "")
    
    heuristics = []
    
    if specialization == "founder" or "team" in what_i_look_for.lower():
        heuristics.append(CognitiveHeuristic(
            id="team_first_evaluation",
            name="Team-First Evaluation",
            description="Prioritize founder quality and team completeness in startup assessments",
            applicable_query_types=["evaluation", "startup_assessment"],
            steps=[
                "Evaluate founder background and domain expertise",
                "Assess team completeness (technical, business, domain)",
                "Check for relevant prior experience",
                "Only then evaluate market and traction"
            ],
            priority=10,
            active=True,
        ))
    
    if specialization == "technical":
        heuristics.append(CognitiveHeuristic(
            id="technical_feasibility",
            name="Technical Feasibility Assessment",
            description="Evaluate technical architecture, scalability, and implementation risk",
            applicable_query_types=["evaluation", "technical_review"],
            steps=[
                "Assess architecture soundness",
                "Evaluate scalability constraints",
                "Identify technical risks",
                "Check for defensible tech moats"
            ],
            priority=15,
            active=True,
        ))
    
    # Default evidence-based heuristic
    heuristics.append(CognitiveHeuristic(
        id="evidence_based_evaluation",
        name="Evidence-Based Evaluation",
        description="Base assessments on available evidence, disclose uncertainty",
        applicable_query_types=["evaluation", "analysis", "factual"],
        steps=[
            "Gather available evidence",
            "Assess evidence quality and relevance",
            "Form provisional assessment",
            "Disclose confidence level and gaps"
        ],
        priority=50,
        active=True,
    ))
    
    return heuristics


def _build_value_hierarchy(data: Dict[str, Any]) -> ValueHierarchy:
    """Build Layer 3: Value Hierarchy from onboarding data."""
    
    # Get prioritized values from drag-to-rank UI
    prioritized_values = data.get("prioritized_values", [])
    
    if not prioritized_values:
        # Default values based on specialization
        specialization = data.get("specialization", "vanilla")
        default_values = _get_default_values_for_specialization(specialization)
        prioritized_values = default_values
    
    # Build ValueItems with priorities
    values: List[ValueItem] = []
    for i, val in enumerate(prioritized_values):
        values.append(ValueItem(
            name=val.get("name", f"value_{i}"),
            priority=i + 1,  # 1 is highest
            description=val.get("description", ""),
            applicable_contexts=val.get("contexts", []),
        ))
    
    # Conflict rules from tradeoff preferences
    conflict_rules: List[ValueConflictRule] = []
    tradeoffs = data.get("tradeoff_preferences", [])
    for tradeoff in tradeoffs:
        conflict_rules.append(ValueConflictRule(
            value_a=tradeoff.get("value_a", ""),
            value_b=tradeoff.get("value_b", ""),
            resolution=tradeoff.get("resolution", "context_dependent"),
            context_override=tradeoff.get("context_override"),
        ))
    
    # Add default conflict rules if none provided
    if not conflict_rules:
        conflict_rules = [
            ValueConflictRule(
                value_a="speed",
                value_b="quality",
                resolution="context_dependent",
                context_override="prioritize_quality for final deliverables, speed for MVPs",
            ),
            ValueConflictRule(
                value_a="team_quality",
                value_b="market_size",
                resolution="prioritize_a",
                context_override=None,
            ),
        ]
    
    # Scoring dimensions with rubrics
    scoring_dimensions = _build_scoring_dimensions(data)
    
    return ValueHierarchy(
        values=values,
        conflict_rules=conflict_rules,
        scoring_dimensions=scoring_dimensions,
    )


def _get_default_values_for_specialization(specialization: str) -> List[Dict[str, Any]]:
    """Get default value priorities based on specialization."""
    
    defaults = {
        "founder": [
            {"name": "team_quality", "description": "Strong founding team with relevant experience"},
            {"name": "market_size", "description": "Large addressable market with growth potential"},
            {"name": "traction", "description": "Evidence of product-market fit"},
            {"name": "defensibility", "description": "Sustainable competitive advantage"},
            {"name": "speed", "description": "Velocity of execution and iteration"},
        ],
        "technical": [
            {"name": "technical_excellence", "description": "Sound architecture and implementation"},
            {"name": "scalability", "description": "Ability to handle growth"},
            {"name": "security", "description": "Security and privacy considerations"},
            {"name": "maintainability", "description": "Code quality and documentation"},
            {"name": "innovation", "description": "Novel approaches and defensible tech"},
        ],
        "vanilla": [
            {"name": "quality", "description": "High standards in work"},
            {"name": "clarity", "description": "Clear and understandable communication"},
            {"name": "helpfulness", "description": "Actually solving user's problem"},
            {"name": "honesty", "description": "Truthful about limitations and uncertainty"},
            {"name": "efficiency", "description": "Respecting user's time"},
        ],
    }
    
    return defaults.get(specialization, defaults["vanilla"])


def _build_scoring_dimensions(data: Dict[str, Any]) -> List[ScoringDimension]:
    """Build scoring dimensions with 1-5 rubrics."""
    
    # Get explicit dimensions or use defaults
    dimensions = data.get("scoring_dimensions", [])
    
    if not dimensions:
        # Default startup evaluation dimensions
        dimensions = [
            {
                "name": "market",
                "description": "Market size and growth potential",
                "weight": 1.0,
            },
            {
                "name": "founder",
                "description": "Founder/market fit and team strength",
                "weight": 1.2,
            },
            {
                "name": "traction",
                "description": "Evidence of product-market fit",
                "weight": 1.0,
            },
            {
                "name": "defensibility",
                "description": "Competitive moat and barriers to entry",
                "weight": 0.9,
            },
            {
                "name": "speed",
                "description": "Velocity of execution and iteration",
                "weight": 0.8,
            },
        ]
    
    scoring_dimensions: List[ScoringDimension] = []
    for dim in dimensions:
        name = dim.get("name", "unknown")
        # Get rubric definitions or use defaults
        rubric = dim.get("rubric", _get_default_rubric(name))
        
        scoring_dimensions.append(ScoringDimension(
            name=name,
            description=dim.get("description", ""),
            weight=dim.get("weight", 1.0),
            scoring_criteria=rubric,
        ))
    
    return scoring_dimensions


def _get_default_rubric(dimension_name: str) -> Dict[int, str]:
    """Get default 1-5 scoring rubric for a dimension."""
    
    rubrics = {
        "market": {
            1: "Tiny or shrinking market (<$10M), no growth",
            2: "Small niche market, limited growth potential",
            3: "Moderate market, some growth, competitive",
            4: "Large market ($1B+), strong growth trajectory",
            5: "Massive market ($10B+), explosive growth, timing is right",
        },
        "founder": {
            1: "No relevant experience, first-time founders, gaps in team",
            2: "Some relevant experience but gaps, unproven team",
            3: "Solid team with relevant experience, some gaps",
            4: "Strong team, proven track record, domain expertise",
            5: "Exceptional team, prior success, deep domain expertise, complete skill set",
        },
        "traction": {
            1: "No traction, pre-product, no validation",
            2: "Early validation, some interest, no paying customers",
            3: "Early customers, some revenue, product working",
            4: "Strong growth, product-market fit signals, healthy unit economics",
            5: "Clear product-market fit, rapid growth, excellent retention, scalable acquisition",
        },
        "defensibility": {
            1: "No moat, easily copyable, commodity product",
            2: "Weak differentiation, some brand but easily replicated",
            3: "Moderate moat through brand or network effects beginning",
            4: "Strong moat - proprietary tech, network effects, or exclusive relationships",
            5: "Unassailable moat - multiple reinforcing advantages, regulatory barriers, or deep network effects",
        },
        "speed": {
            1: "Slow execution, missed deadlines, no shipping",
            2: "Inconsistent execution, occasional delays",
            3: "Steady execution, meeting reasonable deadlines",
            4: "Fast execution, rapid iteration, quick to market",
            5: "Exceptional velocity, weekly shipping, rapid learning and pivoting",
        },
    }
    
    return rubrics.get(dimension_name, {
        1: "Poor - significant issues",
        2: "Below average - some concerns",
        3: "Average - acceptable",
        4: "Good - above average",
        5: "Excellent - exceptional",
    })


def _build_communication_patterns(data: Dict[str, Any]) -> CommunicationPatterns:
    """Build Layer 4: Communication Patterns from onboarding data."""
    
    personality = data.get("personality", {})
    
    # Response templates based on intent
    templates = _build_response_templates(personality)
    
    # Signature phrases
    signature_phrases = data.get("signature_phrases", [])
    if not signature_phrases:
        # Default based on tone
        tone = personality.get("tone", "friendly")
        signature_phrases = _get_default_signatures(tone)
    
    # Linguistic markers
    linguistic_markers = _build_linguistic_markers(personality)
    
    # Anti-patterns (phrases to avoid)
    anti_patterns = data.get("anti_patterns", [
        "As an AI language model",
        "I don't have personal opinions",
        "I cannot provide investment advice",  # We'll handle this via safety boundaries
    ])
    
    # Brevity preference
    brevity = personality.get("response_length", "balanced")
    
    return CommunicationPatterns(
        response_templates=templates,
        signature_phrases=signature_phrases,
        linguistic_markers=linguistic_markers,
        anti_patterns=anti_patterns,
        brevity_preference=brevity,
    )


def _build_response_templates(personality: Dict[str, Any]) -> List[ResponseTemplate]:
    """Build response templates for different intents."""
    
    tone = personality.get("tone", "friendly")
    first_person = personality.get("firstPerson", True)
    
    subject = "I" if first_person else "This"
    possessive = "my" if first_person else "the"
    
    templates = [
        ResponseTemplate(
            id="evaluation_positive",
            intent_label="evaluation",
            template=f"{{{{subject}}}} thinks this looks promising. {{{{subject}}}} is particularly impressed by {{{{strength}}}}. Overall assessment: {{{{overall_score}}}}/5.",
            required_slots=["subject", "strength", "overall_score"],
        ),
        ResponseTemplate(
            id="evaluation_mixed",
            intent_label="evaluation",
            template=f"{{{{subject}}}} sees both strengths and concerns here. {{{{subject}}}} likes {{{{strength}}}}, but {{{{concern}}}} gives {{{{subject}}}} pause. Overall: {{{{overall_score}}}}/5.",
            required_slots=["subject", "strength", "concern", "overall_score"],
        ),
        ResponseTemplate(
            id="evaluation_negative",
            intent_label="evaluation",
            template=f"{{{{subject}}}} has some reservations about this. {{{{subject}}}} is concerned about {{{{concern}}}}. Overall assessment: {{{{overall_score}}}}/5.",
            required_slots=["subject", "concern", "overall_score"],
        ),
        ResponseTemplate(
            id="clarification_needed",
            intent_label="clarification",
            template=f"{{{{subject}}}} needs to understand {{{{missing_info}}}} before {{{{subject}}}} can give {{{{possessive}}}} best assessment. Can you clarify?",
            required_slots=["subject", "missing_info", "possessive"],
        ),
    ]
    
    return templates


def _get_default_signatures(tone: str) -> List[str]:
    """Get default signature phrases based on tone."""
    
    signatures = {
        "friendly": ["Here's the thing...", "I think what's important here is..."],
        "professional": ["From my perspective...", "The key consideration is..."],
        "technical": ["The data suggests...", "Technically speaking..."],
        "casual": ["Look, here's my take...", "Honestly? I think..."],
    }
    
    return signatures.get(tone, signatures["friendly"])


def _build_linguistic_markers(personality: Dict[str, Any]) -> Dict[str, List[str]]:
    """Build linguistic markers for different contexts."""
    
    tone = personality.get("tone", "friendly")
    
    markers = {
        "friendly": {
            "agreement": ["I think that's right", "Absolutely", "Makes sense to me"],
            "disagreement": ["I see it a bit differently", "I'd push back on that", "Not sure I agree"],
            "uncertainty": ["I'm not certain", "It's unclear", "Hard to say"],
            "emphasis": ["Here's the thing", "What matters is", "The key point"],
        },
        "professional": {
            "agreement": ["I concur", "That aligns with my assessment", "Correct"],
            "disagreement": ["I respectfully disagree", "My analysis differs", "I see it another way"],
            "uncertainty": ["The evidence is inconclusive", "More data needed", "Unclear at this time"],
            "emphasis": ["The critical factor", "Most importantly", "The key consideration"],
        },
        "technical": {
            "agreement": ["Confirmed", "Validates with data", "Technically correct"],
            "disagreement": ["Contradicts the data", "Not supported by evidence", "Incorrect assumption"],
            "uncertainty": ["Insufficient data", "Unvalidated hypothesis", "Requires testing"],
            "emphasis": ["The bottleneck is", "The constraint is", "The critical path"],
        },
    }
    
    return markers.get(tone, markers["friendly"])


def _build_memory_anchors(data: Dict[str, Any]) -> MemoryAnchors:
    """Build Layer 5: Memory Anchors from onboarding data."""
    
    anchors: List[MemoryAnchor] = []
    
    # Key experiences
    experiences = data.get("key_experiences", [])
    for i, exp in enumerate(experiences):
        anchors.append(MemoryAnchor(
            id=f"experience_{i}",
            type="experience",
            content=exp.get("content", ""),
            context=exp.get("context", ""),
            applicable_intents=exp.get("applicable_intents", ["evaluation"]),
            weight=exp.get("weight", 0.8),
            tags=exp.get("tags", []),
        ))
    
    # Lessons learned
    lessons = data.get("lessons_learned", [])
    for i, lesson in enumerate(lessons):
        anchors.append(MemoryAnchor(
            id=f"lesson_{i}",
            type="lesson",
            content=lesson.get("content", ""),
            context=lesson.get("context", "General principle"),
            applicable_intents=lesson.get("applicable_intents", ["advice", "evaluation"]),
            weight=lesson.get("weight", 0.9),
            tags=["lesson", "principle"],
        ))
    
    # Recurring patterns
    patterns = data.get("recurring_patterns", [])
    for i, pattern in enumerate(patterns):
        anchors.append(MemoryAnchor(
            id=f"pattern_{i}",
            type="pattern",
            content=pattern.get("content", ""),
            context=pattern.get("context", ""),
            applicable_intents=pattern.get("applicable_intents", []),
            weight=pattern.get("weight", 0.7),
            tags=["pattern"],
        ))
    
    return MemoryAnchors(
        anchors=anchors,
        max_anchors_per_query=3,
        retrieval_threshold=0.7,
    )


def _build_safety_boundaries(data: Dict[str, Any]) -> List[SafetyBoundary]:
    """Build safety boundaries from onboarding data."""
    
    boundaries: List[SafetyBoundary] = []
    
    # Always add investment advice boundary
    boundaries.append(SafetyBoundary(
        id="no_investment_promises",
        pattern=r"(should I invest|is this a good investment|will this make money|should I put money in|investment advice)",
        category="investment_promise",
        action="refuse",
        refusal_template="I can't provide investment advice. I can share my perspective on the team and market, but you should consult with a financial advisor for investment decisions.",
        is_regex=True,
    ))
    
    # Always add legal advice boundary
    boundaries.append(SafetyBoundary(
        id="no_legal_advice",
        pattern=r"(is this legal|can I do this legally|legal implications|legal advice|lawyer|attorney)",
        category="legal_advice",
        action="refuse",
        refusal_template="I'm not qualified to provide legal advice. Please consult with a legal professional for guidance on legal matters.",
        is_regex=True,
    ))
    
    # Always add medical advice boundary
    boundaries.append(SafetyBoundary(
        id="no_medical_advice",
        pattern=r"(should I take|medical advice|doctor|health|diagnosis|treatment|medication)",
        category="medical_advice",
        action="refuse",
        refusal_template="I'm not qualified to provide medical advice. Please consult with a healthcare professional for medical concerns.",
        is_regex=True,
    ))
    
    # Add user-defined boundaries
    user_boundaries = data.get("safety_boundaries", [])
    for i, boundary in enumerate(user_boundaries):
        boundaries.append(SafetyBoundary(
            id=boundary.get("id", f"user_boundary_{i}"),
            pattern=boundary.get("pattern", ""),
            category=boundary.get("category", "harmful"),
            action=boundary.get("action", "refuse"),
            refusal_template=boundary.get("refusal_template", "I'm not able to provide that guidance."),
            is_regex=boundary.get("is_regex", True),
        ))
    
    return boundaries


# Helper functions for tone mapping

def _map_tone_to_directness(tone: str) -> str:
    """Map personality tone to directness level."""
    mapping = {
        "friendly": "moderate",
        "professional": "moderate",
        "technical": "direct",
        "casual": "moderate",
    }
    return mapping.get(tone, "moderate")


def _map_tone_to_formality(tone: str) -> str:
    """Map personality tone to formality level."""
    mapping = {
        "friendly": "casual",
        "professional": "professional",
        "technical": "professional",
        "casual": "casual",
    }
    return mapping.get(tone, "professional")
