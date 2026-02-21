"""
Persona Migration Utilities

Handles migration from v1 (legacy) to v2 (5-Layer) persona specs.

Usage:
    from modules.persona_migration import migrate_v1_to_v2, MigrationValidator
    
    # Migrate a single spec
    v2_spec = migrate_v1_to_v2(v1_spec_dict)
    
    # Validate migration
    validator = MigrationValidator()
    result = validator.validate_migration(v1_spec_dict, v2_spec)
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from modules.persona_spec import PersonaSpec as PersonaSpecV1
from modules.persona_spec_v2 import (
    PersonaSpecV2,
    IdentityFrame,
    CognitiveHeuristics,
    CognitiveHeuristic,
    ValueHierarchy,
    ValueItem,
    ValueConflictRule,
    CommunicationPatterns,
    MemoryAnchor,
    MemoryAnchors,
    SafetyBoundary,
)


# =============================================================================
# Migration Configuration
# =============================================================================

DEFAULT_SAFETY_BOUNDARIES = [
    SafetyBoundary(
        id="no_investment_promises",
        pattern=r"(should I invest|is this a good investment|will this make money|should I put money in)",
        category="investment_promise",
        action="refuse",
        refusal_template="I can't provide investment advice. I can share my perspective on the team and market, but you should consult with a financial advisor for investment decisions.",
        is_regex=True,
    ),
    SafetyBoundary(
        id="no_legal_advice",
        pattern=r"(is this legal|can I do this legally|legal implications|legal advice|lawyer)",
        category="legal_advice",
        action="refuse",
        refusal_template="I'm not qualified to provide legal advice. Please consult with a legal professional for guidance on legal matters.",
        is_regex=True,
    ),
    SafetyBoundary(
        id="no_medical_advice",
        pattern=r"(should I take|medical advice|doctor|health|diagnosis|treatment)",
        category="medical_advice",
        action="refuse",
        refusal_template="I'm not qualified to provide medical advice. Please consult with a healthcare professional for medical concerns.",
        is_regex=True,
    ),
    SafetyBoundary(
        id="no_confidential_info",
        pattern=r"(password|api key|secret|token|credential|private key)",
        category="confidential_info",
        action="escalate",
        refusal_template="I can't help with confidential information like passwords or API keys. Please handle these securely.",
        is_regex=True,
    ),
]

DEFAULT_COGNITIVE_HEURISTICS = [
    CognitiveHeuristic(
        id="evidence_evaluation",
        name="Evidence-Based Evaluation",
        description="Evaluate claims based on available evidence quality and quantity",
        applicable_query_types=["factual", "evaluation", "analysis"],
        steps=[
            "Identify claims to evaluate",
            "Gather available evidence",
            "Assess evidence quality",
            "Determine confidence level",
            "Form conclusion"
        ],
        priority=10,
    ),
    CognitiveHeuristic(
        id="first_principles",
        name="First Principles Analysis",
        description="Break down problems to fundamental truths and build up",
        applicable_query_types=["strategy", "problem_solving", "innovation"],
        steps=[
            "Identify fundamental truths",
            "Question assumptions",
            "Build from fundamentals",
            "Validate conclusions"
        ],
        priority=20,
    ),
    CognitiveHeuristic(
        id="comparative_analysis",
        name="Comparative Analysis",
        description="Compare against known benchmarks or alternatives",
        applicable_query_types=["evaluation", "comparison", "benchmarking"],
        steps=[
            "Identify comparison points",
            "Establish criteria",
            "Compare systematically",
            "Draw relative conclusions"
        ],
        priority=30,
    ),
]

DEFAULT_VALUE_CONFLICT_RULES = [
    ValueConflictRule(
        value_a="speed",
        value_b="quality",
        resolution="context_dependent",
        context_override="prioritize_quality when evaluating final deliverables"
    ),
    ValueConflictRule(
        value_a="transparency",
        value_b="privacy",
        resolution="context_dependent",
        context_override="prioritize_privacy when dealing with personal data"
    ),
]


# =============================================================================
# Migration Result
# =============================================================================

@dataclass
class MigrationIssue:
    """Issue encountered during migration"""
    field: str
    issue_type: str  # "warning", "error", "info"
    message: str
    suggestion: Optional[str] = None


@dataclass
class MigrationResult:
    """Result of a migration operation"""
    success: bool
    v2_spec: Optional[PersonaSpecV2]
    issues: List[MigrationIssue] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_issue(self, field: str, issue_type: str, message: str, suggestion: Optional[str] = None):
        self.issues.append(MigrationIssue(field, issue_type, message, suggestion))
        if issue_type == "warning":
            self.warnings.append(message)


# =============================================================================
# Migration Functions
# =============================================================================

def migrate_v1_to_v2(
    v1_spec: Dict[str, Any],
    add_defaults: bool = True,
    strict: bool = False
) -> MigrationResult:
    """
    Migrate a v1 persona spec to v2 (5-Layer)
    
    Args:
        v1_spec: The v1 spec dict or PersonaSpecV1 object
        add_defaults: Whether to add default heuristics, safety boundaries, etc.
        strict: If True, fail on any validation error
        
    Returns:
        MigrationResult with the v2 spec and any issues
    """
    result = MigrationResult(success=False, v2_spec=None)
    
    try:
        # Parse v1 spec
        if isinstance(v1_spec, dict):
            v1 = PersonaSpecV1.model_validate(v1_spec)
            v1_dict = v1_spec
        else:
            v1 = v1_spec
            v1_dict = v1.model_dump()
        
        # Build Layer 1: Identity Frame
        identity_frame = _migrate_identity_frame(v1, v1_dict, result)
        
        # Build Layer 2: Cognitive Heuristics
        cognitive_heuristics = _migrate_cognitive_heuristics(v1, v1_dict, result, add_defaults)
        
        # Build Layer 3: Value Hierarchy
        value_hierarchy = _migrate_value_hierarchy(v1, v1_dict, result, add_defaults)
        
        # Build Layer 4: Communication Patterns
        communication_patterns = _migrate_communication_patterns(v1, v1_dict, result)
        
        # Build Layer 5: Memory Anchors (empty - needs manual curation)
        memory_anchors = MemoryAnchors()
        if v1_dict.get("canonical_examples"):
            # Convert examples to memory anchors as a starting point
            for i, ex in enumerate(v1_dict.get("canonical_examples", [])[:5]):
                memory_anchors.anchors.append(MemoryAnchor(
                    id=f"migrated_example_{i}",
                    type="experience",
                    content=f"Example: {ex.get('prompt', '')} -> {ex.get('response', '')}",
                    context=f"Intent: {ex.get('intent_label', 'unknown')}",
                    applicable_intents=[ex.get("intent_label", "")] if ex.get("intent_label") else [],
                ))
        
        # Build Safety Boundaries
        safety_boundaries = _migrate_safety_boundaries(v1, v1_dict, result, add_defaults)
        
        # Construct v2 spec
        v2 = PersonaSpecV2(
            version="2.0.0",
            name=v1_dict.get("name", ""),
            description=v1_dict.get("description", ""),
            identity_frame=identity_frame,
            cognitive_heuristics=cognitive_heuristics,
            value_hierarchy=value_hierarchy,
            communication_patterns=communication_patterns,
            memory_anchors=memory_anchors,
            safety_boundaries=safety_boundaries,
            constitution=list(v1.constitution),
            deterministic_rules=dict(v1.deterministic_rules),
            status=v1_dict.get("status", "draft"),
        )
        
        result.v2_spec = v2
        result.success = True
        
    except Exception as e:
        result.add_issue("general", "error", f"Migration failed: {str(e)}")
        if strict:
            raise
    
    return result


def _migrate_identity_frame(
    v1: PersonaSpecV1,
    v1_dict: Dict[str, Any],
    result: MigrationResult
) -> IdentityFrame:
    """Migrate v1 identity_voice to Layer 1: Identity Frame"""
    identity_voice = v1_dict.get("identity_voice", {})
    
    # Map reasoning style
    reasoning_style = identity_voice.get("reasoning_style", "balanced")
    if reasoning_style not in ["analytical", "intuitive", "balanced", "first_principles", "pattern_based"]:
        result.add_issue(
            "identity_frame.reasoning_style",
            "warning",
            f"Unknown reasoning style: {reasoning_style}, defaulting to 'balanced'",
            "Update to one of: analytical, intuitive, balanced, first_principles, pattern_based"
        )
        reasoning_style = "balanced"
    
    # Map relationship
    relationship = identity_voice.get("relationship", "advisor")
    if relationship not in ["mentor", "peer", "advisor", "collaborator", "evaluator"]:
        relationship = "advisor"
    
    return IdentityFrame(
        role_definition=identity_voice.get("role", v1_dict.get("description", "")),
        expertise_domains=identity_voice.get("domains", []),
        background_summary=identity_voice.get("background", ""),
        reasoning_style=reasoning_style,
        relationship_to_user=relationship,
        communication_tendencies=identity_voice.get("communication", {
            "directness": identity_voice.get("directness", "moderate"),
            "formality": identity_voice.get("formality", "professional"),
            "verbosity": v1_dict.get("interaction_style", {}).get("brevity", "moderate"),
        }),
    )


def _migrate_cognitive_heuristics(
    v1: PersonaSpecV1,
    v1_dict: Dict[str, Any],
    result: MigrationResult,
    add_defaults: bool
) -> CognitiveHeuristics:
    """Migrate v1 decision_policy to Layer 2: Cognitive Heuristics"""
    decision_policy = v1_dict.get("decision_policy", {})
    
    heuristics = []
    
    # Try to infer heuristics from procedural modules
    for i, module in enumerate(v1_dict.get("procedural_modules", [])):
        if isinstance(module, dict) and module.get("active", True):
            heuristic = CognitiveHeuristic(
                id=f"migrated_module_{i}",
                name=module.get("id", f"module_{i}"),
                description=f"When: {module.get('when', 'N/A')}. Do: {module.get('do', [])}",
                applicable_query_types=module.get("intent_labels", []),
                steps=module.get("do", []),
                priority=module.get("priority", 50),
            )
            heuristics.append(heuristic)
    
    # Add default heuristics if requested
    if add_defaults and len(heuristics) < 2:
        heuristics.extend(DEFAULT_COGNITIVE_HEURISTICS)
        result.add_issue(
            "cognitive_heuristics",
            "info",
            "Added default cognitive heuristics",
            "Review and customize for your persona"
        )
    
    return CognitiveHeuristics(
        default_framework=decision_policy.get("framework", "evidence_based"),
        heuristics=heuristics,
        evidence_evaluation_criteria=decision_policy.get("evidence_criteria", [
            "source_credibility",
            "recency",
            "relevance",
            "corroboration"
        ]),
        confidence_thresholds=decision_policy.get("thresholds", {
            "factual_question": 0.7,
            "advice_request": 0.6,
            "evaluation_request": 0.8,
        }),
    )


def _migrate_value_hierarchy(
    v1: PersonaSpecV1,
    v1_dict: Dict[str, Any],
    result: MigrationResult,
    add_defaults: bool
) -> ValueHierarchy:
    """Migrate v1 stance_values to Layer 3: Value Hierarchy"""
    stance_values = v1_dict.get("stance_values", {})
    
    values = []
    priority = 1
    for key, val in stance_values.items():
        values.append(ValueItem(
            name=key,
            priority=priority,
            description=str(val),
        ))
        priority += 1
    
    # If no values, add some defaults
    if not values and add_defaults:
        values = [
            ValueItem(name="transparency", priority=1, description="Open and honest communication"),
            ValueItem(name="quality", priority=2, description="High standards in work"),
            ValueItem(name="speed", priority=3, description="Rapid execution and iteration"),
        ]
        result.add_issue(
            "value_hierarchy",
            "info",
            "Added default values",
            "Review and customize for your persona"
        )
    
    conflict_rules = []
    if add_defaults:
        conflict_rules = DEFAULT_VALUE_CONFLICT_RULES.copy()
    
    return ValueHierarchy(
        values=values,
        conflict_rules=conflict_rules,
    )


def _migrate_communication_patterns(
    v1: PersonaSpecV1,
    v1_dict: Dict[str, Any],
    result: MigrationResult
) -> CommunicationPatterns:
    """Migrate v1 interaction_style to Layer 4: Communication Patterns"""
    interaction_style = v1_dict.get("interaction_style", {})
    
    # Convert few-shot examples to templates if possible
    templates = []
    for i, ex in enumerate(v1_dict.get("canonical_examples", [])[:3]):
        if isinstance(ex, dict):
            templates.append({
                "id": f"migrated_template_{i}",
                "intent_label": ex.get("intent_label", "general"),
                "template": ex.get("response", "No template available"),
            })
    
    return CommunicationPatterns(
        response_templates=templates,
        signature_phrases=interaction_style.get("signatures", []),
        anti_patterns=interaction_style.get("avoid", [
            "As an AI language model",
            "I cannot provide investment advice",
        ]),
        brevity_preference=interaction_style.get("brevity", "moderate"),
    )


def _migrate_safety_boundaries(
    v1: PersonaSpecV1,
    v1_dict: Dict[str, Any],
    result: MigrationResult,
    add_defaults: bool
) -> List[SafetyBoundary]:
    """Migrate v1 deterministic_rules to Safety Boundaries"""
    deterministic_rules = v1_dict.get("deterministic_rules", {})
    
    boundaries = []
    
    # Convert banned phrases to safety boundaries
    banned = deterministic_rules.get("banned_phrases", [])
    for phrase in banned:
        boundaries.append(SafetyBoundary(
            id=f"banned_phrase_{hash(phrase) % 10000}",
            pattern=phrase,
            category="harmful",
            action="log",
            refusal_template="",
            is_regex=False,
        ))
    
    # Add default safety boundaries
    if add_defaults:
        boundaries.extend(DEFAULT_SAFETY_BOUNDARIES)
    
    return boundaries


# =============================================================================
# Migration Validation
# =============================================================================

class MigrationValidator:
    """Validates that a v1 → v2 migration was successful"""
    
    def validate_migration(
        self,
        v1_spec: Dict[str, Any],
        v2_spec: PersonaSpecV2
    ) -> Tuple[bool, List[str]]:
        """
        Validate that v2 spec is a complete migration of v1
        
        Returns:
            (is_valid, list_of_issues)
        """
        issues = []
        
        # Check basic fields
        if v1_spec.get("name") != v2_spec.name:
            issues.append(f"Name mismatch: v1={v1_spec.get('name')}, v2={v2_spec.name}")
        
        # Check constitution migrated
        v1_constitution = v1_spec.get("constitution", [])
        v2_constitution = v2_spec.constitution
        if set(v1_constitution) != set(v2_constitution):
            issues.append(f"Constitution not fully migrated")
        
        # Check identity elements
        v1_identity = v1_spec.get("identity_voice", {})
        if v1_identity.get("role") != v2_spec.identity_frame.role_definition:
            issues.append("Role not migrated to identity_frame")
        
        # Check value elements migrated
        v1_stance = v1_spec.get("stance_values", {})
        v2_values = {v.name for v in v2_spec.value_hierarchy.values}
        for key in v1_stance.keys():
            if key not in v2_values:
                issues.append(f"Stance value '{key}' not migrated to value_hierarchy")
        
        return len(issues) == 0, issues
    
    def validate_completeness(self, v2_spec: PersonaSpecV2) -> Tuple[bool, List[str]]:
        """
        Validate that v2 spec is complete (has minimum required content)
        
        Returns:
            (is_complete, list_of_missing)
        """
        missing = []
        
        # Layer 1 checks
        if not v2_spec.identity_frame.role_definition:
            missing.append("identity_frame.role_definition is empty")
        
        # Layer 2 checks
        if len(v2_spec.cognitive_heuristics.heuristics) < 1:
            missing.append("cognitive_heuristics has no heuristics")
        
        # Layer 3 checks
        if len(v2_spec.value_hierarchy.values) < 1:
            missing.append("value_hierarchy has no values")
        if len(v2_spec.value_hierarchy.scoring_dimensions) < 1:
            missing.append("value_hierarchy has no scoring dimensions")
        
        # Safety checks
        if len(v2_spec.safety_boundaries) < 1:
            missing.append("safety_boundaries is empty")
        
        return len(missing) == 0, missing


# =============================================================================
# Batch Migration
# =============================================================================

async def migrate_twin_persona_specs(
    twin_id: str,
    dry_run: bool = False,
    add_defaults: bool = True
) -> Dict[str, Any]:
    """
    Migrate all persona specs for a twin
    
    Args:
        twin_id: The twin ID
        dry_run: If True, don't actually save
        add_defaults: Whether to add default heuristics/boundaries
        
    Returns:
        Migration report
    """
    from modules.persona_spec_store import list_persona_specs
    from modules.persona_spec_store_v2 import create_persona_spec_v2
    
    report = {
        "twin_id": twin_id,
        "dry_run": dry_run,
        "migrated": [],
        "failed": [],
        "skipped": [],
    }
    
    # Get all v1 specs for this twin
    v1_specs = list_persona_specs(twin_id)
    
    for v1_spec in v1_specs:
        version = v1_spec.get("version", "unknown")
        
        # Skip if already v2
        if version.startswith("2."):
            report["skipped"].append({"version": version, "reason": "Already v2"})
            continue
        
        # Migrate
        result = migrate_v1_to_v2(v1_spec, add_defaults=add_defaults)
        
        if result.success and result.v2_spec:
            if not dry_run:
                try:
                    # Save as new v2 spec
                    await create_persona_spec_v2(
                        twin_id=twin_id,
                        spec=result.v2_spec,
                        created_by="migration"
                    )
                    report["migrated"].append({
                        "version": version,
                        "new_version": result.v2_spec.version,
                        "warnings": result.warnings,
                    })
                except Exception as e:
                    report["failed"].append({
                        "version": version,
                        "error": str(e),
                    })
            else:
                report["migrated"].append({
                    "version": version,
                    "new_version": result.v2_spec.version,
                    "dry_run": True,
                    "warnings": result.warnings,
                })
        else:
            report["failed"].append({
                "version": version,
                "errors": [i.message for i in result.issues if i.issue_type == "error"],
            })
    
    return report
