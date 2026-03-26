"""
Entity Abstractions

Base classes for all domain entities following DDD principles.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
import uuid


@dataclass(frozen=True)
class EntityId:
    """Value object for entity identifiers"""
    value: str
    
    def __post_init__(self):
        if not self.value:
            raise ValueError("EntityId cannot be empty")
    
    @classmethod
    def generate(cls) -> "EntityId":
        """Generate new unique ID"""
        return cls(str(uuid.uuid4()))
    
    def __str__(self) -> str:
        return self.value
    
    def __hash__(self) -> int:
        return hash(self.value)


@dataclass
class DomainEvent:
    """Base class for domain events"""
    event_id: EntityId = field(default_factory=EntityId.generate)
    aggregate_id: Optional[EntityId] = None
    occurred_on: datetime = field(default_factory=datetime.utcnow)
    event_type: str = field(default="")
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.event_type:
            self.event_type = self.__class__.__name__


T = TypeVar('T', bound=EntityId)


class Entity(ABC, Generic[T]):
    """
    Abstract base class for all domain entities.
    
    Implements:
    - Identity-based equality
    - Domain event tracking
    - State tracking
    """
    
    def __init__(self, entity_id: T):
        self._id = entity_id
        self._domain_events: List[DomainEvent] = []
        self._created_at = datetime.utcnow()
        self._updated_at = self._created_at
        self._version = 0
    
    @property
    def id(self) -> T:
        """Get entity identity"""
        return self._id
    
    @property
    def created_at(self) -> datetime:
        return self._created_at
    
    @property
    def updated_at(self) -> datetime:
        return self._updated_at
    
    @property
    def version(self) -> int:
        return self._version
    
    def add_domain_event(self, event: DomainEvent) -> None:
        """Add domain event to track"""
        event.aggregate_id = self._id
        self._domain_events.append(event)
        self._updated_at = datetime.utcnow()
        self._version += 1
    
    def get_domain_events(self) -> List[DomainEvent]:
        """Get all pending domain events"""
        return self._domain_events.copy()
    
    def clear_domain_events(self) -> None:
        """Clear domain events after publishing"""
        self._domain_events.clear()
    
    def __eq__(self, other: object) -> bool:
        """Entities are equal if same type and ID"""
        if not isinstance(other, Entity):
            return False
        return self._id == other._id and type(self) == type(other)
    
    def __hash__(self) -> int:
        return hash((type(self), self._id))
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize entity to dictionary"""
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Entity":
        """Deserialize entity from dictionary"""
        pass


class AggregateRoot(Entity[T]):
    """
    Aggregate Root entity.
    
    An aggregate is a cluster of associated objects that we treat as a unit
    for the purpose of data changes. The aggregate root is the parent entity.
    """
    
    def __init__(self, entity_id: T):
        super().__init__(entity_id)
        self._is_consistent = True
    
    def check_invariants(self) -> bool:
        """Check business invariants"""
        return self._is_consistent
    
    def mark_inconsistent(self) -> None:
        """Mark aggregate as inconsistent (for eventual consistency)"""
        self._is_consistent = False
    
    def mark_consistent(self) -> None:
        """Mark aggregate as consistent"""
        self._is_consistent = True
