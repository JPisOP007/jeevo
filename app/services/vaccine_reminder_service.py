import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import select, and_
from app.database.models import FamilyMember, VaccinationRecord
from app.services.vaccine_service import VaccineService
from app.services.anganwadi_finder_service import AnganwadiFinderService
from app.services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)


class VaccineReminderService:
    """Proactive vaccine reminder service - sends alerts 2 weeks BEFORE vaccine is due"""

    # Vaccine schedule with days from birth
    VACCINE_MILESTONES = {
        "birth": {"days": 0, "vaccines": ["BCG", "Hepatitis B", "OPV 0"]},
        "6_weeks": {"days": 42, "vaccines": ["DPT 1", "Hib 1", "Rotavirus 1", "PCV 1", "IPV 1", "Hepatitis B 2"]},
        "10_weeks": {"days": 70, "vaccines": ["DPT 2", "Hib 2", "Rotavirus 2", "PCV 2", "IPV 2", "Hepatitis B 3"]},
        "14_weeks": {"days": 98, "vaccines": ["DPT 3", "Hib 3", "Rotavirus 3", "PCV 3", "IPV 3"]},
        "9_months": {"days": 270, "vaccines": ["Measles 1 (MR)"]},
        "12_months": {"days": 365, "vaccines": ["PCV Booster"]},
        "16_18_months": {"days": 500, "vaccines": ["Measles 2", "DPT Booster 1", "OPV Booster"]},
        "5_6_years": {"days": 1825, "vaccines": ["DPT Booster 2", "OPV Booster 2"]}
    }

    REMINDER_DAYS_BEFORE = 14  # Send reminder 2 weeks before deadline

    @staticmethod
    async def calculate_vaccine_schedule(dob: datetime) -> Dict[str, Dict]:
        """Calculate scheduled vaccine dates for a child based on DOB"""
        schedule = {}

        for milestone_name, milestone_info in VaccineReminderService.VACCINE_MILESTONES.items():
            scheduled_date = dob + timedelta(days=milestone_info["days"])
            schedule[milestone_name] = {
                "scheduled_date": scheduled_date,
                "vaccines": milestone_info["vaccines"],
                "status": VaccineReminderService._get_vaccine_status(scheduled_date)
            }

        return schedule

    @staticmethod
    def _get_vaccine_status(scheduled_date: datetime) -> str:
        """Determine vaccine status based on scheduled date"""
        today = datetime.now().date()
        scheduled = scheduled_date.date()
        days_until = (scheduled - today).days

        if days_until < -30:
            return "overdue"
        elif days_until < 0:
            return "slightly_overdue"
        elif days_until <= VaccineReminderService.REMINDER_DAYS_BEFORE:
            return "due_soon"
        else:
            return "upcoming"

    @staticmethod
    async def get_due_vaccines_for_family(family_id: str, session) -> List[Dict]:
        """Get all vaccines that are due or due soon for a family"""
        
        if not session:
            logger.error("Database session is required")
            return []
        
        try:
            children = await session.execute(
                select(FamilyMember).where(
                    and_(
                        FamilyMember.family_id == family_id,
                        FamilyMember.role == "child"
                    )
                )
            )
            children = children.scalars().all()

            due_vaccines = []

            for child in children:
                if not child.date_of_birth:
                    continue

                schedule = await VaccineReminderService.calculate_vaccine_schedule(child.date_of_birth)

                for milestone_name, milestone_data in schedule.items():
                    status = milestone_data["status"]
                    if status in ["due_soon", "overdue", "slightly_overdue"]:
                        completed = await session.execute(
                            select(VaccinationRecord).where(
                                and_(
                                    VaccinationRecord.family_member_id == child.id,
                                    VaccinationRecord.is_completed == True
                                )
                            )
                        )
                        completed = completed.scalars().first()

                        if not completed:
                            due_vaccines.append({
                                "child_name": child.name,
                                "child_id": str(child.id),
                                "family_id": family_id,
                                "milestone": milestone_name,
                                "scheduled_date": milestone_data["scheduled_date"],
                                "vaccines": milestone_data["vaccines"],
                                "status": status,
                                "urgency": "urgent" if status in ["overdue", "slightly_overdue"] else "reminder"
                            })

            return due_vaccines

        except Exception as e:
            logger.error(f"Error getting due vaccines: {e}")
            return []

    @staticmethod
    async def send_vaccine_reminder(
        family_id: str,
        child_name: str,
        vaccines: List[str],
        scheduled_date: datetime,
        location: str,
        user_phone: str,
        user_language: str = "en",
        session=None
    ) -> bool:
        """Send WhatsApp reminder for upcoming vaccine"""

        translations = {
            "hi": {
                "reminder_title": "💉 *टीकाकरण की याद दिलाएं*",
                "upcoming_title": "⏰ *आने वाली वैक्सीन*",
                "overdue_title": "⚠️ *तुरंत एक्शन चाहिए!*",
                "child": "बच्चा",
                "vaccines": "टीके",
                "date": "तारीख",
                "location": "स्थान",
                "days_until": "दिन बाकी",
                "days_ago": "दिन पहले",
                "message": "कृपया नजदीकी आंगनवाड़ी केंद्र पर जाएं और बच्चे का टीकाकरण करवाएं।",
                "overdue_message": "यह टीकाकरण समय सीमा पार हो गया है। कृपया तुरंत बुक करें!"
            },
            "en": {
                "reminder_title": "💉 *Vaccination Reminder*",
                "upcoming_title": "⏰ *Upcoming Vaccine*",
                "overdue_title": "⚠️ *Immediate Action Needed!*",
                "child": "Child",
                "vaccines": "Vaccines",
                "date": "Date",
                "location": "Location",
                "days_until": "Days remaining",
                "days_ago": "days ago",
                "message": "Please visit the nearest Anganwadi center to get the vaccine done.",
                "overdue_message": "This vaccination has passed its deadline. Please book immediately!"
            },
            "mr": {
                "reminder_title": "💉 *लसीकरणाची याद दिला*",
                "upcoming_title": "⏰ *आणि असलेली लसी*",
                "overdue_title": "⚠️ *तात्काळ कारवाई आवश्यक!*",
                "child": "मूल",
                "vaccines": "लसी",
                "date": "तारीख",
                "location": "स्थान",
                "days_until": "दिवस बाकी",
                "days_ago": "दिवस आधी",
                "message": "कृपया जवळच्या आंगनवाड़ी केंद्रात जा आणि मुलाला लसीकरण करा।",
                "overdue_message": "हे लसीकरण अवधि संपले आहे. कृपया ताबडतोब बुक करा!"
            },
            "gu": {
                "reminder_title": "💉 *રસીકરણ યાદ*",
                "upcoming_title": "⏰ *આવતી રસી*",
                "overdue_title": "⚠️ *તાત્કાલીક પગલાં જરૂરી!*",
                "child": "બાળક",
                "vaccines": "રસીઓ",
                "date": "તારીખ",
                "location": "સ્થાન",
                "days_ago": "દિવસ પહેલાં",
                "days_until": "દિવસો બાકી",
                "message": "કૃપયા નજીકના આંગણવાડી કેન્દ્રમાં જાઓ અને બાળકને રસીકરણ કરાવો.",
                "overdue_message": "આ રસીકરણ સમયમર્યાદા પાર થઈ ગયું છે. કૃપયા તાત્કાલીક બુક કરો!"
            },
            "bn": {
                "reminder_title": "💉 *টিকাকরণ রিমাইন্ডার*",
                "upcoming_title": "⏰ *আসন্ন ভ্যাকসিন*",
                "overdue_title": "⚠️ *তাৎক্ষণিক ব্যবস্থা প্রয়োজন!*",
                "child": "শিশু",
                "vaccines": "ভ্যাকসিন",
                "date": "তারিখ",
                "location": "অবস্থান",
                "days_ago": "দিন আগে",
                "days_until": "অবশিষ্ট দিন",
                "message": "কৃপয়া নিকটতম আঙ্গনওয়াড়ি কেন্দ্রে যান এবং শিশুকে টিকাকরণ করান।",
                "overdue_message": "এই টিকাকরণ সময়সীমা অতিক্রম করেছে। অনুগ্রহ করে অবিলম্বে বুক করুন!"
            },
            "ta": {
                "reminder_title": "💉 *தடுப்பூசி நினைவூட்டல்*",
                "upcoming_title": "⏰ *வரவிருக்கும் தடுப்பூசி*",
                "overdue_title": "⚠️ *உடனடி நடவடிக்கை தேவை!*",
                "child": "குழந்தை",
                "vaccines": "தடுப்பூசிகள்",
                "days_until": "எஞ்சிய நாட்கள",
                "days_ago": "நாட்கள் முன்பு",
                "location": "இருப்பிடம்",
                "days_until": "எஞ்சிய நாட்கள்",
                "message": "தயவுசெய்து நெருங்கிய அங்கன்வாடிக்குச் சென்று குழந்தையைக் குத்திக்கொள்ளுங்கள்.",
                "overdue_message": "இந்த தடுப்பூசி கால வரம்பை கடந்துவிட்டது. தயவுசெய்து உடனடியாக புத்தகமிடுங்கள்!"
            },
            "te": {
                "reminder_title": "💉 *టీకాకरण రిమైండర్*",
                "upcoming_title": "⏰ *రాబోయే టీకా*",
                "overdue_title": "⚠️ *తక్షణ చర్య కావాలి!*",
                "child": "బిడ్డ",
                "vaccines": "టీకాలు",
                "date": "తేదీ",
                "location": "స్థానం",
                "days_until": "మిగిలిన రోజులు",                "days_ago": "రోజుల క్రితం",                "message": "దయచేసి సమీప అంగనవాడி కేంద్రానికి వెళ్లి బిడ్డకు టీకాకरણ చేయుకోండి.",
                "overdue_message": "ఈ టీకాకरణ సమయ పరిమితిని అతిక్రమించింది. దయచేసి వెంటనే బుక్ చేయండి!"
            },
            "kn": {
                "reminder_title": "💉 *ಲಸಿಕರಣ ಜ್ಞಾಪನೆ*",
                "upcoming_title": "⏰ *ಮುಂದಿನ ಲಸಿ*",
                "overdue_title": "⚠️ *ತಕ್ಷಣ ಕ್ರಮ ಅಗತ್ಯ!*",
                "child": "ಮಗು",
                "vaccines": "ಲಸಿಗಳು",
                "date": "ದಿನಾಂಕ",
                "location": "ಸ್ಥಳ",
                "days_until": "ಉಳಿದ ದಿನಗಳು",
                "days_ago": "ದಿನಗಳ ಹಿಂದೆ",
                "message": "ದಯವಿಟ್ಟು ಹತ್ತಿರದ ಅಂಗನವಾಡಿ ಕೇಂದ್ರಕ್ಕೆ ಹೋಗಿ ಮಗುವಿಗೆ ಲಸಿಕರಣ ಮಾಡಿಸಿ.",
                "overdue_message": "ಈ ಲಸಿಕರಣ ಸಮಯ ಮಿತಿಯನ್ನು ಮೀರಿದೆ. ದಯವಿಟ್ಟು ತಕ್ಷಣ ಬುಕ್ ಮಾಡಿ!"
            },
            "ml": {
                "reminder_title": "💉 *വാക്സിനേഷൻ നിരൂപണം*",
                "upcoming_title": "⏰ *വരാനിരിക്കുന്ന വാക്സിൻ*",
                "overdue_title": "⚠️ *ഉടനടി നടപടി ആവശ്യമാണ്!*",
                "child": "കുട്ടി",
                "vaccines": "വാക്സിൻ",
                "date": "തീയതി",
                "location": "സ്ഥലം",
                "days_ago": "ദിവസങ്ങൾ മുമ്പ്",
                "days_until": "ശേഷിക്കുന്ന ദിവസങ്ങൾ",
                "message": "ദയവായി സമീപസ്ഥ ആഗന്തുകയ്ക്ക് പോയി കുട്ടിക്ക് വാക്സിനേഷൻ നൽകിക്കോളുക.",
                "overdue_message": "ഈ വാക്സിനേഷനെ സമയ പരിധി കഴിഞ്ഞുപോയി. ദയവായി ഉടനടി ബുക്ക് ചെയ്യുക!"
            },
            "pa": {
                "reminder_title": "💉 *ਟੀਕਾਕਾਰੀ ਯਾਦ ਦਿੰਦੀ*",
                "upcoming_title": "⏰ *ਆਉਣ ਵਾਲੀ ਲਕੀ*",
                "overdue_title": "⚠️ *ਫੌਰੀ ਕਾਰਵਾਈ ਲੋੜੀਂਦੀ!*",
                "child": "ਬੱਚਾ",
                "vaccines": "ਟੀਕੇ",
                "date": "ਸਥਿਤੀ",
                "location": "ਸਥਾਨ",
                "days_ago": "ਦਿਨ ਪਹਿਲਾਂ",
                "days_until": "ਬਾਕੀ ਦਿਨ",
                "message": "ਕਿਰਪਾ ਕਰਕੇ ਨਜ਼ਦੀਕੀ ਆਂਗਨਵਾੜੀ ਕੇਂਦਰ ਜਾਓ ਅਤੇ ਬੱਚੇ ਦਾ ਟੀਕਾਕਾਰੀ ਕਰਾਓ।",
                "overdue_message": "ਇਹ ਟੀਕਾਕਾਰੀ ਸਨ ਸੀਮਾ ਪਾਰ ਹੋ ਗਈ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਫੌਰੀ ਬੁੱਕ ਕਰੋ!"
            }
        }

        t = translations.get(user_language, translations["en"])

        today = datetime.now().date()
        scheduled = scheduled_date.date()
        days_remaining = (scheduled - today).days

        # Determine urgency and title
        if days_remaining < 0:
            title = t["overdue_title"]
            urgency_msg = t["overdue_message"]
        else:
            title = t["upcoming_title"]
            urgency_msg = t["message"]

        # Build message
        message = f"{title}\n\n"
        message += f"✅ {t['child']}: {child_name}\n"
        message += f"💉 {t['vaccines']}: {', '.join(vaccines)}\n"
        message += f"📅 {t['date']}: {scheduled.strftime('%d %B %Y')}\n"

        if days_remaining >= 0:
            message += f"⏳ {t['days_until']}: {days_remaining}\n\n"
        else:
            days_ago_text = t.get('days_ago', 'days ago')
            message += f"⚠️ {t['days_until']}: {abs(days_remaining)} {days_ago_text}\n\n"

        message += f"\n{urgency_msg}\n"

        # Add Anganwadi location (if available)
        if location:
            anganwadi_data = await AnganwadiFinderService.find_nearest_anganwadi(location)
            if anganwadi_data.get("found"):
                anganwadi_msg = AnganwadiFinderService.format_anganwadi_message(anganwadi_data, user_language)
                message += f"\n\n{anganwadi_msg}"

        # Send via WhatsApp
        try:
            await whatsapp_service.send_text_message(user_phone, message)
            logger.info(f"Vaccine reminder sent to {user_phone} for {child_name}")
            return True
        except Exception as e:
            logger.error(f"Error sending vaccine reminder: {e}")
            return False

    @staticmethod
    @staticmethod
    async def send_family_vaccine_status(
        family_id: str,
        user_phone: str,
        user_language: str = "en",
        location: str = None,
        session=None
    ) -> str:
        """Send complete vaccine status for family"""
        
        if not session:
            logger.error("Database session is required for vaccine status")
            return "Error: Database session unavailable"

        translations = {
            "hi": {
                "title": "📋 *परिवार का टीकाकरण स्थिति*",
                "completed": "✅ पूरा हुआ",
                "due_soon": "⏰ जल्द ही देय",
                "overdue": "⚠️ अवधि समाप्त",
                "upcoming": "📅 आने वाली",
                "no_data": "कोई टीकाकरण डेटा नहीं मिला।"
            },
            "en": {
                "title": "📋 *Family Vaccination Status*",
                "completed": "✅ Completed",
                "due_soon": "⏰ Due Soon",
                "overdue": "⚠️ Overdue",
                "upcoming": "📅 Upcoming",
                "no_data": "No vaccination data found."
            },
            "mr": {
                "title": "📋 *कुटुंबाचे लसीकरण स्थिति*",
                "completed": "✅ पूर्ण",
                "due_soon": "⏰ लवकरच देय",
                "overdue": "⚠️ अवधि संपली",
                "upcoming": "📅 आणि असलेली",
                "no_data": "कोणतेही लसीकरण डेटा आढळले नाही."
            },
            "gu": {
                "title": "📋 *કુટુંબ રસીકરણ સ્થિતિ*",
                "completed": "✅ પૂર્ણ",
                "due_soon": "⏰ શીઘ્ર જ દેય",
                "overdue": "⚠️ અવધિ સમાપ્ત",
                "upcoming": "📅 આવતી",
                "no_data": "કોઈ રસીકરણ ડેટા નથી મળ્યો."
            },
            "bn": {
                "title": "📋 *পারিবারিক টিকাকরণ অবস্থা*",
                "completed": "✅ সম্পূর্ণ",
                "due_soon": "⏰ শীঘ্রই দেয়",
                "overdue": "⚠️ মেয়াদ উত্তীর্ণ",
                "upcoming": "📅 আসন্ন",
                "no_data": "কোন টিকাকরণ ডেটা পাওয়া যায়নি।"
            },
            "ta": {
                "title": "📋 *குடும்ப தடுப்பூசி நிலை*",
                "completed": "✅ முடிந்தது",
                "due_soon": "⏰ விரைவில் வாய்க்கக",
                "overdue": "⚠️ விலக்கமாக",
                "upcoming": "📅 வரவிருக்கும்",
                "no_data": "தடுப்பூசி ডेটা கிடைக்கவில்லை।"
            },
            "te": {
                "title": "📋 *కుటుంబ టీకाকरण స్థితి*",
                "completed": "✅ పూర్తిచేసారు",
                "due_soon": "⏰ త్వరలో దేయం",
                "overdue": "⚠️ గడువు మీరిపోయింది",
                "upcoming": "📅 రాబోయే",
                "no_data": "టీకाకරణ డేటా కనుగొనబడలేదు."
            },
            "kn": {
                "title": "📋 *ಕುಟುಂಬ ಲಸಿಕರಣ ಸ್ಥಿತಿ*",
                "completed": "✅ ಪೂರ್ಣ",
                "due_soon": "⏰ ಶೀಘ್ರದಲ್ಲೇ ಪಾವತಿಯಾಗಬೇಕು",
                "overdue": "⚠️ ಗಡುಕಾಲ ಮೀರಿದೆ",
                "upcoming": "📅 ಮುಂದಿನ",
                "no_data": "ಲಸಿಕರಣ ಡೇಟಾ ಕಂಡುಬಂದಿಲ್ಲ."
            },
            "ml": {
                "title": "📋 *കുടുംബ വാക്സിനേഷൻ സ്ഥിതി*",
                "completed": "✅ പൂർത്തിയായി",
                "due_soon": "⏰ ഉടനെ പേയ്‌ക്കാനുണ്ട്",
                "overdue": "⚠️ കാലാവധി കഴിഞ്ഞു",
                "upcoming": "📅 വരാനിരിക്കുന്ന",
                "no_data": "വാക്സിനേഷൻ ഡേറ്റ നിഷ്പ്രയോജനം."
            },
            "pa": {
                "title": "📋 *ਪਰਿਵਾਰ ਟੀਕਾਕਾਰੀ ਸਥਿਤੀ*",
                "completed": "✅ ਪੂਰਾ",
                "due_soon": "⏰ ਛੇਤੀ ਦਿਓ",
                "overdue": "⚠️ ਮਿਆਦ ਲੰਘ ਗਈ",
                "upcoming": "📅 ਆਉਣ ਵਾਲੀ",
                "no_data": "ਕੋਈ ਟੀਕਾਕਾਰੀ ਡੇਟਾ ਨਹੀਂ ਮਿਲਿਆ।"
            }
        }

        t = translations.get(user_language, translations["en"])

        # Get all due vaccines
        due_vaccines = await VaccineReminderService.get_due_vaccines_for_family(family_id, session)

        if not due_vaccines:
            return f"{t['title']}\n\n{t['no_data']}"

        message = f"{t['title']}\n\n"

        for vax in due_vaccines:
            status_text = {
                "due_soon": t["due_soon"],
                "overdue": t["overdue"],
                "upcoming": t["upcoming"]
            }.get(vax["status"], t["upcoming"])

            message += f"{status_text} {vax['child_name']}\n"
            message += f"💉 {', '.join(vax['vaccines'])}\n"
            message += f"📅 {vax['scheduled_date'].strftime('%d %B %Y')}\n\n"

        message += "\n📞 अपनी स्थानीय आंगनवाड़ी निदेशक से संपर्क करें।\n"

        return message
