# backend/modules/_core/host_engine.py
"""Host Engine: Orchestrates the cognitive interview.

Determines the next best question (slot) to ask based on the current
Graph state and the Specialization's Host Policy. Uses question templates
from the ontology pack to generate natural interview questions.
"""

from typing import Dict, Any, List, Optional
import random
import json
import os

def get_next_slot(policy: Dict[str, Any], filled_slots: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Determine the next slot to fill based on policy and current state.
    
    Args:
        policy: The host policy dict (from host_policy.json)
        filled_slots: Dict of slot_id -> value (or node) derived from Graph.
    
    Returns:
        The next slot definition dict, or None if all satisfied.
    """
    required_slots = policy.get("required_slots", [])
    
    # Sort by priority (lower is better, assuming 1=High)
    sorted_slots = sorted(required_slots, key=lambda x: x.get("priority", 999))
    
    for slot in sorted_slots:
        slot_id = slot.get("slot_id")
        if slot_id not in filled_slots:
            return slot
            
    return None

def load_ontology_templates(spec_name: str) -> List[Dict[str, Any]]:
    """
    Load question templates from the specialization's ontology pack.
    
    Args:
        spec_name: Name of the specialization (e.g., "vc", "vanilla")
    
    Returns:
        List of question template dicts
    """
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ontology_path = os.path.join(base_path, "specializations", spec_name, "ontology")
    
    templates = []
    
    # Load templates from all packs
    if os.path.exists(ontology_path):
        for filename in os.listdir(ontology_path):
            if filename.endswith("_pack.json"):
                pack_path = os.path.join(ontology_path, filename)
                try:
                    with open(pack_path, "r", encoding="utf-8") as f:
                        pack = json.load(f)
                        templates.extend(pack.get("question_templates", []))
                except Exception as e:
                    print(f"Error loading ontology pack {filename}: {e}")
    
    return templates

def get_question_for_slot(
    slot: Dict[str, Any], 
    templates: List[Dict[str, Any]],
    asked_template_ids: List[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get a question template that targets the given slot.
    
    Args:
        slot: The slot definition dict containing slot_id and cluster_id
        templates: All available question templates
        asked_template_ids: Template IDs already asked (to avoid repetition)
    
    Returns:
        A question template dict or None if no matching template found
    """
    if asked_template_ids is None:
        asked_template_ids = []
    
    slot_id = slot.get("slot_id", "")
    cluster_id = slot.get("cluster_id", "")
    
    # Filter templates by cluster and not already asked
    matching_templates = [
        t for t in templates
        if t.get("cluster", "") == cluster_id
        and t.get("template_id", "") not in asked_template_ids
    ]
    
    # Also match by target_node containing the slot_id pattern
    if not matching_templates:
        matching_templates = [
            t for t in templates
            if slot_id.replace("_", ".") in t.get("target_node", "")
            and t.get("template_id", "") not in asked_template_ids
        ]
    
    if matching_templates:
        # Return a random matching template for variety
        return random.choice(matching_templates)
    
    return None

def get_next_question(
    policy: Dict[str, Any], 
    filled_slots: Dict[str, Any],
    spec_name: str = "vanilla",
    asked_template_ids: List[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get the next interview question based on policy and filled slots.
    
    Returns a dict with:
    - slot: The slot definition
    - template: The question template (or None if no template available)
    - question: The actual question text
    - follow_up: Follow-up question if response is vague
    
    Args:
        policy: Host policy dict
        filled_slots: Currently filled slots
        spec_name: Specialization name for loading templates
        asked_template_ids: Template IDs already asked
    
    Returns:
        Question info dict or None if all slots are filled
    """
    next_slot = get_next_slot(policy, filled_slots)
    
    if not next_slot:
        return None
    
    # Load templates from ontology
    templates = load_ontology_templates(spec_name)
    
    # Get matching question template
    template = get_question_for_slot(next_slot, templates, asked_template_ids)
    
    if template:
        return {
            "slot": next_slot,
            "template": template,
            "template_id": template.get("template_id"),
            "question": template.get("template"),
            "follow_up": template.get("follow_up_if_vague"),
            "target_node": template.get("target_node")
        }
    else:
        # Fallback: Generate a generic question for the slot
        slot_id = next_slot.get("slot_id", "").replace("_", " ")
        return {
            "slot": next_slot,
            "template": None,
            "template_id": None,
            "question": f"Tell me about your {slot_id}.",
            "follow_up": "Could you elaborate on that?",
            "target_node": None
        }

def process_turn(twin_id: str, user_message: str, history: List[Dict[str, Any]]) -> str:
    """
    Generate a Host-driven response (Question).
    Wrapper around the Agent or a dedicated Question Generator.
    
    (Currently unused if we rely on the main Agent, but provided for the specific Interview Loop)
    """
    # Placeholder: In a full implementation, this would prompt the LLM 
    # explicitly to "Ask about {next_slot}".
    pass

