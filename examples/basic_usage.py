"""
SA Voices - Basic Usage Examples
================================

This file demonstrates basic usage of the SA Voices system.
"""

import asyncio
from pathlib import Path


async def example_1_basic_synthesis():
    """Basic text-to-speech synthesis"""
    print("=" * 60)
    print("Example 1: Basic TTS Synthesis")
    print("=" * 60)
    
    from src.tts.engine import TTSEngine, SynthesisRequest
    
    # Initialize TTS engine
    tts = TTSEngine()
    
    # Create request
    request = SynthesisRequest(
        text="Sawubona, igama lami nguJohn.",
        language="zu"
    )
    
    # Synthesize
    result = tts.synthesize(request)
    
    # Save to file
    output_path = Path("output_zulu.wav")
    result.save(output_path)
    
    print(f"✓ Synthesized: {request.text}")
    print(f"✓ Language: {result.language}")
    print(f"✓ Duration: {len(result.audio) / result.sample_rate:.2f}s")
    print(f"✓ Saved to: {output_path}")
    print()


async def example_2_language_detection():
    """Language detection"""
    print("=" * 60)
    print("Example 2: Language Detection")
    print("=" * 60)
    
    from skills.language_detection import LanguageDetector
    
    detector = LanguageDetector()
    
    texts = [
        "Sawubona, unjani?",  # Zulu
        "Molo, unjani?",      # Xhosa
        "Hallo, hoe gaan dit?",  # Afrikaans
        "Hello, how are you?",   # English
        "Dumela, o kae?",     # Sepedi
    ]
    
    for text in texts:
        result = detector.detect(text)
        print(f"Text: {text}")
        print(f"  → Detected: {result.language} ({result.confidence:.0%})")
        print(f"  → Method: {result.method.value}")
        print()


async def example_3_session_management():
    """Session management"""
    print("=" * 60)
    print("Example 3: Session Management")
    print("=" * 60)
    
    from src.state.manager import StateManager, VoiceProfile
    from src.state.storage import SQLiteStorage
    
    # Initialize with SQLite storage
    storage = SQLiteStorage()
    manager = StateManager(storage_backend=storage)
    
    # Create session with voice profile
    profile = VoiceProfile(
        name="custom",
        language="zu",
        gender="female",
        speaking_rate=1.2
    )
    
    session = await manager.create_session(
        user_id="user123",
        language="zu",
        voice_profile=profile
    )
    
    print(f"✓ Session created: {session.session_id}")
    print(f"✓ Language: {session.language}")
    print(f"✓ Voice: {session.voice_profile.name}")
    
    # Add messages
    await manager.add_message(
        session_id=session.session_id,
        role="user",
        content="Sawubona",
        language="zu"
    )
    
    await manager.add_message(
        session_id=session.session_id,
        role="assistant",
        content="Sawubona! Unjani namhlanje?",
        language="zu"
    )
    
    # Retrieve session
    retrieved = await manager.get_session(session.session_id)
    print(f"✓ Messages: {len(retrieved.messages)}")
    print()


async def example_4_routing():
    """Request routing"""
    print("=" * 60)
    print("Example 4: Request Routing")
    print("=" * 60)
    
    from src.routing.router import VoiceRouter, RouteRequest, RouteType, RoutePriority
    from src.routing.strategies import PriorityStrategy, LoadBalancingStrategy
    
    # Initialize router
    router = VoiceRouter()
    
    # Register handlers
    router.register_handler(
        "tts_primary",
        route_types=[RouteType.TTS_SYNTHESIS],
        max_capacity=5
    )
    
    router.register_handler(
        "tts_secondary",
        route_types=[RouteType.TTS_SYNTHESIS],
        max_capacity=3
    )
    
    # Add strategies
    router.add_strategy(PriorityStrategy())
    router.add_strategy(LoadBalancingStrategy("least_loaded"))
    
    # Create request
    request = RouteRequest(
        request_id="req_001",
        route_type=RouteType.TTS_SYNTHESIS,
        priority=RoutePriority.HIGH,
        payload={"text": "Hello", "language": "en"},
        language="en"
    )
    
    # Route request
    result = await router.route(request)
    
    print(f"✓ Request routed to: {result.handler}")
    print(f"✓ Queue position: {result.queue_position}")
    print(f"✓ Strategy used: {result.strategy_used}")
    print()


async def example_5_voice_processing():
    """Voice processing"""
    print("=" * 60)
    print("Example 5: Voice Processing")
    print("=" * 60)
    
    from skills.voice_processing import VoiceProcessor, ProcessingOptions
    import numpy as np
    
    # Create sample audio
    sample_rate = 24000
    duration = 2.0
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave
    
    # Process audio
    processor = VoiceProcessor()
    
    options = ProcessingOptions(
        normalize=True,
        remove_silence=False,
        target_sample_rate=16000
    )
    
    result = processor.process(audio, sample_rate, options)
    
    print(f"✓ Input: {len(audio)} samples @ {sample_rate}Hz")
    print(f"✓ Output: {len(result)} samples @ {options.target_sample_rate}Hz")
    print()


async def example_6_batch_synthesis():
    """Batch synthesis"""
    print("=" * 60)
    print("Example 6: Batch Synthesis")
    print("=" * 60)
    
    from src.tts.engine import TTSEngine, SynthesisRequest
    
    tts = TTSEngine()
    
    # Create multiple requests
    requests = [
        SynthesisRequest(text="Sawubona", language="zu"),
        SynthesisRequest(text="Molo", language="xh"),
        SynthesisRequest(text="Dumela", language="nso"),
        SynthesisRequest(text="Hallo", language="af"),
    ]
    
    # Batch process
    results = tts.synthesize_batch(requests)
    
    for req, res in zip(requests, results):
        print(f"✓ {req.language}: '{req.text}' → {len(res.audio)/res.sample_rate:.2f}s")
    
    print()


async def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("SA Voices - Usage Examples")
    print("=" * 60 + "\n")
    
    try:
        await example_2_language_detection()
    except Exception as e:
        print(f"Error in example 2: {e}\n")
    
    try:
        await example_3_session_management()
    except Exception as e:
        print(f"Error in example 3: {e}\n")
    
    try:
        await example_4_routing()
    except Exception as e:
        print(f"Error in example 4: {e}\n")
    
    try:
        await example_5_voice_processing()
    except Exception as e:
        print(f"Error in example 5: {e}\n")
    
    print("=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
