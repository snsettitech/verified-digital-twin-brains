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
        """Return standardized default triggers for twins."""
        return [
            {
                "name": "Low Confidence Alert",
                "description": "Notify owner when confidence drops below threshold",
                "event_type": "confidence_low",
                "conditions": {"confidence_below": 0.6},
                "action_type": "notify_owner",
                "requires_approval": False
            },
            {
                "name": "Escalation Request",
                "description": "Create escalation when user explicitly requests",
                "event_type": "message_received",
                "conditions": {"keywords": ["speak to owner", "talk to human", "escalate", "urgent", "help"]},
                "action_type": "escalate",
                "requires_approval": True
            }
        ]
    
    def get_sidebar_config(self) -> Dict[str, Any]:
        """Return standardized 5-section sidebar configuration."""
        return {
            "sections": [
                {
                    "title": "Core",
                    "items": [
                        {"name": "Home", "href": "/dashboard", "icon": "home"},
                        {"name": "Knowledge", "href": "/dashboard/knowledge", "icon": "book"},
                        {"name": "Insights", "href": "/dashboard/brain", "icon": "activity"},
                        {"name": "Training", "href": "/dashboard/training-jobs", "icon": "training"}
                    ]
                },
                {
                    "title": "Management",
                    "items": [
                        {"name": "Escalations", "href": "/dashboard/escalations", "icon": "alert"},
                        {"name": "Access Groups", "href": "/dashboard/access-groups", "icon": "users"},
                        {"name": "Governance", "href": "/dashboard/governance", "icon": "shield"}
                    ]
                },
                {
                    "title": "Automation",
                    "items": [
                        {"name": "Actions Hub", "href": "/dashboard/actions", "icon": "bolt"},
                        {"name": "Triggers", "href": "/dashboard/actions/triggers", "icon": "bolt"},
                        {"name": "Inbox", "href": "/dashboard/actions/inbox", "icon": "mail"}
                    ]
                },
                {
                    "title": "Distribution",
                    "items": [
                        {"name": "API Keys", "href": "/dashboard/api-keys", "icon": "key"},
                        {"name": "Share Links", "href": "/dashboard/share", "icon": "share"},
                        {"name": "Widget", "href": "/dashboard/widget", "icon": "code"}
                    ]
                },
                {
                    "title": "Settings",
                    "items": [
                        {"name": "Settings", "href": "/dashboard/settings", "icon": "settings"}
                    ]
                }
            ]
        }
