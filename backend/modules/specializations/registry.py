"""
Specialization Registry

Loads and manages specialization variants based on environment or tenant configuration.
"""

import os
from typing import Dict, Type, Optional
from .base import Specialization


# Registry of available specializations
_REGISTRY: Dict[str, Type[Specialization]] = {}


def register_specialization(name: str, spec_class: Type[Specialization]) -> None:
    """
    Register a specialization class.
    
    Args:
        name: Unique identifier for the specialization
        spec_class: Class implementing Specialization interface
    """
    _REGISTRY[name] = spec_class


def get_specialization(name: Optional[str] = None) -> Specialization:
    """
    Get the Digital Twin specialization instance.
    
    The system now uses a standardized 'Vanilla' platform for all twins.
    This function remains as an entry point for backward compatibility and
    to provide the unified specialization logic.
    
    Args:
        name: Ignored (standardized to vanilla)
        
    Returns:
        Instantiated Specialization object
    """
    _ensure_registered()
    return _REGISTRY.get("vanilla")()


def list_specializations() -> Dict[str, Dict[str, str]]:
    """List the primary specialization."""
    _ensure_registered()
    return {"vanilla": _REGISTRY["vanilla"]().get_metadata()}


def _ensure_registered() -> None:
    """Register the core vanilla specialization."""
    if "vanilla" not in _REGISTRY:
        from .vanilla import VanillaSpecialization
        register_specialization("vanilla", VanillaSpecialization)


# Tier configuration (Standardized for Digital Twin)
_TIER_CONFIG = {
    "vanilla": {"tier": "free", "icon": "🧠"}
}


def get_all_specializations():
    """Get the standardized specialization for UI display."""
    _ensure_registered()
    spec = _REGISTRY["vanilla"]()
    return [{
        "id": "vanilla",
        "name": spec.display_name,
        "description": spec.description,
        "tier": "free",
        "icon": "🧠",
        "coming_soon": False
    }]
