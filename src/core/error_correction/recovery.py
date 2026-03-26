"""
Error Recovery System

Provides automatic recovery from various error conditions,
including crashes, corruption, and service failures.
"""

import asyncio
import functools
import json
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union
import logging

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of errors"""
    FILESYSTEM = auto()
    NETWORK = auto()
    DATABASE = auto()
    MEMORY = auto()
    TTS = auto()
    API = auto()
    UNKNOWN = auto()


class RecoveryStrategy(Enum):
    """Recovery strategies"""
    RETRY = "retry"  # Simple retry
    BACKOFF = "backoff"  # Exponential backoff
    CIRCUIT_BREAKER = "circuit_breaker"  # Circuit breaker pattern
    FALLBACK = "fallback"  # Use fallback
    RESET = "reset"  # Reset and restart
    NONE = "none"  # No recovery


@dataclass
class ErrorContext:
    """Context information about an error"""
    error_id: str
    category: ErrorCategory
    error_type: str
    error_message: str
    stack_trace: str
    timestamp: datetime
    component: str
    operation: str
    context_data: Dict[str, Any]
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_id": self.error_id,
            "category": self.category.name,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace,
            "timestamp": self.timestamp.isoformat(),
            "component": self.component,
            "operation": self.operation,
            "context_data": self.context_data,
            "recovery_attempts": self.recovery_attempts,
            "max_recovery_attempts": self.max_recovery_attempts,
        }


@dataclass
class RecoveryResult:
    """Result of a recovery attempt"""
    success: bool
    strategy_used: RecoveryStrategy
    attempts_made: int
    final_error: Optional[Exception] = None
    recovery_data: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.recovery_data is None:
            self.recovery_data = {}


T = TypeVar('T')


class RecoveryAction(ABC, Generic[T]):
    """Abstract base class for recovery actions"""
    
    @abstractmethod
    async def execute(self, context: ErrorContext) -> RecoveryResult:
        """Execute recovery action"""
        pass
    
    @property
    @abstractmethod
    def strategy(self) -> RecoveryStrategy:
        """Get recovery strategy type"""
        pass


class RetryRecovery(RecoveryAction):
    """Simple retry recovery"""
    
    def __init__(self, max_retries: int = 3, delay: float = 1.0):
        self.max_retries = max_retries
        self.delay = delay
    
    @property
    def strategy(self) -> RecoveryStrategy:
        return RecoveryStrategy.RETRY
    
    async def execute(self, context: ErrorContext) -> RecoveryResult:
        # This is a placeholder - actual retry logic is in the decorator
        return RecoveryResult(
            success=True,
            strategy_used=self.strategy,
            attempts_made=context.recovery_attempts,
            recovery_data={"max_retries": self.max_retries, "delay": self.delay}
        )


class BackoffRecovery(RecoveryAction):
    """Exponential backoff recovery"""
    
    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
    
    @property
    def strategy(self) -> RecoveryStrategy:
        return RecoveryStrategy.BACKOFF
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for attempt"""
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)
    
    async def execute(self, context: ErrorContext) -> RecoveryResult:
        return RecoveryResult(
            success=True,
            strategy_used=self.strategy,
            attempts_made=context.recovery_attempts,
            recovery_data={
                "max_retries": self.max_retries,
                "base_delay": self.base_delay,
                "max_delay": self.max_delay,
            }
        )


class CircuitBreakerRecovery(RecoveryAction):
    """Circuit breaker pattern recovery"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._failures = 0
        self._last_failure_time: Optional[datetime] = None
        self._state = "closed"  # closed, open, half_open
        self._half_open_calls = 0
    
    @property
    def strategy(self) -> RecoveryStrategy:
        return RecoveryStrategy.CIRCUIT_BREAKER
    
    def can_execute(self) -> bool:
        """Check if operation can be executed"""
        if self._state == "closed":
            return True
        
        if self._state == "open":
            if self._last_failure_time:
                elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self._state = "half_open"
                    self._half_open_calls = 0
                    return True
            return False
        
        if self._state == "half_open":
            return self._half_open_calls < self.half_open_max_calls
        
        return True
    
    def record_success(self):
        """Record successful operation"""
        if self._state == "half_open":
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                self._state = "closed"
                self._failures = 0
        else:
            self._failures = 0
    
    def record_failure(self):
        """Record failed operation"""
        self._failures += 1
        self._last_failure_time = datetime.now()
        
        if self._state == "half_open":
            self._state = "open"
        elif self._failures >= self.failure_threshold:
            self._state = "open"
    
    async def execute(self, context: ErrorContext) -> RecoveryResult:
        if not self.can_execute():
            return RecoveryResult(
                success=False,
                strategy_used=self.strategy,
                attempts_made=0,
                final_error=Exception("Circuit breaker is open"),
                recovery_data={"state": self._state, "failures": self._failures}
            )
        
        return RecoveryResult(
            success=True,
            strategy_used=self.strategy,
            attempts_made=context.recovery_attempts,
            recovery_data={"state": self._state, "can_execute": True}
        )


class FallbackRecovery(RecoveryAction):
    """Fallback to alternative implementation"""
    
    def __init__(self, fallback_callable: Callable[..., T]):
        self.fallback_callable = fallback_callable
    
    @property
    def strategy(self) -> RecoveryStrategy:
        return RecoveryStrategy.FALLBACK
    
    async def execute(self, context: ErrorContext) -> RecoveryResult:
        try:
            if asyncio.iscoroutinefunction(self.fallback_callable):
                result = await self.fallback_callable()
            else:
                result = self.fallback_callable()
            
            return RecoveryResult(
                success=True,
                strategy_used=self.strategy,
                attempts_made=1,
                recovery_data={"fallback_result": result}
            )
        except Exception as e:
            return RecoveryResult(
                success=False,
                strategy_used=self.strategy,
                attempts_made=1,
                final_error=e,
            )


class ErrorRecovery:
    """
    Central error recovery manager.
    
    Coordinates recovery actions and tracks error history.
    """
    
    def __init__(self):
        self._recovery_actions: Dict[ErrorCategory, List[RecoveryAction]] = {}
        self._error_history: List[ErrorContext] = []
        self._max_history = 1000
        self._circuit_breakers: Dict[str, CircuitBreakerRecovery] = {}
    
    def register_recovery_action(
        self,
        category: ErrorCategory,
        action: RecoveryAction
    ):
        """Register recovery action for error category"""
        if category not in self._recovery_actions:
            self._recovery_actions[category] = []
        self._recovery_actions[category].append(action)
    
    def get_circuit_breaker(self, name: str) -> CircuitBreakerRecovery:
        """Get or create circuit breaker"""
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = CircuitBreakerRecovery()
        return self._circuit_breakers[name]
    
    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify error into category"""
        error_type = type(error).__name__.lower()
        error_msg = str(error).lower()
        
        if any(x in error_type for x in ['file', 'io', 'notfound', 'permission']):
            return ErrorCategory.FILESYSTEM
        
        if any(x in error_type for x in ['connection', 'network', 'timeout', 'http']):
            return ErrorCategory.NETWORK
        
        if any(x in error_type for x in ['database', 'sql', 'db']):
            return ErrorCategory.DATABASE
        
        if any(x in error_type for x in ['memory', 'oom', 'allocation']):
            return ErrorCategory.MEMORY
        
        if any(x in error_type for x in ['tts', 'synthesis', 'audio']):
            return ErrorCategory.TTS
        
        if any(x in error_type for x in ['api', 'route', 'endpoint']):
            return ErrorCategory.API
        
        return ErrorCategory.UNKNOWN
    
    def create_error_context(
        self,
        error: Exception,
        component: str,
        operation: str,
        context_data: Dict[str, Any] = None
    ) -> ErrorContext:
        """Create error context from exception"""
        import uuid
        
        return ErrorContext(
            error_id=str(uuid.uuid4())[:8],
            category=self.classify_error(error),
            error_type=type(error).__name__,
            error_message=str(error),
            stack_trace=traceback.format_exc(),
            timestamp=datetime.now(),
            component=component,
            operation=operation,
            context_data=context_data or {},
        )
    
    async def attempt_recovery(
        self,
        context: ErrorContext,
        strategy: Optional[RecoveryStrategy] = None
    ) -> RecoveryResult:
        """Attempt to recover from error"""
        self._error_history.append(context)
        
        # Trim history
        if len(self._error_history) > self._max_history:
            self._error_history = self._error_history[-self._max_history:]
        
        # Get recovery actions for category
        actions = self._recovery_actions.get(context.category, [])
        
        if strategy:
            # Filter to specific strategy
            actions = [a for a in actions if a.strategy == strategy]
        
        if not actions:
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.NONE,
                attempts_made=0,
                final_error=Exception(f"No recovery actions for {context.category}"),
            )
        
        # Try each recovery action
        for action in actions:
            try:
                result = await action.execute(context)
                if result.success:
                    return result
            except Exception as e:
                logger.error(f"Recovery action failed: {e}")
                continue
        
        return RecoveryResult(
            success=False,
            strategy_used=RecoveryStrategy.NONE,
            attempts_made=len(actions),
            final_error=Exception("All recovery actions failed"),
        )
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        stats = {
            "total_errors": len(self._error_history),
            "by_category": {},
            "by_component": {},
            "recent_errors": [],
        }
        
        for error in self._error_history:
            # By category
            cat = error.category.name
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
            
            # By component
            comp = error.component
            stats["by_component"][comp] = stats["by_component"].get(comp, 0) + 1
        
        # Recent errors (last 10)
        stats["recent_errors"] = [
            {
                "error_id": e.error_id,
                "category": e.category.name,
                "component": e.component,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in self._error_history[-10:]
        ]
        
        return stats


def with_recovery(
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    max_retries: int = 3,
    strategy: RecoveryStrategy = RecoveryStrategy.BACKOFF,
    fallback: Optional[Callable] = None,
    component: str = "unknown"
):
    """Decorator for automatic error recovery"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            recovery = ErrorRecovery()
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    
                    # Create error context
                    context = recovery.create_error_context(
                        error=e,
                        component=component,
                        operation=func.__name__,
                        context_data={"attempt": attempt, "args": str(args), "kwargs": str(kwargs)}
                    )
                    context.recovery_attempts = attempt
                    
                    # Calculate backoff delay
                    if strategy == RecoveryStrategy.BACKOFF and attempt < max_retries - 1:
                        delay = min(2 ** attempt, 60)
                        logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                        await asyncio.sleep(delay)
                    
                    # Attempt recovery on last try
                    if attempt == max_retries - 1:
                        result = await recovery.attempt_recovery(context, strategy)
                        if result.success and fallback:
                            return fallback()
            
            raise last_error
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Run async wrapper
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# Global error recovery instance
_global_recovery = ErrorRecovery()


def get_error_recovery() -> ErrorRecovery:
    """Get global error recovery instance"""
    return _global_recovery
