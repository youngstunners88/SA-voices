# Voice Processing Skill

Advanced voice processing capabilities for SA Voices.

## Overview

This skill provides specialized voice processing for South African languages, including audio enhancement, noise reduction, and format conversion.

## Usage

```python
from skills.voice_processing import VoiceProcessor, ProcessingOptions

# Initialize
processor = VoiceProcessor()

# Process audio
options = ProcessingOptions(
    normalize=True,
    noise_reduction=True,
    target_sample_rate=24000
)

result = processor.process(audio_array, options)
```

## Features

- **Noise Reduction**: Removes background noise
- **Volume Normalization**: Consistent audio levels
- **Sample Rate Conversion**: High-quality resampling
- **Format Conversion**: WAV, MP3, OGG support
- **Silence Removal**: Automatic trimming
- **Voice Activity Detection**: Detect speech segments

## Configuration

```yaml
voice_processing:
  sample_rate: 24000
  noise_reduction_strength: 0.5
  normalize_target: -3.0  # dB
  silence_threshold: 0.01
```
