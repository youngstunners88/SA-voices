"""Tests for routing system"""

import pytest
import asyncio
from src.routing.router import VoiceRouter, RouteRequest, RouteType, RoutePriority
from src.routing.strategies import PriorityStrategy, LoadBalancingStrategy


class TestVoiceRouter:
    """Test voice router"""
    
    @pytest.fixture
    def router(self):
        return VoiceRouter()
    
    @pytest.mark.asyncio
    async def test_register_handler(self, router):
        handler = router.register_handler(
            "test_handler",
            route_types=[RouteType.TTS_SYNTHESIS],
            max_capacity=5
        )
        assert handler.name == "test_handler"
        assert handler.max_capacity == 5
    
    @pytest.mark.asyncio
    async def test_route_request(self, router):
        router.register_handler(
            "tts_1",
            route_types=[RouteType.TTS_SYNTHESIS],
            max_capacity=5
        )
        
        request = RouteRequest(
            request_id="req_1",
            route_type=RouteType.TTS_SYNTHESIS,
            priority=RoutePriority.NORMAL,
            payload={"text": "Hello"},
            language="en"
        )
        
        result = await router.route(request)
        assert result.handler == "tts_1"
        assert result.request_id == "req_1"
    
    @pytest.mark.asyncio
    async def test_complete_request(self, router):
        router.register_handler(
            "tts_1",
            route_types=[RouteType.TTS_SYNTHESIS],
            max_capacity=5
        )
        
        # Route and complete
        request = RouteRequest(
            request_id="req_1",
            route_type=RouteType.TTS_SYNTHESIS,
            priority=RoutePriority.NORMAL,
            payload={"text": "Hello"},
            language="en"
        )
        
        await router.route(request)
        await router.complete_request("tts_1", success=True, processing_time=1.0)
        
        stats = router.get_stats()
        assert stats["handlers"]["tts_1"]["load"] == 0


class TestRoutingStrategies:
    """Test routing strategies"""
    
    def test_priority_strategy(self):
        strategy = PriorityStrategy()
        assert strategy.get_name() == "priority"
    
    def test_load_balancing_strategy(self):
        strategy = LoadBalancingStrategy("least_loaded")
        assert strategy.get_name() == "load_balancing_least_loaded"
        
        strategy = LoadBalancingStrategy("round_robin")
        assert strategy.get_name() == "load_balancing_round_robin"


class TestRouteRequest:
    """Test route request model"""
    
    def test_request_creation(self):
        request = RouteRequest(
            request_id="req_1",
            route_type=RouteType.TTS_SYNTHESIS,
            priority=RoutePriority.HIGH,
            payload={"text": "Hello"}
        )
        
        assert request.request_id == "req_1"
        assert request.priority == RoutePriority.HIGH
        assert request.retry_count == 0
        assert request.max_retries == 3
