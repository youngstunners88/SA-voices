# Language Detection Skill

Advanced language detection for South African languages.

## Overview

This skill provides accurate language detection for all 11 official South African languages, using a combination of statistical and neural methods.

## Usage

```python
from skills.language_detection import LanguageDetector, DetectionResult

# Initialize
detector = LanguageDetector()

# Detect language
result = detector.detect("Sawubona, unjani?")
print(result.language)  # "zu"
print(result.confidence)  # 0.95

# Detect with all scores
results = detector.detect_all("Dumela, o kae?")
for r in results:
    print(f"{r.language}: {r.confidence:.2f}")
```

## Features

- **Fast Detection**: Keyword-based for common phrases
- **Statistical**: N-gram analysis
- **Neural**: Transformer-based classifier
- **Confidence Scoring**: Reliable predictions
- **Code Switching**: Detect mixed languages

## Supported Languages

- Afrikaans (af)
- English (en)
- isiNdebele (nr)
- Sepedi (nso)
- Sesotho (st)
- siSwati (ss)
- Setswana (tn)
- Xitsonga (ts)
- Tshivenda (ve)
- isiXhosa (xh)
- isiZulu (zu)

## Configuration

```yaml
language_detection:
  method: "hybrid"  # keyword, statistical, neural, hybrid
  confidence_threshold: 0.7
  fallback_language: "en"
  enable_code_switching: true
```
