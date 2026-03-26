"""State management for conversations and voice profiles"""

import json
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path


class ConversationStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class VoiceProfile:
    """Voice profile for a user or character"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "default"
    language: str = "en"
    gender: str = "neutral"
    age_group: str = "adult"
    accent: Optional[str] = None
    speaking_rate: float = 1.0  # 0.5 to 2.0
    pitch: float = 1.0  # 0.5 to 2.0
    volume: float = 1.0  # 0.0 to 1.0
    emotion: str = "neutral"
    custom_settings: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VoiceProfile":
        return cls(**data)


@dataclass
class Message:
    """A single message in a conversation"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: str = "user"  # user, assistant, system
    content: str = ""
    language: str = "en"
    audio_path: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConversationState:
    """Complete conversation state"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    status: str = ConversationStatus.ACTIVE.value
    language: str = "en"
    detected_language: Optional[str] = None
    voice_profile: VoiceProfile = field(default_factory=VoiceProfile)
    messages: List[Message] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None
    
    def __post_init__(self):
        if isinstance(self.voice_profile, dict):
            self.voice_profile = VoiceProfile.from_dict(self.voice_profile)
        if isinstance(self.messages, list) and len(self.messages) > 0:
            if isinstance(self.messages[0], dict):
                self.messages = [Message(**m) for m in self.messages]
    
    def add_message(self, role: str, content: str, language: str = None, 
                   audio_path: str = None, metadata: Dict = None) -> Message:
        """Add a message to the conversation"""
        message = Message(
            role=role,
            content=content,
            language=language or self.language,
            audio_path=audio_path,
            metadata=metadata or {}
        )
        self.messages.append(message)
        self.updated_at = datetime.now().isoformat()
        return message
    
    def get_context_window(self, max_messages: int = 10) -> List[Message]:
        """Get recent messages for context"""
        return self.messages[-max_messages:] if self.messages else []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "status": self.status,
            "language": self.language,
            "detected_language": self.detected_language,
            "voice_profile": self.voice_profile.to_dict(),
            "messages": [m.to_dict() for m in self.messages],
            "context": self.context,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationState":
        return cls(**data)


class StateManager:
    """Manages conversation and voice profile states"""
    
    def __init__(self, storage_backend=None, session_timeout: int = 3600):
        self.storage = storage_backend
        self.session_timeout = session_timeout
        self._local_cache: Dict[str, ConversationState] = {}
    
    async def create_session(self, user_id: Optional[str] = None,
                           language: str = None,
                           voice_profile: VoiceProfile = None) -> ConversationState:
        """Create a new conversation session"""
        expires = datetime.now() + timedelta(seconds=self.session_timeout)
        
        state = ConversationState(
            user_id=user_id,
            language=language or "en",
            voice_profile=voice_profile or VoiceProfile(),
            expires_at=expires.isoformat()
        )
        
        await self._save_state(state)
        return state
    
    async def get_session(self, session_id: str) -> Optional[ConversationState]:
        """Get conversation state by session ID"""
        # Check local cache first
        if session_id in self._local_cache:
            return self._local_cache[session_id]
        
        # Try storage backend
        if self.storage:
            data = await self.storage.get(f"session:{session_id}")
            if data:
                state = ConversationState.from_dict(json.loads(data))
                self._local_cache[session_id] = state
                return state
        
        return None
    
    async def update_session(self, session_id: str, 
                           updates: Dict[str, Any]) -> Optional[ConversationState]:
        """Update conversation state"""
        state = await self.get_session(session_id)
        if not state:
            return None
        
        for key, value in updates.items():
            if hasattr(state, key):
                setattr(state, key, value)
        
        state.updated_at = datetime.now().isoformat()
        await self._save_state(state)
        return state
    
    async def add_message(self, session_id: str, role: str, content: str,
                         language: str = None, audio_path: str = None,
                         metadata: Dict = None) -> Optional[Message]:
        """Add message to conversation"""
        state = await self.get_session(session_id)
        if not state:
            return None
        
        message = state.add_message(role, content, language, audio_path, metadata)
        await self._save_state(state)
        return message
    
    async def end_session(self, session_id: str) -> bool:
        """End a conversation session"""
        state = await self.get_session(session_id)
        if not state:
            return False
        
        state.status = ConversationStatus.COMPLETED.value
        await self._save_state(state)
        
        # Clear from cache
        if session_id in self._local_cache:
            del self._local_cache[session_id]
        
        return True
    
    async def get_user_sessions(self, user_id: str, 
                               limit: int = 10) -> List[ConversationState]:
        """Get recent sessions for a user"""
        if self.storage:
            session_ids = await self.storage.list_keys(f"user:{user_id}:sessions")
            sessions = []
            for sid in session_ids[:limit]:
                state = await self.get_session(sid.replace("session:", ""))
                if state:
                    sessions.append(state)
            return sessions
        return []
    
    async def save_voice_profile(self, profile: VoiceProfile) -> str:
        """Save a voice profile"""
        await self._save_to_storage(f"profile:{profile.id}", profile.to_dict())
        return profile.id
    
    async def get_voice_profile(self, profile_id: str) -> Optional[VoiceProfile]:
        """Get voice profile by ID"""
        data = await self._get_from_storage(f"profile:{profile_id}")
        if data:
            return VoiceProfile.from_dict(data)
        return None
    
    async def _save_state(self, state: ConversationState):
        """Save state to all backends"""
        self._local_cache[state.session_id] = state
        await self._save_to_storage(f"session:{state.session_id}", state.to_dict())
        
        if state.user_id:
            await self._save_to_storage(
                f"user:{state.user_id}:sessions:{state.session_id}",
                {"session_id": state.session_id, "updated_at": state.updated_at}
            )
    
    async def _save_to_storage(self, key: str, data: Any):
        """Save to storage backend"""
        if self.storage:
            await self.storage.set(key, json.dumps(data), ttl=self.session_timeout)
    
    async def _get_from_storage(self, key: str) -> Optional[Dict]:
        """Get from storage backend"""
        if self.storage:
            data = await self.storage.get(key)
            if data:
                return json.loads(data)
        return None
    
    def clear_cache(self):
        """Clear local cache"""
        self._local_cache.clear()
