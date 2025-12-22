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
    Get a specialization instance by name or environment variable.
    
    Priority:
    1. Explicit name argument
    2. SPECIALIZATION environment variable
    3. Default to 'vanilla'
    
    Args:
        name: Optional specialization name to load
        
    Returns:
        Instantiated Specialization object
    """
    # Determine which specialization to load
    spec_name = name or os.getenv("SPECIALIZATION", "vanilla")
    
    # Import specializations lazily to avoid circular imports
    _ensure_registered()
    
    # Get the class or default to vanilla
    spec_class = _REGISTRY.get(spec_name)
    if not spec_class:
        print(f"Warning: Unknown specialization '{spec_name}', falling back to vanilla")
        spec_class = _REGISTRY.get("vanilla")
    
    if not spec_class:
        raise RuntimeError("No specializations registered. Check module imports.")
    
    return spec_class()


def list_specializations() -> Dict[str, Dict[str, str]]:
    """
    List all registered specializations with metadata.
    
    Returns:
        Dict mapping name to metadata (display_name, description)
    """
    _ensure_registered()
    
    result = {}
    for name, spec_class in _REGISTRY.items():
        spec = spec_class()
        result[name] = spec.get_metadata()
    
    return result


def _ensure_registered() -> None:
    """Ensure all specializations are imported and registered."""
    if _REGISTRY:
        return
    
    # Import to trigger registration
    from .vanilla import VanillaSpecialization
    from .vc import VCSpecialization
    
    register_specialization("vanilla", VanillaSpecialization)
    register_specialization("vc", VCSpecialization)
