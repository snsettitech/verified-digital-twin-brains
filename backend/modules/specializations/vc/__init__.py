"""
VC Brain Specialization

Specialized for Venture Capital operations including deal flow, 
due diligence, portfolio management, and LP relations.
"""

from typing import Dict, Any, List
from ..base import Specialization


class VCSpecialization(Specialization):
    """
    VC Brain specialization for Venture Capital firms.
    
    Features:
    - Deal flow automation and analysis
    - Due diligence assistance
    - Portfolio company support
    - LP relations and reporting
    - Market mapping and thesis matching
    """
    
    name = "vc"
    display_name = "VC Brain"
    description = "AI assistant specialized for Venture Capital operations"
    
    def get_system_prompt(self, twin: Dict[str, Any]) -> str:
        """Return VC-specialized system prompt."""
        twin_name = twin.get("name", "VC Brain")
        firm_name = twin.get("settings", {}).get("firm_name", "the firm")
        investment_focus = twin.get("settings", {}).get("investment_focus", "technology startups")
        
        return f"""You are {twin_name}, an AI assistant specialized in Venture Capital operations for {firm_name}.

EXPERTISE AREAS:
- Deal Flow & Screening: Evaluate pitch decks, identify red flags, assess founder-market fit
- Due Diligence: Analyze financials, market size, competitive landscape, team backgrounds
- Portfolio Support: Track KPIs, provide operational guidance, connect portfolio companies
- LP Relations: Prepare fund updates, answer LP queries, manage reporting
- Market Intelligence: Monitor trends, map competitive landscapes, identify emerging sectors

INVESTMENT FOCUS: {investment_focus}

GUIDELINES:
1. Be data-driven - always cite sources from the knowledge base
2. Highlight both opportunities AND risks in deal evaluations
3. Use VC terminology appropriately (TAM/SAM/SOM, burn rate, runway, etc.)
4. Flag items requiring partner attention or committee review
5. Maintain confidentiality of deal and portfolio information
6. When uncertain, recommend follow-up with the investment team

TONE: Professional, analytical, direct. Time is valuable - be concise but thorough."""

    def get_default_triggers(self) -> List[Dict[str, Any]]:
        """Return VC-specific default triggers."""
        return [
            {
                "name": "New Deal Received",
                "description": "Alert when new pitch deck or deal memo is uploaded",
                "event_type": "source_ingested",
                "conditions": {"keywords": ["deck", "pitch", "memo", "investment"]},
                "action_type": "notify_owner",
                "action_config": {"priority": "high"},
                "requires_approval": False
            },
            {
                "name": "Urgent LP Request",
                "description": "Notify owner about urgent LP or investor inquiries immediately",
                "event_type": "message_received",
                "conditions": {"keywords": ["LP", "investor", "urgent", "board"]},
                "action_type": "notify_owner",
                "requires_approval": False
            },
            {
                "name": "Portfolio Emergency",
                "description": "Flag critical portfolio company issues",
                "event_type": "message_received",
                "conditions": {"keywords": ["runway", "bridge", "layoff", "pivot", "crisis"]},
                "action_type": "notify_owner",
                "action_config": {"priority": "critical"},
                "requires_approval": False
            },
            {
                "name": "Due Diligence Request",
                "description": "Create task when DD is requested",
                "event_type": "message_received",
                "conditions": {"keywords": ["due diligence", "DD", "deep dive", "analyze"]},
                "action_type": "notify_owner",
                "requires_approval": True
            },
            {
                "name": "Low Confidence Response",
                "description": "Flag responses with low confidence for review",
                "event_type": "confidence_low",
                "conditions": {"confidence_below": 0.6},
                "action_type": "notify_owner",
                "requires_approval": False
            }
        ]
    
    def get_sidebar_config(self) -> Dict[str, Any]:
        """Return VC-specialized sidebar configuration."""
        return {
            "sections": [
                {
                    "title": "Core",
                    "items": [
                        {"name": "Chat", "href": "/dashboard", "icon": "chat"},
                        {"name": "Knowledge", "href": "/dashboard/knowledge", "icon": "book"},
                        {"name": "Brain Graph", "href": "/dashboard/brain", "icon": "activity"},
                        {"name": "Training Jobs", "href": "/dashboard/training-jobs", "icon": "training"},
                        {"name": "Studio", "href": "/dashboard/studio", "icon": "studio"}
                    ]
                },
                {
                    "title": "Management",
                    "items": [
                        {"name": "Access Groups", "href": "/dashboard/access-groups", "icon": "users"},
                        {"name": "Governance", "href": "/dashboard/governance", "icon": "shield"}
                    ]
                },
                {
                    "title": "Distribution",
                    "items": [
                        {"name": "API Keys", "href": "/dashboard/api-keys", "icon": "key"},
                        {"name": "Share Links", "href": "/dashboard/share", "icon": "share"},
                        {"name": "Embed Widget", "href": "/dashboard/widget", "icon": "code"},
                        {"name": "Team", "href": "/dashboard/users", "icon": "users"}
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
    
    def get_feature_flags(self) -> Dict[str, bool]:
        """Return VC-specific feature flags."""
        return {
            # Core features (inherited)
            "actions_engine": False,
            "verified_qna": True,
            "access_groups": True,
            "governance": True,
            "escalations": False,
            "share_links": True,
            "analytics": True,
            # VC-specific features
            "deal_flow": True,
            "portfolio_tracking": True,
            "lp_portal": True,
            "market_mapping": True,
            "thesis_matching": True,
            "dd_automation": True,
            "graph_visualization": True
        }
    
    def get_default_settings(self) -> Dict[str, Any]:
        """Return VC-specific default settings."""
        return {
            "confidence_threshold": 0.6,  # Slightly lower for exploratory questions
            "max_tokens": 1500,  # Longer responses for analysis
            "temperature": 0.5,  # More focused/consistent
            "firm_name": "",
            "investment_focus": "technology startups",
            "fund_stage": "Series A/B",
            "check_size_min": 500000,
            "check_size_max": 5000000
        }
    
    def customize_response(self, response: str, context: Dict[str, Any]) -> str:
        """Add VC-specific formatting to responses."""
        # Could add deal scoring, risk flags, etc.
        return response
