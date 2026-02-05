"""
Specialization Base Class

Abstract interface that all specialization variants must implement.
This enables the Strategy Pattern for different brain types (Vanilla, VC, Legal, etc.)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class Specialization(ABC):
    """
    Base class for all specialization variants.
    
    Specializations customize behavior without modifying core modules:
    - System prompts / persona
    - Default triggers for new twins
    - Sidebar configuration
    - Feature flags
    
    Usage:
        spec = get_specialization()  # Loads based on SPECIALIZATION env var
        prompt = spec.get_system_prompt(twin)
    """
    
    # Override in subclasses
    name: str = "base"
    display_name: str = "Digital Twin"
    description: str = "Base specialization"
    
    @abstractmethod
    def get_system_prompt(self, twin: Dict[str, Any]) -> str:
        """
        Return the system prompt for this specialization.
        
        Args:
            twin: Twin configuration dict with name, description, settings
            
        Returns:
            System prompt string to use with LLM
        """
        pass
    
    @abstractmethod
    def get_default_triggers(self) -> List[Dict[str, Any]]:
        """
        Return default triggers for new twins of this type.
        
        Returns:
            List of trigger configurations to create for new twins
        """
        pass
    
    @abstractmethod
    def get_sidebar_config(self) -> Dict[str, Any]:
        """
        Return frontend sidebar configuration.
        
        Returns:
            Dict with 'sections' list containing title and items
        """
        pass
    
    def get_feature_flags(self) -> Dict[str, bool]:
        """
        Return enabled features for this specialization.
        Override in subclasses to enable/disable specific features.
        
        Returns:
            Dict of feature name to enabled boolean
        """
        return {
            "actions_engine": False,
            "verified_qna": True,
            "access_groups": True,
            "governance": True,
            "escalations": False,
            "share_links": True,
            "analytics": True
        }
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return specialization metadata for API responses."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description
        }
    
    def customize_response(self, response: str, context: Dict[str, Any]) -> str:
        """
        Optional hook to customize assistant responses.
        Override in subclasses for specialized post-processing.
        
        Args:
            response: The assistant's response
            context: Additional context (twin, user, etc.)
            
        Returns:
            Potentially modified response
        """
        return response
    
    def get_default_settings(self) -> Dict[str, Any]:
        """
        Return default twin settings for this specialization.
        Override in subclasses for specialized defaults.
        
        Returns:
            Dict of setting name to default value
        """
        return {
            "confidence_threshold": 0.7,
            "max_tokens": 1000,
            "temperature": 0.7
        }
