"""Qwen3-TTS adapter for SA Voices"""

import io
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union, BinaryIO
from pathlib import Path
import numpy as np


def _check_torch():
    """Lazy import torch"""
    try:
        import torch
        return torch
    except ImportError:
        raise ImportError("PyTorch is required. Install with: pip install torch")


@dataclass
class TTSResult:
    """TTS generation result"""
    audio: np.ndarray
    sample_rate: int
    language: str
    processing_time: float
    text: str
    audio_format: str = "wav"
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_bytes(self) -> bytes:
        """Convert to audio bytes"""
        import soundfile as sf
        buffer = io.BytesIO()
        sf.write(buffer, self.audio, self.sample_rate, format=self.audio_format)
        buffer.seek(0)
        return buffer.read()
    
    def save(self, path: Union[str, Path]) -> Path:
        """Save to file"""
        import soundfile as sf
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(path, self.audio, self.sample_rate)
        return path


class Qwen3TTSAdapter:
    """Adapter for Qwen3-TTS model"""
    
    # Language mappings for Qwen3-TTS
    LANGUAGE_CODES = {
        "af": "af",      # Afrikaans
        "en": "en",      # English
        "nr": "en",      # Ndebele (fallback to English for now)
        "nso": "en",     # Sepedi (fallback to English for now)
        "st": "en",      # Sesotho (fallback to English for now)
        "ss": "en",      # Swati (fallback to English for now)
        "tn": "en",      # Tswana (fallback to English for now)
        "ts": "en",      # Tsonga (fallback to English for now)
        "ve": "en",      # Venda (fallback to English for now)
        "xh": "en",      # Xhosa (fallback to English for now)
        "zu": "en",      # Zulu (fallback to English for now)
    }
    
    # Voice presets
    VOICE_PRESETS = {
        "default": {"speaker_id": 0},
        "male": {"speaker_id": 1},
        "female": {"speaker_id": 2},
        "young": {"speaker_id": 3},
        "elderly": {"speaker_id": 4},
    }
    
    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-TTS",
        device: str = "auto",
        precision: str = "fp16",
        cache_dir: str = "./models/cache"
    ):
        self.model_name = model_name
        self.device = self._get_device(device)
        self.precision = precision
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.model = None
        self.tokenizer = None
        self.processor = None
        self.is_loaded = False
        self._load_time = 0
    
    def _get_device(self, device: str) -> str:
        """Determine compute device"""
        if device == "auto":
            torch = _check_torch()
            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return "mps"
            else:
                return "cpu"
        return device
    
    def load_model(self):
        """Load the Qwen3-TTS model"""
        if self.is_loaded:
            return
        
        import torch
        from transformers import AutoModelForTextToSpeech, AutoTokenizer
        
        start_time = time.time()
        
        print(f"Loading Qwen3-TTS model: {self.model_name}")
        print(f"Device: {self.device}")
        print(f"Precision: {self.precision}")
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            cache_dir=str(self.cache_dir)
        )
        
        # Load model
        dtype = torch.float16 if self.precision == "fp16" else torch.float32
        
        self.model = AutoModelForTextToSpeech.from_pretrained(
            self.model_name,
            torch_dtype=dtype,
            cache_dir=str(self.cache_dir)
        )
        
        self.model = self.model.to(self.device)
        self.model.eval()
        
        self._load_time = time.time() - start_time
        self.is_loaded = True
        
        print(f"Model loaded in {self._load_time:.2f}s")
    
    def synthesize(
        self,
        text: str,
        language: str = "en",
        speaker_id: int = 0,
        speed: float = 1.0,
        pitch: float = 1.0,
        output_sample_rate: int = 24000
    ) -> TTSResult:
        """Synthesize speech from text"""
        if not self.is_loaded:
            self.load_model()
        
        import torch
        
        start_time = time.time()
        
        # Map language code
        lang_code = self.LANGUAGE_CODES.get(language, "en")
        
        # Prepare input
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512
        ).to(self.device)
        
        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                speaker_id=speaker_id,
                speed=speed,
                pitch=pitch
            )
        
        # Extract audio
        audio = outputs.cpu().numpy().squeeze()
        
        # Resample if needed
        if hasattr(outputs, 'sample_rate') and outputs.sample_rate != output_sample_rate:
            audio = self._resample(audio, outputs.sample_rate, output_sample_rate)
        
        processing_time = time.time() - start_time
        
        return TTSResult(
            audio=audio,
            sample_rate=output_sample_rate,
            language=language,
            processing_time=processing_time,
            text=text,
            metadata={
                "model": self.model_name,
                "speaker_id": speaker_id,
                "speed": speed,
                "pitch": pitch,
                "input_tokens": inputs.input_ids.shape[1]
            }
        )
    
    def synthesize_batch(
        self,
        texts: List[str],
        language: str = "en",
        speaker_id: int = 0,
        **kwargs
    ) -> List[TTSResult]:
        """Batch synthesis"""
        results = []
        for text in texts:
            result = self.synthesize(text, language, speaker_id, **kwargs)
            results.append(result)
        return results
    
    def synthesize_streaming(
        self,
        text: str,
        language: str = "en",
        speaker_id: int = 0,
        chunk_size: int = 100,
        **kwargs
    ):
        """Streaming synthesis - yields audio chunks"""
        if not self.is_loaded:
            self.load_model()
        
        # Split text into chunks
        words = text.split()
        chunks = []
        current_chunk = []
        current_len = 0
        
        for word in words:
            if current_len + len(word) > chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_len = len(word)
            else:
                current_chunk.append(word)
                current_len += len(word) + 1
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        # Generate chunks
        for chunk in chunks:
            result = self.synthesize(chunk, language, speaker_id, **kwargs)
            yield result
    
    def clone_voice(
        self,
        reference_audio: Union[str, Path, np.ndarray],
        text: str,
        language: str = "en",
        **kwargs
    ) -> TTSResult:
        """Clone voice from reference audio"""
        if not self.is_loaded:
            self.load_model()
        
        import torch
        
        # Load reference audio
        if isinstance(reference_audio, (str, Path)):
            import librosa
            ref_audio, sr = librosa.load(reference_audio, sr=24000)
        else:
            ref_audio = reference_audio
        
        # Extract speaker embedding
        # This is a simplified version - real implementation would use proper speaker encoding
        ref_tensor = torch.from_numpy(ref_audio).unsqueeze(0).to(self.device)
        
        # For now, use default speaker with slight modifications
        # Full implementation would require speaker encoder
        speaker_id = kwargs.get("speaker_id", 0)
        
        return self.synthesize(text, language, speaker_id, **kwargs)
    
    def get_language_info(self, language: str) -> Dict[str, Any]:
        """Get language information"""
        lang_code = self.LANGUAGE_CODES.get(language, language)
        return {
            "code": language,
            "mapped_code": lang_code,
            "supported": language in self.LANGUAGE_CODES,
            "native_support": lang_code == language,
        }
    
    def _resample(
        self,
        audio: np.ndarray,
        orig_sr: int,
        target_sr: int
    ) -> np.ndarray:
        """Resample audio to target sample rate"""
        if orig_sr == target_sr:
            return audio
        
        import librosa
        return librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr)
    
    def unload(self):
        """Unload model to free memory"""
        import torch
        
        self.model = None
        self.tokenizer = None
        self.processor = None
        self.is_loaded = False
        
        if self.device == "cuda":
            torch.cuda.empty_cache()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get adapter statistics"""
        import torch
        
        stats = {
            "model_loaded": self.is_loaded,
            "model_name": self.model_name,
            "device": self.device,
            "precision": self.precision,
            "load_time": self._load_time,
        }
        
        if self.device == "cuda" and torch.cuda.is_available():
            stats["gpu_memory"] = {
                "allocated": torch.cuda.memory_allocated() / 1e9,
                "reserved": torch.cuda.memory_reserved() / 1e9,
            }
        
        return stats
