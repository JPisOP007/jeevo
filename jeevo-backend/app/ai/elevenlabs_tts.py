"""Text-to-Speech using ElevenLabs"""

from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)


class ElevenLabsTTS:
    """Text-to-Speech service using ElevenLabs"""
    
    def __init__(self, api_key: str = None):
        """Initialize ElevenLabs TTS"""
        if api_key is None:
            api_key = os.getenv("ELEVENLABS_API_KEY")
        
        if not api_key:
            logger.warning("ElevenLabs API key not found. TTS will not work.")
            self.client = None
            return
            
        self.client = ElevenLabs(api_key=api_key)
        
        # Voice IDs for different languages/genders
        self.voices = {
            "en_female": "21m00Tcm4TlvDq8ikWAM",  # Rachel
            "en_male": "ErXwobaYiN019PkySvjV",    # Antoni
            "hi_female": "pNInz6obpgDQGcFmaJgB",  # Freya (multilingual)
            "hi_male": "pNInz6obpgDQGcFmaJgB",    # Same for now
        }
        
        logger.info("Initialized ElevenLabs TTS")
    
    def text_to_speech(self, text: str, language: str = "en", gender: str = "female") -> bytes:
        """
        Convert text to speech audio
        
        Args:
            text: Text to convert
            language: Language code
            gender: 'female' or 'male'
            
        Returns:
            Audio bytes
        """
        if not self.client:
            raise Exception("ElevenLabs client not initialized. Check API key.")
        
        voice_key = f"{language}_{gender}"
        voice_id = self.voices.get(voice_key, self.voices["en_female"])
        
        try:
            audio = self.client.generate(
                text=text,
                voice=voice_id,
                model="eleven_multilingual_v2",  # Supports Indian languages
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.75,
                    style=0.0,
                    use_speaker_boost=True
                )
            )
            
            # Convert generator to bytes
            audio_bytes = b"".join(audio)
            
            logger.info(f"Generated TTS audio: {len(audio_bytes)} bytes")
            return audio_bytes
            
        except Exception as e:
            logger.error(f"TTS error: {e}")
            raise Exception(f"TTS error: {str(e)}")
    
    def save_audio(self, audio_bytes: bytes, filepath: str):
        """Save audio bytes to file"""
        try:
            with open(filepath, "wb") as f:
                f.write(audio_bytes)
            logger.info(f"Saved audio to {filepath}")
        except Exception as e:
            logger.error(f"Error saving audio: {e}")
            raise
