
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)

class ElevenLabsTTS:

    def __init__(self, api_key: str = None):

        if api_key is None:
            api_key = os.getenv("ELEVENLABS_API_KEY")

        if not api_key:
            logger.warning("ElevenLabs API key not found. TTS will not work.")
            self.client = None
            return

        self.client = ElevenLabs(api_key=api_key)

        self.voices = {
            "en_female": "21m00Tcm4TlvDq8ikWAM",
            "en_male": "ErXwobaYiN019PkySvjV",
            "hi_female": "pNInz6obpgDQGcFmaJgB",
            "hi_male": "pNInz6obpgDQGcFmaJgB",
            "mr_female": "pNInz6obpgDQGcFmaJgB",
            "mr_male": "pNInz6obpgDQGcFmaJgB",
            "gu_female": "pNInz6obpgDQGcFmaJgB",
            "gu_male": "pNInz6obpgDQGcFmaJgB",
            "bn_female": "pNInz6obpgDQGcFmaJgB",
            "bn_male": "pNInz6obpgDQGcFmaJgB",
            "ta_female": "pNInz6obpgDQGcFmaJgB",
            "ta_male": "pNInz6obpgDQGcFmaJgB",
            "te_female": "pNInz6obpgDQGcFmaJgB",
            "te_male": "pNInz6obpgDQGcFmaJgB",
            "kn_female": "pNInz6obpgDQGcFmaJgB",
            "kn_male": "pNInz6obpgDQGcFmaJgB",
            "ml_female": "pNInz6obpgDQGcFmaJgB",
            "ml_male": "pNInz6obpgDQGcFmaJgB",
            "pa_female": "pNInz6obpgDQGcFmaJgB",
            "pa_male": "pNInz6obpgDQGcFmaJgB",
        }
        
        self.speech_speed_multiplier = 0.85
        self.voice_stability = 0.5
        self.voice_similarity = 0.75

        logger.info("Initialized ElevenLabs TTS")

    def text_to_speech(self, text: str, language: str = "en", gender: str = "female") -> bytes:

        if not self.client:
            raise Exception("ElevenLabs client not initialized. Check API key.")

        voice_key = f"{language}_{gender}"
        voice_id = self.voices.get(voice_key, self.voices["en_female"])

        try:
            audio = self.client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2",
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.75,
                    style=0.0,
                    use_speaker_boost=True
                )
            )

            audio_bytes = b"".join(audio)

            logger.info(f"Generated TTS audio: {len(audio_bytes)} bytes")
            return audio_bytes

        except Exception as e:
            logger.error(f"TTS error: {e}")
            raise Exception(f"TTS error: {str(e)}")

    def save_audio(self, audio_bytes: bytes, filepath: str):

        try:
            with open(filepath, "wb") as f:
                f.write(audio_bytes)
            logger.info(f"Saved audio to {filepath}")
        except Exception as e:
            logger.error(f"Error saving audio: {e}")
            raise