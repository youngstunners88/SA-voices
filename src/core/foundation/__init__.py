"""
Foundational Environment Systems for SA Voices

Provides core infrastructure for:
- Environment management
- Configuration orchestration
- Service lifecycle management
- Dependency injection
- Event system
"""

from .environment import Environment, EnvironmentConfig
from .orchestrator import ServiceOrchestrator, ServiceLifecycle
from .events import EventBus, Event, EventHandler
from .di import Container, inject, singleton

__all__ = [
    "Environment",
    "EnvironmentConfig",
    "ServiceOrchestrator",
    "ServiceLifecycle",
    "EventBus",
    "Event",
    "EventHandler",
    "Container",
    "inject",
    "singleton",
]
