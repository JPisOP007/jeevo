
import logging
from typing import Dict, List
import httpx
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.repositories import UserRepository, FamilyMemberRepository, VaccinationRecordRepository

logger = logging.getLogger(__name__)

class HealthSupportService:

    @staticmethod
    async def process_symptom(user_message: str, user_location: Dict, language: str) -> str:

        messages = {
            "en": "I understand your symptoms. Please note that I provide general guidance only - always consult a qualified doctor for accurate diagnosis and treatment.",
            "hi": "मैं आपके लक्षणों को समझ रहा हूं। कृपया ध्यान दें कि मैं केवल सामान्य सलाह प्रदान करता हूं - सटीक निदान और उपचार के लिए हमेशा योग्य डॉक्टर से सलाह लें।"
        }
        return messages.get(language, messages["en"])

class FamilyCareService:

    @staticmethod
    async def add_family_member(db: AsyncSession, user_id: int, details: Dict) -> Dict:

        try:
            member = await FamilyMemberRepository.create_family_member(
                db,
                user_id=user_id,
                name=details.get("name"),
                relation=details.get("relation"),
                age=details.get("age"),
                gender=details.get("gender"),
                blood_type=details.get("blood_type"),
                allergies=details.get("allergies")
            )

            return {
                "success": True,
                "member_id": member.id,
                "name": member.name,
                "message": f"✅ {member.name} added successfully!"
            }
        except Exception as e:
            logger.error(f"Error adding family member: {e}")
            return {
                "success": False,
                "message": "❌ Could not save family member. Please try again."
            }

    @staticmethod
    async def get_family_members(db: AsyncSession, user_id: int) -> List[Dict]:

        try:
            members = await FamilyMemberRepository.get_user_family_members(db, user_id)
            return [
                {
                    "id": m.id,
                    "name": m.name,
                    "relation": m.relation,
                    "age": m.age
                }
                for m in members
            ]
        except Exception as e:
            logger.error(f"Error fetching family members: {e}")
            return []

class VaccinationService:

    VACCINE_SCHEDULE = {
        0: ["BCG", "Hepatitis B", "OPV 0"],
        42: ["DPT 1", "Hepatitis B 1", "OPV 1", "Hib 1", "Rotavirus 1", "PCV 1"],
        70: ["DPT 2", "Hepatitis B 2", "OPV 2", "Hib 2", "Rotavirus 2", "PCV 2"],
        98: ["DPT 3", "Hepatitis B 3", "OPV 3", "Hib 3", "Rotavirus 3", "PCV 3"],
        270: ["Measles 1 (MR)"],
        365: ["PCV Booster"],
        456: ["Measles 2 (MR)", "DPT Booster 1", "OPV Booster"],
        1825: ["DPT Booster 2"]
    }

    @staticmethod
    async def setup_child_vaccination(db: AsyncSession, user_id: int, name: str, dob: datetime) -> Dict:

        age_days = (datetime.now() - dob).days

        due_vaccines = []
        upcoming = []

        for age, vaccines in VaccinationService.VACCINE_SCHEDULE.items():
            if age <= age_days <= age + 30:
                due_vaccines.extend(vaccines)
            elif age_days < age <= age_days + 90:
                upcoming.extend(vaccines)

        return {
            "child_name": name,
            "age_days": age_days,
            "due_now": due_vaccines,
            "upcoming": upcoming
        }

    @staticmethod
    def format_vaccine_info(info: Dict, lang: str) -> str:

        messages = {
            "hi": (
                f"💉 *{info['child_name']} की वैक्सीन स्थिति*\n"
                f"आयु: {info['age_days']} दिन\n\n"
            ),
            "en": (
                f"💉 *Vaccine Status for {info['child_name']}*\n"
                f"Age: {info['age_days']} days\n\n"
            )
        }

        msg = messages.get(lang, messages["en"])

        if info['due_now']:
            if lang == "hi":
                msg += "*अभी देय:*\n"
                for v in info['due_now']:
                    msg += f"• {v}\n"
                msg += "\n🏥 नजदीकी आंगनवाड़ी केंद्र जाएं!\n\n"
            else:
                msg += "*Due Now:*\n"
                for v in info['due_now']:
                    msg += f"• {v}\n"
                msg += "\n🏥 Visit nearest Anganwadi center!\n\n"

        if info['upcoming']:
            if lang == "hi":
                msg += "*आगामी (90 दिन):*\n"
                for v in info['upcoming']:
                    msg += f"• {v}\n"
            else:
                msg += "*Upcoming (90 days):*\n"
                for v in info['upcoming']:
                    msg += f"• {v}\n"

        return msg

class HospitalFinderService:

    @staticmethod
    async def find_hospitals(location: Dict, emergency: bool = False) -> List[Dict]:

        city = location.get("city", "")

        if settings.GOOGLE_MAPS_API_KEY and settings.GOOGLE_MAPS_API_KEY != "your_google_maps_key":
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "https://maps.googleapis.com/maps/api/place/textsearch/json",
                        params={
                            "query": f"hospital near {city}",
                            "key": settings.GOOGLE_MAPS_API_KEY
                        },
                        timeout=10
                    )
                    if response.status_code == 200:
                        data = response.json()
                        hospitals = []
                        for place in data.get("results", [])[:5]:
                            hospitals.append({
                                "name": place["name"],
                                "address": place.get("formatted_address", ""),
                                "rating": place.get("rating", "N/A"),
                                "phone": place.get("formatted_phone_number", "108")
                            })
                        return hospitals
            except Exception as e:
                logger.error(f"Maps API error: {e}")

        return [
            {"name": "सरकारी अस्पताल", "distance": "2 km", "phone": "108", "emergency": True},
            {"name": "प्राथमिक स्वास्थ्य केंद्र", "distance": "1 km", "type": "PHC", "phone": "102"}
        ]

    @staticmethod
    def format_hospitals(hospitals: List[Dict], lang: str) -> str:

        if not hospitals:
            return "No hospitals found in your area."

        msg = "🏥 *Nearby Hospitals:*\n\n" if lang == "en" else "🏥 *नजदीकी अस्पताल:*\n\n"

        for i, h in enumerate(hospitals[:5], 1):
            msg += f"{i}. {h.get('name', 'Hospital')}\n"
            if h.get('address'):
                msg += f"   📍 {h['address']}\n"
            if h.get('phone'):
                msg += f"   📞 {h['phone']}\n"
            msg += "\n"

        return msg

class EnvironmentalAlertService:

    @staticmethod
    async def get_alerts(location: Dict) -> List[Dict]:

        city = location.get("city", "Unknown")
        state = location.get("state", "Unknown")

        alerts: List[Dict] = []

        # 1) Check AQI via Google Maps Air Quality API (requires API key and coordinates)
        try:
            if settings.GOOGLE_MAPS_API_KEY and settings.GOOGLE_MAPS_API_KEY != "your_google_maps_key":
                async with httpx.AsyncClient(timeout=10) as client:
                    # First, get coordinates for the city using Google Geocoding
                    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
                    geocode_params = {
                        "address": f"{city}, {state}, India",
                        "key": settings.GOOGLE_MAPS_API_KEY
                    }
                    
                    geocode_resp = await client.get(geocode_url, params=geocode_params)
                    if geocode_resp.status_code == 200:
                        geocode_data = geocode_resp.json()
                        results = geocode_data.get("results", [])
                        
                        if results:
                            location_coords = results[0].get("geometry", {}).get("location", {})
                            lat = location_coords.get("lat")
                            lon = location_coords.get("lng")
                            
                            if lat and lon:
                                # Call Google Air Quality API
                                aqi_url = "https://airquality.googleapis.com/v1/currentAirQuality:lookup"
                                aqi_params = {
                                    "key": settings.GOOGLE_MAPS_API_KEY
                                }
                                aqi_body = {
                                    "location": {
                                        "latitude": lat,
                                        "longitude": lon
                                    }
                                }
                                
                                aqi_resp = await client.post(aqi_url, params=aqi_params, json=aqi_body)
                                if aqi_resp.status_code == 200:
                                    aqi_data = aqi_resp.json()
                                    
                                    # Extract primary pollutant and US AQI
                                    indexes = aqi_data.get("indexes", [])
                                    us_aqi = None
                                    primary_pollutant = None
                                    
                                    for idx in indexes:
                                        if idx.get("code") == "uaqi":
                                            us_aqi = idx.get("aqi")
                                            primary_pollutant = idx.get("dominantPollutant")
                                            break
                                    
                                    if us_aqi is not None:
                                        # Classify AQI level based on US EPA standards
                                        if us_aqi <= 50:
                                            level = "good"
                                        elif us_aqi <= 100:
                                            level = "moderate"
                                        elif us_aqi <= 150:
                                            level = "unhealthy_sensitive"
                                        elif us_aqi <= 200:
                                            level = "unhealthy"
                                        elif us_aqi <= 300:
                                            level = "very_unhealthy"
                                        else:
                                            level = "hazardous"
                                        
                                        # Build alert message with health recommendations
                                        pollutant_name = primary_pollutant or "air quality"
                                        health_messages = {
                                            "good": "Air quality is satisfactory. Enjoy outdoor activities!",
                                            "moderate": "Air quality is acceptable. Sensitive groups may experience mild effects.",
                                            "unhealthy_sensitive": "Sensitive groups should consider limiting prolonged outdoor activities.",
                                            "unhealthy": "Everyone may begin to experience health effects. Avoid outdoor activities if possible.",
                                            "very_unhealthy": "Health alert: The risk of health effects is increased. Stay indoors and keep activity levels low.",
                                            "hazardous": "Health warning: Everyone should avoid all outdoor exertion. Stay indoors with air filters."
                                        }
                                        
                                        alerts.append({
                                            "type": "aqi",
                                            "title": f"Air Quality Alert - {city}",
                                            "message": f"AQI: {us_aqi} ({level.replace('_', ' ').title()})\nPrimary pollutant: {pollutant_name}\n{health_messages.get(level, '')}",
                                            "level": level,
                                            "aqi": us_aqi,
                                            "pollutant": primary_pollutant
                                        })
        except Exception as e:
            logger.warning(f"[WEATHER] Failed to fetch AQI via Google Maps API: {e}")
            # Silent fallback to avoid failing the whole endpoint
            pass

        # 2) Check basic weather conditions via OpenWeather if API key provided
        ow_key = getattr(settings, "OPENWEATHER_API_KEY", None)
        try:
            if ow_key and ow_key != "your_openweather_key":
                async with httpx.AsyncClient(timeout=10) as client:
                    wresp = await client.get(
                        "https://api.openweathermap.org/data/2.5/weather",
                        params={"q": f"{city},{state}", "appid": ow_key, "units": "metric"}
                    )
                    if wresp.status_code == 200:
                        w = wresp.json()
                        temp = w.get("main", {}).get("temp")
                        weather_main = w.get("weather", [{}])[0].get("main", "")
                        # Extreme heat/cold alerts
                        if temp is not None:
                            if temp >= 40:
                                alerts.append({
                                    "type": "weather",
                                    "title": f"Heat Alert - {city}",
                                    "message": f"High temperature {temp}°C. Stay hydrated and avoid outdoor work.",
                                    "level": "high",
                                    "temp": temp
                                })
                            elif temp <= 5:
                                alerts.append({
                                    "type": "weather",
                                    "title": f"Cold Alert - {city}",
                                    "message": f"Low temperature {temp}°C. Keep warm and check on vulnerable people.",
                                    "level": "moderate",
                                    "temp": temp
                                })

                        # Severe weather keywords
                        if weather_main and weather_main.lower() in ["storm", "thunderstorm", "tornado", "hurricane"]:
                            alerts.append({
                                "type": "weather",
                                "title": f"Severe Weather - {city}",
                                "message": f"{weather_main} expected. Follow local advisories and stay safe.",
                                "level": "high",
                            })
        except Exception:
            pass

        # 3) If no dynamic alerts found, return a low-level seasonal/disease advisory
        if not alerts:
            alerts.append({
                "type": "disease",
                "title": "Health Advisory",
                "message": "No immediate environmental hazards detected. Stay informed and follow hygiene best practices.",
                "level": "low"
            })

        return alerts

    @staticmethod
    def format_alerts(alerts: List[Dict], lang: str) -> str:

        if not alerts:
            return "✅ No alerts in your area" if lang == "en" else "✅ आपके क्षेत्र में कोई अलर्ट नहीं"

        msg = "⚠️ *Health Alerts:*\n\n" if lang == "en" else "⚠️ *स्वास्थ्य चेतावनी:*\n\n"

        for alert in alerts:
            msg += f"🔔 {alert.get('title')}\n"
            msg += f"   {alert.get('message')}\n\n"

        return msg