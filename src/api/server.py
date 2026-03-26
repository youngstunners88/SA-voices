"""FastAPI server for SA Voices"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from ..core.config import get_settings
from .endpoints import router
from ..routing.router import VoiceRouter
from ..routing.strategies import PriorityStrategy, LoadBalancingStrategy, LanguageBasedStrategy


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    settings = get_settings()
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Initialize router and start queue processing
    router_instance = app.state.voice_router
    queue_task = asyncio.create_task(router_instance.process_queues())
    
    print(f"✅ Server ready on http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"📚 API documentation: http://{settings.API_HOST}:{settings.API_PORT}/docs")
    
    yield
    
    # Shutdown
    print("\n🛑 Shutting down...")
    router_instance.stop_processing()
    queue_task.cancel()
    try:
        await queue_task
    except asyncio.CancelledError:
        pass
    print("👋 Goodbye!")


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    settings = get_settings()
    
    # Create app
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="South African Multilingual Voice Agent API",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Initialize voice router
    voice_router = VoiceRouter()
    
    # Register handlers
    voice_router.register_handler(
        "tts_primary",
        route_types=[],
        max_capacity=5
    )
    voice_router.register_handler(
        "language_detector", 
        route_types=[],
        max_capacity=10
    )
    
    # Add strategies
    voice_router.add_strategy(PriorityStrategy())
    voice_router.add_strategy(LoadBalancingStrategy("least_loaded"))
    
    # Store in app state
    app.state.voice_router = voice_router
    
    # Include routers
    app.include_router(router, prefix="/api/v1")
    
    return app


# Create app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "src.api.server:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        workers=1 if settings.API_DEBUG else settings.API_WORKERS,
        reload=settings.API_DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
