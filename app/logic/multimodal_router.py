
from app.ai.llm import MedicalLLM
from app.ai.whisper_stt import WhisperSTT
from app.ai.elevenlabs_tts import ElevenLabsTTS
from app.ai.vision import VisionAnalyzer
from app.services.location_health_context import location_health_context
from app.services.symptom_checker_service import symptom_checker
from typing import Dict, Optional, List
import os
import logging
import asyncio

logger = logging.getLogger(__name__)

class MultimodalRouter:

    def __init__(self):

        try:
            self.llm = MedicalLLM()
            logger.info("✅ Medical LLM initialized")

            from app.services.intelligent_orchestrator import get_orchestrator
            self.orchestrator = get_orchestrator(self.llm.client, self.llm.model)
            logger.info("✅ Intelligent Orchestrator initialized")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            self.llm = None
            self.orchestrator = None

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

    @staticmethod
    def _ui_text(key: str, language: str) -> str:
        texts = {
            "ai_unavailable": {
                "en": "⚠️ AI service temporarily unavailable. Please try again later.",
                "hi": "⚠️ AI सेवा अस्थायी रूप से उपलब्ध नहीं है। कृपया बाद में पुनः प्रयास करें।",
                "ta": "⚠️ AI சேவை தற்காலிகமாக கிடைக்கவில்லை. தயவுசெய்து பின்னர் முயற்சிக்கவும்.",
                "te": "⚠️ AI సేవ తాత్కాలికంగా అందుబాటులో లేదు. దయచేసి తర్వాత మళ్లీ ప్రయత్నించండి.",
            },
            "text_error": {
                "en": "⚠️ Sorry, I encountered an error. Please try again.",
                "hi": "⚠️ क्षमा करें, मुझे एक त्रुटि आई। कृपया पुनः प्रयास करें।",
                "ta": "⚠️ மன்னிக்கவும், ஒரு பிழை ஏற்பட்டது. தயவுசெய்து மீண்டும் முயற்சிக்கவும்.",
                "te": "⚠️ క్షమించండి, నాకు లోపం ఎదురైంది. దయచేసి మళ్లీ ప్రయత్నించండి.",
            },
            "voice_unavailable": {
                "en": "⚠️ Voice processing temporarily unavailable.",
                "hi": "⚠️ वॉयस प्रोसेसिंग अस्थायी रूप से उपलब्ध नहीं है।",
                "ta": "⚠️ குரல் செயலாக்கம் தற்காலிகமாக கிடைக்கவில்லை.",
                "te": "⚠️ వాయిస్ ప్రాసెసింగ్ తాత్కాలికంగా అందుబాటులో లేదు.",
            },
            "voice_error": {
                "en": "⚠️ Could not process voice message. Please try again.",
                "hi": "⚠️ वॉयस मैसेज प्रोसेस नहीं कर सका। कृपया पुनः प्रयास करें।",
                "ta": "⚠️ குரல் செய்தியை செயலாக்க முடியவில்லை. தயவுசெய்து மீண்டும் முயற்சிக்கவும்.",
                "te": "⚠️ వాయిస్ సందేశాన్ని ప్రాసెస్ చేయలేకపోయాము. దయచేసి మళ్లీ ప్రయత్నించండి.",
            },
            "image_unavailable": {
                "en": "⚠️ Image analysis temporarily unavailable.",
                "hi": "⚠️ इमेज विश्लेषण अस्थायी रूप से उपलब्ध नहीं है।",
                "ta": "⚠️ பட பகுப்பாய்வு தற்காலிகமாக கிடைக்கவில்லை.",
                "te": "⚠️ చిత్రం విశ్లేషణ తాత్కాలికంగా అందుబాటులో లేదు.",
            },
            "image_error": {
                "en": "⚠️ Could not analyze image. Please try again.",
                "hi": "⚠️ इमेज का विश्लेषण नहीं कर सका। कृपया पुनः प्रयास करें।",
                "ta": "⚠️ படத்தை பகுப்பாய்வு செய்ய முடியவில்லை. தயவுசெய்து மீண்டும் முயற்சிக்கவும்.",
                "te": "⚠️ చిత్రాన్ని విశ్లేషించలేకపోయాము. దయచేసి మళ్లీ ప్రయత్నించండి.",
            },
            "unsupported": {
                "en": "⚠️ Sorry, this message type is not yet supported.",
                "hi": "⚠️ क्षमा करें, यह संदेश प्रकार अभी समर्थित नहीं है।",
                "ta": "⚠️ மன்னிக்கவும், இந்த செய்தி வகை இன்னும் ஆதரிக்கப்படவில்லை.",
                "te": "⚠️ క్షమించండి, ఈ సందేశ రకం ఇంకా మద్దతు ఇవ్వబడలేదు.",
            },
        }
        return texts.get(key, {}).get(language, texts.get(key, {}).get("en", ""))

    async def process_text_message(self, text: str, language: str = "en", user_location: Dict = None, 
                                  user_id: int = None, family_members: List[Dict] = None,
                                  conversation_context: str = None) -> Dict:

        if not self.llm:
            return {
                "type": "text",
                "content": self._ui_text("ai_unavailable", language),
                "language": language
            }

        try:
            detected_symptom = symptom_checker.detect_symptom(text)
            
            location_context = ""
            if user_location:
                location_context = location_health_context.get_location_health_context(user_location)

            family_context = ""
            if family_members:
                family_info = ", ".join([f"{member.get('name', 'Unknown')} ({member.get('relation', '')}, Age: {member.get('age', '?')})" 
                                       for member in family_members if member])
                family_context = f"Family members: {family_info}\n"

            base_prompt = text
            if location_context:
                base_prompt = f"User Location Context:\n{location_context}\n\nUser Request:\n{text}"
            
            if family_context:
                base_prompt = family_context + base_prompt
            
            if conversation_context:
                base_prompt = f"Recent Conversation History:\n{conversation_context}\n\n{base_prompt}"

            if self.orchestrator and user_location:
                response_text = await self.orchestrator.process_with_tools(
                    base_prompt, 
                    language, 
                    user_location
                )
            else:
                response_text = self.llm.get_medical_response(base_prompt, language)

            metadata = {
                "type": "text",
                "content": response_text,
                "language": language
            }
            
            if detected_symptom:
                metadata["detected_symptom"] = detected_symptom
                workflow = symptom_checker.get_assessment_flow(detected_symptom)
                if workflow:
                    metadata["symptom_workflow"] = workflow.get("name")

            return metadata

        except Exception as e:
            logger.error(f"Error processing text message: {e}")
            return {
                "type": "text",
                "content": self._ui_text("text_error", language),
                "language": language
            }

    async def process_voice_message(self, audio_file_path: str, language: str = "hi", user_location: Dict = None) -> Dict:
        
        logger.info(f"Processing voice message path={audio_file_path} stt={self.stt is not None} llm={self.llm is not None}")

        if not self.stt or not self.llm:
            logger.warning("STT or LLM not initialized - returning voice_unavailable")
            return {
                "type": "text",
                "content": self._ui_text("voice_unavailable", language),
                "language": language
            }

        try:

            with open(audio_file_path, "rb") as audio_file:
                transcription = self.stt.detect_language_and_transcribe(audio_file)

            if "error" in transcription:
                # Don't leak provider/English errors to the user; always return in preferred language.
                return {
                    "type": "text",
                    "content": self._ui_text("voice_error", language),
                    "language": language
                }

            detected_language = transcription.get("language", None)
            user_text = transcription["text"]

            logger.info(f"Transcribed: '{user_text[:50]}...' detected_language={detected_language} preferred_language={language}")

            # IMPORTANT: Always respond in the user's preferred language (the `language` argument).
            # Detected language is only used for metadata/logging.
            if self.orchestrator and user_location:
                response_text = await self.orchestrator.process_with_tools(
                    user_text,
                    language,
                    user_location
                )
            else:
                response_text = self.llm.get_medical_response(user_text, language)

            audio_path = None
            if self.tts and self.tts.client:
                try:
                    audio_bytes = self.tts.text_to_speech(
                        text=response_text,
                        language=language,
                        gender="female"
                    )

                    output_path = f"temp/response_{os.urandom(8).hex()}.ogg"
                    os.makedirs("temp", exist_ok=True)
                    self.tts.save_audio(audio_bytes, output_path)
                    audio_path = output_path

                    logger.info(f"Generated voice response at {audio_path}")
                except Exception as e:
                    logger.warning(f"TTS failed, sending text response: {e}")

            return {
                "type": "voice" if audio_path else "text",
                "audio_path": audio_path,
                "content": response_text,
                "transcription": user_text,
                "language": language,
                "detected_language": detected_language
            }

        except Exception as e:
            logger.error(f"Error processing voice message: {e}")
            return {
                "type": "text",
                "content": self._ui_text("voice_error", language),
                "language": language
            }

    def process_image_message(self, image_path: str, caption: str = "",
                             language: str = "en") -> Dict:

        if not self.vision:
            return {
                "type": "text",
                "content": self._ui_text("image_unavailable", language),
                "language": language
            }

        try:
            language_names = {
                "en": "English",
                "hi": "Hindi",
                "ta": "Tamil",
                "te": "Telugu",
                "bn": "Bengali",
                "mr": "Marathi",
                "gu": "Gujarati",
                "kn": "Kannada",
                "ml": "Malayalam",
                "pa": "Punjabi",
            }
            lang_name = language_names.get(language, "English")
            query = caption if caption else f"Analyze this medical image and provide guidance. Respond only in {lang_name}."

            analysis = self.vision.analyze_image(image_path, query, language)

            return {
                "type": "text",
                "content": analysis,
                "language": language,
                "original_image": image_path
            }

        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return {
                "type": "text",
                "content": self._ui_text("image_error", language),
                "language": language
            }

    async def route_message(self, message_type: str, content: str, caption: str = "",
                     language: str = "en", user_location: Dict = None,
                     user_id: int = None, family_members: List[Dict] = None,
                     conversation_context: str = None) -> Dict:

        logger.info(f"Routing {message_type} message in {language}")

        if message_type == "text":
            return await self.process_text_message(
                content, 
                language, 
                user_location,
                user_id=user_id,
                family_members=family_members,
                conversation_context=conversation_context
            )

        elif message_type == "audio" or message_type == "voice":
            return await self.process_voice_message(content, language, user_location=user_location)

        elif message_type == "image":
            return self.process_image_message(content, caption, language)

        else:
            return {
                "type": "text",
                "content": self._ui_text("unsupported", language),
                "language": language
            }