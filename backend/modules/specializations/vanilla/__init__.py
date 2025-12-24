"""
Vanilla Specialization

The default "Digital Twin" behavior - general purpose knowledge assistant.
"""

from typing import Dict, Any, List
from ..base import Specialization


class VanillaSpecialization(Specialization):
    """
    Default specialization for general-purpose digital twins.
    
    This is the baseline behavior that other specializations extend from.
    """
    
    name = "vanilla"
    display_name = "Digital Twin"
    description = "General-purpose AI knowledge assistant"
    
    def get_system_prompt(self, twin: Dict[str, Any]) -> str:
        """Return the default system prompt."""
        twin_name = twin.get("name", "Assistant")
        twin_description = twin.get("description", "")
        
        return f"""You are {twin_name}, an AI knowledge assistant.

{twin_description}

Your responsibilities:
- Answer questions based on the provided knowledge base
- Cite sources when providing information
- Be honest when you don't know something
- Escalate complex or sensitive questions to the owner when appropriate

Guidelines:
- Be helpful, accurate, and concise
- Always ground answers in the knowledge base when possible
- If confidence is low, say so and offer to escalate
- Maintain a professional yet approachable tone"""

    def get_default_triggers(self) -> List[Dict[str, Any]]:
        """Return default triggers for vanilla twins."""
        return [
            {
                "name": "Low Confidence Alert",
                "description": "Notify owner when confidence drops below threshold",
                "event_type": "confidence_low",
                "conditions": {"confidence_below": 0.5},
                "action_type": "notify_owner",
                "requires_approval": False
            },
            {
                "name": "Escalation Request",
                "description": "Create escalation when user explicitly requests",
                "event_type": "message_received",
                "conditions": {"keywords": ["speak to owner", "talk to human", "escalate"]},
                "action_type": "escalate",
                "requires_approval": True
            }
        ]
    
    def get_sidebar_config(self) -> Dict[str, Any]:
        """Return default sidebar configuration."""
        return {
            "sections": [
                {
                    "title": "Core",
                    "items": [
                        {"name": "Dashboard", "href": "/dashboard", "icon": "home"},
                        {"name": "Left Brain (Sources)", "href": "/dashboard/knowledge", "icon": "book"},
                        {"name": "Right Brain (Interview)", "href": "/dashboard/right-brain", "icon": "activity"},
                        {"name": "Simulator", "href": "/dashboard/simulator", "icon": "chat"}
                    ]
                },
                {
                    "title": "Management",
                    "items": [
                        {"name": "Escalations", "href": "/dashboard/escalations", "icon": "alert"},
                        {"name": "Verified Q&A", "href": "/dashboard/verified-qna", "icon": "check"},
                        {"name": "Access Groups", "href": "/dashboard/access-groups", "icon": "users"}
                    ]
                },
                {
                    "title": "Automation",
                    "items": [
                        {"name": "Actions Hub", "href": "/dashboard/actions", "icon": "bolt"}
                    ]
                },
                {
                    "title": "Settings",
                    "items": [
                        {"name": "Governance", "href": "/dashboard/governance", "icon": "shield"},
                        {"name": "Settings", "href": "/dashboard/settings", "icon": "settings"}
                    ]
                }
            ]
        }
