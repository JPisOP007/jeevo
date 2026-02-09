
import openai
from typing import BinaryIO, Dict
import os
import logging

logger = logging.getLogger(__name__)

class WhisperSTT:

    def __init__(self, api_key: str = None):
        from app.config.settings import settings

        use_groq = settings.USE_GROQ
        groq_api_key = settings.GROQ_API_KEY
        openai_api_key = settings.OPENAI_API_KEY

        # Auto-detect: Use Groq if explicitly requested OR if OpenAI key is missing but Groq key exists
        if use_groq or (not openai_api_key and groq_api_key):
            api_key = api_key or groq_api_key
            if not api_key:
                raise ValueError("Groq API key missing (USE_GROQ=true or fallback)")
            
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            self.whisper_model = "whisper-large-v3-turbo"
            logger.info("Initialized Whisper STT with Groq")
        else:
            api_key = api_key or openai_api_key
            if not api_key:
                # If both missing, try Groq as last resort (will fail if no key)
                if groq_api_key:
                    logger.warning("OpenAI key missing, falling back to Groq")
                    self.client = openai.OpenAI(
                        api_key=groq_api_key,
                        base_url="https://api.groq.com/openai/v1"
                    )
                    self.whisper_model = "whisper-large-v3-turbo"
                    logger.info("Initialized Whisper STT with Groq (Fallback)")
                else:
                    raise ValueError("OpenAI API key missing and no Groq key found")
            else:
                self.client = openai.OpenAI(api_key=api_key)
                self.whisper_model = "whisper-1"
                logger.info("Initialized Whisper STT with OpenAI")

    def transcribe_audio(self, audio_file: BinaryIO, language: str = "hi") -> str:

        try:
            transcript = self.client.audio.transcriptions.create(
                model=self.whisper_model,
                file=audio_file,
                language=language,
                response_format="text"
            )

            logger.info(f"Successfully transcribed audio in {language}")
            return transcript

        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return f"Error transcribing audio: {str(e)}"

    def detect_language_and_transcribe(self, audio_file: BinaryIO) -> Dict:

        try:
            transcript = self.client.audio.transcriptions.create(
                model=self.whisper_model,
                file=audio_file,
                response_format="verbose_json"
            )

            result = {
                "text": transcript.text,
                "language": transcript.language
            }

            logger.info(f"Transcribed audio: detected language={result['language']}")
            return result

        except Exception as e:
            logger.error(f"Error in language detection/transcription: {e}")
            return {"error": str(e)}