"""API endpoints for SA Voices"""

import io
import base64
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from ..core.config import get_settings, LANGUAGE_METADATA
from ..state.manager import StateManager, ConversationState, VoiceProfile
from ..routing.router import VoiceRouter, RouteRequest, RouteType, RoutePriority
from ..tts.engine import TTSEngine, SynthesisRequest


router = APIRouter()

# Global instances (would be properly managed with dependency injection in production)
_state_manager: Optional[StateManager] = None
_voice_router: Optional[VoiceRouter] = None
_tts_engine: Optional[TTSEngine] = None


def get_state_manager() -> StateManager:
    global _state_manager
    if _state_manager is None:
        from ..state.storage import SQLiteStorage
        _state_manager = StateManager(storage_backend=SQLiteStorage())
    return _state_manager


def get_voice_router() -> VoiceRouter:
    global _voice_router
    if _voice_router is None:
        _voice_router = VoiceRouter()
        # Register handlers
        _voice_router.register_handler(
            "tts_primary",
            [RouteType.TTS_SYNTHESIS, RouteType.STREAMING],
            max_capacity=5
        )
        _voice_router.register_handler(
            "language_detector",
            [RouteType.LANGUAGE_DETECTION],
            max_capacity=10
        )
        # Add strategies
        from ..routing.strategies import PriorityStrategy, LoadBalancingStrategy
        _voice_router.add_strategy(PriorityStrategy())
        _voice_router.add_strategy(LoadBalancingStrategy("least_loaded"))
    return _voice_router


def get_tts_engine() -> TTSEngine:
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = TTSEngine()
        # Add default preprocessors
        from ..tts.engine import normalize_text, expand_abbreviations
        from ..tts.engine import normalize_volume, remove_silence_edges
        _tts_engine.add_preprocessor(normalize_text)
        _tts_engine.add_preprocessor(expand_abbreviations)
        _tts_engine.add_postprocessor(normalize_volume)
        _tts_engine.add_postprocessor(remove_silence_edges)
    return _tts_engine


# Pydantic models
class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Text to synthesize")
    language: str = Field(default="en", description="Language code (e.g., 'zu', 'af', 'en')")
    voice_profile: Optional[Dict[str, Any]] = Field(default=None, description="Voice settings")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed")
    pitch: float = Field(default=1.0, ge=0.5, le=2.0, description="Voice pitch")
    format: str = Field(default="wav", description="Audio format: wav, mp3, ogg")
    stream: bool = Field(default=False, description="Enable streaming")


class SynthesizeResponse(BaseModel):
    success: bool
    audio_base64: Optional[str] = None
    audio_url: Optional[str] = None
    language: str
    processing_time: float
    sample_rate: int
    session_id: Optional[str] = None
    metadata: Dict[str, Any]


class CreateSessionRequest(BaseModel):
    user_id: Optional[str] = None
    language: Optional[str] = "en"
    voice_profile: Optional[Dict[str, Any]] = None


class SessionResponse(BaseModel):
    session_id: str
    status: str
    language: str
    created_at: str
    expires_at: Optional[str]


class LanguageInfo(BaseModel):
    code: str
    name: str
    native_name: str
    speakers: str
    region: str
    sample_text: str
    supported: bool


# Endpoints
@router.get("/")
async def root():
    """API root"""
    settings = get_settings()
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "South African Multilingual Voice Agent API",
        "languages": len(settings.supported_languages_list),
        "docs": "/docs"
    }


@router.get("/languages", response_model=List[LanguageInfo])
async def list_languages():
    """List all supported languages"""
    settings = get_settings()
    
    languages = []
    for code in settings.supported_languages_list:
        info = LANGUAGE_METADATA.get(code, {})
        languages.append(LanguageInfo(
            code=code,
            name=info.get("name", code),
            native_name=info.get("native_name", code),
            speakers=info.get("speakers", "Unknown"),
            region=info.get("region", "Unknown"),
            sample_text=info.get("sample_text", ""),
            supported=True
        ))
    
    return languages


@router.get("/languages/{code}")
async def get_language(code: str):
    """Get language details"""
    settings = get_settings()
    
    if code not in settings.supported_languages_list:
        raise HTTPException(status_code=404, detail=f"Language '{code}' not supported")
    
    info = LANGUAGE_METADATA.get(code, {})
    return {
        "code": code,
        **info,
        "tts_support": True,
        "dataset_samples": 0  # Would be populated from actual dataset
    }


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    state_manager: StateManager = Depends(get_state_manager)
):
    """Create a new conversation session"""
    voice_profile = None
    if request.voice_profile:
        voice_profile = VoiceProfile(**request.voice_profile)
    
    state = await state_manager.create_session(
        user_id=request.user_id,
        language=request.language,
        voice_profile=voice_profile
    )
    
    return SessionResponse(
        session_id=state.session_id,
        status=state.status,
        language=state.language,
        created_at=state.created_at,
        expires_at=state.expires_at
    )


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    state_manager: StateManager = Depends(get_state_manager)
):
    """Get session details"""
    state = await state_manager.get_session(session_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return state.to_dict()


@router.post("/sessions/{session_id}/messages")
async def add_message(
    session_id: str,
    role: str,
    content: str,
    language: Optional[str] = None,
    state_manager: StateManager = Depends(get_state_manager)
):
    """Add a message to a session"""
    message = await state_manager.add_message(
        session_id=session_id,
        role=role,
        content=content,
        language=language
    )
    
    if not message:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return message.to_dict()


@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize(
    request: SynthesizeRequest,
    background_tasks: BackgroundTasks,
    state_manager: StateManager = Depends(get_state_manager),
    voice_router: VoiceRouter = Depends(get_voice_router),
    tts_engine: TTSEngine = Depends(get_tts_engine)
):
    """Synthesize speech from text"""
    settings = get_settings()
    
    # Validate language
    if request.language not in settings.supported_languages_list:
        raise HTTPException(
            status_code=400, 
            detail=f"Language '{request.language}' not supported"
        )
    
    # Route the request
    route_request = RouteRequest(
        request_id=f"tts_{hash(request.text + request.language)}",
        route_type=RouteType.TTS_SYNTHESIS,
        priority=RoutePriority.NORMAL,
        payload=request.dict(),
        language=request.language
    )
    
    route_result = await voice_router.route(route_request)
    
    if request.stream:
        # Return streaming response
        async def generate_audio():
            synth_request = SynthesisRequest(
                text=request.text,
                language=request.language,
                voice_profile=request.voice_profile,
                speed=request.speed,
                pitch=request.pitch,
                stream=True
            )
            
            for chunk in tts_engine.synthesize_stream(synth_request):
                yield chunk.to_bytes()
            
            await voice_router.complete_request(
                route_result.handler,
                success=True
            )
        
        return StreamingResponse(
            generate_audio(),
            media_type=f"audio/{request.format}",
            headers={
                "X-Processing-Handler": route_result.handler,
                "X-Queue-Position": str(route_result.queue_position)
            }
        )
    
    # Synchronous synthesis
    synth_request = SynthesisRequest(
        text=request.text,
        language=request.language,
        voice_profile=request.voice_profile,
        speed=request.speed,
        pitch=request.pitch
    )
    
    try:
        result = tts_engine.synthesize(synth_request)
        
        # Complete routing
        await voice_router.complete_request(
            route_result.handler,
            success=True,
            processing_time=result.processing_time
        )
        
        # Convert to base64
        audio_bytes = result.to_bytes()
        audio_base64 = base64.b64encode(audio_bytes).decode()
        
        return SynthesizeResponse(
            success=True,
            audio_base64=audio_base64,
            language=result.language,
            processing_time=result.processing_time,
            sample_rate=result.sample_rate,
            metadata=result.metadata or {}
        )
        
    except Exception as e:
        await voice_router.complete_request(
            route_result.handler,
            success=False
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synthesize/batch")
async def synthesize_batch(
    requests: List[SynthesizeRequest],
    tts_engine: TTSEngine = Depends(get_tts_engine)
):
    """Batch synthesize multiple texts"""
    synth_requests = [
        SynthesisRequest(
            text=req.text,
            language=req.language,
            voice_profile=req.voice_profile,
            speed=req.speed,
            pitch=req.pitch
        )
        for req in requests
    ]
    
    results = tts_engine.synthesize_batch(synth_requests)
    
    return {
        "results": [
            {
                "success": "error" not in r.metadata,
                "audio_base64": base64.b64encode(r.to_bytes()).decode(),
                "language": r.language,
                "processing_time": r.processing_time,
                "metadata": r.metadata
            }
            for r in results
        ]
    }


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "tts": True,
            "state": True,
            "router": True
        }
    }


@router.get("/stats")
async def get_stats(
    voice_router: VoiceRouter = Depends(get_voice_router),
    tts_engine: TTSEngine = Depends(get_tts_engine)
):
    """Get system statistics"""
    return {
        "router": voice_router.get_stats(),
        "tts": tts_engine.get_metrics()
    }


@router.post("/detect-language")
async def detect_language(text: str):
    """Detect language of text"""
    # Simple detection - in production use proper language detection
    # For now, return based on common words
    
    text_lower = text.lower()
    
    # Simple keyword-based detection
    keywords = {
        "zu": ["sawubona", "unjani", "ngiyaphila", "yebo", "cha"],
        "xh": ["molo", "unjani", "ndiphilile", "ewe", "hayi"],
        "af": ["hallo", "hoe gaan", "goed", "ja", "nee"],
        "nso": ["dumela", "o kae", "ke gona", "ee", "aa"],
        "st": ["lumela", "o phela", "ke teng", "e", "tjhe"],
        "tn": ["dumela", "o tsogile", "ke teng", "ee", "nyaa"],
        "ts": ["avuxeni", "ku njhani", "ndza kona", "ina", "eh"],
        "ss": ["sawubona", "unjani", "ngiyaphila", "yebo", "cha"],
        "ve": ["ndaa", "vho", "ndivhuwa", "ee", "hai"],
        "nr": ["lotjhani", "unjani", "siyaphila", "yebo", "cha"],
    }
    
    scores = {}
    for lang, words in keywords.items():
        score = sum(1 for word in words if word in text_lower)
        if score > 0:
            scores[lang] = score
    
    if scores:
        detected = max(scores, key=scores.get)
        confidence = min(1.0, scores[detected] / 3)
    else:
        detected = "en"
        confidence = 0.5
    
    return {
        "detected_language": detected,
        "confidence": confidence,
        "all_scores": scores
    }
