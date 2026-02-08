"""Multimodal message routing for different input types"""

from app.ai.llm import MedicalLLM
from app.ai.whisper_stt import WhisperSTT
from app.ai.elevenlabs_tts import ElevenLabsTTS
from app.ai.vision import VisionAnalyzer
from typing import Dict, Optional
import os
import logging

logger = logging.getLogger(__name__)


class MultimodalRouter:
    """Route and process different types of messages (text, voice, image)"""
    
    def __init__(self):
        """Initialize all AI services"""
        try:
            self.llm = MedicalLLM()
            logger.info("✅ Medical LLM initialized")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            self.llm = None
        
        try:
            self.stt = WhisperSTT()
            logger.info("✅ Whisper STT initialized")
        except Exception as e:
            logger.error(f"Failed to initialize STT: {e}")
            self.stt = None
        
        try:
            self.tts = ElevenLabsTTS()
            if self.tts.client:
                logger.info("✅ ElevenLabs TTS initialized")
            else:
                logger.warning("⚠️ TTS not initialized (API key missing)")
                self.tts = None
        except Exception as e:
            logger.error(f"Failed to initialize TTS: {e}")
            self.tts = None
        
        try:
            self.vision = VisionAnalyzer()
            logger.info("✅ Vision analyzer initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Vision: {e}")
            self.vision = None
    
    def process_text_message(self, text: str, language: str = "en") -> Dict:
        """
        Handle text input → text output
        
        Args:
            text: User's text message
            language: Language code
            
        Returns:
            Dict with response details
        """
        if not self.llm:
            return {
                "type": "text",
                "content": "⚠️ AI service temporarily unavailable. Please try again later.",
                "language": language
            }
        
        try:
            response_text = self.llm.get_medical_response(text, language)
            
            return {
                "type": "text",
                "content": response_text,
                "language": language
            }
        except Exception as e:
            logger.error(f"Error processing text message: {e}")
            return {
                "type": "text",
                "content": "⚠️ Sorry, I encountered an error. Please try again.",
                "language": language
            }
    
    def process_voice_message(self, audio_file_path: str, language: str = "hi") -> Dict:
        """
        Handle voice input → text OR voice output
        
        Args:
            audio_file_path: Path to audio file
            language: Expected language
            
        Returns:
            Dict with response details
        """
        if not self.stt or not self.llm:
            return {
                "type": "text",
                "content": "⚠️ Voice processing temporarily unavailable.",
                "language": language
            }
        
        try:
            # Step 1: Convert voice to text
            with open(audio_file_path, "rb") as audio_file:
                transcription = self.stt.detect_language_and_transcribe(audio_file)
            
            if "error" in transcription:
                return {"type": "error", "content": transcription["error"]}
            
            detected_language = transcription.get("language", language)
            user_text = transcription["text"]
            
            logger.info(f"Transcribed: '{user_text[:50]}...' in {detected_language}")
            
            # Step 2: Get LLM response
            response_text = self.llm.get_medical_response(user_text, detected_language)
            
            # Step 3: Try to convert response to speech (optional, fallback to text)
            audio_path = None
            if self.tts and self.tts.client:
                try:
                    audio_bytes = self.tts.text_to_speech(
                        text=response_text,
                        language=detected_language,
                        gender="female"
                    )
                    
                    # Save audio file
                    output_path = f"temp/response_{os.urandom(8).hex()}.mp3"
                    os.makedirs("temp", exist_ok=True)
                    self.tts.save_audio(audio_bytes, output_path)
                    audio_path = output_path
                    
                    logger.info(f"Generated voice response at {audio_path}")
                except Exception as e:
                    logger.warning(f"TTS failed, sending text response: {e}")
            
            return {
                "type": "voice" if audio_path else "text",
                "audio_path": audio_path,
                "content": response_text,  # Always include text
                "transcription": user_text,
                "language": detected_language
            }
            
        except Exception as e:
            logger.error(f"Error processing voice message: {e}")
            return {
                "type": "text",
                "content": "⚠️ Could not process voice message. Please try again.",
                "language": language
            }
    
    def process_image_message(self, image_path: str, caption: str = "", 
                             language: str = "en") -> Dict:
        """
        Handle image input → visual explanation (text)
        
        Args:
            image_path: Path to image file
            caption: Optional caption from user
            language: Language code
            
        Returns:
            Dict with response details
        """
        if not self.vision:
            return {
                "type": "text",
                "content": "⚠️ Image analysis temporarily unavailable.",
                "language": language
            }
        
        try:
            query = caption if caption else "What do you see in this medical image? Provide guidance and assessment."
            
            # Analyze image
            analysis = self.vision.analyze_image(image_path, query, language)
            
            return {
                "type": "text",  # Response is text explanation
                "content": analysis,
                "language": language,
                "original_image": image_path
            }
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return {
                "type": "text",
                "content": "⚠️ Could not analyze image. Please try again.",
                "language": language
            }
    
    def route_message(self, message_type: str, content: str, caption: str = "", 
                     language: str = "en") -> Dict:
        """
        Main routing function
        
        Args:
            message_type: 'text', 'voice', 'image'
            content: Message content (text or file path)
            caption: Optional caption for images
            language: Language code
            
        Returns:
            Dict with response details
        """
        logger.info(f"Routing {message_type} message in {language}")
        
        if message_type == "text":
            return self.process_text_message(content, language)
        
        elif message_type == "audio" or message_type == "voice":
            return self.process_voice_message(content, language)
        
        elif message_type == "image":
            return self.process_image_message(content, caption, language)
        
        else:
            return {
                "type": "text",
                "content": f"⚠️ Sorry, {message_type} messages are not yet supported.",
                "language": language
            }
