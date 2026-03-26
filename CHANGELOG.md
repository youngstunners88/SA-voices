# Changelog

All notable changes to SA Voices will be documented in this file.

## [0.1.0] - 2026-03-26

### Added
- Initial release of SA Voices
- Support for all 11 official South African languages:
  - isiZulu, isiXhosa, isiNdebele
  - Sepedi, Sesotho, Setswana
  - Xitsonga, siSwati, Tshivenda
  - Afrikaans, English
- Qwen3-TTS integration for high-quality text-to-speech
- WaxalNLP dataset integration
- Intelligent routing system with multiple strategies:
  - Priority-based routing
  - Load balancing
  - Language-based routing
  - Hybrid strategies
- Comprehensive state management:
  - Redis, SQLite, and file-based storage
  - Session management
  - Voice profiles
  - Conversation history
- FastAPI REST API with WebSocket support
- Gradio web UI with South African flag theme
- Rich CLI interface with multiple commands
- Specialized skills:
  - Voice processing with audio enhancement
  - Language detection with hybrid methods
  - State management with multiple backends
- Docker and docker-compose setup
- GitHub Actions CI/CD pipeline
- Comprehensive documentation and examples

### Features
- Language auto-detection
- Voice customization (speed, pitch, presets)
- Audio format conversion
- Noise reduction and normalization
- Streaming synthesis support
- Batch processing
- Session persistence
- Health checks and monitoring

### Infrastructure
- Python 3.10+ support
- PyTorch-based TTS engine
- Async/await throughout
- Modular architecture
- Extensive test coverage

## Future Roadmap

### [0.2.0] - Planned
- Fine-tuned models for each SA language
- Voice cloning improvements
- Real-time streaming enhancements
- Mobile app integration
- Voice activity detection improvements

### [0.3.0] - Planned
- Additional African languages
- Dialect support
- Custom voice training interface
- Cloud deployment guides
- Performance optimizations

### [1.0.0] - Planned
- Production-ready stability
- Enterprise features
- Advanced analytics
- Multi-tenant support
- SLA guarantees
