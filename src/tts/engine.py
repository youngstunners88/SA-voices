"""TTS Engine with caching and optimization"""

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable
from functools import lru_cache
import numpy as np

from .qwen3_adapter import Qwen3TTSAdapter, TTSResult


@dataclass
class SynthesisRequest:
    """TTS synthesis request"""
    text: str
    language: str = "en"
    voice_profile: Optional[Dict] = None
    speed: float = 1.0
    pitch: float = 1.0
    use_cache: bool = True
    stream: bool = False
    session_id: Optional[str] = None


class CacheManager:
    """Manages TTS cache"""
    
    def __init__(self, cache_dir: str = "./data/cache/tts", max_size_mb: int = 1000):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_mb = max_size_mb
        self._memory_cache: Dict[str, np.ndarray] = {}
        self._max_memory_items = 100
    
    def _get_cache_key(self, text: str, language: str, 
                      voice_profile: Dict = None) -> str:
        """Generate cache key"""
        key_data = f"{text}:{language}:{json.dumps(voice_profile or {}, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, text: str, language: str, 
           voice_profile: Dict = None) -> Optional[TTSResult]:
        """Get cached result"""
        key = self._get_cache_key(text, language, voice_profile)
        
        # Check memory cache
        if key in self._memory_cache:
            return TTSResult(
                audio=self._memory_cache[key],
                sample_rate=24000,
                language=language,
                processing_time=0,
                text=text
            )
        
        # Check disk cache
        cache_file = self.cache_dir / f"{key}.npz"
        if cache_file.exists():
            data = np.load(cache_file)
            return TTSResult(
                audio=data['audio'],
                sample_rate=int(data['sample_rate']),
                language=language,
                processing_time=0,
                text=text
            )
        
        return None
    
    def put(self, result: TTSResult, voice_profile: Dict = None):
        """Cache result"""
        key = self._get_cache_key(result.text, result.language, voice_profile)
        
        # Memory cache
        self._memory_cache[key] = result.audio
        if len(self._memory_cache) > self._max_memory_items:
            # Remove oldest (first added)
            oldest = next(iter(self._memory_cache))
            del self._memory_cache[oldest]
        
        # Disk cache
        cache_file = self.cache_dir / f"{key}.npz"
        np.savez(
            cache_file,
            audio=result.audio,
            sample_rate=result.sample_rate
        )
        
        # Cleanup old cache files if needed
        self._cleanup_if_needed()
    
    def _cleanup_if_needed(self):
        """Remove old cache files if exceeding max size"""
        import os
        
        total_size = sum(
            f.stat().st_size 
            for f in self.cache_dir.glob("*.npz")
        ) / (1024 * 1024)  # MB
        
        if total_size > self.max_size_mb:
            # Remove oldest files
            files = sorted(
                self.cache_dir.glob("*.npz"),
                key=lambda f: f.stat().st_mtime
            )
            
            while total_size > self.max_size_mb * 0.8 and files:
                file = files.pop(0)
                total_size -= file.stat().st_size / (1024 * 1024)
                file.unlink()


class VoicePool:
    """Pool of TTS adapters for load balancing"""
    
    def __init__(self, max_adapters: int = 2):
        self.max_adapters = max_adapters
        self.adapters: List[Qwen3TTSAdapter] = []
        self.current_index = 0
        self._lock = False
    
    def get_adapter(self) -> Qwen3TTSAdapter:
        """Get next available adapter"""
        if not self.adapters:
            adapter = Qwen3TTSAdapter()
            self.adapters.append(adapter)
            return adapter
        
        # Round-robin
        adapter = self.adapters[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.adapters)
        return adapter
    
    def scale_up(self):
        """Add another adapter to pool"""
        if len(self.adapters) < self.max_adapters:
            adapter = Qwen3TTSAdapter()
            self.adapters.append(adapter)
    
    def scale_down(self):
        """Remove an adapter from pool"""
        if len(self.adapters) > 1:
            adapter = self.adapters.pop()
            adapter.unload()


class TTSEngine:
    """High-level TTS engine with caching and pooling"""
    
    def __init__(
        self,
        cache_dir: str = "./data/cache/tts",
        cache_enabled: bool = True,
        pool_size: int = 1,
        default_sample_rate: int = 24000
    ):
        self.cache_enabled = cache_enabled
        self.cache = CacheManager(cache_dir) if cache_enabled else None
        self.pool = VoicePool(max_adapters=pool_size)
        self.default_sample_rate = default_sample_rate
        
        self._metrics = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_processing_time": 0,
            "errors": 0
        }
        
        self._preprocessors: List[Callable] = []
        self._postprocessors: List[Callable] = []
    
    def add_preprocessor(self, func: Callable):
        """Add text preprocessor"""
        self._preprocessors.append(func)
    
    def add_postprocessor(self, func: Callable):
        """Add audio postprocessor"""
        self._postprocessors.append(func)
    
    def synthesize(self, request: SynthesisRequest) -> TTSResult:
        """Synthesize speech with caching and preprocessing"""
        self._metrics["total_requests"] += 1
        
        # Preprocess text
        text = request.text
        for preprocessor in self._preprocessors:
            text = preprocessor(text, request.language)
        
        # Check cache
        if self.cache_enabled and request.use_cache and not request.stream:
            cached = self.cache.get(text, request.language, request.voice_profile)
            if cached:
                self._metrics["cache_hits"] += 1
                return cached
        
        self._metrics["cache_misses"] += 1
        
        # Get adapter and synthesize
        adapter = self.pool.get_adapter()
        
        # Extract voice settings from profile
        speaker_id = 0
        if request.voice_profile:
            speaker_id = request.voice_profile.get("speaker_id", 0)
        
        try:
            result = adapter.synthesize(
                text=text,
                language=request.language,
                speaker_id=speaker_id,
                speed=request.speed,
                pitch=request.pitch,
                output_sample_rate=self.default_sample_rate
            )
            
            # Postprocess audio
            for postprocessor in self._postprocessors:
                result.audio = postprocessor(result.audio, result.sample_rate)
            
            # Cache result
            if self.cache_enabled and request.use_cache:
                self.cache.put(result, request.voice_profile)
            
            self._metrics["total_processing_time"] += result.processing_time
            
            return result
            
        except Exception as e:
            self._metrics["errors"] += 1
            raise TTSError(f"Synthesis failed: {str(e)}") from e
    
    def synthesize_batch(
        self,
        requests: List[SynthesisRequest],
        max_workers: int = 4
    ) -> List[TTSResult]:
        """Batch synthesis"""
        from concurrent.futures import ThreadPoolExecutor
        
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.synthesize, req) for req in requests]
            for future in futures:
                try:
                    results.append(future.result())
                except Exception as e:
                    self._metrics["errors"] += 1
                    # Return error result
                    results.append(TTSResult(
                        audio=np.zeros(24000),  # 1 second silence
                        sample_rate=24000,
                        language="en",
                        processing_time=0,
                        text="",
                        metadata={"error": str(e)}
                    ))
        
        return results
    
    def synthesize_stream(self, request: SynthesisRequest):
        """Streaming synthesis"""
        adapter = self.pool.get_adapter()
        
        speaker_id = 0
        if request.voice_profile:
            speaker_id = request.voice_profile.get("speaker_id", 0)
        
        # Preprocess
        text = request.text
        for preprocessor in self._preprocessors:
            text = preprocessor(text, request.language)
        
        # Stream chunks
        for chunk_result in adapter.synthesize_streaming(
            text=text,
            language=request.language,
            speaker_id=speaker_id,
            speed=request.speed,
            pitch=request.pitch
        ):
            # Postprocess
            for postprocessor in self._postprocessors:
                chunk_result.audio = postprocessor(
                    chunk_result.audio, 
                    chunk_result.sample_rate
                )
            
            yield chunk_result
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get engine metrics"""
        metrics = self._metrics.copy()
        
        if metrics["total_requests"] > 0:
            metrics["cache_hit_rate"] = (
                metrics["cache_hits"] / metrics["total_requests"]
            )
            metrics["avg_processing_time"] = (
                metrics["total_processing_time"] / metrics["total_requests"]
            )
        else:
            metrics["cache_hit_rate"] = 0
            metrics["avg_processing_time"] = 0
        
        return metrics
    
    def clear_cache(self):
        """Clear TTS cache"""
        if self.cache:
            import shutil
            shutil.rmtree(self.cache.cache_dir, ignore_errors=True)
            self.cache.cache_dir.mkdir(parents=True, exist_ok=True)
            self.cache._memory_cache.clear()


class TTSError(Exception):
    """TTS-specific error"""
    pass


# Preprocessors
def normalize_text(text: str, language: str) -> str:
    """Normalize text for TTS"""
    # Remove excessive whitespace
    text = " ".join(text.split())
    
    # Language-specific normalizations
    if language in ["zu", "xh", "nr", "ss"]:
        # Handle click consonants properly
        pass
    
    return text


def expand_abbreviations(text: str, language: str) -> str:
    """Expand abbreviations"""
    # Common SA abbreviations
    expansions = {
        "en": {
            "Dr.": "Doctor",
            "Prof.": "Professor",
            "Mr.": "Mister",
            "Mrs.": "Missus",
            "St.": "Saint",
        },
        "af": {
            "Dr.": "Dokter",
            "Mnr.": "Meneer",
            "Me.": "Mevrou",
        },
    }
    
    for lang_expansions in expansions.get(language, {}).items():
        text = text.replace(abbr, expansion)
    
    return text


# Postprocessors
def normalize_volume(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Normalize audio volume"""
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.95
    return audio


def remove_silence_edges(audio: np.ndarray, sample_rate: int,
                        threshold: float = 0.01) -> np.ndarray:
    """Remove silence from audio edges"""
    # Find start
    start = 0
    for i in range(len(audio)):
        if abs(audio[i]) > threshold:
            start = max(0, i - int(0.05 * sample_rate))  # 50ms padding
            break
    
    # Find end
    end = len(audio)
    for i in range(len(audio) - 1, -1, -1):
        if abs(audio[i]) > threshold:
            end = min(len(audio), i + int(0.05 * sample_rate))
            break
    
    return audio[start:end]
