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
    
    This function uses lazy loading - VC Python class is only imported
    when explicitly requested. This ensures VC files don't interfere
    with vanilla flows.
    
    Priority:
    1. Explicit name argument
    2. SPECIALIZATION environment variable
    3. Default to 'vanilla'
    
    Args:
        name: Optional specialization name to load
        
    Returns:
        Instantiated Specialization object (always returns vanilla as fallback)
    """
    # Determine which specialization to load
    spec_name = name or os.getenv("SPECIALIZATION", "vanilla")
    
    # Ensure vanilla is registered (required fallback)
    _ensure_registered()
    
    # Try to load the requested specialization (lazy loading)
    spec_class = _load_specialization_class(spec_name)
    
    # Fallback to vanilla if not found or failed
    if not spec_class:
        if spec_name != "vanilla":
            print(f"Warning: Specialization '{spec_name}' not available, falling back to vanilla")
        spec_class = _REGISTRY.get("vanilla")
    
    if not spec_class:
        raise RuntimeError("Vanilla specialization not available. Check module imports.")
    
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
    """Ensure vanilla specialization is imported and registered.
    
    Note: Only vanilla is pre-registered. Other specializations (like VC)
    are loaded lazily via _load_specialization_class() when requested.
    This ensures VC files are never imported unless explicitly needed.
    """
    if "vanilla" in _REGISTRY:
        return
    
    # Always register vanilla (required fallback)
    from .vanilla import VanillaSpecialization
    register_specialization("vanilla", VanillaSpecialization)


def _load_specialization_class(spec_id: str) -> Optional[Type[Specialization]]:
    """
    Lazy-load a specialization Python class only when needed.
    
    This ensures VC files are never imported unless explicitly requested.
    This is critical because:
    1. VC imports should not interfere with vanilla flows
    2. VC may have dependencies that aren't needed for vanilla
    3. Prevents circular import issues
    4. Reduces memory footprint when VC is not used
    
    Args:
        spec_id: Specialization identifier (e.g., "vc")
        
    Returns:
        Specialization class or None if not found/available
    """
    # If already registered, return immediately
    if spec_id in _REGISTRY:
        return _REGISTRY[spec_id]
    
    # Ensure vanilla is registered (required fallback)
    _ensure_registered()
    
    # Lazy import based on spec_id
    if spec_id == "vc":
        try:
            from .vc import VCSpecialization
            register_specialization("vc", VCSpecialization)
            return VCSpecialization
        except ImportError as e:
            print(f"Warning: VC specialization not available: {e}")
            return None
    elif spec_id == "vanilla":
        return _REGISTRY.get("vanilla")
    
    # Unknown specialization
    return None


# Tier configuration for specializations
_TIER_CONFIG = {
    "vanilla": {"tier": "free", "icon": "🧠"},
    "legal": {"tier": "premium", "icon": "⚖️", "coming_soon": True},
    "medical": {"tier": "premium", "icon": "🏥", "coming_soon": True},
}


def get_all_specializations():
    """
    Get all available specializations with metadata for UI display.
    
    Returns:
        List of specialization dicts with id, name, description, tier, icon
    """
    _ensure_registered()
    
    result = []
    for name, spec_class in _REGISTRY.items():
        spec = spec_class()
        tier_info = _TIER_CONFIG.get(name, {"tier": "free", "icon": "🧠"})
        result.append({
            "id": name,
            "name": spec.display_name,
            "description": spec.description,
            "tier": tier_info.get("tier", "free"),
            "icon": tier_info.get("icon", "🧠"),
            "coming_soon": tier_info.get("coming_soon", False)
        })
    
    # Add coming soon specializations
    for name, tier_info in _TIER_CONFIG.items():
        if tier_info.get("coming_soon") and name not in _REGISTRY:
            result.append({
                "id": name,
                "name": name.title() + " Brain",
                "description": f"Specialized for {name} operations",
                "tier": tier_info.get("tier", "premium"),
                "icon": tier_info.get("icon", "🧠"),
                "coming_soon": True
            })
    
    return result
