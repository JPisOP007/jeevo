
import logging
from typing import List, Dict
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.models import User, Reminder, ReminderType

logger = logging.getLogger(__name__)

VACCINE_SCHEDULE = {
    "birth": [
        {"name": "BCG", "age_days": 0, "description": "Tuberculosis prevention"},
        {"name": "Hepatitis B - Birth Dose", "age_days": 0},
        {"name": "OPV 0", "age_days": 0, "description": "Oral Polio Vaccine"},
    ],
    "6_weeks": [
        {"name": "DPT 1", "age_days": 42, "description": "Diphtheria, Pertussis, Tetanus"},
        {"name": "Hepatitis B 1", "age_days": 42},
        {"name": "OPV 1", "age_days": 42},
        {"name": "Hib 1", "age_days": 42, "description": "Haemophilus influenzae"},
        {"name": "Rotavirus 1", "age_days": 42},
        {"name": "PCV 1", "age_days": 42, "description": "Pneumococcal"},
    ],
    "10_weeks": [
        {"name": "DPT 2", "age_days": 70},
        {"name": "Hepatitis B 2", "age_days": 70},
        {"name": "OPV 2", "age_days": 70},
        {"name": "Hib 2", "age_days": 70},
        {"name": "Rotavirus 2", "age_days": 70},
        {"name": "PCV 2", "age_days": 70},
    ],
    "14_weeks": [
        {"name": "DPT 3", "age_days": 98},
        {"name": "Hepatitis B 3", "age_days": 98},
        {"name": "OPV 3", "age_days": 98},
        {"name": "Hib 3", "age_days": 98},
        {"name": "Rotavirus 3", "age_days": 98},
        {"name": "PCV 3", "age_days": 98},
    ],
    "9_months": [
        {"name": "Measles 1 (MR)", "age_days": 270, "description": "Measles-Rubella"},
    ],
    "12_months": [
        {"name": "PCV Booster", "age_days": 365},
    ],
    "16_18_months": [
        {"name": "Measles 2 (MR)", "age_days": 456},
        {"name": "DPT Booster 1", "age_days": 456},
        {"name": "OPV Booster", "age_days": 456},
    ],
    "5_6_years": [
        {"name": "DPT Booster 2", "age_days": 1825},
    ]
}

class VaccineService:

    @staticmethod
    async def check_pending_vaccines(db: AsyncSession, user: User) -> List[Dict]:

        reminders = []

        result = await db.execute(
            select(Reminder).where(
                Reminder.user_id == user.id,
                Reminder.reminder_type == ReminderType.IMMUNIZATION,
                Reminder.is_sent == False,
                Reminder.is_completed == False
            ).order_by(Reminder.scheduled_time)
        )

        db_reminders = result.scalars().all()

        current_date = datetime.utcnow()
        for reminder in db_reminders:
            days_until = (reminder.scheduled_time - current_date).days

            if -30 <= days_until <= 7:
                status = "DUE SOON" if days_until > 0 else "OVERDUE" if days_until < -7 else "DUE NOW"
                reminders.append({
                    "title": reminder.title,
                    "description": reminder.description,
                    "due_date": reminder.scheduled_time.strftime("%d %b %Y"),
                    "days_until": days_until,
                    "status": status
                })

        return reminders

    @staticmethod
    def format_vaccine_reminders(reminders: List[Dict], language: str = "hi") -> str:

        if not reminders:
            return ""

        message = "\\n\\n💉 *Vaccine Reminders:*\\n"

        for reminder in reminders[:3]:
            emoji = "⏰" if reminder["status"] == "DUE SOON" else "⚠️" if reminder["status"] == "OVERDUE" else "📅"
            message += f"\\n{emoji} {reminder['title']}\\n"
            message += f"   Due: {reminder['due_date']} ({reminder['status']})\\n"
            if reminder.get("description"):
                message += f"   {reminder['description']}\\n"

        return message

    @staticmethod
    def get_anganwadi_message(city: str, state: str, language: str = "hi") -> str:

        messages = {
            "hi": f"\n\n🏥 कृपया अपने नजदीकी आंगनवाड़ी केंद्र ({city}, {state}) में टीकाकरण के लिए जाएं।",
            "en": f"\n\n🏥 Please visit your local Anganwadi center ({city}, {state}) for vaccination.",
            "ta": f"\n\n🏥 தயவுசெய்து தடுப்பூசிக்கு உங்கள் உள்ளூர் அங்கன்வாடி மையத்தை ({city}, {state}) பார்வையிடவும்.",
            "te": f"\n\n🏥 దయచేసి టీకా కోసం మీ స్థానిక అంగన్ వాడీ కేంద్రాన్ని ({city}, {state}) సందర్శించండి.",
            "bn": f"\n\n🏥 অনুগ্রহ করে টিকা নেওয়ার জন্য আপনার স্থানীয় আঙ্গনওয়াড়ি কেন্দ্র ({city}, {state}) দেখুন।",
            "mr": f"\n\n🏥 कृपया लसीकरणासाठी आपल्या स ्थानीय आंगनवाड़ी केंद्र ({city}, {state}) ला भेट द्या।",
            "gu": f"\n\n🏥 કૃપા કરીને રસીકરણ માટે તમારા સ્થાનિક આંગણવાડી કેન્દ્ર ({city}, {state}) ની મુલાકાત લો.",
            "kn": f"\n\n🏥 ದಯವಿಟ್ಟು ಲಸಿಕೆಗಾಗಿ ನಿಮ್ಮ ಸ್ಥಳೀಯ ಅಂಗನವಾಡಿ ಕೇಂದ್ರವನ್ನು ({city}, {state}) ಭೇಟಿ ಮಾಡಿ.",
            "ml": f"\n\n🏥 ദയവായി വാക്സിനേഷനായി നിങ്ങളുടെ പ്രാദേശിക അങ്കണവാടി കേന്ദ്രം ({city}, {state}) സന്ദർശിക്കുക.",
            "pa": f"\n\n🏥 ਕਿਰਪਾ ਕਰਕੇ ਟੀਕਾਕਰਨ ਲਈ ਆਪਣੇ ਸਥਾਨਕ ਆਂਗਨਵਾੜੀ ਕੇਂਦਰ ({city}, {state}) ਦਾ ਦੌਰਾ ਕਰੋ।"
        }

        return messages.get(language, messages["hi"])

vaccine_service = VaccineService()