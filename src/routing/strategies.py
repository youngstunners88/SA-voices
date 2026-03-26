"""Routing strategies for voice processing"""

import random
from typing import List, Optional

from .router import RoutingStrategy, RouteRequest, HandlerStatus, RouteType, RoutePriority


class LanguageBasedStrategy(RoutingStrategy):
    """Route based on language requirements"""
    
    def __init__(self, language_capabilities: dict = None):
        self.language_capabilities = language_capabilities or {}
    
    def get_name(self) -> str:
        return "language_based"
    
    def select_handler(self, request: RouteRequest, 
                      handlers: List[HandlerStatus]) -> Optional[HandlerStatus]:
        if not request.language:
            return None
        
        # Find handlers that support the requested language
        capable = []
        for handler in handlers:
            langs = self.language_capabilities.get(handler.name, [])
            if request.language in langs:
                capable.append(handler)
        
        if not capable:
            return None
        
        # Select least loaded capable handler
        return min(capable, key=lambda h: h.utilization)
    
    def set_capabilities(self, handler_name: str, languages: List[str]):
        """Set supported languages for a handler"""
        self.language_capabilities[handler_name] = languages


class PriorityStrategy(RoutingStrategy):
    """Route based on priority levels with preference for less loaded handlers"""
    
    def __init__(self, priority_weights: dict = None):
        self.priority_weights = priority_weights or {
            RoutePriority.CRITICAL: 10.0,
            RoutePriority.HIGH: 5.0,
            RoutePriority.NORMAL: 1.0,
            RoutePriority.LOW: 0.5,
            RoutePriority.BATCH: 0.1,
        }
    
    def get_name(self) -> str:
        return "priority"
    
    def select_handler(self, request: RouteRequest, 
                      handlers: List[HandlerStatus]) -> Optional[HandlerStatus]:
        if not handlers:
            return None
        
        # Calculate score for each handler
        best_handler = None
        best_score = float('-inf')
        
        for handler in handlers:
            # Higher availability is better
            availability_score = handler.available_capacity / handler.max_capacity
            
            # Higher success rate is better
            success_score = handler.success_rate
            
            # Lower latency is better (inverse of processing time)
            latency_score = 1.0 / (1.0 + handler.avg_processing_time)
            
            # Weight by priority
            priority_weight = self.priority_weights.get(request.priority, 1.0)
            
            # Combine scores
            score = (
                availability_score * 0.4 +
                success_score * 0.3 +
                latency_score * 0.3
            ) * priority_weight
            
            if score > best_score:
                best_score = score
                best_handler = handler
        
        return best_handler


class LoadBalancingStrategy(RoutingStrategy):
    """Distribute load evenly across handlers"""
    
    def __init__(self, algorithm: str = "least_loaded"):
        self.algorithm = algorithm
        self._round_robin_index = 0
    
    def get_name(self) -> str:
        return f"load_balancing_{self.algorithm}"
    
    def select_handler(self, request: RouteRequest, 
                      handlers: List[HandlerStatus]) -> Optional[HandlerStatus]:
        if not handlers:
            return None
        
        healthy = [h for h in handlers if h.is_healthy]
        if not healthy:
            return None
        
        if self.algorithm == "least_loaded":
            # Select handler with lowest utilization
            return min(healthy, key=lambda h: h.utilization)
        
        elif self.algorithm == "round_robin":
            # Cycle through handlers
            handler = healthy[self._round_robin_index % len(healthy)]
            self._round_robin_index = (self._round_robin_index + 1) % len(healthy)
            return handler
        
        elif self.algorithm == "weighted_random":
            # Random selection weighted by available capacity
            total_capacity = sum(h.available_capacity for h in healthy)
            if total_capacity == 0:
                return random.choice(healthy)
            
            r = random.uniform(0, total_capacity)
            cumulative = 0
            for handler in healthy:
                cumulative += handler.available_capacity
                if r <= cumulative:
                    return handler
            return healthy[-1]
        
        elif self.algorithm == "response_time":
            # Select based on response time (lower is better)
            return min(healthy, key=lambda h: h.avg_processing_time)
        
        else:
            return healthy[0]


class CostBasedStrategy(RoutingStrategy):
    """Route based on estimated processing cost"""
    
    def __init__(self):
        self.cost_estimates = {}
    
    def get_name(self) -> str:
        return "cost_based"
    
    def set_cost_estimate(self, handler_name: str, cost_per_request: float):
        """Set cost estimate for a handler"""
        self.cost_estimates[handler_name] = cost_per_request
    
    def select_handler(self, request: RouteRequest, 
                      handlers: List[HandlerStatus]) -> Optional[HandlerStatus]:
        # Estimate request complexity
        complexity = self._estimate_complexity(request)
        
        best_handler = None
        best_cost = float('inf')
        
        for handler in handlers:
            base_cost = self.cost_estimates.get(handler.name, 1.0)
            total_cost = base_cost * complexity / max(0.1, handler.success_rate)
            
            if total_cost < best_cost:
                best_cost = total_cost
                best_handler = handler
        
        return best_handler
    
    def _estimate_complexity(self, request: RouteRequest) -> float:
        """Estimate processing complexity"""
        complexity = 1.0
        
        payload = request.payload
        
        # Text length affects TTS complexity
        if 'text' in payload:
            text_len = len(payload['text'])
            complexity += text_len / 100  # Per 100 chars
        
        # Audio processing complexity
        if request.route_type == RouteType.AUDIO_PROCESSING:
            complexity *= 2.0
        
        # Voice cloning is most complex
        if request.route_type == RouteType.VOICE_CLONING:
            complexity *= 3.0
        
        # Streaming has overhead
        if request.route_type == RouteType.STREAMING:
            complexity *= 1.5
        
        return complexity


class AffinityStrategy(RoutingStrategy):
    """Route requests from same session to same handler (session affinity)"""
    
    def __init__(self):
        self.session_handlers: dict = {}
        self.max_sessions_per_handler = 100
    
    def get_name(self) -> str:
        return "affinity"
    
    def select_handler(self, request: RouteRequest, 
                      handlers: List[HandlerStatus]) -> Optional[HandlerStatus]:
        if not request.session_id:
            return None
        
        # Check if session already assigned
        if request.session_id in self.session_handlers:
            assigned = self.session_handlers[request.session_id]
            # Verify handler is still healthy
            if assigned in [h.name for h in handlers if h.is_healthy]:
                for h in handlers:
                    if h.name == assigned and h.is_healthy:
                        return h
        
        # Assign to least loaded handler
        healthy = [h for h in handlers if h.is_healthy]
        if not healthy:
            return None
        
        selected = min(healthy, key=lambda h: h.utilization)
        self.session_handlers[request.session_id] = selected.name
        
        return selected


class HybridStrategy(RoutingStrategy):
    """Combines multiple strategies with fallback"""
    
    def __init__(self, strategies_with_weights: List[tuple] = None):
        # Default: Try language, then priority, then load balancing
        self.strategies = strategies_with_weights or [
            (LanguageBasedStrategy(), 0.4),
            (PriorityStrategy(), 0.3),
            (LoadBalancingStrategy("least_loaded"), 0.3),
        ]
    
    def get_name(self) -> str:
        return "hybrid"
    
    def select_handler(self, request: RouteRequest, 
                      handlers: List[HandlerStatus]) -> Optional[HandlerStatus]:
        scores = {h.name: 0.0 for h in handlers}
        
        for strategy, weight in self.strategies:
            selected = strategy.select_handler(request, handlers)
            if selected:
                scores[selected.name] += weight
        
        if not scores:
            return None
        
        # Select handler with highest score
        best_name = max(scores, key=scores.get)
        for h in handlers:
            if h.name == best_name:
                return h
        
        return None


class FallbackStrategy(RoutingStrategy):
    """Try primary strategies, fall back to simple selection"""
    
    def __init__(self, primary_strategies: List[RoutingStrategy] = None):
        self.primary = primary_strategies or [
            LanguageBasedStrategy(),
            LoadBalancingStrategy("least_loaded"),
        ]
    
    def get_name(self) -> str:
        return "fallback"
    
    def select_handler(self, request: RouteRequest, 
                      handlers: List[HandlerStatus]) -> Optional[HandlerStatus]:
        # Try primary strategies
        for strategy in self.primary:
            selected = strategy.select_handler(request, handlers)
            if selected:
                return selected
        
        # Fallback: random healthy handler
        healthy = [h for h in handlers if h.is_healthy]
        return random.choice(healthy) if healthy else None
