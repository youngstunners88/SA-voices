"""
Core Abstractions Layer

Clean Architecture: Abstract base classes and interfaces
that define contracts for all implementations.
"""

from .entity import Entity, EntityId, AggregateRoot
from .repository import Repository, UnitOfWork
from .event import DomainEvent, EventBus, EventHandler
from .service import DomainService, ApplicationService
from .value_object import ValueObject

__all__ = [
    "Entity",
    "EntityId", 
    "AggregateRoot",
    "Repository",
    "UnitOfWork",
    "DomainEvent",
    "EventBus",
    "EventHandler",
    "DomainService",
    "ApplicationService",
    "ValueObject",
]
