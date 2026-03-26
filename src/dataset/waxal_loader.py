"""WaxalNLP dataset loader for South African languages"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union
import numpy as np


@dataclass
class WaxalSample:
    """A single sample from WaxalNLP"""
    id: str
    language: str
    text: str
    audio: Optional[np.ndarray] = None
    sample_rate: int = 16000
    speaker_id: Optional[str] = None
    duration: float = 0.0
    transcription_quality: str = "automatic"
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class WaxalDataset:
    """In-memory Waxal dataset"""
    
    def __init__(self):
        self.samples: List[WaxalSample] = []
        self._by_language: Dict[str, List[WaxalSample]] = {}
        self._by_speaker: Dict[str, List[WaxalSample]] = {}
    
    def add(self, sample: WaxalSample):
        """Add a sample"""
        self.samples.append(sample)
        
        # Index by language
        if sample.language not in self._by_language:
            self._by_language[sample.language] = []
        self._by_language[sample.language].append(sample)
        
        # Index by speaker
        if sample.speaker_id:
            if sample.speaker_id not in self._by_speaker:
                self._by_speaker[sample.speaker_id] = []
            self._by_speaker[sample.speaker_id].append(sample)
    
    def get_by_language(self, language: str) -> List[WaxalSample]:
        """Get all samples for a language"""
        return self._by_language.get(language, [])
    
    def get_by_speaker(self, speaker_id: str) -> List[WaxalSample]:
        """Get all samples for a speaker"""
        return self._by_speaker.get(speaker_id, [])
    
    def get_languages(self) -> List[str]:
        """Get all languages in dataset"""
        return list(self._by_language.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get dataset statistics"""
        total_duration = sum(s.duration for s in self.samples)
        
        return {
            "total_samples": len(self.samples),
            "total_hours": total_duration / 3600,
            "languages": {
                lang: {
                    "samples": len(samples),
                    "hours": sum(s.duration for s in samples) / 3600,
                    "speakers": len(set(s.speaker_id for s in samples if s.speaker_id))
                }
                for lang, samples in self._by_language.items()
            }
        }
    
    def __len__(self) -> int:
        return len(self.samples)
    
    def __iter__(self) -> Iterator[WaxalSample]:
        return iter(self.samples)


class WaxalLoader:
    """Loader for WaxalNLP dataset from HuggingFace"""
    
    # South African language codes in Waxal
    SA_LANGUAGES = {
        "af": "Afrikaans",
        "en": "English",
        "zu": "Zulu",
        "xh": "Xhosa",
        "nso": "Northern Sotho",
        "st": "Southern Sotho",
        "tn": "Tswana",
        "ts": "Tsonga",
        "ss": "Swati",
        "ve": "Venda",
        "nr": "Ndebele",
    }
    
    def __init__(
        self,
        dataset_name: str = "google/WaxalNLP",
        cache_dir: str = "./data/waxal",
        split: str = "train",
        streaming: bool = False
    ):
        self.dataset_name = dataset_name
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.split = split
        self.streaming = streaming
        
        self._dataset = None
        self._loaded = False
    
    def load(self, languages: List[str] = None) -> WaxalDataset:
        """Load dataset for specified languages"""
        try:
            from datasets import load_dataset, Audio
        except ImportError:
            raise ImportError("Install datasets with: pip install datasets[audio]")
        
        print(f"Loading WaxalNLP dataset...")
        print(f"Languages: {languages or 'all SA languages'}")
        
        # Load from HuggingFace
        self._dataset = load_dataset(
            self.dataset_name,
            split=self.split,
            cache_dir=str(self.cache_dir),
            streaming=self.streaming
        )
        
        # Cast to audio type
        self._dataset = self._dataset.cast_column("audio", Audio())
        
        # Filter for SA languages if specified
        if languages:
            lang_set = set(languages)
            self._dataset = self._dataset.filter(
                lambda x: x.get("language", "") in lang_set
            )
        
        # Convert to WaxalDataset
        waxal_dataset = WaxalDataset()
        
        print("Converting samples...")
        for i, item in enumerate(self._dataset):
            try:
                sample = self._convert_sample(item)
                if sample:
                    waxal_dataset.add(sample)
                
                if (i + 1) % 1000 == 0:
                    print(f"Processed {i + 1} samples...")
                    
            except Exception as e:
                print(f"Error processing sample {i}: {e}")
                continue
        
        self._loaded = True
        
        print(f"\nDataset loaded: {len(waxal_dataset)} samples")
        stats = waxal_dataset.get_stats()
        print(f"Total duration: {stats['total_hours']:.2f} hours")
        
        return waxal_dataset
    
    def _convert_sample(self, item: Dict) -> Optional[WaxalSample]:
        """Convert HuggingFace sample to WaxalSample"""
        language = item.get("language", "")
        
        # Skip if not an SA language
        if language not in self.SA_LANGUAGES:
            return None
        
        # Get audio data
        audio_data = item.get("audio", {})
        
        if isinstance(audio_data, dict):
            array = audio_data.get("array")
            sample_rate = audio_data.get("sampling_rate", 16000)
        else:
            array = None
            sample_rate = 16000
        
        # Calculate duration
        duration = 0.0
        if array is not None:
            duration = len(array) / sample_rate
        
        return WaxalSample(
            id=str(item.get("id", "")),
            language=language,
            text=item.get("text", ""),
            audio=array,
            sample_rate=sample_rate,
            speaker_id=item.get("speaker_id"),
            duration=duration,
            transcription_quality=item.get("transcription_quality", "automatic"),
            metadata={
                k: v for k, v in item.items() 
                if k not in ["audio", "text", "language", "id", "speaker_id"]
            }
        )
    
    def load_local(self, path: Union[str, Path]) -> WaxalDataset:
        """Load from local cache"""
        path = Path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"Dataset not found at {path}")
        
        dataset = WaxalDataset()
        
        # Load metadata
        metadata_file = path / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)
        
        # Load samples
        samples_dir = path / "samples"
        for lang_dir in samples_dir.iterdir():
            if lang_dir.is_dir():
                for sample_file in lang_dir.glob("*.npz"):
                    try:
                        data = np.load(sample_file)
                        sample = WaxalSample(
                            id=sample_file.stem,
                            language=lang_dir.name,
                            text=str(data.get("text", "")),
                            audio=data.get("audio"),
                            sample_rate=int(data.get("sample_rate", 16000)),
                            duration=float(data.get("duration", 0))
                        )
                        dataset.add(sample)
                    except Exception as e:
                        print(f"Error loading {sample_file}: {e}")
        
        return dataset
    
    def save_local(self, dataset: WaxalDataset, path: Union[str, Path]):
        """Save dataset to local cache"""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        # Save metadata
        metadata = {
            "dataset_name": self.dataset_name,
            "stats": dataset.get_stats()
        }
        
        with open(path / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        # Save samples
        samples_dir = path / "samples"
        samples_dir.mkdir(exist_ok=True)
        
        for sample in dataset:
            lang_dir = samples_dir / sample.language
            lang_dir.mkdir(exist_ok=True)
            
            np.savez(
                lang_dir / f"{sample.id}.npz",
                audio=sample.audio,
                text=sample.text,
                sample_rate=sample.sample_rate,
                duration=sample.duration
            )
    
    def get_sample_by_text(self, text: str, language: str = None) -> Optional[WaxalSample]:
        """Find sample by text content"""
        if not self._loaded or not self._dataset:
            return None
        
        for item in self._dataset:
            if item.get("text", "") == text:
                if language is None or item.get("language") == language:
                    return self._convert_sample(item)
        
        return None
    
    def create_voice_samples(self, language: str, num_samples: int = 5) -> List[WaxalSample]:
        """Get diverse voice samples for a language"""
        if not self._loaded or not self._dataset:
            raise RuntimeError("Dataset not loaded. Call load() first.")
        
        samples = []
        speakers_seen = set()
        
        for item in self._dataset:
            if item.get("language") == language:
                speaker = item.get("speaker_id")
                if speaker and speaker not in speakers_seen:
                    sample = self._convert_sample(item)
                    if sample:
                        samples.append(sample)
                        speakers_seen.add(speaker)
                        
                        if len(samples) >= num_samples:
                            break
        
        return samples
