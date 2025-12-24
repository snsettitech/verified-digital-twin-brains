# backend/modules/_core/interview_controller.py
"""Interview Controller: Manages the intent-first podcast interview flow.

Implements a state machine with stages:
- opening: Set expectations
- intent_capture: Capture 3 core intent questions
- confirm_intent: Summarize and confirm understanding
- deep_interview: Slot-driven interview with podcast style
- complete: All required slots filled

The Host uses templates but enhances them with context awareness.
"""

from typing import Dict, Any, List, Optional
from enum import Enum
import json
import os

from modules.observability import supabase


class InterviewStage(str, Enum):
    OPENING = "opening"
    INTENT_CAPTURE = "intent_capture"
    CONFIRM_INTENT = "confirm_intent"
    DEEP_INTERVIEW = "deep_interview"
    COMPLETE = "complete"


# Stage 1: Intent questions (always asked first)
INTENT_QUESTIONS = [
    {
        "id": "intent_use_case",
        "question": "What are you trying to use this twin for?",
        "examples": "For example: VC twin for my investment style, productivity twin, coaching twin...",
        "target_node": "intent.primary_use_case",
        "follow_up": "Could you be more specific about your main goal?"
    },
    {
        "id": "intent_audience",
        "question": "Who will use this twin and what should it help them accomplish?",
        "examples": "Will it be just you, your team, or external people?",
        "target_node": "intent.audience",
        "follow_up": "What's the main outcome they're looking for?"
    },
    {
        "id": "intent_boundaries",
        "question": "Anything you want it to avoid or never do?",
        "examples": "For example: no hallucinations, always escalate if unsure, don't discuss competitors...",
        "target_node": "intent.boundaries",
        "follow_up": "Any specific topics that should be off-limits?",
        "optional": True
    }
]


class InterviewController:
    """Manages interview state and stage transitions."""
    
    @staticmethod
    def get_or_create_session(twin_id: str, conversation_id: str = None) -> Dict[str, Any]:
        """Get existing active session or create a new one."""
        try:
            result = supabase.rpc("get_or_create_interview_session", {
                "t_id": twin_id,
                "conv_id": conversation_id
            }).execute()
            
            if result.data:
                return result.data
            
            # Fallback if RPC not available
            return {
                "id": None,
                "twin_id": twin_id,
                "conversation_id": conversation_id,
                "stage": InterviewStage.OPENING.value,
                "intent_confirmed": False,
                "turn_count": 0,
                "asked_template_ids": [],
                "blueprint_json": {}
            }
        except Exception as e:
            print(f"Error getting session: {e}")
            # Return a default session structure
            return {
                "id": None,
                "twin_id": twin_id,
                "conversation_id": conversation_id,
                "stage": InterviewStage.OPENING.value,
                "intent_confirmed": False,
                "turn_count": 0,
                "asked_template_ids": [],
                "blueprint_json": {}
            }
    
    @staticmethod
    def update_session(session_id: str, **kwargs) -> Dict[str, Any]:
        """Update session state."""
        if not session_id:
            return {}
            
        try:
            result = supabase.rpc("update_interview_session", {
                "session_id": session_id,
                **kwargs
            }).execute()
            return result.data if result.data else {}
        except Exception as e:
            print(f"Error updating session: {e}")
            return {}
    
    @staticmethod
    def get_stage(session: Dict[str, Any]) -> InterviewStage:
        """Get current interview stage."""
        stage_str = session.get("stage", InterviewStage.OPENING.value)
        try:
            return InterviewStage(stage_str)
        except ValueError:
            return InterviewStage.OPENING
    
    @staticmethod
    def get_opening_message(host_policy: Dict[str, Any]) -> str:
        """Get the opening message for Stage 0."""
        return host_policy.get(
            "opening_message",
            "I'm going to ask a few questions to understand what you want this twin to do. "
            "I'll repeat back what I heard and you can correct me. Ready?"
        )
    
    @staticmethod
    def get_next_intent_question(session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get the next intent question to ask (Stage 1)."""
        asked = session.get("asked_template_ids", []) or []
        
        for q in INTENT_QUESTIONS:
            if q["id"] not in asked:
                return q
        
        return None
    
    @staticmethod
    def generate_intent_summary(intent_nodes: List[Dict[str, Any]]) -> str:
        """Generate a summary of captured intent for confirmation (Stage 1.5)."""
        summary_parts = []
        
        for node in intent_nodes:
            node_type = node.get("type", "").lower()
            name = node.get("name", "")
            desc = node.get("description", "")
            
            if "use_case" in node_type or "primary" in node_type:
                summary_parts.append(f"You want to create a twin for: **{desc or name}**")
            elif "audience" in node_type:
                summary_parts.append(f"It will be used by: **{desc or name}**")
            elif "boundaries" in node_type:
                summary_parts.append(f"Boundaries: **{desc or name}**")
            elif "goal" in node_type:
                summary_parts.append(f"The goal is to: **{desc or name}**")
        
        if not summary_parts:
            return "I understand you want to create a digital twin."
        
        return "\n".join(summary_parts)
    
    @staticmethod
    def generate_interview_blueprint(
        intent_nodes: List[Dict[str, Any]], 
        spec_name: str,
        host_policy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate interview blueprint after intent confirmation."""
        # Determine which packs to use based on intent
        selected_packs = ["vc_base"]
        intent_tags = []
        
        for node in intent_nodes:
            desc = (node.get("description", "") + " " + node.get("name", "")).lower()
            
            # Detect focus areas from intent
            if any(tag in desc for tag in ["deeptech", "deep tech", "frontier", "hardware", "science"]):
                selected_packs.append("vc_deeptech")
                intent_tags.append("deeptech")
            if any(tag in desc for tag in ["b2b", "saas", "enterprise"]):
                intent_tags.append("b2b_saas")
            if any(tag in desc for tag in ["consumer", "b2c", "d2c"]):
                intent_tags.append("consumer")
            if any(tag in desc for tag in ["climate", "cleantech", "sustainability"]):
                intent_tags.append("climate")
        
        # Get slot order from policy
        required_slots = host_policy.get("required_slots", [])
        slot_order = [slot["slot_id"] for slot in sorted(required_slots, key=lambda x: x.get("priority", 999))]
        
        return {
            "selected_packs": list(set(selected_packs)),
            "slot_order": slot_order,
            "intent_tags": list(set(intent_tags)),
            "total_slots": len(required_slots)
        }
    
    @staticmethod
    def should_confirm_periodically(turn_count: int) -> bool:
        """Check if we should confirm understanding (every 3-5 turns)."""
        return turn_count > 0 and turn_count % 4 == 0
    
    @staticmethod
    def get_confirmation_message(host_policy: Dict[str, Any], summary: str) -> str:
        """Get confirmation message with summary inserted."""
        template = host_policy.get(
            "confirmation_prompt",
            "Here's what I understood: {summary}. Did I get that right?"
        )
        return template.format(summary=summary)


# Helper function for podcast-style transitions
TRANSITIONS = [
    "That's helpful. Building on that...",
    "Interesting. Let me ask about...",
    "Got it. Now I'm curious about...",
    "Makes sense. Shifting gears a bit...",
    "Thanks for sharing. Related to that...",
]

def get_podcast_transition() -> str:
    """Get a random natural transition phrase."""
    import random
    return random.choice(TRANSITIONS)


def generate_podcast_question(
    slot: Dict[str, Any],
    template_question: str,
    history: List[Dict[str, Any]],
    intent_nodes: List[Dict[str, Any]]
) -> str:
    """
    Enhance a template question with context to feel like a podcast.
    
    For now, uses simple template + transition.
    Future: Could use LLM to reference specific prior context.
    """
    # Get recent context from history
    recent_user_message = ""
    if history:
        for msg in reversed(history[-4:]):
            if msg.get("role") == "user":
                recent_user_message = msg.get("content", "")[:100]
                break
    
    # Build contextual question
    transition = get_podcast_transition()
    
    # For MVP, just add transition to template
    return f"{transition}\n\n{template_question}"
