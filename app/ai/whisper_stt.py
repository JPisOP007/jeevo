
import openai
from typing import BinaryIO, Dict
import os
import logging

logger = logging.getLogger(__name__)

class WhisperSTT:

    def __init__(self, api_key: str = None):

        use_groq = os.getenv("USE_GROQ", "false").lower() == "true"

        if use_groq:
            api_key = api_key or os.getenv("GROQ_API_KEY")
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            self.whisper_model = "whisper-large-v3-turbo"
            logger.info("Initialized Whisper STT with Groq")
        else:
            api_key = api_key or os.getenv("OPENAI_API_KEY")
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