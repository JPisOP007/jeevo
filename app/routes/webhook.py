from fastapi import APIRouter, Request, HTTPException, Query, Depends
from fastapi.responses import PlainTextResponse
from typing import Dict, Any
import logging
import os
import time
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models.message import WhatsAppMessage
from app.services.whatsapp_service import whatsapp_service
from app.services.cache_service import cache_service
from app.services.medical_validation_service import MedicalValidationService
from app.services.escalation_service import EscalationService
from app.services.disclaimer_service import DisclaimerService
from app.database.base import get_db
from app.database.repositories import (
    UserRepository, ConversationRepository, FamilyMemberRepository,
    ResponseValidationRepository
)
from app.logic.multimodal_router import MultimodalRouter
from app.logic.language_manager import LanguageManager
from app.services.jeevo_onboarding import jeevo_onboarding
from app.services.service_handlers import (
    HealthSupportService,
    FamilyCareService,
    VaccinationService,
    HospitalFinderService,
    EnvironmentalAlertService
)
from app.services.heatmap_update_service import HeatmapUpdateService
from app.services.risk_alert_service import RiskAlertService
from app.services.risk_aggregation_service import RiskAggregationService
from app.services.vaccine_reminder_service import VaccineReminderService
from app.services.anganwadi_finder_service import AnganwadiFinderService
from app.services.location_parser_service import location_parser_service
from app.ai.whisper_stt import WhisperSTT
from app.utils.helpers import (
    is_webhook_valid,
    log_incoming_message,
    validate_user_location,
    sanitize_user_input
)

logger = logging.getLogger(__name__)
router = APIRouter()

multimodal_router = MultimodalRouter()
language_manager = LanguageManager()

async def complete_onboarding(phone_number: str, db: AsyncSession):
    """Mark user as onboarded and clean up all cache keys to prevent state inconsistency"""
    try:
        # Mark user as onboarded in database (permanent)
        await UserRepository.update_user(db, phone_number, is_onboarded=True)
        
        # Clean up ALL onboarding cache keys
        keys_to_delete = [
            f"onboarding_stage:{phone_number}",
            f"onboarding_lang:{phone_number}",
            f"onboarding_name:{phone_number}",
        ]
        for key in keys_to_delete:
            try:
                await cache_service.delete(key)
            except:
                pass
        
        logger.info(f"[ONBOARDING] ✅ Completed for {phone_number} - marked onboarded and cache cleared")
    except Exception as e:
        logger.error(f"[ONBOARDING] Error completing onboarding: {e}")

@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    request: Request,
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge")
):

    logger.info(f"[WEBHOOK VERIFICATION] Mode: {mode}, Token received: {token[:10]}...")

    if mode == "subscribe" and token == settings.WEBHOOK_VERIFY_TOKEN:
        logger.info("[WEBHOOK VERIFICATION] ✅ Success - Returning challenge")
        return challenge
    else:
        logger.warning("[WEBHOOK VERIFICATION] ❌ Failed - Invalid token")
        raise HTTPException(status_code=403, detail="Verification token mismatch")

@router.post("/webhook")
async def receive_webhook(request: Request, db: AsyncSession = Depends(get_db)):

    try:
        webhook_data: Dict[str, Any] = await request.json()

        logger.info("[WEBHOOK] Received data")

        if not is_webhook_valid(webhook_data):
            logger.warning("[WEBHOOK] Invalid webhook structure")
            return {"status": "ignored", "reason": "invalid_structure"}

        entry = webhook_data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "statuses" in value:
            logger.info("[WEBHOOK] Status update received - ignoring")
            return {"status": "ok", "type": "status_update"}

        try:
            message = whatsapp_service.parse_incoming_message(webhook_data)
            log_incoming_message(message)
        except ValueError as e:
            logger.error(f"[WEBHOOK] Error parsing message: {e}")
            return {"status": "error", "message": str(e)}

        try:
            await whatsapp_service.mark_message_as_read(message.message_id)
        except Exception as e:
            logger.warning(f"[WEBHOOK] Could not mark message as read: {e}")

        await process_message(message, db)

        return {"status": "ok", "message_id": message.message_id}

    except Exception as e:
        logger.error(f"[WEBHOOK] Unexpected error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

async def process_message(message: WhatsAppMessage, db: AsyncSession) -> None:

    start_time = time.time()

    try:

        user = await UserRepository.get_by_phone_number(db, message.from_number)

        is_new = False
        if not user:
            is_new = True
            user = await UserRepository.create_user(db, phone_number=message.from_number)
            logger.info(f"[USER] New user created: {message.from_number}")

            await whatsapp_service.send_text_message(
                to_number=message.from_number,
                text=jeevo_onboarding.welcome_message()
            )

            await cache_service.set(f"onboarding_stage:{message.from_number}", "language_selection", 600)
            return
        else:
            logger.info(f"[USER] Existing user: {message.from_number}")

        # Always read onboarding stage from cache so users can re-open the menu
        # and select options at any time (even after initial onboarding).
        onboarding_stage = await cache_service.get(f"onboarding_stage:{message.from_number}")

        if onboarding_stage:
            text = message.text_content.strip() if (message.message_type == "text" and message.text_content) else ""

            if onboarding_stage == "language_selection":
                lang_code = jeevo_onboarding.get_language_from_number(text)
                if lang_code:
                    await UserRepository.update_user(db, message.from_number, language=lang_code)
                    await cache_service.set(f"onboarding_lang:{message.from_number}", lang_code, 600)
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "name_collection", 600)

                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=jeevo_onboarding.get_name_request(lang_code)
                    )
                    return
                else:
                    invalid_messages = {
                        "en": "❌ Invalid. Reply with number 1-10",
                        "hi": "❌ अमान्य। 1-10 नंबर के साथ जवाब दें",
                        "ta": "❌ தவறானது. 1-10 எண்ணுடன் பதிலளிக்கவும்",
                        "te": "❌ చెల్లనిది. 1-10 సంఖ్యతో ప్రత్యుత్తరం ఇవ్వండి"
                    }
                    user_lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=invalid_messages.get(user_lang, invalid_messages["en"])
                    )
                    return

            elif onboarding_stage == "name_collection":
                # Allow voice-first: accept audio input to extract name (and possible location)
                if message.message_type == "audio" and message.media_id:
                    try:
                        audio_path = await whatsapp_service.download_media(message.media_id, message.message_type)
                        stt = WhisperSTT()
                        # detect language and transcribe
                        with open(audio_path, "rb") as af:
                            stt_result = stt.detect_language_and_transcribe(af)

                        # stt_result may be dict with 'text' and 'language' or error
                        if isinstance(stt_result, dict) and stt_result.get("text"):
                            transcript = stt_result.get("text")
                            detected_lang = stt_result.get("language") or None
                            preferred_lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"

                            # Simple heuristic: try to extract name from phrases
                            name = None
                            lower = transcript.lower()
                            # English patterns
                            if "my name is" in lower:
                                name = transcript.partition("my name is")[-1].strip().split("\n")[0]
                            # Hindi patterns
                            elif "मेरा नाम" in transcript:
                                name = transcript.partition("मेरा नाम")[-1].strip().split("\n")[0]
                            # Fallback: take first short line
                            if not name:
                                first_line = transcript.strip().split("\n")[0]
                                if 1 < len(first_line) <= 60:
                                    name = first_line

                            if name:
                                await UserRepository.update_user(db, message.from_number, name=name)
                                await cache_service.set(f"onboarding_name:{message.from_number}", name, 600)
                                await cache_service.set(f"onboarding_stage:{message.from_number}", "location_collection", 600)

                                lang = preferred_lang
                                await whatsapp_service.send_text_message(
                                    to_number=message.from_number,
                                    text=jeevo_onboarding.get_location_request(lang)
                                )
                                return

                            # If we couldn't extract a name, ask user to type or re-record
                            error_messages = {
                                "en": "❌ Could not detect your name from the voice note. Please type your name or try again.",
                                "hi": "❌ वॉयस नोट से आपका नाम पता नहीं लगा सका। कृपया अपना नाम टाइप करें या पुनः प्रयास करें।",
                                "ta": "❌ குரல் குறிப்பிலிருந்து உங்கள் பெயரைக் கண்டறிய முடியவில்லை. தயவுசெய்து உங்கள் பெயரைத் தட்டச்சு செய்யவும் அல்லது மீண்டும் முயற்சிக்கவும்।",
                                "te": "❌ వాయిస్ నోట్ నుండి మీ పేరును గుర్తించలేకపోయాము. దయచేసి మీ పేరును టైప్ చేయండి లేదా మళ్లీ ప్రయత్నించండి।"
                            }
                            user_lang = preferred_lang
                            await whatsapp_service.send_text_message(
                                to_number=message.from_number,
                                text=error_messages.get(user_lang, error_messages["en"])
                            )
                            return

                        else:
                            error_messages = {
                                "en": "⚠️ Couldn't transcribe your audio. Please type your name.",
                                "hi": "⚠️ आपका ऑडियो ट्रांसक्राइब नहीं कर सका। कृपया अपना नाम टाइप करें।",
                                "ta": "⚠️ உங்கள் ஆடியோவை படியெடுக்க முடியவில்லை. தயவுசெய்து உங்கள் பெயரைத் தட்டச்சு செய்யவும்।",
                                "te": "⚠️ మీ ఆడియోను ట్రాన్స్క్రిబ్ చేయలేకపోయాము. దయచేసి మీ పేరును టైప్ చేయండి।"
                            }
                            user_lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                            await whatsapp_service.send_text_message(
                                to_number=message.from_number,
                                text=error_messages.get(user_lang, error_messages["en"])
                            )
                            return

                    except Exception as e:
                        logger.error(f"[ONBOARDING][VOICE] Error processing voice for name collection: {e}")
                        error_messages = {
                            "en": "⚠️ Error processing your voice message. Please type your name.",
                            "hi": "⚠️ आपके वॉयस मैसेज को प्रोसेस करने में त्रुटि। कृपया अपना नाम टाइप करें।",
                            "ta": "⚠️ உங்கள் குரல் செய்தியை செயலாக்குவதில் பிழை. தயவுசெய்து உங்கள் பெயரைத் தட்டச்சு செய்யவும்।",
                            "te": "⚠️ మీ వాయిస్ సందేశాన్ని ప్రాసెస్ చేయడంలో లోపం. దయచేసి మీ పేరును టైప్ చేయండి।"
                        }
                        user_lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                        await whatsapp_service.send_text_message(
                            to_number=message.from_number,
                            text=error_messages.get(user_lang, error_messages["en"])
                        )
                        return

                # Fallback: text name collection
                name = text
                await UserRepository.update_user(db, message.from_number, name=name)
                await cache_service.set(f"onboarding_name:{message.from_number}", name, 600)
                await cache_service.set(f"onboarding_stage:{message.from_number}", "location_collection", 600)

                lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=jeevo_onboarding.get_location_request(lang)
                )
                return

            elif onboarding_stage == "location_collection":
                # Accept audio or text; use STT + LLM parser to normalize freeform locations
                user_lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                location_text = text

                if message.message_type == "audio" and message.media_id:
                    try:
                        audio_path = await whatsapp_service.download_media(message.media_id, message.message_type)
                        stt = WhisperSTT()
                        with open(audio_path, "rb") as af:
                            stt_result = stt.detect_language_and_transcribe(af)

                        if isinstance(stt_result, dict) and stt_result.get("text"):
                            location_text = stt_result.get("text")
                        else:
                            await whatsapp_service.send_text_message(
                                to_number=message.from_number,
                                text=jeevo_onboarding.get_location_request(user_lang)
                            )
                            return
                    except Exception as e:
                        logger.error(f"[ONBOARDING][VOICE] Error processing voice for location: {e}")
                        await whatsapp_service.send_text_message(
                            to_number=message.from_number,
                            text=jeevo_onboarding.get_location_request(user_lang)
                        )
                        return

                # Use LLM-based parser to normalize
                logger.info(f"[LOCATION] Parsing user input: {location_text}")
                parse_result = await location_parser_service.parse_and_validate_location(location_text, language=user_lang)

                if not parse_result["success"]:
                    # Location parsing failed - show friendly error message
                    error_message = parse_result.get("error", "Could not understand your location.")
                    logger.warning(f"[LOCATION] Parse failed: {error_message}")
                    
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=f"❌ {error_message}"
                    )
                    
                    # Provide helpful hint for next attempt
                    hint_message = {
                        "en": "💡 Try again with format like: 'Dharavi, Mumbai' or 'Village XYZ, Maharashtra'",
                        "hi": "💡 इस तरह कोशिश करें: 'धारावी, मुंबई' या 'गांव XYZ, महाराष्ट्र'"
                    }
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=hint_message.get(user_lang, hint_message["en"])
                    )
                    return

                # Successfully parsed location
                logger.info(f"[LOCATION] ✅ Parsed: city={parse_result['city']}, state={parse_result['state']}, pincode={parse_result['pincode']}")
                
                await UserRepository.update_user(
                    db, message.from_number,
                    city=parse_result["city"],
                    state=parse_result["state"],
                    pincode=parse_result["pincode"]
                )

                # Send confirmation of what we understood
                confirm_templates = {
                    "en": "✅ Got it! You're in {city}, {state}",
                    "hi": "✅ समझ गया! आप {city}, {state} में हैं",
                    "mr": "✅ समजले! तुम्ही {city}, {state} मध्ये आहात",
                    "gu": "✅ સમજી ગયા! તમે {city}, {state} માં છો",
                    "bn": "✅ বুঝতে পেরেছি! আপনি {city}, {state}-এ আছেন",
                    "ta": "✅ புரிந்தது! நீங்கள் {city}, {state} இல் இருக்கிறீர்கள்",
                    "te": "✅ అర్థమైంది! మీరు {city}, {state} లో ఉన్నారు",
                    "kn": "✅ ಅರ್ಥವಾಯಿತು! ನೀವು {city}, {state} ನಲ್ಲಿದ್ದೀರಿ",
                    "ml": "✅ മനസ്സിലായി! നിങ്ങൾ {city}, {state}-ൽ ആണ്",
                    "pa": "✅ ਸਮਝ ਗਿਆ! ਤੁਸੀਂ {city}, {state} ਵਿੱਚ ਹੋ"
                }
                confirm_message = confirm_templates.get(user_lang, confirm_templates["en"]).format(
                    city=parse_result["city"],
                    state=parse_result["state"]
                )
                if parse_result.get("interpretation"):
                    confirm_message += f"\n({parse_result['interpretation']})"
                
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=confirm_message
                )

                # Find hospitals for the location
                location = {"city": parse_result["city"], "state": parse_result["state"]}
                hospitals = await HospitalFinderService.find_hospitals(location)

                name = await cache_service.get(f"onboarding_name:{message.from_number}") or "User"

                await cache_service.set(f"onboarding_stage:{message.from_number}", "service_selection", 600)

                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=jeevo_onboarding.get_service_selection(user_lang, name)
                )
                return

            elif onboarding_stage == "profile_update_selection":
                # Handle profile update options
                profile_option = text.strip()
                lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                
                if profile_option == "1":
                    # Update location
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "updating_location", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_location_request(lang)
                    )
                    return
                
                elif profile_option == "2":
                    # Update name
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "updating_name", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_name_request(lang)
                    )
                    return
                
                elif profile_option == "3":
                    # Update language
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "language_selection", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.welcome_message()
                    )
                    return
                else:
                    invalid_messages = {
                        "en": "❌ Invalid. Reply with number 1-3",
                        "hi": "❌ अमान्य। 1-3 नंबर के साथ जवाब दें",
                        "ta": "❌ தவறானது. 1-3 எண்ணுடன் பதிலளிக்கவும்",
                        "te": "❌ చెల్లనిది. 1-3 సంఖ్యతో ప్రత్యుత్తరం ఇవ్వండి"
                    }
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        invalid_messages.get(lang, invalid_messages["en"])
                    )
                    return

            elif onboarding_stage == "updating_location":
                # Handle location update (allow audio input too)
                lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                location_text = text

                if message.message_type == "audio" and message.media_id:
                    try:
                        audio_path = await whatsapp_service.download_media(message.media_id, message.message_type)
                        stt = WhisperSTT()
                        with open(audio_path, "rb") as af:
                            stt_result = stt.detect_language_and_transcribe(af)

                        if isinstance(stt_result, dict) and stt_result.get("text"):
                            location_text = stt_result.get("text")
                            lang = stt_result.get("language") or lang
                        else:
                            await whatsapp_service.send_text_message(
                                to_number=message.from_number,
                                text=jeevo_onboarding.get_location_request(lang)
                            )
                            return
                    except Exception as e:
                        logger.error(f"[ONBOARDING][VOICE] Error processing voice for updating location: {e}")
                        await whatsapp_service.send_text_message(
                            to_number=message.from_number,
                            text=jeevo_onboarding.get_location_request(lang)
                        )
                        return

                logger.info(f"[LOCATION] Parsing user input for update: {location_text}")
                parse_result = await location_parser_service.parse_and_validate_location(location_text, language=lang)

                if not parse_result["success"]:
                    error_message = parse_result.get("error", "Could not understand your location.")
                    logger.warning(f"[LOCATION] Parse failed: {error_message}")
                    
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=f"❌ {error_message}"
                    )
                    
                    hint_message = {
                        "en": "💡 Try again with format like: 'Dharavi, Mumbai' or 'Village XYZ, Maharashtra'",
                        "hi": "💡 इस तरह कोशिश करें: 'धारावी, मुंबई' या 'गांव XYZ, महाराष्ट्र'"
                    }
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=hint_message.get(lang, hint_message["en"])
                    )
                    return

                # Successfully parsed and updated location
                logger.info(f"[LOCATION] ✅ Updated: city={parse_result['city']}, state={parse_result['state']}")
                
                await UserRepository.update_user(
                    db, message.from_number,
                    city=parse_result['city'],
                    state=parse_result['state'],
                    pincode=parse_result['pincode']
                )

                confirm_message = f"✅ Location updated! You're now in {parse_result['city']}, {parse_result['state']}"
                if parse_result.get("interpretation"):
                    confirm_message += f"\n({parse_result['interpretation']})"
                
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=confirm_message
                )
                
                # Clear the profile update stage and return to main services
                await cache_service.delete(f"onboarding_stage:{message.from_number}")
                
                return_msg = {
                    "en": "✅ Profile updated successfully! Type *MENU* to access services.",
                    "hi": "✅ प्रोफाइल सफलतापूर्वक अपडेट हो गया! सेवाओं के लिए *MENU* टाइप करें।"
                }
                await whatsapp_service.send_text_message(
                    message.from_number,
                    return_msg.get(lang, return_msg["en"])
                )
                return

            elif onboarding_stage == "updating_name":
                # Handle name update
                new_name = text.strip()
                await UserRepository.update_user(db, message.from_number, name=new_name)
                
                lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                
                # Clear the profile update stage
                await cache_service.delete(f"onboarding_stage:{message.from_number}")
                
                confirm_msgs = {
                    "en": f"✅ Name updated to '{new_name}'! Type *MENU* to access services.",
                    "hi": f"✅ नाम '{new_name}' में बदल दिया गया! सेवाओं के लिए *MENU* टाइप करें।",
                    "mr": f"✅ नाव '{new_name}' मध्ये अपडेट केले! सेवांसाठी *MENU* टाइप करा।",
                    "gu": f"✅ નામ '{new_name}' માં અપડેટ થયું! સેવાઓ માટે *MENU* ટાઇપ કરો.",
                    "bn": f"✅ নাম '{new_name}'-এ আপডেট করা হয়েছে! পরিষেবাগুলির জন্য *MENU* টাইপ করুন।",
                    "ta": f"✅ பெயர் '{new_name}' என மாற்றப்பட்டது! சேவைகளுக்கு *MENU* என டைப் செய்யவும்.",
                    "te": f"✅ పేరు '{new_name}' కి అప్‌డేట్ చేయబడింది! సేవల కోసం *MENU* అని టైప్ చేయండి.",
                    "kn": f"✅ ಹೆಸರು '{new_name}' ಗೆ ಅಪ್‌ಡೇಟ್ ಆಗಿದೆ! ಸೇವೆಗಳಿಗಾಗಿ *MENU* ಟೈಪ್ ಮಾಡಿ.",
                    "ml": f"✅ പേര് '{new_name}' എന്നതിലേക്ക് മാറ്റി! സേവനങ്ങൾക്കായി *MENU* എന്ന് ടൈപ്പ് ചെയ്യുക.",
                    "pa": f"✅ ਨਾਮ '{new_name}' ਵਿੱਚ ਬਦਲ ਦਿੱਤਾ ਗਿਆ! ਸੇਵਾਵਾਂ ਲਈ *MENU* ਟਾਈਪ ਕਰੋ।"
                }
                await whatsapp_service.send_text_message(
                    message.from_number,
                    confirm_msgs.get(lang, confirm_msgs["en"])
                )
                return

            elif onboarding_stage == "service_selection":
                service_num = text.strip()
                lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                name = await cache_service.get(f"onboarding_name:{message.from_number}") or "User"

                if service_num == "1":
                    await complete_onboarding(message.from_number, db)
                    health_prompts = {
                        "en": "Describe your health problem",
                        "hi": "अपनी समस्या विस्तार से बताएं",
                        "mr": "तुमची आरोग्य समस्या सांगा",
                        "gu": "તમારી આરોગ્ય સમસ્યા જણાવો",
                        "bn": "আপনার স্বাস্থ্য সমস্যা বর্ণনা করুন",
                        "ta": "உங்கள் சுகாதார சிக்கலை விவரிக்கவும்",
                        "te": "మీ ఆరోగ్య సమస్యను వివరించండి",
                        "kn": "ನಿಮ್ಮ ఆరోగ్య ಸಮಸ್ಯೆಯನ್ನು ವಿವರಿಸಿ",
                        "ml": "നിങ്ങളുടെ ఆరోగ్య പ്രശ്നം വിവരിക്കുക",
                        "pa": "ਆਪਣੀ ਸਿਹਤ ਸਮੱਸਿਆ ਬਾਰੇ ਦੱਸੋ"
                    }
                    msg = health_prompts.get(lang, health_prompts["en"])
                    await whatsapp_service.send_text_message(message.from_number, msg)
                    return

                elif service_num == "2":
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "adding_family", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_family_member_request(lang)
                    )
                    return

                elif service_num == "3":
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "vaccination_setup", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_vaccination_setup(lang)
                    )
                    return

                elif service_num == "4":
                    user_data = await UserRepository.get_by_phone_number(db, message.from_number)
                    location = {"city": user_data.city, "state": user_data.state}
                    hospitals = await HospitalFinderService.find_hospitals(location)
                    response = HospitalFinderService.format_hospitals(hospitals, lang)

                    await complete_onboarding(message.from_number, db)
                    await whatsapp_service.send_text_message(message.from_number, response)

                    services_enabled = ["🏥 Hospital Finder"]
                    completion = jeevo_onboarding.get_completion_message(lang, name, services_enabled)
                    await whatsapp_service.send_text_message(message.from_number, completion)
                    return

                elif service_num == "5":
                    user_data = await UserRepository.get_by_phone_number(db, message.from_number)
                    location = {"city": user_data.city, "state": user_data.state}
                    alerts = await EnvironmentalAlertService.get_alerts(location)
                    response = EnvironmentalAlertService.format_alerts(alerts, lang)

                    await complete_onboarding(message.from_number, db)
                    await whatsapp_service.send_text_message(message.from_number, response)

                    services_enabled = ["🌡️ Environmental Alerts"]
                    completion = jeevo_onboarding.get_completion_message(lang, name, services_enabled)
                    await whatsapp_service.send_text_message(message.from_number, completion)
                    return

                elif service_num == "6":
                    await complete_onboarding(message.from_number, db)
                    msg = "दवा का नाम बताएं" if lang == "hi" else "Tell me medicine name"
                    await whatsapp_service.send_text_message(message.from_number, msg)
                    return

                elif service_num == "7":
                    # Profile update option
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "profile_update_selection", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_profile_update_menu(lang)
                    )
                    return
                else:
                    invalid_messages = {
                        "en": "❌ Invalid. Reply with number 1-7",
                        "hi": "❌ अमान्य। 1-7 नंबर के साथ जवाब दें",
                        "ta": "❌ தவறானது. 1-7 எண்ணுடன் பதிலளிக்கவும்",
                        "te": "❌ చెల్లనిది. 1-7 సంఖ్యతో ప్రత్యుత్తరం ఇవ్వండి"
                    }
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        invalid_messages.get(lang, invalid_messages["en"])
                    )
                    return

            elif onboarding_stage == "adding_family":
                if text.upper() == "DONE":
                    lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                    name = await cache_service.get(f"onboarding_name:{message.from_number}") or "User"

                    await complete_onboarding(message.from_number, db)

                    services_enabled = ["👨‍👩‍👧 Family Care"]
                    completion = jeevo_onboarding.get_completion_message(lang, name, services_enabled)
                    await whatsapp_service.send_text_message(message.from_number, completion)
                    return
                else:

                    parts = [p.strip() for p in text.split(",")]
                    if len(parts) >= 3:

                        try:
                            await FamilyMemberRepository.create_family_member(
                                db,
                                user_id=user.id,
                                name=parts[0],
                                relation=parts[1],
                                age=int(parts[2]) if parts[2].isdigit() else None
                            )

                            await whatsapp_service.send_text_message(
                                message.from_number,
                                f"✅ Added {parts[0]}!\n\nAdd more or reply *DONE*"
                            )
                        except Exception as e:
                            logger.error(f"Error saving family member: {e}")
                            error_messages = {
                                "en": "❌ Error saving family member. Please try again.",
                                "hi": "❌ परिवार के सदस्य को सहेजने में त्रुटि। कृपया पुनः प्रयास करें।",
                                "ta": "❌ குடும்ப உறுப்பினரை சேமிக்கும்போது பிழை. தயவுசெய்து மீண்டும் முயற்சிக்கவும்।",
                                "te": "❌ కుటుంబ సభ్యుని సేవ్ చేయడంలో లోపం. దయచేసి మళ్లీ ప్రయత్నించండి।"
                            }
                            await whatsapp_service.send_text_message(
                                message.from_number,
                                error_messages.get(lang, error_messages["en"])
                            )
                        return
                    else:
                        lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                        await whatsapp_service.send_text_message(
                            message.from_number,
                            jeevo_onboarding.get_family_member_request(lang)
                        )
                        return

            elif onboarding_stage == "vaccination_setup":

                parts = [p.strip() for p in text.split(",")]
                if len(parts) >= 2:

                    lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                    name = await cache_service.get(f"onboarding_name:{message.from_number}") or "User"

                    await complete_onboarding(message.from_number, db)

                    msg = f"✅ Vaccination tracking setup for {parts[0]}!\n\nI'll send automatic reminders."
                    await whatsapp_service.send_text_message(message.from_number, msg)

                    services_enabled = ["💉 Vaccination Tracking"]
                    completion = jeevo_onboarding.get_completion_message(lang, name, services_enabled)
                    await whatsapp_service.send_text_message(message.from_number, completion)
                    return
                else:
                    lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_vaccination_setup(lang)
                    )
                    return

        user_language = user.language.value if user.language else "en"

        if message.message_type == "text" and message.text_content:
            text_lower = message.text_content.lower().strip()

            if text_lower in ["menu", "मेनू", "services", "सेवाएं", "help", "मदद", "options", "विकल्प", "0"]:
                name = user.name or "User"
                # Save context for menu flow
                await cache_service.set(f"onboarding_stage:{message.from_number}", "service_selection", 600)
                await cache_service.set(f"onboarding_lang:{message.from_number}", user_language, 600)
                await cache_service.set(f"onboarding_name:{message.from_number}", name, 600)

                # Send consolidated menu with interactive buttons and embedded help
                try:
                    # Get the menu text once
                    menu_text = jeevo_onboarding.get_service_selection(user_language, name)
                    
                    # Map to interactive button IDs: btn_0=option 1, btn_1=option 2, btn_2=option 3
                    # Build buttons for most common rural health use cases
                    menu_buttons_map = {
                        "en": ["💊 Health Problem", "💉 Vaccination", "🏥 Hospital"],
                        "hi": ["💊 स्वास्थ्य समस्या", "💉 टीकाकरण", "🏥 अस्पताल"],
                        "mr": ["💊 आरोग्य समस्या", "💉 लसीकरण", "🏥 रुग्णालय"],
                        "gu": ["💊 આરોગ્ય સમસ્યા", "💉 રસીકરણ", "🏥 હોસ્પિટલ"],
                        "bn": ["💊 স্বাস্থ্য সমস্যা", "💉 টিকা", "🏥 হাসপাতাল"],
                        "ta": ["💊 சுகாதार சிக்கல்", "💉 தடுப்பூசி", "🏥 மருத்துவமனை"],
                        "te": ["💊 ఆరోగ్య సమస్య", "💉 టీకా", "🏥 ఆసుపత్రి"],
                        "kn": ["💊 ಆರೋಗ್ಯ ಸಮಸ್ಯೆ", "💉 ಲಸಿಕ", "🏥 ಆಸ್ಪತ್ರೆ"],
                        "ml": ["💊 ആരോഗ്യ പ്രശ്നം", "💉 വാക്സിൻ", "🏥 ആശുപത്രി"],
                        "pa": ["💊 ਸਿਹਤ ਸਮੱਸਿਆ", "💉 ਵੈਕਸੀਨ", "🏥 ਹਸਪਤਾਲ"]
                    }
                    
                    # Map to interactive button IDs to match onboarding menu indices:
                    # btn_0 -> "1" (Health Problem), btn_2 -> "3" (Vaccination), btn_3 -> "4" (Hospital)
                    # Building button objects with consistent IDs across all languages
                    buttons = [
                        {"title": menu_buttons_map.get(user_language, menu_buttons_map["en"])[0], "id": "btn_0"},
                        {"title": menu_buttons_map.get(user_language, menu_buttons_map["en"])[1], "id": "btn_2"},
                        {"title": menu_buttons_map.get(user_language, menu_buttons_map["en"])[2], "id": "btn_3"}
                    ]
                    
                    # Send as interactive message with buttons
                    await whatsapp_service.send_message_with_suggestions(
                        to_number=message.from_number,
                        text=menu_text,
                        suggestions=buttons
                    )
                except Exception as e:
                    logger.warning(f"Interactive menu failed, falling back to text: {e}")
                    # Fallback: send plain text menu if interactive fails
                    menu_text = jeevo_onboarding.get_service_selection(user_language, name)
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=menu_text
                    )
                return

            if text_lower in ["language", "lang", "भाषा", "change language", "भाषा बदलें"]:
                await cache_service.set(f"onboarding_stage:{message.from_number}", "language_selection", 600)
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=jeevo_onboarding.welcome_message()
                )
                return

            if text_lower in ["heatmap", "हीटमैप", "risk", "जोखिम", "map", "नक्शा", "health risk"]:
                if user.city:
                    heatmap_data = await HeatmapUpdateService.get_city_heatmap(db, user.city)
                    if heatmap_data.get("risk_level") != "unknown":
                        heatmap_msg = RiskAggregationService.format_heatmap_display(
                            {"risk_level": heatmap_data.get("risk_level"), "score": 5.0, "components": {}},
                            user.city,
                            user_language
                        )
                        await whatsapp_service.send_text_message(
                            message.from_number, heatmap_msg
                        )
                        logger.info(f"[HEATMAP] Sent heatmap for {user.city} to {message.from_number}")
                        return
                
                await whatsapp_service.send_text_message(
                    message.from_number,
                    "📍 Please update your location first to view local health risk map."
                )
                return

            if text_lower in ["briefing", "brief", "सारांश", "daily", "दैनिक"]:
                if user.city:
                    briefing = await RiskAlertService.send_periodic_health_briefing(
                        db, user.city, user_language
                    )
                    await whatsapp_service.send_text_message(
                        message.from_number, briefing
                    )
                    logger.info(f"[BRIEFING] Sent health briefing to {message.from_number}")
                    return
                
                await whatsapp_service.send_text_message(
                    message.from_number,
                    "📍 Please update your location first to receive health briefing."
                )
                return

            if text_lower in ["vaccine", "vaccines", "vaccination", "टीकाकरण", "टीके", "immunization", "వ్యాధిబాధ్యతా", "टीका"]:
                # Get family member info from database
                user_family = await FamilyMemberRepository.get_family_members(db, user.phone_number)
                
                if not user_family:
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        "👨‍👩‍👧 No family members found. Please add family members first to track vaccinations."
                    )
                    return

                # Get vaccine status for family
                vaccine_status = await VaccineReminderService.send_family_vaccine_status(
                    family_id=user.phone_number,
                    user_phone=message.from_number,
                    user_language=user_language,
                    location=user.city,
                    session=db
                )
                
                await whatsapp_service.send_text_message(
                    message.from_number, vaccine_status
                )
                
                # If user has location, also provide nearest Aanganwadi center
                if user.city:
                    anganwadi_data = await AnganwadiFinderService.find_nearest_anganwadi(user.city)
                    if anganwadi_data.get("found"):
                        anganwadi_msg = AnganwadiFinderService.format_anganwadi_message(anganwadi_data, user_language)
                        await whatsapp_service.send_text_message(
                            message.from_number, anganwadi_msg
                        )
                        logger.info(f"[VACCINE] Sent vaccine status and Aanganwadi info to {message.from_number}")
                    else:
                        logger.warning(f"[VACCINE] Aanganwadi data not available for {user.city}")
                else:
                    logger.info(f"[VACCINE] Sent vaccine status (no location) to {message.from_number}")
                
                return

            if text_lower in ["hi", "hello", "start", "namaste", "hey", "नमस्ते", "வணக்கம்", "నమస్కారం"] or is_new:

                welcome_msg = language_manager.get_system_message("welcome", user_language)

                menu_hint = "\n\n💡 Type *MENU* anytime for services" if user_language == "en" else "\n\n💡 सेवाओं के लिए *MENU* टाइप करें"
                welcome_msg += menu_hint

                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=welcome_msg
                )

                await ConversationRepository.create_conversation(
                    db,
                    user_id=user.id,
                    message_id=message.message_id,
                    message_type=message.message_type,
                    user_message=message.text_content,
                    bot_response=welcome_msg,
                    media_id=message.media_id,
                    response_time_ms=int((time.time() - start_time) * 1000)
                )

                logger.info(f"[RESPONSE] Sent welcome message to {message.from_number}")
                return

        content = message.text_content
        caption = ""

        if message.media_id:
            try:

                media_path = await whatsapp_service.download_media(message.media_id, message.message_type)
                content = media_path

                if message.message_type == "image" and message.text_content:
                    caption = message.text_content

                logger.info(f"[MEDIA] Downloaded {message.message_type} to {media_path}")
            except Exception as e:
                logger.error(f"[MEDIA] Failed to download media: {e}")
                error_msg = language_manager.get_system_message("error", user_language)
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=error_msg
                )
                return
        # Fallback: if user replies with a single-digit number (or small option number)
        # treat it as a menu selection even if onboarding_stage cache expired.
        if message.message_type == "text" and message.text_content:
            candidate = message.text_content.strip()
            
            # Handle any numeric menu selection (0 for menu, 1-10 for language/service)
            if candidate.isdigit() and candidate in {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}:
                lang = user_language
                name = user.name or await cache_service.get(f"onboarding_name:{message.from_number}") or "User"
                
                # Handle "0" as menu/services trigger
                if candidate == "0":
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "service_selection", 600)
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=jeevo_onboarding.get_service_selection(lang, name)
                    )
                    return
                
                # Try to interpret as a language selection (1-10)
                lang_code = jeevo_onboarding.get_language_from_number(candidate)
                if lang_code:
                    # Valid language selection
                    await UserRepository.update_user(db, message.from_number, language=lang_code)
                    await cache_service.set(f"onboarding_lang:{message.from_number}", lang_code, 600)
                    
                    # Check if user is in language_selection stage
                    onboarding_stage = await cache_service.get(f"onboarding_stage:{message.from_number}")
                    if onboarding_stage == "language_selection":
                        # User is actively selecting language during onboarding
                        await cache_service.set(f"onboarding_stage:{message.from_number}", "name_collection", 600)
                        await whatsapp_service.send_text_message(
                            to_number=message.from_number,
                            text=jeevo_onboarding.get_name_request(lang_code)
                        )
                        return
                    else:
                        # User is just changing language mid-conversation
                        lang_change_messages = {
                            "en": "✅ Language changed",
                            "hi": "✅ भाषा बदल दी गई",
                            "mr": "✅ भाषा बदलली आहे",
                            "gu": "✅ ભાષા બદલાઈ ગઈ છે",
                            "bn": "✅ ভাষা পরিবর্তিত হয়েছে",
                            "ta": "✅ மொழி மாற்றப்பட்டது",
                            "te": "✅ భాష మార్చబడింది",
                            "kn": "✅ ಭಾಷೆ ಬದಲಾಗಿದೆ",
                            "ml": "✅ ഭാഷ മാറ്റി",
                            "pa": "✅ ਭਾਸ਼ਾ ਬਦਲ ਦਿੱਤੀ ਗਈ"
                        }
                        await whatsapp_service.send_text_message(
                            message.from_number,
                            lang_change_messages.get(lang_code, lang_change_messages["en"])
                        )
                        return
                
                # If not a language selection, try service selection (1-6)
                service_num = candidate
                if service_num == "1":
                    await complete_onboarding(message.from_number, db)
                    health_prompts = {
                        "en": "Describe your health problem",
                        "hi": "अपनी समस्या विस्तार से बताएं",
                        "mr": "तुमची आरोग्य समस्या सांगा",
                        "gu": "તમારી આરોગ્ય સમસ્યા જણાવો",
                        "bn": "আপনার স্বাস্থ্য समस्या বর্ণনা করুন",
                        "ta": "உங்கள் சுகாதார சிக்கலை விவரிக்கவும்",
                        "te": "మీ ఆరోగ్య సమస్యను వివరించండి",
                        "kn": "ನಿಮ್ಮ ఆరోగ్య ಸಮಸ್ಯೆಯನ್ನು ವಿವರಿಸಿ",
                        "ml": "നിങ്ങളുടെ ఆరోగ్య പ്രശ്നം വിവരിക്കുക",
                        "pa": "ਆਪਣੀ ਸਿਹਤ ਸਮੱਸਿਆ ਬਾਰੇ ਦੱਸો"
                    }
                    msg = health_prompts.get(lang, health_prompts["en"])
                    await whatsapp_service.send_text_message(message.from_number, msg)
                    return

                if service_num == "2":
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "adding_family", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_family_member_request(lang)
                    )
                    return

                if service_num == "3":
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "vaccination_setup", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_vaccination_setup(lang)
                    )
                    return

                if service_num == "4":
                    user_data = await UserRepository.get_by_phone_number(db, message.from_number)
                    location = {"city": user_data.city, "state": user_data.state}
                    hospitals = await HospitalFinderService.find_hospitals(location)
                    response = HospitalFinderService.format_hospitals(hospitals, lang)

                    await complete_onboarding(message.from_number, db)
                    await whatsapp_service.send_text_message(message.from_number, response)

                    services_enabled = ["🏥 Hospital Finder"]
                    completion = jeevo_onboarding.get_completion_message(lang, name, services_enabled)
                    await whatsapp_service.send_text_message(message.from_number, completion)
                    return

                if service_num == "5":
                    user_data = await UserRepository.get_by_phone_number(db, message.from_number)
                    location = {"city": user_data.city, "state": user_data.state}
                    alerts = await EnvironmentalAlertService.get_alerts(location)
                    response = EnvironmentalAlertService.format_alerts(alerts, lang)

                    await complete_onboarding(message.from_number, db)
                    await whatsapp_service.send_text_message(message.from_number, response)

                    services_enabled = ["🌡️ Environmental Alerts"]
                    completion = jeevo_onboarding.get_completion_message(lang, name, services_enabled)
                    await whatsapp_service.send_text_message(message.from_number, completion)
                    return

                if service_num == "6":
                    await complete_onboarding(message.from_number, db)
                    msg = "दवा का नाम बताएं" if lang == "hi" else "Tell me medicine name"
                    await whatsapp_service.send_text_message(message.from_number, msg)
                    return

                if service_num == "7":
                    # Profile update option
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "profile_update_selection", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_profile_update_menu(lang)
                    )
                    return

        logger.info(f"[ROUTER] Processing {message.message_type} message in {user_language}")

        user_location = {
            "city": user.city,
            "state": user.state,
            "latitude": user.latitude,
            "longitude": user.longitude
        }

        if not user.city or not user.state:
            location_msg = {
                "en": "⚠️ Please update your location first for better assistance. Use command: MENU → Location",
                "hi": "⚠️ बेहतर सहायता के लिए कृपया अपना स्थान अपडेट करें। कमांड उपयोग करें: MENU → Location"
            }
            await whatsapp_service.send_text_message(
                to_number=message.from_number,
                text=location_msg.get(user_language, location_msg["en"])
            )
            return

        response = await multimodal_router.route_message(
            message_type=message.message_type,
            content=content,
            caption=caption,
            language=user_language,
            user_location=user_location
        )

        # ==================== MEDICAL VALIDATION ====================
        logger.info(f"[VALIDATION] Starting validation for message: {message.message_id}")
        
        # Estimate confidence based on response type and content
        confidence_score = 0.7 if response.get("type") != "error" else 0.2
        
        validation_result = MedicalValidationService.validate_response(
            user_query=message.text_content or (caption if caption else ""),
            bot_response=response.get("content", ""),
            confidence_score=confidence_score
        )
        
        logger.info(
            f"[VALIDATION] Result - Risk: {validation_result.risk_level}, "
            f"Escalation: {validation_result.requires_escalation}, "
            f"Confidence: {validation_result.confidence_score}"
        )
        
        # Save validation record
        validation_record = await ResponseValidationRepository.create_validation(
            db,
            response_text=response.get("content", ""),
            user_id=user.id,
            message_id=message.message_id,
            user_query=message.text_content or (caption if caption else ""),
            confidence_score=validation_result.confidence_score,
            risk_level=validation_result.risk_level,
            high_risk_keywords_detected=validation_result.high_risk_keywords_detected,
            emergency_keywords_detected=validation_result.emergency_keywords_detected,
            requires_escalation=validation_result.requires_escalation,
            escalation_reason=validation_result.validation_message if validation_result.requires_escalation else None,
            approved_for_sending=not validation_result.requires_escalation
        )
        
        # Get disclaimer if needed
        disclaimer_shown = False
        disclaimer_text = ""
        
        if validation_result.risk_level != "low":
            logger.info(f"[DISCLAIMER] Getting disclaimer for risk level: {validation_result.risk_level}")
            
            disclaimer = await DisclaimerService.get_disclaimer_for_risk_level(
                db,
                risk_level=validation_result.risk_level,
                language=user_language
            )
            
            if disclaimer:
                # Track disclaimer shown
                await DisclaimerService.track_disclaimer_shown(
                    db,
                    user_id=user.id,
                    disclaimer_id=disclaimer.id,
                    context={
                        "risk_level": validation_result.risk_level,
                        "keywords": validation_result.high_risk_keywords_detected
                    },
                    message_id=message.message_id
                )
                
                disclaimer_text = f"\n\n{disclaimer.content}"
                disclaimer_shown = True
                logger.info(f"[DISCLAIMER] Disclaimer shown to user {user.id}")
        
        # Prepare final response with disclaimer
        final_response_content = response.get("content", "") + disclaimer_text
        
        # ==================== ESCALATION ====================
        escalation_id = None
        is_escalated = False
        escalation_reason = None
        
        if validation_result.requires_escalation:
            logger.info(f"[ESCALATION] Escalating case - Risk: {validation_result.risk_level}")
            
            escalated_case = await EscalationService.escalate_case(
                db=db,
                user_id=user.id,
                original_query=message.text_content or (caption if caption else ""),
                bot_response=response.get("content", ""),
                severity=validation_result.risk_level,
                reason=validation_result.validation_message,
                keywords_triggered=validation_result.high_risk_keywords_detected + 
                                 validation_result.emergency_keywords_detected,
                validation_id=validation_record.id
            )
            
            if escalated_case:
                escalation_id = escalated_case.id
                is_escalated = True
                escalation_reason = escalated_case.escalation_reason
                logger.info(
                    f"[ESCALATION] Case created: {escalated_case.id}, "
                    f"Status: {escalated_case.status}"
                )
                
                # Notify expert if assigned
                if escalated_case.assigned_expert_id:
                    expert_message = (
                        f"🚨 New escalated case assigned to you:\n"
                        f"Case ID: {escalated_case.id}\n"
                        f"Severity: {escalated_case.severity}\n"
                        f"Reason: {escalated_case.escalation_reason}\n"
                        f"Patient: {user.phone_number}"
                    )
                    try:
                        from app.database.repositories import ExpertRepository
                        expert = await ExpertRepository.get_expert(db, escalated_case.assigned_expert_id)
                        if expert:
                            await whatsapp_service.send_text_message(
                                to_number=expert.phone_number,
                                text=expert_message
                            )
                            logger.info(f"[ESCALATION] Expert notified")
                    except Exception as e:
                        logger.warning(f"[ESCALATION] Could not notify expert: {e}")
        
        # Update response object with final content
        response["content"] = final_response_content

        # For audio inputs, use STT-detected language (if available) for responses
        # IMPORTANT: Always respond in the user's preferred language
        response_language = user_language

        # Auto-generate audio for medical responses only when the incoming message was audio
        # and user has voice enabled. For audio inputs we will send BOTH text and audio.
        logger.info(f"[AUTO-VOICE CHECK] type={response.get('type')} voice_enabled={user.voice_enabled} msg_type={message.message_type}")
        
        if response.get("type") == "text" and user.voice_enabled and message.message_type == "audio":
            detected_symptom = response.get("detected_symptom")
            is_medical_related = detected_symptom or (message.text_content and any(
                keyword in message.text_content.lower() 
                for keyword in ["fever", "pain", "disease", "medicine", "doctor", "hospital", 
                              "बीमारी", "दर्द", "दवा", "डॉक्टर", "अस्पताल", "बुखार"]
            ))
            
            logger.info(f"[AUTO-VOICE CHECK] is_medical_related={is_medical_related} symptom={detected_symptom}")

            if is_medical_related:
                try:
                    logger.info(f"[AUTO-VOICE] Generating audio for medical response in {response_language} (audio input)")
                    from app.services.tts_fallback_service import tts_fallback_service

                    audio_bytes, provider = await tts_fallback_service.text_to_speech_with_fallback(
                        text=response["content"],
                        language=response_language,
                        gender="female"
                    )

                    if audio_bytes:
                        output_path = f"temp/auto_voice_{os.urandom(8).hex()}.ogg"
                        os.makedirs("temp", exist_ok=True)
                        with open(output_path, "wb") as f:
                            f.write(audio_bytes)

                        # Keep response type as text so we send the textual reply first,
                        # but attach an audio_path so we can send audio afterwards.
                        response["audio_path"] = output_path
                        response["audio_provider"] = provider
                        logger.info(f"[AUTO-VOICE] Generated audio via {provider}")
                    else:
                        logger.warning("[AUTO-VOICE] No audio generated, falling back to text")

                except Exception as e:
                    logger.warning(f"[AUTO-VOICE] Failed to auto-generate audio: {e}, using text fallback")

        if response["type"] == "text":

            await whatsapp_service.send_text_message(
                to_number=message.from_number,
                text=response["content"]
            )

            bot_response = response["content"]

            # If we generated an audio_path for an audio input, send audio after sending text
            if response.get("audio_path") and message.message_type == "audio":
                try:
                    logger.info(f"[VOICE] Sending audio message to {message.from_number} (audio input)")
                    await whatsapp_service.send_audio_message(
                        to_number=message.from_number,
                        audio_path=response["audio_path"]
                    )
                    bot_response = f"[Voice Response] {response['content']}"
                    logger.info(f"[VOICE] Audio message sent successfully")

                    # Clean up temp file after successful send
                    try:
                        await asyncio.sleep(0.5)
                        if os.path.exists(response["audio_path"]):
                            os.remove(response["audio_path"])
                            logger.debug(f"[VOICE] Cleaned up temp file: {response['audio_path']}")
                    except Exception as cleanup_error:
                        logger.warning(f"[VOICE] Failed to clean up temp file: {cleanup_error}")

                except Exception as e:
                    logger.error(f"[VOICE] Failed to send voice message: {e}", exc_info=True)
                    # Fallback to text if voice fails (text already sent)
                    bot_response = f"[Voice Failed→Text] {response['content']}"

        elif response["type"] == "voice":

            # Only send outgoing audio if the incoming message was audio. Otherwise
            # fall back to sending text to avoid unsolicited audio messages.
            if message.message_type != "audio":
                logger.info("[VOICE] Incoming message not audio; skipping outgoing audio and sending text instead")
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=response.get("content")
                )
                bot_response = response.get("content")
            elif response.get("audio_path"):
                try:
                    # Always send the textual content first so user has a readable copy
                    # and for accessibility / record-keeping, then send the audio.
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=response.get("content")
                    )
                    bot_response = response.get("content")

                    logger.info(f"[VOICE] Sending audio message to {message.from_number}")
                    await whatsapp_service.send_audio_message(
                        to_number=message.from_number,
                        audio_path=response["audio_path"]
                    )

                    # Mark the logged response to indicate an audio was sent too
                    bot_response = f"[Voice Response] {response['content']}"
                    logger.info(f"[VOICE] Audio message sent successfully")

                    # Clean up temp file after successful send (with delay to ensure upload completes)
                    try:
                        await asyncio.sleep(0.5)  # Give upload time to finish
                        if os.path.exists(response["audio_path"]):
                            os.remove(response["audio_path"])
                            logger.debug(f"[VOICE] Cleaned up temp file: {response['audio_path']}")
                    except Exception as cleanup_error:
                        logger.warning(f"[VOICE] Failed to clean up temp file: {cleanup_error}")

                except Exception as e:
                    logger.error(f"[VOICE] Failed to send voice message: {e}", exc_info=True)
                    # Fallback to text if voice fails
                    fallback_text = f"Audio response unavailable. {response['content']}"
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=fallback_text
                    )
                    bot_response = f"[Voice Failed→Text] {response['content']}"
            else:
                logger.warning(f"[VOICE] No audio_path in response, falling back to text")
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=response["content"]
                )
                bot_response = response["content"]

        else:

            error_msg = language_manager.get_system_message("error", user_language)
            await whatsapp_service.send_text_message(
                to_number=message.from_number,
                text=error_msg
            )
            bot_response = error_msg

        response_time_ms = int((time.time() - start_time) * 1000)

        try:
            await ConversationRepository.create_conversation(
                db,
                user_id=user.id,
                message_id=message.message_id,
                message_type=message.message_type,
                user_message=message.text_content or f"[{message.message_type}]",
                bot_response=bot_response,
                media_id=message.media_id,
                response_time_ms=response_time_ms,
                validation_id=validation_record.id,
                validation_status=validation_result.risk_level,
                confidence_score=validation_result.confidence_score,
                requires_escalation=validation_result.requires_escalation,
                escalation_id=escalation_id,
                high_risk_keywords=validation_result.high_risk_keywords_detected + validation_result.emergency_keywords_detected,
                medical_disclaimer_shown=disclaimer_shown
            )
        except Exception as e:
            logger.error(f"[DB] Failed to log conversation: {e}")

        new_context = {
            "last_message_type": message.message_type,
            "last_message_time": message.timestamp,
            "conversation_state": "active",
            "language": user_language
        }
        await cache_service.set_user_context(message.from_number, new_context)

        logger.info(f"[RESPONSE] Sent to {message.from_number} (took {response_time_ms}ms)")

    except Exception as e:
        logger.error(f"[PROCESS] Error processing message: {e}", exc_info=True)

        try:
            error_messages = {
                "en": "⚠️ Sorry, I encountered an error. Please try again in a moment.",
                "hi": "⚠️ क्षमा करें, मुझे एक त्रुटि आई। कृपया एक क्षण में पुनः प्रयास करें।",
                "ta": "⚠️ மன்னிக்கவும், ஒரு பிழை ஏற்பட்டது. தயவுசெய்து சிறிது நேரம் கழித்து மீண்டும் முயற்சிக்கவும்।",
                "te": "⚠️ క్షమించండి, నాకు లోపం ఎదురైంది. దయచేసి కొద్ది సేపట్లో మళ్లీ ప్రయత్నించండి।"
            }
            user_lang = user.language.value if user and user.language else "en"
            error_message = error_messages.get(user_lang, error_messages["en"])
            await whatsapp_service.send_text_message(
                to_number=message.from_number,
                text=error_message
            )
        except Exception as send_error:
            logger.error(f"[PROCESS] Could not send error message: {send_error}")