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
- Ask clarifying questions when requests are ambiguous or sensitive

Guidelines:
- Be helpful, accurate, and concise
- Always ground answers in the knowledge base when possible
- If confidence is low, say so and request clarification
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
            }
        ]
    
    def get_sidebar_config(self) -> Dict[str, Any]:
        """Return default sidebar configuration."""
        return {
            "sections": [
                {
                    "title": "Build",
                    "items": [
                        {"name": "Dashboard", "href": "/dashboard", "icon": "home"},
                        {"name": "Interview Mode", "href": "/dashboard/interview", "icon": "activity"},
                        {"name": "Knowledge", "href": "/dashboard/knowledge", "icon": "book"},
                        {"name": "Right Brain", "href": "/dashboard/right-brain", "icon": "chart"}
                    ]
                },
                {
                    "title": "Train",
                    "items": [
                        {"name": "Simulator", "href": "/dashboard/simulator", "icon": "chat"},
                        {"name": "Verified Q&A", "href": "/dashboard/verified-qna", "icon": "check"}
                    ]
                },
                {
                    "title": "Share",
                    "items": [
                        {"name": "Access Groups", "href": "/dashboard/access-groups", "icon": "users"},
                        {"name": "Widget", "href": "/dashboard/widget", "icon": "code"},
                        {"name": "API Keys", "href": "/dashboard/api-keys", "icon": "key"}
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
