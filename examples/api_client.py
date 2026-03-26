"""
SA Voices API Client Example
============================

Example client for interacting with the SA Voices API.
"""

import asyncio
import base64
import io
from pathlib import Path

import httpx


class SAVoicesClient:
    """Client for SA Voices API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def get_languages(self) -> list:
        """Get list of supported languages"""
        response = await self.client.get(f"{self.base_url}/api/v1/languages")
        response.raise_for_status()
        return response.json()
    
    async def synthesize(
        self,
        text: str,
        language: str = "en",
        speed: float = 1.0,
        pitch: float = 1.0,
        output_file: Path = None
    ) -> dict:
        """Synthesize speech"""
        data = {
            "text": text,
            "language": language,
            "speed": speed,
            "pitch": pitch,
            "format": "wav"
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/synthesize",
            json=data
        )
        response.raise_for_status()
        result = response.json()
        
        # Save audio if output file specified
        if output_file and result.get("audio_base64"):
            audio_bytes = base64.b64decode(result["audio_base64"])
            output_file.write_bytes(audio_bytes)
            print(f"✓ Saved to {output_file}")
        
        return result
    
    async def detect_language(self, text: str) -> dict:
        """Detect language of text"""
        response = await self.client.post(
            f"{self.base_url}/api/v1/detect-language",
            params={"text": text}
        )
        response.raise_for_status()
        return response.json()
    
    async def create_session(self, user_id: str = None, language: str = "en") -> dict:
        """Create a new session"""
        data = {
            "user_id": user_id,
            "language": language
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/sessions",
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    async def get_health(self) -> dict:
        """Check API health"""
        response = await self.client.get(f"{self.base_url}/api/v1/health")
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        """Close client"""
        await self.client.aclose()


async def main():
    """Example usage"""
    client = SAVoicesClient()
    
    try:
        # Check health
        print("Checking API health...")
        health = await client.get_health()
        print(f"✓ API Status: {health['status']}\n")
        
        # Get languages
        print("Supported languages:")
        languages = await client.get_languages()
        for lang in languages[:5]:
            print(f"  - {lang['name']} ({lang['code']})")
        print(f"  ... and {len(languages) - 5} more\n")
        
        # Detect language
        text = "Sawubona, unjani?"
        print(f"Detecting language for: '{text}'")
        detection = await client.detect_language(text)
        print(f"✓ Detected: {detection['detected_language']}")
        print(f"✓ Confidence: {detection['confidence']:.0%}\n")
        
        # Synthesize
        print("Synthesizing speech...")
        result = await client.synthesize(
            text=text,
            language="zu",
            output_file=Path("api_test_zulu.wav")
        )
        print(f"✓ Processing time: {result['processing_time']:.2f}s")
        print(f"✓ Sample rate: {result['sample_rate']}Hz\n")
        
        # Create session
        print("Creating session...")
        session = await client.create_session(
            user_id="test_user",
            language="zu"
        )
        print(f"✓ Session ID: {session['session_id']}")
        print(f"✓ Expires: {session['expires_at']}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    print("SA Voices API Client Example\n")
    asyncio.run(main())
