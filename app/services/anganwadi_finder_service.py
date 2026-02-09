import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)


class AnganwadiFinderService:
    """Find nearest Anganwadi Kendra (childcare centers) and health facilities"""

    ANGANWADI_CENTERS_DB = {
        "delhi": [
            {"name": "East Delhi Anganwadi", "lat": 28.5673, "lon": 77.2860, "address": "Laxmi Nagar, Delhi", "phone": "011-XXXX-XXXX"},
            {"name": "South Delhi Anganwadi", "lat": 28.5244, "lon": 77.1855, "address": "Greater Kailash, Delhi", "phone": "011-XXXX-XXXX"},
            {"name": "North Delhi Anganwadi", "lat": 28.7405, "lon": 77.2270, "address": "Civil Lines, Delhi", "phone": "011-XXXX-XXXX"},
        ],
        "mumbai": [
            {"name": "Mumbai Central Anganwadi", "lat": 19.0176, "lon": 72.8479, "address": "Fort, Mumbai", "phone": "022-XXXX-XXXX"},
            {"name": "Bandra Anganwadi", "lat": 19.0596, "lon": 72.8295, "address": "Bandra East, Mumbai", "phone": "022-XXXX-XXXX"},
            {"name": "Dharavi Anganwadi", "lat": 19.0176, "lon": 72.8614, "address": "Dharavi, Mumbai", "phone": "022-XXXX-XXXX"},
        ],
        "bangalore": [
            {"name": "Whitefield Anganwadi", "lat": 12.9698, "lon": 77.7499, "address": "Whitefield, Bangalore", "phone": "080-XXXX-XXXX"},
            {"name": "Indiranagar Anganwadi", "lat": 13.0017, "lon": 77.6434, "address": "Indiranagar, Bangalore", "phone": "080-XXXX-XXXX"},
        ],
        "kolkata": [
            {"name": "Kolkata South Anganwadi", "lat": 22.5355, "lon": 88.3574, "address": "Salt Lake, Kolkata", "phone": "033-XXXX-XXXX"},
            {"name": "Kolkata North Anganwadi", "lat": 22.6158, "lon": 88.4306, "address": "Baranagar, Kolkata", "phone": "033-XXXX-XXXX"},
        ]
    }

    VACCINATION_CENTERS = {
        "delhi": [
            {"name": "Delhi ASHA Center", "lat": 28.6139, "lon": 77.2090, "type": "public"},
            {"name": "Safdarjung Hospital", "lat": 28.5673, "lon": 77.1860, "type": "hospital"},
        ],
        "mumbai": [
            {"name": "BMC Vaccination Center", "lat": 19.0176, "lon": 72.8479, "type": "public"},
            {"name": "Grant Medical College", "lat": 19.0176, "lon": 72.8273, "type": "hospital"},
        ],
    }

    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance using Haversine formula (in km)"""
        from math import radians, sin, cos, sqrt, atan2

        R = 6371
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c

    @staticmethod
    async def find_nearest_anganwadi(
        city: str, user_lat: float = None, user_lon: float = None
    ) -> Dict:
        """Find nearest Anganwadi Kendra"""

        city_lower = city.lower()
        centers = AnganwadiFinderService.ANGANWADI_CENTERS_DB.get(city_lower, [])

        if not centers:
            logger.warning(f"No Anganwadi centers found for {city}")
            return {
                "found": False,
                "city": city,
                "message": f"Anganwadi Kendra database for {city} not yet populated"
            }

        if user_lat and user_lon:
            for center in centers:
                center["distance"] = AnganwadiFinderService.calculate_distance(
                    user_lat, user_lon, center["lat"], center["lon"]
                )

            nearest = min(centers, key=lambda x: x["distance"])
            return {
                "found": True,
                "city": city,
                "nearest": {
                    "name": nearest["name"],
                    "address": nearest["address"],
                    "distance_km": round(nearest["distance"], 2),
                    "phone": nearest["phone"],
                    "lat": nearest["lat"],
                    "lon": nearest["lon"]
                }
            }
        else:
            return {
                "found": True,
                "city": city,
                "centers": centers[:3]
            }

    @staticmethod
    async def find_vaccination_centers(city: str) -> List[Dict]:
        """Find vaccination centers in the city"""
        city_lower = city.lower()
        return AnganwadiFinderService.VACCINATION_CENTERS.get(city_lower, [])

    @staticmethod
    def format_anganwadi_message(anganwadi_data: Dict, lang: str = "en") -> str:
        """Format Anganwadi information for WhatsApp"""

        translations = {
            "hi": {
                "title": "🏥 *नजदीकी आंगनवाड़ी केंद्र*",
                "name": "नाम",
                "address": "पता",
                "distance": "दूरी",
                "phone": "फोन",
                "directions": "📍 Google Maps पर दिशाएं खोलें",
                "hours": "समय: सोमवार-शुक्रवार 9 AM - 5 PM",
                "documents": "📋 ले जाएं: आधार, स्वास्थ्य कार्ड, बच्चे का जन्म प्रमाण पत्र"
            },
            "en": {
                "title": "🏥 *Nearest Anganwadi Kendra*",
                "name": "Name",
                "address": "Address",
                "distance": "Distance",
                "phone": "Phone",
                "directions": "📍 Open directions on Google Maps",
                "hours": "Hours: Monday-Friday 9 AM - 5 PM",
                "documents": "📋 Bring: Aadhar, Health Card, Birth Certificate"
            },
            "mr": {
                "title": "🏥 *जवळचे आंगनवाड़ी केंद्र*",
                "name": "नाव",
                "address": "पता",
                "distance": "अंतर",
                "phone": "फोन",
                "directions": "📍 Google Maps वर दिशा उघडा",
                "hours": "वेळ: सोमवार-शुक्रवार 9 AM - 5 PM",
                "documents": "📋 नेवून या: आधार, आरोग्य कार्ड, जन्म प्रमाणपत्र"
            },
            "gu": {
                "title": "🏥 *નિકટતમ આંગણવાડી કેન્દ્ર*",
                "name": "નામ",
                "address": "સરનામું",
                "distance": "અંતર",
                "phone": "ફોન",
                "directions": "📍 Google Maps પર દિશાઓ ખોલો",
                "hours": "સમય: સોમવાર-શુક્રવાર 9 AM - 5 PM",
                "documents": "📋 લાવો: આધાર, આરોગ્ય કાર્ડ, જન્મ પ્રમાણપત્ર"
            },
            "bn": {
                "title": "🏥 *নিকটতম আঙ্গনওয়াড়ি কেন্দ্র*",
                "name": "নাম",
                "address": "ঠিকানা",
                "distance": "দূরত্ব",
                "phone": "ফোন",
                "directions": "📍 Google Maps এ দিকনির্দেশনা খুলুন",
                "hours": "সময়: সোমবার-শুক্রবার 9 AM - 5 PM",
                "documents": "📋 নিয়ে আসুন: আধার, স্বাস্থ্য কার্ড, জন্মপ্রমাণ"
            },
            "ta": {
                "title": "🏥 *மிக கெளிய அங்கன்வாடி மையம்*",
                "name": "பெயர்",
                "address": "முகவரி",
                "distance": "தொலைவு",
                "phone": "ஃபோன்",
                "directions": "📍 Google Maps இல் திசைகளைத் திறக்கவும்",
                "hours": "நேரம்: திங்கட்கிழமை-வெள்ளிக்கிழமை 9 AM - 5 PM",
                "documents": "📋 கொண்டு வாருங்கள்: ஆதார், சுகாதார அட்டை, பிறப்பு சான்றிதழ்"
            },
            "te": {
                "title": "🏥 *సమీప అంగనవాడి కేంద్రం*",
                "name": "పేరు",
                "address": "చిరునామా",
                "distance": "దూరం",
                "phone": "ఫోన్",
                "directions": "📍 Google Maps లో దిశలను తెరవండి",
                "hours": "సమయం: సోమవారం-శుక్రవారం 9 AM - 5 PM",
                "documents": "📋 తీసుకువెళ్లండి: ఆధార్, ఆరోగ్య కార్డ్, జన్మ సర్టిఫికేట్"
            },
            "kn": {
                "title": "🏥 *ಹತ್ತಿರದ ಅಂಗನವಾಡಿ ಕೇಂದ್ರ*",
                "name": "ಹೆಸರು",
                "address": "ವಿಳಾಸ",
                "distance": "ದೂರ",
                "phone": "ಫೋನ್",
                "directions": "📍 Google Maps ನಲ್ಲಿ ದಿಕ್ಸೂಚನೆ ತೆರೆಯಿರಿ",
                "hours": "ಸ್ಮಿ: ಸೋಮ-ಶುಕ್ರ 9 AM - 5 PM",
                "documents": "📋 ತೆಗೆದುಕೊಂಡುಕೋ: ಆಧಾರ, ಆರೋಗ್ಯ ಕಾರ್ಡ್, ಜನ್ಮ ಪ್ರಮಾಣ"
            },
            "ml": {
                "title": "🏥 *ഏറ്റവും അടുത്ത ആഗന്തുക കേന്ദ്രം*",
                "name": "പേര്",
                "address": "വിലാസം",
                "distance": "അകലം",
                "phone": "ഫോൺ",
                "directions": "📍 Google Maps ൽ ദിശകൾ തുറക്കുക",
                "hours": "സമയം: തിങ്കൾ-വെള്ളി 9 AM - 5 PM",
                "documents": "📋 കൊണ്ടുവരിക: ആധാർ, ആരോഗ്യ കാർഡ്, ജന്മ സർട്ടിഫിക്കറ്റ്"
            },
            "pa": {
                "title": "🏥 *ਨਜ਼ਦੀਕੀ ਆਂਗਨਵਾੜੀ ਕੇਂਦਰ*",
                "name": "ਨਾਮ",
                "address": "ਪਤਾ",
                "distance": "ਦੂਰੀ",
                "phone": "ਫ਼ੋਨ",
                "directions": "📍 Google Maps ਵਿੱਚ ਰਸਤਾ ਖੋਲੋ",
                "hours": "ਸਮਾਂ: ਸੋਮ-ਸ਼ੁੱਕਰ 9 AM - 5 PM",
                "documents": "📋 ਲੈ ਕੇ ਆਉ: ਆਧਾਰ, ਸਿਹਤ ਕਾਰਡ, ਜਨਮ ਪਰਮਾਣ"
            }
        }

        t = translations.get(lang, translations["en"])

        if not anganwadi_data.get("found"):
            return f"❌ {t['title']}\n\nडेटाबेस अभी अपडेट हो रहा है। कृपया बाद में पूछें।"

        msg = f"{t['title']} - {anganwadi_data['city']}\n\n"

        if "nearest" in anganwadi_data:
            nearest = anganwadi_data["nearest"]
            msg += f"✅ {t['name']}: {nearest['name']}\n"
            msg += f"📍 {t['address']}: {nearest['address']}\n"
            msg += f"📏 {t['distance']}: {nearest['distance_km']} km\n"
            msg += f"📞 {t['phone']}: {nearest['phone']}\n\n"
        else:
            msg += f"{t['name']}: {anganwadi_data['centers'][0]['name']}\n"

        msg += f"\n{t['hours']}\n"
        msg += f"{t['documents']}\n"
        msg += f"\n💡 {t['directions']}"

        return msg
