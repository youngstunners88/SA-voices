"""Voice processing utilities"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np


@dataclass
class ProcessingOptions:
    """Audio processing options"""
    normalize: bool = True
    noise_reduction: bool = False
    noise_reduction_strength: float = 0.5
    remove_silence: bool = False
    silence_threshold: float = 0.01
    silence_padding: float = 0.05  # seconds
    target_sample_rate: Optional[int] = None
    format: str = "wav"
    bit_depth: int = 16


@dataclass
class AudioSegment:
    """Audio segment with metadata"""
    audio: np.ndarray
    sample_rate: int
    start_time: float
    end_time: float
    is_speech: bool = True


class VoiceProcessor:
    """Voice processing for SA languages"""
    
    def __init__(self):
        self._noise_profile = None
    
    def process(
        self,
        audio: np.ndarray,
        sample_rate: int,
        options: ProcessingOptions
    ) -> np.ndarray:
        """Process audio with given options"""
        result = audio.copy()
        
        # Resample if needed
        if options.target_sample_rate and options.target_sample_rate != sample_rate:
            result = self._resample(result, sample_rate, options.target_sample_rate)
            sample_rate = options.target_sample_rate
        
        # Noise reduction
        if options.noise_reduction:
            result = self._reduce_noise(result, sample_rate, options.noise_reduction_strength)
        
        # Normalize
        if options.normalize:
            result = self._normalize(result)
        
        # Remove silence
        if options.remove_silence:
            result = self._remove_silence(
                result, 
                sample_rate,
                options.silence_threshold,
                options.silence_padding
            )
        
        return result
    
    def detect_voice_activity(
        self,
        audio: np.ndarray,
        sample_rate: int,
        frame_length: int = 1024,
        hop_length: int = 512,
        threshold: float = 0.01
    ) -> List[AudioSegment]:
        """Detect speech segments in audio"""
        # Calculate RMS energy per frame
        frames = []
        for i in range(0, len(audio) - frame_length, hop_length):
            frame = audio[i:i + frame_length]
            rms = np.sqrt(np.mean(frame ** 2))
            frames.append({
                "start": i / sample_rate,
                "end": (i + frame_length) / sample_rate,
                "rms": rms,
                "is_speech": rms > threshold
            })
        
        # Merge consecutive frames
        segments = []
        current_segment = None
        
        for frame in frames:
            if current_segment is None:
                current_segment = {
                    "start": frame["start"],
                    "end": frame["end"],
                    "is_speech": frame["is_speech"]
                }
            elif current_segment["is_speech"] == frame["is_speech"]:
                current_segment["end"] = frame["end"]
            else:
                # Add padding for speech segments
                if current_segment["is_speech"]:
                    current_segment["start"] = max(0, current_segment["start"] - 0.05)
                    current_segment["end"] = min(len(audio) / sample_rate, current_segment["end"] + 0.05)
                
                start_sample = int(current_segment["start"] * sample_rate)
                end_sample = int(current_segment["end"] * sample_rate)
                
                segments.append(AudioSegment(
                    audio=audio[start_sample:end_sample],
                    sample_rate=sample_rate,
                    start_time=current_segment["start"],
                    end_time=current_segment["end"],
                    is_speech=current_segment["is_speech"]
                ))
                
                current_segment = {
                    "start": frame["start"],
                    "end": frame["end"],
                    "is_speech": frame["is_speech"]
                }
        
        # Add final segment
        if current_segment:
            if current_segment["is_speech"]:
                current_segment["start"] = max(0, current_segment["start"] - 0.05)
                current_segment["end"] = min(len(audio) / sample_rate, current_segment["end"] + 0.05)
            
            start_sample = int(current_segment["start"] * sample_rate)
            end_sample = int(current_segment["end"] * sample_rate)
            
            segments.append(AudioSegment(
                audio=audio[start_sample:end_sample],
                sample_rate=sample_rate,
                start_time=current_segment["start"],
                end_time=current_segment["end"],
                is_speech=current_segment["is_speech"]
            ))
        
        return segments
    
    def extract_features(
        self,
        audio: np.ndarray,
        sample_rate: int
    ) -> dict:
        """Extract audio features"""
        try:
            import librosa
        except ImportError:
            raise ImportError("Install librosa for feature extraction: pip install librosa")
        
        features = {
            "duration": len(audio) / sample_rate,
            "rms": np.sqrt(np.mean(audio ** 2)),
            "peak": np.max(np.abs(audio)),
            "zero_crossing_rate": np.mean(librosa.feature.zero_crossing_rate(audio)),
        }
        
        # MFCCs
        mfccs = librosa.feature.mfcc(y=audio, sr=sample_rate, n_mfcc=13)
        features["mfcc_mean"] = np.mean(mfccs, axis=1).tolist()
        features["mfcc_std"] = np.std(mfccs, axis=1).tolist()
        
        # Spectral features
        features["spectral_centroid"] = np.mean(
            librosa.feature.spectral_centroid(y=audio, sr=sample_rate)
        )
        features["spectral_rolloff"] = np.mean(
            librosa.feature.spectral_rolloff(y=audio, sr=sample_rate)
        )
        
        return features
    
    def _resample(
        self,
        audio: np.ndarray,
        orig_sr: int,
        target_sr: int
    ) -> np.ndarray:
        """Resample audio"""
        if orig_sr == target_sr:
            return audio
        
        try:
            import librosa
            return librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr)
        except ImportError:
            # Simple linear interpolation fallback
            from scipy import signal
            return signal.resample(audio, int(len(audio) * target_sr / orig_sr))
    
    def _reduce_noise(
        self,
        audio: np.ndarray,
        sample_rate: int,
        strength: float
    ) -> np.ndarray:
        """Reduce noise using spectral subtraction"""
        try:
            import noisereduce as nr
            return nr.reduce_noise(
                y=audio,
                sr=sample_rate,
                prop_decrease=strength
            )
        except ImportError:
            # Simple noise reduction fallback
            # Estimate noise from first 100ms
            noise_samples = int(0.1 * sample_rate)
            if len(audio) > noise_samples:
                noise_profile = np.mean(np.abs(audio[:noise_samples]))
                mask = np.abs(audio) > noise_profile * (1 + strength)
                return audio * mask
            return audio
    
    def _normalize(self, audio: np.ndarray, target_db: float = -3.0) -> np.ndarray:
        """Normalize audio to target dB"""
        peak = np.max(np.abs(audio))
        if peak > 0:
            # Convert dB to linear
            target_linear = 10 ** (target_db / 20)
            audio = audio / peak * target_linear
        return audio
    
    def _remove_silence(
        self,
        audio: np.ndarray,
        sample_rate: int,
        threshold: float,
        padding: float
    ) -> np.ndarray:
        """Remove silence from audio edges"""
        # Find start
        start = 0
        padding_samples = int(padding * sample_rate)
        
        for i in range(len(audio)):
            if abs(audio[i]) > threshold:
                start = max(0, i - padding_samples)
                break
        
        # Find end
        end = len(audio)
        for i in range(len(audio) - 1, -1, -1):
            if abs(audio[i]) > threshold:
                end = min(len(audio), i + padding_samples)
                break
        
        return audio[start:end]
    
    def apply_effects(
        self,
        audio: np.ndarray,
        sample_rate: int,
        effects: dict
    ) -> np.ndarray:
        """Apply audio effects"""
        result = audio.copy()
        
        # Speed change
        if "speed" in effects:
            import librosa
            result = librosa.effects.time_stretch(result, rate=effects["speed"])
        
        # Pitch shift
        if "pitch" in effects:
            import librosa
            result = librosa.effects.pitch_shift(
                result,
                sr=sample_rate,
                n_steps=effects["pitch"]
            )
        
        # Reverb (simple)
        if "reverb" in effects and effects["reverb"] > 0:
            delay = int(0.05 * sample_rate)  # 50ms
            decay = effects["reverb"]
            reverb = np.zeros_like(result)
            if len(result) > delay:
                reverb[delay:] = result[:-delay] * decay
            result = result + reverb
            result = self._normalize(result)
        
        return result
