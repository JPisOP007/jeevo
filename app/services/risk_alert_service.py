import logging
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.database.repositories import UserRepository, RiskLevelRepository
from app.services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)


class RiskAlertService:
    """
    Monitors risk level changes and sends alerts to users in affected areas.
    Triggers when: green→yellow, yellow→red, or red→any.
    """

    RISK_PRIORITY = {"red": 3, "yellow": 2, "green": 1}

    @staticmethod
    async def check_and_alert_risk_changes(
        db: AsyncSession, city: str, new_risk_level: str
    ) -> Dict:
        """
        Check if risk level changed and send alerts to affected users.
        Returns: {alerts_sent, users_notified, errors}
        """
        logger.info(f"🔔 Checking risk changes for {city}...")

        old_risk_level = await RiskAlertService._get_previous_risk_level(
            db, city
        )

        if old_risk_level == new_risk_level:
            logger.info(f"ℹ️ No risk change for {city}: {new_risk_level}")
            return {
                "city": city,
                "risk_changed": False,
                "old_level": old_risk_level,
                "new_level": new_risk_level,
                "alerts_sent": 0
            }

        is_escalation = (
            RiskAlertService.RISK_PRIORITY.get(new_risk_level, 0) >
            RiskAlertService.RISK_PRIORITY.get(old_risk_level, 0)
        )

        logger.warning(
            f"⚠️ Risk escalation in {city}: {old_risk_level} → {new_risk_level}"
        )

        users_to_alert = await RiskAlertService._get_users_in_area(
            db, city
        )

        alerts_sent = 0
        errors = []

        for user in users_to_alert:
            try:
                alert_msg = RiskAlertService._generate_alert_message(
                    city, old_risk_level, new_risk_level, is_escalation
                )

                await whatsapp_service.send_text_message(
                    user.phone_number, alert_msg
                )
                alerts_sent += 1
                logger.info(f"📱 Alert sent to {user.phone_number}")

            except Exception as e:
                logger.error(f"Failed to send alert to {user.phone_number}: {e}")
                errors.append(str(e))

        logger.info(
            f"✅ Risk alerts complete: {alerts_sent} sent, {len(errors)} failed"
        )

        return {
            "city": city,
            "risk_changed": True,
            "old_level": old_risk_level,
            "new_level": new_risk_level,
            "is_escalation": is_escalation,
            "alerts_sent": alerts_sent,
            "users_notified": len(users_to_alert),
            "errors": errors
        }

    @staticmethod
    async def _get_previous_risk_level(
        db: AsyncSession, city: str
    ) -> str:
        """Get previous risk level from database"""
        try:
            risk_record = await RiskLevelRepository.get_risk_level(
                db, city.lower()
            )
            if risk_record:
                return risk_record.risk_level
        except Exception as e:
            logger.debug(f"Could not fetch previous risk level: {e}")

        return "unknown"

    @staticmethod
    async def _get_users_in_area(
        db: AsyncSession, city: str
    ) -> List[User]:
        """Get all users whose location matches the city"""
        try:
            result = await db.execute(
                select(User).where(
                    (User.city.ilike(f"%{city}%")) & 
                    (User.is_onboarded == True)
                ).limit(100)
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error fetching users in {city}: {e}")
            return []

    @staticmethod
    def _generate_alert_message(
        city: str,
        old_level: str,
        new_level: str,
        is_escalation: bool
    ) -> str:
        """Generate alert message for users"""

        if is_escalation:
            subject = f"⚠️ *HEALTH ALERT - {city.upper()}*"
        else:
            subject = f"✅ *Health Update - {city.upper()}*"

        level_emoji = {
            "red": "🔴",
            "yellow": "🟡",
            "green": "🟢",
            "unknown": "⚪"
        }

        msg = f"{subject}\n\n"
        msg += f"Risk Level Changed:\n"
        msg += f"{level_emoji.get(old_level, '⚪')} {old_level.upper()} "
        msg += f"→ {level_emoji.get(new_level, '⚪')} {new_level.upper()}\n\n"

        if new_level == "red":
            msg += (
                "🚨 *SEVERE CONDITIONS DETECTED*\n\n"
                "⚠️ Recommended Actions:\n"
                "• 🏠 Limit outdoor activities\n"
                "• 😷 Wear N95 masks if going out\n"
                "• 👨‍👩‍👧 Keep children and elderly indoors\n"
                "• 💧 Stay hydrated\n"
                "• 📞 Emergency contacts ready\n\n"
                "Monitor local health advisories.\n"
            )

        elif new_level == "yellow":
            msg += (
                "🟡 *CAUTION ADVISED*\n\n"
                "⚠️ Take Precautions:\n"
                "• 🧴 Maintain hygiene protocols\n"
                "• 😷 Use masks in crowded areas\n"
                "• 💨 Limit strenuous outdoor activities\n"
                "• 👶 Extra care for vulnerable groups\n"
            )

        else:
            msg += (
                "✅ *Risk Level Improved*\n\n"
                "Good news! You can resume normal outdoor activities.\n"
                "Continue monitoring local updates.\n"
            )

        msg += f"\n📍 Check /heatmap for detailed risk breakdown"

        return msg

    @staticmethod
    async def send_custom_alert(
        db: AsyncSession,
        city: str,
        alert_title: str,
        alert_message: str,
        risk_level: str
    ) -> Dict:
        """Send custom alert to all users in area"""

        users = await RiskAlertService._get_users_in_area(db, city)
        alerts_sent = 0

        for user in users:
            try:
                msg = f"⚠️ *{alert_title}*\n\n{alert_message}"
                await whatsapp_service.send_text_message(user.phone_number, msg)
                alerts_sent += 1
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")

        return {
            "alert_sent": True,
            "city": city,
            "users_notified": alerts_sent,
            "timestamp": datetime.utcnow().isoformat()
        }

    @staticmethod
    async def send_periodic_health_briefing(
        db: AsyncSession, user_city: str, user_lang: str = "en"
    ) -> str:
        """
        Send daily/weekly health briefing to users in their language.
        Format for WhatsApp display.
        """

        translations = {
            "hi": {
                "title": "📊 *दैनिक स्वास्थ्य ब्रीफिंग*",
                "risk_level": "जोखिम स्तर",
                "active_diseases": "⚕️ *सक्रिय रोग:*",
                "weather_alerts": "🌦️ *मौसम सतर्कता:*",
                "last_updated": "अंतिम अपडेट",
                "detailed": "विस्तृत विश्लेषण के लिए *HEATMAP* के साथ उत्तर दें",
                "no_data": "📍 आपके स्थान के लिए अभी स्वास्थ्य डेटा उपलब्ध नहीं है।"
            },
            "en": {
                "title": "📊 *Daily Health Briefing*",
                "risk_level": "Risk Level",
                "active_diseases": "⚕️ *Active Diseases:*",
                "weather_alerts": "🌦️ *Weather Alerts:*",
                "last_updated": "Last Updated",
                "detailed": "Reply with /heatmap for detailed analysis",
                "no_data": "📍 No health data available for your location yet."
            },
            "mr": {
                "title": "📊 *दैनिक आरोग्य ब्रीफिंग*",
                "risk_level": "जोखिम स्तर",
                "active_diseases": "⚕️ *सक्रिय रोग:*",
                "weather_alerts": "🌦️ *हवामान सतर्कता:*",
                "last_updated": "अंतिम अपडेट",
                "detailed": "*HEATMAP* सह उत्तर द्या",
                "no_data": "📍 आपल्या स्थानासाठी आरोग्य डेटा उपलब्ध नाही।"
            },
            "gu": {
                "title": "📊 *દૈનિક આરોગ્ય બ્રીફિંગ*",
                "risk_level": "જોખમ સ્તર",
                "active_diseases": "⚕️ *સક્રિય રોગ:*",
                "weather_alerts": "🌦️ *હવામાન ચેતવણીઓ:*",
                "last_updated": "છેલ્લો અપડેટ",
                "detailed": "*HEATMAP* સાથે જવાબ આપો",
                "no_data": "📍 તમારા સ્થાન માટે આરોગ્ય ડેટા ઉપલબ્ધ નથી।"
            },
            "bn": {
                "title": "📊 *দৈনিক স্বাস্থ্য ব্রীফিং*",
                "risk_level": "ঝুঁকি স্তর",
                "active_diseases": "⚕️ *সক্রিয় রোগ:*",
                "weather_alerts": "🌦️ *আবহাওয়া সতর্কতা:*",
                "last_updated": "শেষ আপডেট",
                "detailed": "বিস্তারিত বিশ্লেষণের জন্য *HEATMAP* উত্তর দিন",
                "no_data": "📍 আপনার অবস্থানের জন্য এখনও স্বাস্থ্য ডেটা উপলব্ধ নেই।"
            },
            "ta": {
                "title": "📊 *தினசரி சுகாதார ব்রீஃபிங்*",
                "risk_level": "ஆபத்து நிலை",
                "active_diseases": "⚕️ *நோயுள்ள நோய்கள்:*",
                "weather_alerts": "🌦️ *வானிலை எச்சரிக்கைகள்:*",
                "last_updated": "கடைசியாக அப்டேட்",
                "detailed": "விस்तாரமான பகுப்பாய்வுக்கு *HEATMAP* சொல்லவும்",
                "no_data": "📍 உங்கள் இடத்திற்கான சுகாதார தகவல் இன்னும் கிடைக்கவில்லை।"
            },
            "te": {
                "title": "📊 *రోజువారీ ఆరోగ్య సంక్షిప్తం*",
                "risk_level": "ఆపద్ స్థాయి",
                "active_diseases": "⚕️ *క్రియాశీల రోగాలు:*",
                "weather_alerts": "🌦️ *వాతావరణ అలర్టులు:*",
                "last_updated": "చివరకు అపడేట్ చేయబడింది",
                "detailed": "వివరణాత్మక విశ్లేషణ కోసం *HEATMAP* సమాధానం",
                "no_data": "📍 మీ ప్రదేశానికి ఇంకా ఆరోగ్య డేటా లేదు।"
            },
            "kn": {
                "title": "📊 *ದೈನಿಕ ಆರೋಗ್ಯ ಬ್ರೀಫಿಂಗ್*",
                "risk_level": "ಅಪಾಯದ ಮಟ್ಟ",
                "active_diseases": "⚕️ *ಸಕ್ರಿಯ ರೋಗಗಳು:*",
                "weather_alerts": "🌦️ *ವಾತಾವರಣ ಎಚ್ಚರಿಕೆಗಳು:*",
                "last_updated": "ಕೊನೆಯ ಅಪಡೇಟ್",
                "detailed": "ವಿವರವಾದ ವಿಶ್ಲೇಷಣೆಗಾಗಿ *HEATMAP* ಉತ್ತರ",
                "no_data": "📍 ನಿಮ್ಮ ಸ್ಥಾನಕ್ಕೆ ಇನ್ನೂ ಆರೋಗ್ಯ ಡೇಟಾ ಲಭ್ಯವಿಲ್ಲ।"
            },
            "ml": {
                "title": "📊 *ദൈനിക ആരോഗ്യ സംഗ്രഹം*",
                "risk_level": "അപകട തലം",
                "active_diseases": "⚕️ *സক്രിയ രോഗങ്ങൾ:*",
                "weather_alerts": "🌦️ *കാലാവസ്ഥ മുന്നറിപ്പ്:*",
                "last_updated": "അവസാനം আপডేট്",
                "detailed": "വിശദമായ വിശകലനത്തിനായി *HEATMAP* ഉത്തരം",
                "no_data": "📍 നിങ്ങളുടെ സ്ഥലത്തിനുള്ള ആരോഗ്യ ഡാറ്റ ഇതുവരെ ലഭ്യമല്ല।"
            },
            "pa": {
                "title": "📊 *ਰੋਜ਼ਾਨਾ ਸਿਹਤ ਸੰਖਿਪ್ਤ*",
                "risk_level": "ਜੋਖਮ ਪੱਧਰ",
                "active_diseases": "⚕️ *ਸਕ੍ਰਿਆ ਰੋਗ:*",
                "weather_alerts": "🌦️ *ਮੌਸਮ ਸਚੇਤੀ:*",
                "last_updated": "ਆਖਰੀ ਅਪਡੇਟ",
                "detailed": "ਵਿਸਤ੍ਰਿਤ ਵਿਸ਼ਲੇਸ਼ਣ ਲਈ *HEATMAP* ਜਵਾਬ",
                "no_data": "📍 ਤੁਹਾਡੇ ਸਥਾਨ ਲਈ ਅਜੇ ਸਿਹਤ ਡਾਟਾ ਉਪਲਬਧ ਨਹੀਂ।"
            }
        }

        t = translations.get(user_lang, translations["en"])

        try:
            risk_data = await RiskLevelRepository.get_risk_level(
                db, user_city.lower()
            )

            if not risk_data:
                return t["no_data"]

            risk_emoji = {
                "red": "🔴",
                "yellow": "🟡",
                "green": "🟢"
            }.get(risk_data.risk_level, "⚪")

            msg = f"{t['title']} - {user_city}\n\n"
            msg += f"{risk_emoji} {t['risk_level']}: {risk_data.risk_level.upper()}\n\n"

            if risk_data.active_diseases:
                msg += f"{t['active_diseases']}\n"
                for disease, info in risk_data.active_diseases.items():
                    msg += f"  • {disease}: {info.get('severity', 'N/A')}\n"
                msg += "\n"

            if risk_data.weather_alerts:
                msg += f"{t['weather_alerts']}\n"
                for alert in risk_data.weather_alerts[:3]:
                    msg += f"  • {alert}\n"
                msg += "\n"

            msg += (
                f"{t['last_updated']}: {risk_data.last_updated.strftime('%Y-%m-%d %H:%M')}\n\n"
                f"💡 {t['detailed']}"
            )

            return msg

        except Exception as e:
            logger.error(f"Error generating briefing: {e}")
            return "Unable to fetch health briefing."

