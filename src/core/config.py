"""Configuration management for SA Voices"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "SA Voices"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # HuggingFace
    HUGGINGFACE_API_KEY: str
    HUGGINGFACE_CACHE_DIR: str = "./models/cache"
    
    # Qwen3-TTS
    QWEN_TTS_MODEL: str = "Qwen/Qwen3-TTS"
    QWEN_TTS_DEVICE: str = "auto"  # auto, cuda, cpu
    QWEN_TTS_PRECISION: str = "fp16"  # fp16, fp32, int8
    
    # WaxalNLP Dataset
    WAXAL_DATASET: str = "google/WaxalNLP"
    WAXAL_CACHE_DIR: str = "./data/waxal"
    
    # Audio
    AUDIO_SAMPLE_RATE: int = 24000
    AUDIO_FORMAT: str = "wav"
    AUDIO_CHUNK_SIZE: int = 1024
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4
    API_DEBUG: bool = False
    
    # State Management
    REDIS_URL: Optional[str] = None
    DATABASE_URL: str = "sqlite:///./data/sa_voices.db"
    SESSION_TIMEOUT: int = 3600
    
    # Languages
    DEFAULT_LANGUAGE: str = "en"
    SUPPORTED_LANGUAGES: str = "af,en,nr,nso,st,ss,tn,ts,ve,xh,zu"
    LANGUAGE_DETECTION_CONFIDENCE: float = 0.8
    
    # Voice Processing
    VOICE_CLONING_ENABLED: bool = True
    MAX_AUDIO_LENGTH: int = 300  # seconds
    MIN_AUDIO_LENGTH: int = 1    # seconds
    
    # Security
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: str = "./logs/sa_voices.log"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @property
    def supported_languages_list(self) -> List[str]:
        """Get list of supported languages"""
        return [lang.strip() for lang in self.SUPPORTED_LANGUAGES.split(",")]
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get list of CORS origins"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Language metadata
LANGUAGE_METADATA = {
    "af": {
        "name": "Afrikaans",
        "native_name": "Afrikaans",
        "family": "Germanic",
        "speakers": "7.2 million",
        "region": "Western Cape, Northern Cape",
        "sample_text": "Hallo, hoe gaan dit?"
    },
    "en": {
        "name": "English",
        "native_name": "English",
        "family": "Germanic",
        "speakers": "4.9 million",
        "region": "Nationwide",
        "sample_text": "Hello, how are you?"
    },
    "nr": {
        "name": "isiNdebele",
        "native_name": "isiNdebele",
        "family": "Bantu",
        "speakers": "1.1 million",
        "region": "Mpumalanga, Gauteng",
        "sample_text": "Lotjhani, unjani?"
    },
    "nso": {
        "name": "Sepedi",
        "native_name": "Sepedi",
        "family": "Bantu",
        "speakers": "4.7 million",
        "region": "Limpopo, Gauteng",
        "sample_text": "Dumela, o kae?"
    },
    "st": {
        "name": "Sesotho",
        "native_name": "Sesotho",
        "family": "Bantu",
        "speakers": "3.8 million",
        "region": "Free State, Gauteng",
        "sample_text": "Dumela, o phela joang?"
    },
    "ss": {
        "name": "siSwati",
        "native_name": "siSwati",
        "family": "Bantu",
        "speakers": "1.3 million",
        "region": "Mpumalanga, KwaZulu-Natal",
        "sample_text": "Sawubona, unjani?"
    },
    "tn": {
        "name": "Setswana",
        "native_name": "Setswana",
        "family": "Bantu",
        "speakers": "4.1 million",
        "region": "North West, Northern Cape",
        "sample_text": "Dumela, o tsogile jang?"
    },
    "ts": {
        "name": "Xitsonga",
        "native_name": "Xitsonga",
        "family": "Bantu",
        "speakers": "3.2 million",
        "region": "Limpopo, Mpumalanga",
        "sample_text": "Avuxeni, ku njhani?"
    },
    "ve": {
        "name": "Tshivenda",
        "native_name": "Tshivenda",
        "family": "Bantu",
        "speakers": "1.3 million",
        "region": "Limpopo",
        "sample_text": "Ndaa, vhufhee?"
    },
    "xh": {
        "name": "isiXhosa",
        "native_name": "isiXhosa",
        "family": "Bantu",
        "speakers": "8.2 million",
        "region": "Eastern Cape, Western Cape",
        "sample_text": "Molo, unjani?"
    },
    "zu": {
        "name": "isiZulu",
        "native_name": "isiZulu",
        "family": "Bantu",
        "speakers": "12 million",
        "region": "KwaZulu-Natal, Gauteng",
        "sample_text": "Sawubona, unjani?"
    }
}
