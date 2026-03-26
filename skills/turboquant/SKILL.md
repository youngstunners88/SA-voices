# TurboQuant Skill

Vector quantization and compression for AI efficiency.

## Overview

This skill implements concepts from Google's TurboQuant research:
- PolarQuant for high-quality compression
- QJL (Quantized Johnson-Lindenstrauss) for zero-overhead compression
- KV cache compression for LLMs
- Vector search acceleration

## Features

- **PolarQuant**: Angle-based vector quantization
- **QJL**: 1-bit compression with mathematical error correction
- **KV Cache Compression**: Reduce memory by 6x without accuracy loss
- **Vector Search**: Fast similarity search
- **Auto-Optimization**: Self-tuning compression levels

## Usage

```python
from skills.turboquant import TurboQuantCompressor, CompressionConfig

# Initialize compressor
config = CompressionConfig(
    method="turboquant",
    bits=3,  # 3-bit compression
    preserve_accuracy=True
)
compressor = TurboQuantCompressor(config)

# Compress vectors
compressed = compressor.compress(vectors)
decompressed = compressor.decompress(compressed)

# For KV cache
kv_cache = compressor.compress_kv_cache(keys, values)
```

## Autonomous Usage

The skill automatically activates when:
- Memory usage exceeds threshold
- Processing large vector batches
- KV cache size becomes critical
- Vector search performance degrades

## Configuration

```yaml
turboquant:
  auto_enable: true
  memory_threshold: 80%
  default_bits: 3
  kv_cache:
    enabled: true
    compression_ratio: 6.0
  vector_search:
    enabled: true
    recall_threshold: 0.95
```

## Learning & Adaptation

The skill continuously learns:
- Optimal compression levels for different data types
- Performance impact vs memory savings trade-offs
- Workload patterns for predictive activation
- Accuracy preservation strategies

See the self-improvement module for details.
