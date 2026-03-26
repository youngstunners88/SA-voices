"""Intelligent request routing for voice processing"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Generic
from collections import deque
import asyncio


class RoutePriority(Enum):
    CRITICAL = 0    # System-critical operations
    HIGH = 1        # Real-time voice synthesis
    NORMAL = 2      # Standard requests
    LOW = 3         # Background tasks
    BATCH = 4       # Bulk processing


class RouteType(Enum):
    TTS_SYNTHESIS = "tts_synthesis"
    LANGUAGE_DETECTION = "language_detection"
    VOICE_CLONING = "voice_cloning"
    AUDIO_PROCESSING = "audio_processing"
    STREAMING = "streaming"
    BATCH_PROCESSING = "batch_processing"


@dataclass
class RouteRequest:
    """A routing request"""
    request_id: str
    route_type: RouteType
    priority: RoutePriority
    payload: Dict[str, Any]
    language: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    timeout: float = 30.0
    retry_count: int = 0
    max_retries: int = 3
    
    @property
    def age(self) -> float:
        return time.time() - self.timestamp


@dataclass
class RouteResult:
    """Result of a routing decision"""
    request_id: str
    handler: str
    queue_position: int
    estimated_wait: float
    priority: RoutePriority
    strategy_used: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HandlerStatus:
    """Status of a route handler"""
    name: str
    route_types: List[RouteType]
    current_load: int = 0
    max_capacity: int = 10
    avg_processing_time: float = 1.0
    success_rate: float = 1.0
    is_healthy: bool = True
    last_health_check: float = field(default_factory=time.time)
    
    @property
    def available_capacity(self) -> int:
        return max(0, self.max_capacity - self.current_load)
    
    @property
    def utilization(self) -> float:
        return self.current_load / self.max_capacity if self.max_capacity > 0 else 1.0


class RoutingStrategy(ABC):
    """Abstract routing strategy"""
    
    @abstractmethod
    def select_handler(self, request: RouteRequest, 
                      handlers: List[HandlerStatus]) -> Optional[HandlerStatus]:
        """Select best handler for request"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get strategy name"""
        pass


class VoiceRouter:
    """Intelligent voice request router"""
    
    def __init__(self):
        self.handlers: Dict[str, HandlerStatus] = {}
        self.queues: Dict[RouteType, deque] = {
            route_type: deque() for route_type in RouteType
        }
        self.strategies: List[RoutingStrategy] = []
        self.request_history: deque = deque(maxlen=1000)
        self._processing = False
        self._lock = asyncio.Lock()
    
    def register_handler(self, name: str, route_types: List[RouteType],
                        max_capacity: int = 10) -> HandlerStatus:
        """Register a new route handler"""
        status = HandlerStatus(
            name=name,
            route_types=route_types,
            max_capacity=max_capacity
        )
        self.handlers[name] = status
        return status
    
    def unregister_handler(self, name: str):
        """Unregister a handler"""
        if name in self.handlers:
            del self.handlers[name]
    
    def add_strategy(self, strategy: RoutingStrategy):
        """Add a routing strategy"""
        self.strategies.append(strategy)
    
    async def route(self, request: RouteRequest) -> RouteResult:
        """Route a request to appropriate handler"""
        async with self._lock:
            # Get eligible handlers
            eligible = [
                h for h in self.handlers.values()
                if request.route_type in h.route_types and h.is_healthy
            ]
            
            if not eligible:
                # Queue the request
                self.queues[request.route_type].append(request)
                return RouteResult(
                    request_id=request.request_id,
                    handler="queued",
                    queue_position=len(self.queues[request.route_type]),
                    estimated_wait=self._estimate_wait(request.route_type),
                    priority=request.priority,
                    strategy_used="queue"
                )
            
            # Try strategies in order
            selected = None
            strategy_name = "none"
            
            for strategy in self.strategies:
                selected = strategy.select_handler(request, eligible)
                if selected:
                    strategy_name = strategy.get_name()
                    break
            
            # Fallback to first available
            if not selected:
                selected = eligible[0]
                strategy_name = "fallback"
            
            # Update handler load
            selected.current_load += 1
            
            # Calculate queue position and wait
            queue_len = sum(len(q) for q in self.queues.values())
            estimated_wait = selected.avg_processing_time * (selected.current_load - 1)
            
            result = RouteResult(
                request_id=request.request_id,
                handler=selected.name,
                queue_position=queue_len,
                estimated_wait=estimated_wait,
                priority=request.priority,
                strategy_used=strategy_name,
                metadata={
                    "handler_utilization": selected.utilization,
                    "handler_capacity": selected.available_capacity
                }
            )
            
            self.request_history.append({
                "request_id": request.request_id,
                "handler": selected.name,
                "timestamp": time.time(),
                "strategy": strategy_name
            })
            
            return result
    
    async def complete_request(self, handler_name: str, 
                              success: bool = True,
                              processing_time: float = 0):
        """Mark request as complete and update handler stats"""
        if handler_name in self.handlers:
            handler = self.handlers[handler_name]
            handler.current_load = max(0, handler.current_load - 1)
            
            # Update moving average
            alpha = 0.1
            handler.avg_processing_time = (
                alpha * processing_time + 
                (1 - alpha) * handler.avg_processing_time
            )
            
            # Update success rate
            handler.success_rate = (
                alpha * (1.0 if success else 0.0) +
                (1 - alpha) * handler.success_rate
            )
    
    def update_handler_health(self, name: str, is_healthy: bool):
        """Update handler health status"""
        if name in self.handlers:
            self.handlers[name].is_healthy = is_healthy
            self.handlers[name].last_health_check = time.time()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get routing statistics"""
        return {
            "handlers": {
                name: {
                    "load": h.current_load,
                    "capacity": h.max_capacity,
                    "utilization": h.utilization,
                    "success_rate": h.success_rate,
                    "healthy": h.is_healthy
                }
                for name, h in self.handlers.items()
            },
            "queues": {
                rt.value: len(q) for rt, q in self.queues.items()
            },
            "total_queued": sum(len(q) for q in self.queues.values()),
            "recent_requests": len(self.request_history)
        }
    
    def _estimate_wait(self, route_type: RouteType) -> float:
        """Estimate wait time for queued request"""
        handlers = [h for h in self.handlers.values() 
                   if route_type in h.route_types and h.is_healthy]
        
        if not handlers:
            return float('inf')
        
        avg_time = sum(h.avg_processing_time for h in handlers) / len(handlers)
        queue_len = len(self.queues[route_type])
        
        return avg_time * queue_len / max(1, sum(h.available_capacity for h in handlers))
    
    async def process_queues(self):
        """Background task to process queued requests"""
        self._processing = True
        while self._processing:
            async with self._lock:
                for route_type, queue in self.queues.items():
                    if queue:
                        # Check if any handler available
                        available = [
                            h for h in self.handlers.values()
                            if route_type in h.route_types 
                            and h.is_healthy 
                            and h.available_capacity > 0
                        ]
                        
                        if available:
                            request = queue.popleft()
                            # Re-route with high priority
                            request.priority = RoutePriority.HIGH
                            await self.route(request)
            
            await asyncio.sleep(0.1)
    
    def stop_processing(self):
        """Stop queue processing"""
        self._processing = False
