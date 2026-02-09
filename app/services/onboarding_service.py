
import logging
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import UserRepository
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)

class OnboardingFlow:

    LANGUAGES = {
        "en": "English",
        "hi": "Hindi (हिंदी)",
        "ta": "Tamil (தமிழ்)",
        "te": "Telugu (తెలుగు)",
        "bn": "Bengali (বাংলা)",
        "mr": "Marathi (मराठी)",
        "gu": "Gujarati (ગુજરાતી)",
        "kn": "Kannada (ಕನ್ನಡ)",
        "ml": "Malayalam (മലയാളം)",
        "pa": "Punjabi (ਪੰਜਾਬੀ)"
    }

    HELP_TYPES = {
        "symptoms": "💊 Health Symptoms & Medical Advice",
        "hospitals": "🏥 Find Nearby Hospitals & Clinics",
        "vaccines": "💉 Vaccination Tracking & Reminders",
        "environment": "🌡️ Environmental Health Alerts (Weather, AQI)",
        "medicine": "💊 Medicine Information & Dosage",
        "emergency": "🚨 Emergency First Aid",
        "nutrition": "🥗 Nutrition & Diet Advice",
        "mental": "🧘 Mental Health Support",
        "general": "💬 General Health Questions"
    }

    @staticmethod
    async def get_onboarding_stage(phone_number: str) -> str:

        stage = await cache_service.get(f"onboarding:{phone_number}")
        return stage or "new"

    @staticmethod
    async def set_onboarding_stage(phone_number: str, stage: str, ttl: int = 600):

        await cache_service.set(f"onboarding:{phone_number}", stage, ttl)

    @staticmethod
    async def set_onboarding_data(phone_number: str, key: str, value: str, ttl: int = 600):

        await cache_service.set(f"onboarding_data:{phone_number}:{key}", value, ttl)

    @staticmethod
    async def get_onboarding_data(phone_number: str, key: str) -> Optional[str]:

        return await cache_service.get(f"onboarding_data:{phone_number}:{key}")

    @staticmethod
    def get_language_selection_message() -> str:

        msg = "🌍 *Welcome to Jeevo* - Your Health Companion!\n\n"
        msg += "Please select your preferred language / अपनी भाषा चुनें:\n\n"

        for code, name in OnboardingFlow.LANGUAGES.items():
            msg += f"Reply *{code.upper()}* for {name}\n"

        msg += "\n💡 Example: Reply *HI* for Hindi"
        return msg

    @staticmethod
    def get_location_request_message(language: str = "en") -> str:

        messages = {
            "en": "📍 *Share Your Location*\n\n"
                  "To provide personalized health alerts and find nearby hospitals, please share your location.\n\n"
                  "You can:\n"
                  "1️⃣ Send live location (tap 📎 → Location)\n"
                  "2️⃣ Type: City, State\n\n"
                  "Example: `Bhopal, Madhya Pradesh`",
            "hi": "📍 *अपना स्थान साझा करें*\n\n"
                  "व्यक्तिगत स्वास्थ्य अलर्ट और नजदीकी अस्पतालों को खोजने के लिए, कृपया अपना स्थान साझा करें।\n\n"
                  "आप कर सकते हैं:\n"
                  "1️⃣ लाइव लोकेशन भेजें (📎 → Location)\n"
                  "2️⃣ टाइप करें: शहर, राज्य\n\n"
                  "उदाहरण: `भोपाल, मध्य प्रदेश`"
        }
        return messages.get(language, messages["en"])

    @staticmethod
    def get_help_selection_message(language: str = "en") -> str:

        messages = {
            "en": "🎯 *What can I help you with today?*\n\nReply with the number:\n\n",
            "hi": "🎯 *आज मैं आपकी किस तरह मदद कर सकता हूं?*\n\nनंबर के साथ जवाब दें:\n\n"
        }

        msg = messages.get(language, messages["en"])

        for idx, (key, value) in enumerate(OnboardingFlow.HELP_TYPES.items(), 1):
            msg += f"{idx}. {value}\n"

        msg += "\n💡 Example: Reply *1* for Health Symptoms"
        return msg

    @staticmethod
    def get_family_collection_message(language: str = "en") -> str:

        messages = {
            "en": "👨‍👩‍👧‍👦 *Would you like to track health for your family members?*\n\n"
                  "This helps with:\n"
                  "• Vaccination reminders for children\n"
                  "• Health alerts for elderly\n"
                  "• Personalized advice for each member\n\n"
                  "Reply:\n"
                  "*YES* - Add family members now\n"
                  "*NO* - Skip for now (you can add later)",
            "hi": "👨‍👩‍👧‍👦 *क्या आप अपने परिवार के सदस्यों के स्वास्थ्य को ट्रैक करना चाहते हैं?*\n\n"
                  "इससे मदद मिलती है:\n"
                  "• बच्चों के लिए टीकाकरण अनुस्मारक\n"
                  "• बुजुर्गों के लिए स्वास्थ्य चेतावनी\n"
                  "• प्रत्येक सदस्य के लिए व्यक्तिगत सलाह\n\n"
                  "जवाब दें:\n"
                  "*YES* - अभी परिवार के सदस्य जोड़ें\n"
                  "*NO* - अभी के लिए छोड़ें (बाद में जोड़ सकते हैं)"
        }
        return messages.get(language, messages["en"])

    @staticmethod
    def get_family_member_input_message(language: str = "en") -> str:

        messages = {
            "en": "👤 *Add Family Member*\n\n"
                  "Please provide details in this format:\n"
                  "`Name, Relation, Age`\n\n"
                  "Example:\n"
                  "`Rahul, Son, 2`\n"
                  "`Priya, Daughter, 5`\n\n"
                  "Reply *DONE* when finished adding members",
            "hi": "👤 *परिवार का सदस्य जोड़ें*\n\n"
                  "कृपया इस प्रारूप में विवरण दें:\n"
                  "`नाम, रिश्ता, उम्र`\n\n"
                  "उदाहरण:\n"
                  "`राहुल, बेटा, 2`\n"
                  "`प्रिया, बेटी, 5`\n\n"
                  "सदस्य जोड़ना समाप्त होने पर *DONE* उत्तर दें"
        }
        return messages.get(language, messages["en"])

    @staticmethod
    def get_completion_message(language: str = "en", user_name: str = "User") -> str:

        messages = {
            "en": f"✅ *Setup Complete!*\n\n"
                  f"Welcome {user_name}! I'm ready to help you with:\n\n"
                  "💊 Health symptoms & medical advice\n"
                  "🏥 Finding nearby hospitals\n"
                  "💉 Vaccination tracking\n"
                  "🌡️ Environmental health alerts\n"
                  "💊 Medicine information\n"
                  "🚨 Emergency first aid\n\n"
                  "Just send me your health questions anytime!\n\n"
                  "💡 Example: \"My child has fever\" or \"मेरे बच्चे को बुखार है\"",
            "hi": f"✅ *सेटअप पूर्ण!*\n\n"
                  f"स्वागत है {user_name}! मैं आपकी मदद के लिए तैयार हूं:\n\n"
                  "💊 स्वास्थ्य लक्षण और चिकित्सा सलाह\n"
                  "🏥 नजदीकी अस्पताल खोजना\n"
                  "💉 टीकाकरण ट्रैकिंग\n"
                  "🌡️ पर्यावरण स्वास्थ्य अलर्ट\n"
                  "💊 दवा की जानकारी\n"
                  "🚨 आपातकालीन प्राथमिक चिकित्सा\n\n"
                  "मुझे कभी भी अपने स्वास्थ्य प्रश्न भेजें!\n\n"
                  "💡 उदाहरण: \"मेरे बच्चे को बुखार है\""
        }
        return messages.get(language, messages["en"])

onboarding_flow = OnboardingFlow()