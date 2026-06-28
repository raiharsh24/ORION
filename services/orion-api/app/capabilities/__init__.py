"""
Capabilities package.
Defines base interfaces and registries for modular system skills.
"""
from app.capabilities.capability import BaseCapability
from app.capabilities.registry import CapabilityRegistry

__all__ = [
    "BaseCapability",
    "CapabilityRegistry"
]
