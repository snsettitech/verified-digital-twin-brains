"""
Specializations Package

Provides the Strategy Pattern implementation for different brain variants.
"""

from .base import Specialization
from .registry import get_specialization, register_specialization, get_all_specializations

__all__ = [
    "Specialization",
    "get_specialization", 
    "register_specialization",
    "get_all_specializations"
]
