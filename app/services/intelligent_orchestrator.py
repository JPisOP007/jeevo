
import json
import ast
import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import httpx
import asyncio

logger = logging.getLogger(__name__)

class HealthServiceTools:

    def __init__(self):
        from app.config.settings import settings
        self.openweather_key = settings.OPENWEATHER_API_KEY
        self.google_maps_key = settings.GOOGLE_MAPS_API_KEY
        # Optional: if your Google key exposes weather/aqi endpoints, configure URLs in settings
        self.google_weather_url = getattr(settings, "GOOGLE_WEATHER_API_URL", None)
        self.google_aqi_url = getattr(settings, "GOOGLE_AQI_API_URL", None)

    async def check_weather_risks(self, location: str = "India", language: str = "en", **kwargs) -> Dict:
        # Normalize location: detect lat,lon if provided
        lat = None
        lon = None
        has_coords = False
        if isinstance(location, str) and "," in location:
            parts = [p.strip() for p in location.split(",")]
            if len(parts) >= 2:
                try:
                    lat = float(parts[0])
                    lon = float(parts[1])
                    has_coords = True
                except Exception:
                    has_coords = False

        # Prefer OpenWeather if configured for robust data
        if self.openweather_key:
            try:
                async with httpx.AsyncClient() as client:
                    params = {"appid": self.openweather_key, "units": "metric"}
                    if has_coords:
                        params.update({"lat": lat, "lon": lon})
                    else:
                        params.update({"q": location})

                    response = await client.get(
                        "https://api.openweathermap.org/data/2.5/weather",
                        params=params,
                        timeout=10
                    )
                    response.raise_for_status()
                    data = response.json()
                    risks = []
                    temp = data["main"]["temp"]
                    humidity = data["main"]["humidity"]
                    weather = data["weather"][0]["main"]

                    risk_messages = {
                        "en": {
                            "rain": "Heavy rainfall - Risk of dengue/malaria from stagnant water",
                            "high_temp": f"High temperature {temp}°C - Stay hydrated, avoid sun",
                            "high_humidity": "High humidity - Risk of fungal infections",
                            "normal": "Weather conditions normal"
                        },
                        "hi": {
                            "rain": "भारी बारिश - स्थिर पानी से डेंगू/मलेरिया का खतरा",
                            "high_temp": f"उच्च तापमान {temp}°C - हाइड्रेटेड रहें, धूप से बचें",
                            "high_humidity": "उच्च आर्द्रता - फंगल संक्रमण का खतरा",
                            "normal": "मौसम की स्थिति सामान्य"
                        }
                    }
                    
                    t = risk_messages.get(language, risk_messages["en"])
                    
                    if weather in ["Rain", "Thunderstorm"]:
                        risks.append(t["rain"])
                    if temp > 35:
                        risks.append(t["high_temp"])
                    if humidity > 80:
                        risks.append(t["high_humidity"])

                    return {
                        "tool": "weather_risks",
                        "status": "success",
                        "location": location,
                        "temp": temp,
                        "humidity": humidity,
                        "weather": weather,
                        "risks": risks if risks else [t["normal"]],
                        "language": language
                    }
            except Exception as e:
                logger.error(f"OpenWeather API error: {e}")

        # Fallback: use Google Geocoding (if available) to get lat/lon and then Open-Meteo for weather (no API key)
        # If the Google key also exposes a direct weather endpoint, call it first
        if self.google_maps_key and self.google_weather_url:
            try:
                async with httpx.AsyncClient() as client:
                    logger.debug(f"Calling Google weather endpoint: {self.google_weather_url} for location: {location}")
                    gw_resp = await client.get(
                        self.google_weather_url,
                        params={"q": location, "key": self.google_maps_key},
                        timeout=10
                    )
                    gw_resp.raise_for_status()
                    gw = gw_resp.json()
                    # Try to extract common fields from provider response
                    temp = gw.get("temperature") or gw.get("temp") or (gw.get("current", {}) or {}).get("temp")
                    humidity = gw.get("humidity") or (gw.get("current", {}) or {}).get("humidity")
                    weather = gw.get("weather") or (gw.get("current", {}) or {}).get("condition")
                    risks = []
                    if weather and any(w in str(weather).lower() for w in ["rain", "thunder", "storm"]):
                        risks.append("Heavy rainfall - Risk of dengue/malaria from stagnant water")
                    if temp and float(temp) > 35:
                        risks.append(f"High temperature {temp}°C - Stay hydrated, avoid sun")

                    return {
                        "tool": "weather_risks",
                        "status": "success",
                        "location": location,
                        "temp": temp,
                        "humidity": humidity,
                        "weather": weather,
                        "risks": risks if risks else ["Weather conditions normal"],
                        "source": "google_direct"
                    }
            except Exception as e:
                logger.error(f"Google direct weather endpoint error: {e}")

        if self.google_maps_key:
            try:
                async with httpx.AsyncClient() as client:
                    if not has_coords:
                        geo_resp = await client.get(
                            "https://maps.googleapis.com/maps/api/geocode/json",
                            params={"address": location, "key": self.google_maps_key},
                            timeout=10
                        )
                        geo_resp.raise_for_status()
                        geo = geo_resp.json()
                        if not geo.get("results"):
                            raise ValueError("Geocoding failed: no results")
                        loc = geo["results"][0]["geometry"]["location"]
                        lat, lon = loc["lat"], loc["lng"]
                    # else we already have lat/lon from input

                    # Use Open-Meteo to get current weather (no key required)
                    om_resp = await client.get(
                        "https://api.open-meteo.com/v1/forecast",
                        params={"latitude": lat, "longitude": lon, "current_weather": True, "hourly": "", "timezone": "UTC"},
                        timeout=10
                    )
                    om_resp.raise_for_status()
                    om = om_resp.json()
                    cw = om.get("current_weather", {})
                    temp = cw.get("temperature")
                    windspeed = cw.get("windspeed")
                    weather = cw.get("weathercode")

                    risks = []
                    if weather in [61, 63, 65, 95, 96, 99]:
                        risks.append("Precipitation expected - risk of waterborne diseases or mosquito breeding")
                    if temp is not None and temp > 35:
                        risks.append(f"High temperature {temp}°C - Stay hydrated")

                    return {
                        "tool": "weather_risks",
                        "status": "success",
                        "location": location,
                        "temp": temp,
                        "windspeed": windspeed,
                        "weather_code": weather,
                        "risks": risks if risks else ["Weather conditions normal"]
                    }
            except Exception as e:
                logger.error(f"Google/Open-Meteo weather error: {e}")

        error_messages = {
            "en": "Could not fetch weather data",
            "hi": "मौसम डेटा प्राप्त नहीं कर सका",
            "ta": "வானிலை தரவை பெற முடியவில்லை",
            "te": "వాతావరణ డేటాను పొందలేకపోయాము"
        }
        return {"tool": "weather_risks", "status": "error", "message": error_messages.get(language, error_messages["en"])}

    async def check_air_quality(self, location: str = "Delhi", language: str = "en", **kwargs) -> Dict:
        # Normalize location: detect lat,lon if provided
        lat = None
        lon = None
        has_coords = False
        if isinstance(location, str) and "," in location:
            parts = [p.strip() for p in location.split(",")]
            if len(parts) >= 2:
                try:
                    lat = float(parts[0])
                    lon = float(parts[1])
                    has_coords = True
                except Exception:
                    has_coords = False

        # Prefer OpenWeather Air Pollution API if available
        if self.openweather_key:
            try:
                async with httpx.AsyncClient() as client:
                    if not has_coords:
                        geo_response = await client.get(
                            "http://api.openweathermap.org/geo/1.0/direct",
                            params={"q": location, "limit": 1, "appid": self.openweather_key},
                            timeout=10
                        )
                        geo_response.raise_for_status()
                        geo_json = geo_response.json()
                        if geo_json:
                            geo_data = geo_json[0]
                            lat, lon = geo_data["lat"], geo_data["lon"]

                    aqi_response = await client.get(
                        "http://api.openweathermap.org/data/2.5/air_pollution",
                        params={"lat": lat, "lon": lon, "appid": self.openweather_key},
                        timeout=10
                    )
                    aqi_response.raise_for_status()
                    aqi_data = aqi_response.json()
                    aqi = aqi_data["list"][0]["main"]["aqi"]
                    components = aqi_data["list"][0]["components"]

                    aqi_labels_translations = {
                        "en": {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"},
                        "hi": {1: "अच्छा", 2: "ठीक", 3: "मध्यम", 4: "खराब", 5: "बहुत खराब"}
                    }
                    
                    health_advice_translations = {
                        "en": {
                            1: "Air quality is good. Enjoy outdoor activities!",
                            2: "Acceptable for most. Sensitive individuals should limit outdoor exertion.",
                            3: "Moderate pollution. Reduce outdoor activities if you have respiratory issues.",
                            4: "Poor air quality. Limit outdoor activities, wear mask outside.",
                            5: "Very poor air quality. Avoid outdoor activities, keep windows closed."
                        },
                        "hi": {
                            1: "वायु गुणवत्ता अच्छी है। बाहरी गतिविधियों का आनंद लें!",
                            2: "अधिकांश के लिए स्वीकार्य। संवेदनशील व्यक्तियों को बाहरी परिश्रम सीमित करना चाहिए।",
                            3: "मध्यम प्रदूषण। श्वसन समस्याएं होने पर बाहरी गतिविधियां कम करें।",
                            4: "खराब वायु गुणवत्ता। बाहरी गतिविधियां सीमित करें, बाहर मास्क पहनें।",
                            5: "बहुत खराब वायु गुणवत्ता। बाहरी गतिविधियों से बचें, खिड़कियां बंद रखें।"
                        }
                    }
                    
                    aqi_labels = aqi_labels_translations.get(language, aqi_labels_translations["en"])
                    health_advice = health_advice_translations.get(language, health_advice_translations["en"])

                    return {
                        "tool": "air_quality",
                        "status": "success",
                        "location": location,
                        "aqi": aqi,
                        "aqi_label": aqi_labels.get(aqi, "Unknown"),
                        "pm2_5": components.get("pm2_5", 0),
                        "pm10": components.get("pm10", 0),
                        "health_advice": health_advice.get(aqi, "Check local advisories"),
                        "language": language
                    }
            except Exception as e:
                logger.error(f"OpenWeather air quality error: {e}")

        # Fallback: use Google Geocoding to get coordinates then Google Air Quality API for air quality data
        # If a direct Google AQI endpoint is configured, try it first
        if self.google_maps_key and self.google_aqi_url:
            try:
                async with httpx.AsyncClient() as client:
                    logger.debug(f"Calling Google AQI endpoint: {self.google_aqi_url} for location: {location}")
                    ga_resp = await client.get(
                        self.google_aqi_url,
                        params={"q": location, "key": self.google_maps_key},
                        timeout=10
                    )
                    ga_resp.raise_for_status()
                    ga = ga_resp.json()
                    # Try to extract common fields
                    aqi = ga.get("aqi") or (ga.get("data") or {}).get("aqi")
                    pm25 = ga.get("pm2_5") or (ga.get("data") or {}).get("pm2_5")
                    pm10 = ga.get("pm10") or (ga.get("data") or {}).get("pm10")

                    aqi_labels_translations = {
                        "en": {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"},
                        "hi": {1: "अच्छा", 2: "ठीक", 3: "मध्यम", 4: "खराब", 5: "बहुत खराब"}
                    }
                    
                    health_advice_translations = {
                        "en": {
                            1: "Air quality is good. Enjoy outdoor activities!",
                            2: "Acceptable for most. Sensitive individuals should limit outdoor exertion.",
                            3: "Moderate pollution. Reduce outdoor activities if you have respiratory issues.",
                            4: "Poor air quality. Limit outdoor activities, wear mask outside.",
                            5: "Very poor air quality. Avoid outdoor activities, keep windows closed."
                        },
                        "hi": {
                            1: "वायु गुणवत्ता अच्छी है। बाहरी गतिविधियों का आनंद लें!",
                            2: "अधिकांश के लिए स्वीकार्य। संवेदनशील व्यक्तियों को बाहरी परिश्रम सीमित करना चाहिए।",
                            3: "मध्यम प्रदूषण। श्वसन समस्याएं होने पर बाहरी गतिविधियां कम करें।",
                            4: "खराब वायु गुणवत्ता। बाहरी गतिविधियां सीमित करें, बाहर मास्क पहनें।",
                            5: "बहुत खराब वायु गुणवत्ता। बाहरी गतिविधियों से बचें, खिड़कियां बंद रखें।"
                        }
                    }
                    
                    aqi_labels = aqi_labels_translations.get(language, aqi_labels_translations["en"])
                    health_advice = health_advice_translations.get(language, health_advice_translations["en"])

                    return {
                        "tool": "air_quality",
                        "status": "success",
                        "location": location,
                        "aqi": aqi,
                        "aqi_label": aqi_labels.get(aqi, "Unknown"),
                        "pm2_5": pm25,
                        "pm10": pm10,
                        "health_advice": health_advice.get(aqi, "Check local advisories"),
                        "source": "google_direct",
                        "language": language
                    }
            except Exception as e:
                logger.error(f"Google direct AQI endpoint error: {e}")

        if self.google_maps_key:
            try:
                async with httpx.AsyncClient() as client:
                    geo_resp = await client.get(
                        "https://maps.googleapis.com/maps/api/geocode/json",
                        params={"address": location, "key": self.google_maps_key},
                        timeout=10
                    )
                    geo_resp.raise_for_status()
                    geo = geo_resp.json()
                    if not geo.get("results"):
                        raise ValueError("Geocoding failed: no results")
                    loc = geo["results"][0]["geometry"]["location"]
                    lat, lon = loc["lat"], loc["lng"]

                    # Try Open-Meteo's air_quality endpoint
                    aq_resp = await client.get(
                        "https://air-quality-api.open-meteo.com/v1/air-quality",
                        params={"latitude": lat, "longitude": lon, "hourly": "pm10,pm2_5", "timezone": "UTC"},
                        timeout=10
                    )
                    if aq_resp.status_code == 200:
                        aq = aq_resp.json()
                        # attempt to extract most recent values
                        try:
                            pm25 = aq.get("hourly", {}).get("pm2_5", [None])[-1]
                            pm10 = aq.get("hourly", {}).get("pm10", [None])[-1]
                        except Exception:
                            pm25 = None
                            pm10 = None

                        # Simple heuristic for AQI label
                        aqi_val = None
                        if pm25 is not None:
                            if pm25 <= 12:
                                aqi_val = 1
                            elif pm25 <= 35.4:
                                aqi_val = 2
                            elif pm25 <= 55.4:
                                aqi_val = 3
                            elif pm25 <= 150.4:
                                aqi_val = 4
                            else:
                                aqi_val = 5

                        aqi_labels_translations = {
                            "en": {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"},
                            "hi": {1: "अच्छा", 2: "ठीक", 3: "मध्यम", 4: "खराब", 5: "बहुत खराब"}
                        }
                        
                        health_advice_translations = {
                            "en": {
                                1: "Air quality is good. Enjoy outdoor activities!",
                                2: "Acceptable for most. Sensitive individuals should limit outdoor exertion.",
                                3: "Moderate pollution. Reduce outdoor activities if you have respiratory issues.",
                                4: "Poor air quality. Limit outdoor activities, wear mask outside.",
                                5: "Very poor air quality. Avoid outdoor activities, keep windows closed."
                            },
                            "hi": {
                                1: "वायु गुणवत्ता अच्छी है। बाहरी गतिविधियों का आनंद लें!",
                                2: "अधिकांश के लिए स्वीकार्य। संवेदनशील व्यक्तियों को बाहरी परिश्रम सीमित करना चाहिए।",
                                3: "मध्यम प्रदूषण। श्वसन समस्याएं होने पर बाहरी गतिविधियां कम करें।",
                                4: "खराब वायु गुणवत्ता। बाहरी गतिविधियां सीमित करें, बाहर मास्क पहनें।",
                                5: "बहुत खराब वायु गुणवत्ता। बाहरी गतिविधियों से बचें, खिड़कियां बंद रखें।"
                            }
                        }
                        
                        aqi_labels = aqi_labels_translations.get(language, aqi_labels_translations["en"])
                        health_advice = health_advice_translations.get(language, health_advice_translations["en"])

                        return {
                            "tool": "air_quality",
                            "status": "success",
                            "location": location,
                            "aqi": aqi_val,
                            "aqi_label": aqi_labels.get(aqi_val, "Unknown"),
                            "pm2_5": pm25,
                            "pm10": pm10,
                            "health_advice": health_advice.get(aqi_val, "Check local advisories"),
                            "language": language
                        }
            except Exception as e:
                logger.error(f"Google/Open-Meteo air quality error: {e}")

        error_messages = {
            "en": "Could not fetch air quality data",
            "hi": "वायु गुणवत्ता डेटा प्राप्त नहीं कर सका",
            "ta": "காற்று தர தரவை பெற முடியவில்லை",
            "te": "గాలి నాణ్యత డేటాను పొందలేకపోయాము"
        }
        return {"tool": "air_quality", "status": "error", "message": error_messages.get(language, error_messages["en"])}

    async def find_nearby_hospitals(self, location: str = "nearby", emergency: bool = False, language: str = "en", **kwargs) -> Dict:

        hospital_names = {
            "en": {
                "government": "Government Hospital",
                "phc": "Primary Health Center (PHC)",
                "chc": "Community Health Center"
            },
            "hi": {
                "government": "सरकारी अस्पताल",
                "phc": "प्राथमिक स्वास्थ्य केंद्र (PHC)",
                "chc": "सामుदायिक स्वास्थ्य केंद्र"
            },
            "ta": {
                "government": "அரசு மருத்துவமனை",
                "phc": "முதன்மை சுகாதார மையம் (PHC)",
                "chc": "சமூக சுகாதார மையம்"
            },
            "te": {
                "government": "ప్రభుత్వ ఆసుపత్రి",
                "phc": "ప్రాథమిక ఆరోగ్య కేంద్రం (PHC)",
                "chc": "సమాజ ఆరోగ్య కేంద్రం"
            },
            "bn": {
                "government": "সরকারি হাসপাতাল",
                "phc": "প্রাথমিক স্বাস্থ্য কেন্দ্র (PHC)",
                "chc": "সামুদায়িক স্বাস্থ্য কেন্দ্র"
            },
            "mr": {
                "government": "सरकारी रुग्णालय",
                "phc": "प्राथमिक आरोग्य केंद्र (PHC)",
                "chc": "सामुदायिक आरोग्य केंद्र"
            },
            "gu": {
                "government": "સરકારી હોસ્પિટલ",
                "phc": "પ્રાથમિક આરોગ્ય કેન્દ્ર (PHC)",
                "chc": "સમુદાય આરોગ્ય કેન્દ્ર"
            },
            "kn": {
                "government": "ಸರ್ಕಾರಿ ಆಸ್ಪತ್ರೆ",
                "phc": "ಪ್ರಾಥಮಿಕ ಆರೋಗ್ಯ ಕೇಂದ್ರ (PHC)",
                "chc": "ಸಮುದಾಯ ಆರೋಗ್ಯ ಕೇಂದ್ರ"
            },
            "ml": {
                "government": "സർക്കാർ ആശുപത്രി",
                "phc": "പ്രാഥമിക ആരോഗ്യ കേന്ദ്രം (PHC)",
                "chc": "സാമൂഹിക ആരോഗ്യ കേന്ദ്രം"
            },
            "pa": {
                "government": "ਸਰਕਾਰੀ ਹਸਪਤਾਲ",
                "phc": "ਪ੍ਰਾਇਮਰੀ ਹੈਲਥ ਸੈਂਟਰ (PHC)",
                "chc": "ਕਮਿਊਨਿਟੀ ਹੈਲਥ ਸੈਂਟਰ"
            }
        }

        advice_messages = {
            "en": "For emergencies, call 108 immediately",
            "hi": "आपातकाल के लिए, तुरंत 108 पर कॉल करें",
            "ta": "அவசரநிலைகளுக்கு, உடனடியாக 108 க்கு அழைக்கவும்",
            "te": "అత్యవసర సందర్భాలలో, వెంటనే 108 కి కాల్ చేయండి",
            "bn": "জরুরী অবস্থার জন্য অবিলম্বে ১০৮ নম্বরে ফোন করুন",
            "mr": "तातडीच्या प्रसंगी १०८ ला फोन करा",
            "gu": "આપાતકાલીન સ્થિતિમાં ૧૦૮ ને ફોન કરો",
            "kn": "ತುರ್ತು ಸಂದರ್ಭದಲ್ಲಿ 108 ಕ್ಕ್ಕೆ ಕರೆ ಮಾಡಿ",
            "ml": "അടിയന്തര ആവശ്യങ്ങൾക്ക് ഉടൻ 108 വിളിക്കുക",
            "pa": "ਐਮਰਜੈਂਸੀ ਲਈ ਤੁਰੰਤ 108 'ਤੇ ਕਾਲ ਕਰੋ"
        }

        names = hospital_names.get(language, hospital_names["en"])

        return {
            "tool": "hospital_finder",
            "status": "success",
            "emergency_number": "108",
            "hospitals": [
                {"name": names["government"], "distance": "2 km", "phone": "108", "type": "Emergency"},
                {"name": names["phc"], "distance": "1 km", "phone": "102", "type": "PHC"},
                {"name": names["chc"], "distance": "3 km", "phone": "104", "type": "CHC"}
            ],
            "advice": advice_messages.get(language, advice_messages["en"]),
            "language": language
        }

    async def get_medicine_info(self, medicine_name: str = "general", language: str = "en", **kwargs) -> Dict:
        """Return medicine query info for LLM to process.
        The LLM will provide comprehensive, accurate medicine information from its knowledge base.
        """
        return {
            "tool": "medicine_info",
            "status": "success",
            "medicine": medicine_name,
            "query_type": "medicine_information",
            "language": language,
            "instruction": f"Provide detailed information about {medicine_name} including uses, dosage, side effects, and warnings. Always include a medical disclaimer."
        }

    async def check_symptoms(self, symptoms: List[str] = None, age: int = None,
                             gender: str = None, duration: str = None, language: str = "en", **kwargs) -> Dict:

        if not symptoms:
            symptoms = ["general discomfort"]

        symptoms_str = " ".join(symptoms).lower()

        # Translations for symptom checker
        translations = {
            "en": {
                "home_care": ["Rest adequately", "Stay hydrated", "Monitor symptoms"],
                "seek_doctor": ["Symptoms worsen", "No improvement in 2-3 days"],
                "conditions": {
                    "fever": "Viral fever / Flu",
                    "respiratory": "Upper respiratory infection / Common cold",
                    "breathing": "Respiratory distress - needs evaluation",
                    "stomach": "Gastroenteritis / Food poisoning",
                    "headache": "Tension headache / Migraine",
                    "rash": "Allergic reaction / Skin condition",
                    "mumps": "Mumps (viral parotitis)",
                    "general": "General illness - monitor symptoms",
                    "chest": "Chest pain - requires immediate evaluation"
                },
                "home_care_items": {
                    "fever": ["Paracetamol for fever (as per dosage)", "Lukewarm sponging", "Light food"],
                    "respiratory": ["Steam inhalation", "Warm water with honey", "Ginger tea"],
                    "stomach": ["ORS solution frequently", "BRAT diet (banana, rice, apple, toast)", "Avoid spicy/oily food", "Small frequent meals"],
                    "headache": ["Rest in dark quiet room", "Cold compress", "Paracetamol if needed"],
                    "rash": ["Avoid scratching", "Calamine lotion", "Antihistamine if needed"],
                    "mumps": ["Complete rest", "Soft foods", "Cold/warm compress on swelling", "Paracetamol for pain/fever", "Isolation for 5 days (contagious)"]
                },
                "seek_doctor_items": {
                    "fever_infant": "Fever in infants - consult doctor immediately",
                    "breathing": "Difficulty breathing - seek immediate help",
                    "stomach": ["Blood in stool/vomit", "Unable to keep fluids down", "Signs of dehydration"],
                    "mumps": ["High fever persists", "Severe headache", "Abdominal pain", "Difficulty swallowing", "Signs of complications"],
                    "dengue": "Get tested immediately - these need proper diagnosis",
                    "chest": "CALL 108 IMMEDIATELY if chest pain with sweating/breathlessness"
                },
                "disclaimer": "This is general guidance only. Not a diagnosis. Please consult a healthcare provider."
            },
            "hi": {
                "home_care": ["पर्याप्त आराम करें", "हाइड्रेटेड रहें", "लक्षणों की निगरानी करें"],
                "seek_doctor": ["लक्षण बिगड़ते हैं", "2-3 दिनों में सुधार नहीं"],
                "conditions": {
                    "fever": "वायरल बुखार / फ्लू",
                    "respiratory": "ऊपरी श्वसन संक्रमण / सामान्य सर्दी",
                    "breathing": "श्वसन संकट - मूल्यांकन की आवश्यकता",
                    "stomach": "गैस्ट्रोएंटेराइटिस / खाद्य विषाक्तता",
                    "headache": "तनाव सिरदर्द / माइग्रेन",
                    "rash": "एलर्जी प्रतिक्रिया / त्वचा की स्थिति",
                    "mumps": "कण्ठमाला (वायरल पैरोटाइटिस)",
                    "general": "सामान्य बीमारी - लक्षणों की निगरानी करें",
                    "chest": "सीने में दर्द - तत्काल मूल्यांकन की आवश्यकता"
                },
                "home_care_items": {
                    "fever": ["बुखार के लिए पैरासिटामोल (खुराक के अनुसार)", "गुनगुने पानी से स्पंज", "हल्का भोजन"],
                    "respiratory": ["भाप लेना", "शहद के साथ गर्म पानी", "अदरक की चाय"],
                    "stomach": ["ओआरएस घोल बार-बार", "BRAT आहार (केला, चावल, सेब, टोस्ट)", "मसालेदार/तेलयुक्त भोजन से बचें", "छोटे-छोटे भोजन"],
                    "headache": ["अंधेरे शांत कमरे में आराम", "ठंडा सेक", "आवश्यकता होने पर पैरासिटामोल"],
                    "rash": ["खुजली से बचें", "कैलामाइन लोशन", "आवश्यकता होने पर एंटीहिस्टामाइन"],
                    "mumps": ["पूर्ण आराम", "नरम भोजन", "सूजन पर ठंडा/गर्म सेक", "दर्द/बुखार के लिए पैरासिटामोल", "5 दिनों के लिए अलगाव (संक्रामक)"]
                },
                "seek_doctor_items": {
                    "fever_infant": "शिशुओं में बुखार - तुरंत डॉक्टर से सलाह लें",
                    "breathing": "सांस लेने में कठिनाई - तुरंत मदद लें",
                    "stomach": ["मल/उल्टी में खून", "तरल पदार्थ नहीं रख सकते", "निर्जलीकरण के लक्षण"],
                    "mumps": ["उच्च बुखार बना रहता है", "गंभीर सिरदर्द", "पेट दर्द", "निगलने में कठिनाई", "जटिलताओं के लक्षण"],
                    "dengue": "तुरंत परीक्षण कराएं - इन्हें उचित निदान की आवश्यकता है",
                    "chest": "सीने में दर्द के साथ पसीना/सांस की तकलीफ होने पर तुरंत 108 पर कॉल करें"
                },
                "disclaimer": "यह केवल सामान्य मार्गदर्शन है। निदान नहीं। कृपया स्वास्थ्य सेवा प्रदाता से परामर्श करें।"
            },
            "ta": {
                "home_care": ["போதுமான ஓய்வு எடுக்கவும்", "நீரேற்றத்துடன் இருக்கவும்", "அறிகுறிகளைக் கண்காணிக்கவும்"],
                "seek_doctor": ["அறிகுறிகள் மோசமடைந்தால்", "2-3 நாட்களில் முன்னேற்றம் இல்லை"],
                "conditions": {
                    "fever": "வைரஸ் காய்ச்சல் / காய்ச்சல்",
                    "respiratory": "ஜலதோஷம்",
                    "breathing": "சுவாசக் கோளாறு",
                    "stomach": "உணவு நச்சு / வயிற்றுப் போக்கு",
                    "headache": "தலைவலி",
                    "rash": "ஒவ்வாமை / தோல் பாதிப்பு",
                    "mumps": "காளான் (வைரஸ் புரோடிடிஸ்)"
                },
                "home_care_items": {
                    "fever": ["காய்ச்சலுக்கு பாராசிட்டமால்", "நிழலில் ஓய்வு", "தண்ணீர் குடிக்கவும்"],
                    "stomach": ["ORS குடிக்கவும்", "லேசான உணவு உட்கொள்ளவும்"]
                },
                "seek_doctor_items": {
                    "fever_infant": "குழந்தைகளுக்கு காய்ச்சல் - உடனடியாக மருத்துவரை அணுகவும்",
                    "breathing": "சுவாசிப்பதில் சிரமம் - உடனடியாக உதவி பெறவும்",
                    "chest": "உடனடியாக 108 ஐ அழைக்கவும்"
                },
                "disclaimer": "இது பொதுவான வழிகாட்டுதல் மட்டுமே."
            },
            "te": {
                "home_care": ["తగినంత విశ్రాంతి తీసుకోండి", "ఎక్కువగా నీరు తాగండి"],
                "seek_doctor": ["లక్షణాలు తీవ్రమైతే", "2-3 రోజుల్లో మెరుగుదల లేకపోతే"],
                "conditions": {
                    "fever": "వైరల్ జ్వరం / ఫ్లూ",
                    "respiratory": "జలుబు",
                    "breathing": "శ్వాస తీసుకోవడంలో ఇబ్బంది",
                    "stomach": "గ్యాస్ట్రోఎంటెరిటిస్",
                    "headache": "తలనొప్పి",
                    "rash": "అలర్జీ",
                    "mumps": "గవదబిళ్ళలు"
                },
                "home_care_items": {
                    "fever": ["జ్వరం కోసం పారాసిటమాల్", "విశ్రాంతి"],
                    "stomach": ["ORS తాగండి", "తేలికపాటి ఆహారం"]
                },
                "seek_doctor_items": {
                    "fever_infant": "శిశువుల్లో జ్వరం - వెంటనే డాక్టర్ను సంప్రదించండి",
                    "breathing": "శ్వాస తీసుకోవడంలో ఇబ్బంది - వెంటనే సహాయం కోరండి",
                    "chest": "வெంటనే 108 కి కాల్ చేయండి"
                },
                "disclaimer": "ఇది కేవలం సాధారణ మార్గదర్శకం మాత్రమే."
            },
            "bn": {
                "home_care": ["পর্যাপ্ত বিশ্রাম নিন", "পর্যাপ্ত জল পান করুন"],
                "seek_doctor": ["লক্ষণগুলি খারাপ হলে"],
                "conditions": {
                    "fever": "ভাইরাল জ্বর",
                    "respiratory": "সর্দি-কাশি",
                    "breathing": "শ্বাসকষ্ট",
                    "stomach": "পেটের সমস্যা",
                    "headache": "মাথাব্যাথা",
                    "rash": "চুলকানি / র‍্যাশ",
                    "mumps": "মাম্পস"
                },
                "home_care_items": {
                    "fever": ["জ্বরের জন্য প্যারাসিটামল", "বিশ্রাম", "হালকা খাবার"],
                    "stomach": ["ওআরএস পান করুন", "হালকা খাবার"]
                },
                "seek_doctor_items": {
                    "fever_infant": "শিশুদের জ্বর - অবিলম্বে ডাক্তার দেখান",
                    "breathing": "শ্বাসকষ্ট - অবিলম্বে সাহায্য নিন",
                    "chest": "অবিলম্বে ১০৮ নম্বরে ফোন করুন"
                },
                "disclaimer": "এটি শুধুমাত্র সাধারণ নির্দেশিকা।"
            },
            "mr": {
                "home_care": ["विश्रांती घ्या", "पुरेसे पाणी प्या"],
                "seek_doctor": ["लक्षणांत सुधारणा न झाल्यास"],
                "conditions": {
                    "fever": "व्हायरल ताप",
                    "respiratory": "सर्दी-खोकला",
                    "breathing": "श्वास घेण्यास त्रास",
                    "stomach": "पोटाच्या तक्रारी",
                    "headache": "डोकेदुखी",
                    "rash": "त्वचेची समस्या / खाज",
                    "mumps": "गालगुंड"
                },
                "home_care_items": {
                    "fever": ["तापासाठी पॅरासिटामॉल", "विश्रांती", "हलका आहार"],
                    "stomach": ["ओआरएस प्या", "मसालेदार आहार टाळा"]
                },
                "seek_doctor_items": {
                    "fever_infant": "लहान मुलांमध्ये ताप - त्वरित डॉक्टरांना भेटा",
                    "breathing": "श्वास घेण्यास त्रास - त्वरित मदत घ्या",
                    "chest": "तातडीने १०८ ला फोन करा"
                },
                "disclaimer": "हे केवळ सामान्य मार्गदर्शन आहे."
            },
            "gu": {
                "home_care": ["આરામ કરો", "વધારે પાણી પીવો"],
                "seek_doctor": ["સુધારો ન જણાય તો"],
                "conditions": {
                    "fever": "વાયરલ તાવ",
                    "respiratory": "શરદી-ઉધરસ",
                    "breathing": "શ્વાસમાં તકલીફ",
                    "stomach": "પેટની તકલીફ",
                    "headache": "માથાનો દુખાવો",
                    "rash": "ખંજવાળ",
                    "mumps": "ગાલપચોળિયું"
                },
                "home_care_items": {
                    "fever": ["તાવ માટે પેરાસીટામોલ", "આરામ"],
                    "stomach": ["ઓઆરએસ પીવો", "હળવો ખોરાક"]
                },
                "seek_doctor_items": {
                    "fever_infant": "નાના બાળકોમાં તાવ - તરત જ ડોક્ટરને બતાવો",
                    "breathing": "શ્વાસ લેવામાં તકલીફ - તરત મદદ લો",
                    "chest": "તરત જ ૧૦૮ ને ફોન કરો"
                },
                "disclaimer": "આ માત્ર સામાન્ય માર્ગદર્શન છે."
            },
            "kn": {
                "home_care": ["ವಿಶ್ರಾಂತಿ ಪಡೆಯಿರಿ", "ಹೆಚ್ಚು ನೀರು ಕುಡಿಯಿರಿ"],
                "seek_doctor": ["ಸುಧಾರಣೆ ಇಲ್ಲದಿದ್ದರೆ"],
                "conditions": {
                    "fever": "ವೈರಲ್ ಜ್ವರ",
                    "respiratory": "ಶೀತ",
                    "breathing": "ಉಸಿರಾಟದ ತೊಂದರೆ",
                    "stomach": "ಹೊಟ್ಟೆಯ ಸಮಸ್ಯೆ",
                    "headache": "ತಲೆನೋವು",
                    "rash": "ಚರ್ಮದ ಸಮಸ್ಯೆ",
                    "mumps": "ಕೆಪ್ಪಟೆ ರೋಗ"
                },
                "home_care_items": {
                    "fever": ["ಜ್ವರಕ್ಕೆ ಪ್ಯಾರಸಿಟಮೋಲ್", "ವಿಶ್ರಾಂತಿ"],
                    "stomach": ["ಓಆರ್‌ಎಸ್ ಕುಡಿಯಿರಿ", "ಲಘು ಆಹಾರ"]
                },
                "seek_doctor_items": {
                    "fever_infant": "ಮಕ್ಕಳಲ್ಲಿ ಜ್ವರ - ತಕ್ಷಣ ವೈದ್ಯರನ್ನು ಭೇಟಿ ಮಾಡಿ",
                    "breathing": "ಉಸಿರಾಟದಲ್ಲಿ ತೊಂದರೆ - ತಕ್ಷಣ ಸಹಾಯ ಪಡೆಯಿರಿ",
                    "chest": "ತಕ್ಷಣ 108 ಕ್ಕ್ಕೆ ಕರೆ ಮಾಡಿ"
                },
                "disclaimer": "ಇದು ಕೇವલ ಸಾಮಾನ್ಯ ಮಾರ್ಗದರ್ಶನ."
            },
            "ml": {
                "home_care": ["വിശ്രമിക്കുക", "ധാരാളം വെള്ളം കുടിക്കുക"],
                "seek_doctor": ["കുറഞ്ഞില്ലെങ്കിൽ"],
                "conditions": {
                    "fever": "പനി",
                    "respiratory": "ജലദോഷം",
                    "breathing": "ശ്വാസതടസ്സം",
                    "stomach": "വയറുവേദന",
                    "headache": "തലവേദന",
                    "rash": "ചുമപ്പ് / ചൊറിച്ചിൽ",
                    "mumps": "തലമുട്ടി പനി"
                },
                "home_care_items": {
                    "fever": ["പനിക്കായി പാരസിറ്റമോൾ", "വിശ്രമം"],
                    "stomach": ["ORS ലായനി കുടിക്കുക", "ലഘു ഭക്ഷണം"]
                },
                "seek_doctor_items": {
                    "fever_infant": "കുട്ടികളിലെ പനി - ഉടൻ ഡോക്ടറെ കാണുക",
                    "breathing": "ശ്വാസതടസ്സം - ഉടൻ സഹായം തേടുക",
                    "chest": "ഉടൻ 108 വിളിക്കുക"
                },
                "disclaimer": "ഇത് പൊതുവായ അറിവിലേക്കായി മാത്രമുള്ളതാണ്."
            },
            "pa": {
                "home_care": ["ਆਰਾਮ ਕਰੋ", "ਤਰਲ ਪਦਾਰਥ ਲਓ"],
                "seek_doctor": ["ਸੁਧਾਰ ਨਾ ਹੋਣ ਤੇ"],
                "conditions": {
                    "fever": "ਬੁਖ਼ਾਰ",
                    "respiratory": "ਜ਼ੁਕਾਮ",
                    "breathing": "ਸਾਹ ਦੀ ਤਕਲੀਫ",
                    "stomach": "ਪੇਟ ਵਿੱਚ ਤਕਲੀਫ",
                    "headache": "ਸਿਰਦਰਦ",
                    "rash": "ਖਾਰਿਸ਼",
                    "mumps": "ਗਲ਼ਪੇੜੇ"
                },
                "home_care_items": {
                    "fever": ["ਬੁਖ਼ਾਰ ਲਈ ਪੈਰਾਸੀਟਾਮੋਲ", "ਆਰਾਮ"],
                    "stomach": ["ਓਆਰਐਸ", "ਹਲਕਾ ਭੋਜਨ"]
                },
                "seek_doctor_items": {
                    "fever_infant": "ਬੱਚਿਆਂ ਵਿੱਚ ਬੁਖ਼ਾਰ - ਤੁਰੰਤ ਡਾਕਟਰ ਨੂੰ ਮਿਲੋ",
                    "breathing": "ਸਾਹ ਦੀ ਤકલીਫ - ਤੁਰੰਤ ਮਦਦ ਲਓ",
                    "chest": "ਤੁਰੰਤ 108 'ਤੇ ਕਾਲ ਕਰੋ"
                },
                "disclaimer": "ਇਹ ਸਿਰਫ ਆਮ ਜਾਣਕਾਰੀ ਹੈ।"
            }
        }

        t = translations.get(language, translations["en"])

        conditions = []
        severity = "mild"
        urgent = False
        home_care = t["home_care"].copy()
        seek_doctor = t["seek_doctor"].copy()

        if any(s in symptoms_str for s in ["fever", "temperature", "bukhar", "taap", "jwar", "buxar", "kaaychal", "juram", "jwaryam", "panne", "ਤਾਪ"]):
            conditions.append(t["conditions"]["fever"])
            home_care.extend(t["home_care_items"].get("fever", []))
            if age and age < 2:
                severity = "moderate"
                seek_doctor.insert(0, t["seek_doctor_items"]["fever_infant"])
                urgent = True

        if any(s in symptoms_str for s in ["cough", "cold", "khansi", "zukam", "sardi", "sneeze", "irumal", "daggu", "kashi", "khokla", "udharas", "kemmu", "chuma", "khang"]):
            conditions.append(t["conditions"]["respiratory"])
            home_care.extend(t["home_care_items"].get("respiratory", []))

        if any(s in symptoms_str for s in ["breathing", "saans", "breathless", "wheeze", "asthma", "suwas", "mouch", "shwas", "moocha"]):
            conditions.append(t["conditions"]["breathing"])
            severity = "severe"
            urgent = True
            seek_doctor.insert(0, t["seek_doctor_items"]["breathing"])

        if any(s in symptoms_str for s in ["vomiting", "ulti", "nausea", "diarrhea", "loose motion",
                                           "dast", "stomach", "pet dard", "acidity", "pet", "vayiru", "kadupu", "pot", "hotte", "vayar"]):
            conditions.append(t["conditions"]["stomach"])
            severity = "moderate"
            home_care = t["home_care_items"].get("stomach", []).copy()
            seek_doctor.extend(t["seek_doctor_items"].get("stomach", []))

        if any(s in symptoms_str for s in ["headache", "head pain", "sir dard", "migraine", "sar dard", "thalai vali", "thalanopi", "mathabyatha", "dokhedukhi"]):
            conditions.append(t["conditions"]["headache"])
            home_care.extend(t["home_care_items"].get("headache", []))

        if any(s in symptoms_str for s in ["rash", "itching", "khujli", "skin", "allergy", "hives", "sori", "durada", "khaj", "khujali"]):
            conditions.append(t["conditions"]["rash"])
            home_care.extend(t["home_care_items"].get("rash", []))

        if any(s in symptoms_str for s in ["mumps", "swelling jaw", "parotid", "gland swelling", "kan ke neeche", "ponniveekam", "galamuti"]):
            conditions = [t["conditions"]["mumps"]]
            severity = "moderate"
            home_care = t["home_care_items"].get("mumps", []).copy()
            seek_doctor = t["seek_doctor_items"].get("mumps", [t["seek_doctor"][0]]).copy()

        if any(s in symptoms_str for s in ["dengue", "malaria", "chikungunya", "typhoid"]):
            severity = "moderate"
            urgent = True
            seek_doctor.insert(0, t["seek_doctor_items"].get("dengue", "Seek medical evaluation"))

        if any(s in symptoms_str for s in ["chest pain", "seene mein dard", "heart", "dil"]):
            conditions = [t["conditions"]["chest"]]
            severity = "severe"
            urgent = True
            seek_doctor = [t["seek_doctor_items"]["chest"]]

        if not conditions:
            conditions = [t["conditions"]["general"]]

        return {
            "tool": "symptom_checker",
            "status": "success",
            "reported_symptoms": symptoms,
            "patient_age": age,
            "possible_conditions": conditions,
            "severity": severity,
            "urgent_attention_needed": urgent,
            "home_care_advice": home_care,
            "when_to_see_doctor": seek_doctor,
            "emergency_number": "108" if urgent else None,
            "disclaimer": t["disclaimer"],
            "language": language
        }

    async def get_first_aid(self, emergency_type: str = "general", language: str = "en", **kwargs) -> Dict:

        first_aid_translations = {
            "en": {
                "burn": {
                    "title": "Burn First Aid",
                    "steps": [
                        "1. Cool under running water for 10-20 minutes",
                        "2. Remove jewelry/tight items before swelling",
                        "3. Do NOT apply ice, butter, toothpaste, or oil",
                        "4. Cover loosely with clean, non-stick bandage",
                        "5. Take paracetamol for pain if needed"
                    ],
                    "seek_help_if": "Large area, face/hands/joints, deep burn, child/elderly"
                },
                "cut": {
                    "title": "Cut/Wound First Aid",
                    "steps": [
                        "1. Wash hands before treating",
                        "2. Apply firm pressure with clean cloth",
                        "3. Keep pressure for 10-15 minutes",
                        "4. Clean wound with clean water",
                        "5. Apply antiseptic and sterile bandage"
                    ],
                    "seek_help_if": "Deep cut, won't stop bleeding, dirty wound, face injury"
                },
                "choking": {
                    "title": "Choking First Aid",
                    "steps": [
                        "1. Ask 'Are you choking?' - if can't speak, act fast",
                        "2. Call for help/108",
                        "3. Give 5 firm back blows between shoulder blades",
                        "4. If not cleared, 5 abdominal thrusts (Heimlich)",
                        "5. Repeat back blows and thrusts until cleared"
                    ],
                    "seek_help_if": "Person becomes unconscious, breathing doesn't resume"
                },
                "snake_bite": {
                    "title": "Snake Bite First Aid",
                    "steps": [
                        "1. Keep calm, limit movement",
                        "2. Remove jewelry before swelling",
                        "3. Keep bitten area below heart level",
                        "4. Do NOT cut, suck, or apply tourniquet",
                        "5. Get to hospital IMMEDIATELY - antivenom needed"
                    ],
                    "seek_help_if": "ALL snake bites need immediate hospital care"
                },
                "fracture": {
                    "title": "Fracture First Aid",
                    "steps": [
                        "1. Do not move the injured area",
                        "2. Immobilize with splint/padding",
                        "3. Apply ice pack wrapped in cloth",
                        "4. Do NOT try to realign bone",
                        "5. Seek medical help immediately"
                    ],
                    "seek_help_if": "All suspected fractures need X-ray"
                },
                "cpr": {
                    "title": "CPR (Cardiopulmonary Resuscitation)",
                    "steps": [
                        "1. Check responsiveness and breathing",
                        "2. Call 108 immediately",
                        "3. Give 30 hard and fast chest compressions",
                        "4. Give 2 rescue breaths (if trained)",
                        "5. Repeat until medical help arrives or AED arrives"
                    ],
                    "seek_help_if": "Person is unresponsive and not breathing"
                },
                "general": {
                    "title": "General Emergency First Aid",
                    "steps": [
                        "1. Stay calm and assess situation",
                        "2. Call 108 for emergencies",
                        "3. Do not move person if spinal injury suspected",
                        "4. Check breathing and consciousness",
                        "5. Keep person warm and comfortable"
                    ]
                }
            },
            "hi": {
                "burn": {
                    "title": "जलने की प्राथमिक चिकित्सा",
                    "steps": [
                        "1. 10-20 मिनट तक बहते पानी के नीचे ठंडा करें",
                        "2. सूजन से पहले गहने/तंग वस्तुएं हटाएं",
                        "3. बर्फ, मक्खन, टूथपेस्ट या तेल न लगाएं",
                        "4. साफ, नॉन-स्टिक पट्टी से ढीला ढकें",
                        "5. आवश्यकता होने पर दर्द के लिए पैरासिटामोल लें"
                    ]
                },
                "cut": {
                    "title": "कट/घाव की प्राथमिक चिकित्सा",
                    "steps": ["1. उपचार से पहले हाथ धोएं", "2. साफ कपड़े से दबाव डालें", "3. घाव को साफ करें"]
                },
                "snake_bite": {
                    "title": "सांप के काटने की प्राथमिक चिकित्सा",
                    "steps": ["1. शांत रहें", "2. तुरंत अस्पताल जाएं"]
                },
                "cpr": {
                    "title": "सीपीआर (CPR)",
                    "steps": ["1. 108 पर कॉल करें", "2. छाती दबाएं"]
                },
                "general": {
                    "title": "सामान्य आपातकालीन प्राथमिक चिकित्सा",
                    "steps": ["1. शांत रहें", "2. 108 पर कॉल करें"]
                }
            },
            "ta": {
                "burn": {
                    "title": "தீக்காய முதலுதவி",
                    "steps": ["1. 10-20 நிமிடம் குளிர்ந்த நீரில் வைக்கவும்", "2. நகைகளை அகற்றவும்"]
                },
                "cut": {
                    "title": "காய முதலுதவி",
                    "steps": ["1. கையை கழுவவும்", "2. அழுத்தவும்"]
                },
                "snake_bite": {
                    "title": "பாம்பு கடி முதலுதவி",
                    "steps": ["1. அசையாமல் இருக்கவும்", "2. மருத்துவமனைக்கு செல்லவும்"]
                },
                "cpr": {
                    "title": "சிபிஆர் (CPR)",
                    "steps": ["1. 108 ஐ அழைக்கவும்", "2. அழுத்தவும்"]
                },
                "general": {
                    "title": "பொது முதலுதவி",
                    "steps": ["1. நிதானமாக இருங்கள்", "2. 108 ஐ அழைக்கவும்"]
                }
            },
            "te": {
                "burn": {
                    "title": "కాలిన గాయాలకు ప్రథమ చికిత్స",
                    "steps": ["1. 10-20 నిమిషాలు నీటి కింద ఉంచండి"]
                },
                "cut": {
                    "title": "గాయాలకు ప్రథమ చికిత్స",
                    "steps": ["1. చేతులు కడగాలి", "2. నొక్కాలి"]
                },
                "snake_bite": {
                    "title": "పాము కాటుకు ప్రథమ చికిత్స",
                    "steps": ["1. కదలకుండా ఉండాలి", "2. వెంటనే ఆసుపత్రికి వెళ్ళాలి"]
                },
                "cpr": {
                    "title": "CPR విధానం",
                    "steps": ["1. 108 కి కాల్ చేయండి", "2. గుండెపై నొక్కండి"]
                },
                "general": {
                    "title": "సాధారణ ప్రథమ చికిత్స",
                    "steps": ["1. ప్రశాంతంగా ఉండండి", "2. 108 కి కాల్ చేయండి"]
                }
            },
            "bn": {
                "burn": {
                    "title": "পুড়ে যাওয়ার প্রাথমিক চিকিৎসা",
                    "steps": ["1. ১০-২০ মিনিট ঠান্ডা জলে ভেজান"]
                },
                "cut": {
                    "title": "কেটে যাওয়ার প্রাথমিক চিকিৎসা",
                    "steps": ["1. হাত ধুয়ে নিন", "2. চেপে ধরুন"]
                },
                "snake_bite": {
                    "title": "সাপের কামড়ের প্রাথমিক চিকিৎসা",
                    "steps": ["1. শান্ত থাকুন", "2. দ্রুত হাসপাতালে যান"]
                },
                "cpr": {
                    "title": "সিপিআর (CPR)",
                    "steps": ["1. ১০৮ নম্বরে ফোন করুন", "2. বুকে চাপ দিন"]
                },
                "general": {
                    "title": "সাধারণ প্রাথমিক চিকিৎসা",
                    "steps": ["1. শান্ত থাকুন", "2. ১০৮ নম্বরে ফোন করুন"]
                }
            },
            "mr": {
                "burn": {
                    "title": "भाजल्यावर प्राथमिक उपचार",
                    "steps": ["1. १०-२० मिनिटे थंड पाण्याखाली धरा"]
                },
                "cut": {
                    "title": "जखमेवर प्राथमिक उपचार",
                    "steps": ["1. दाब द्या", "2. जखम स्वच्छ करा"]
                },
                "snake_bite": {
                    "title": "सर्पदंश प्राथमिक उपचार",
                    "steps": ["1. शांत रहा", "2. दवाखान्यात जा"]
                },
                "cpr": {
                    "title": "सीपीआर (CPR)",
                    "steps": ["1. १०८ ला फोन करा", "2. छाती दाबा"]
                },
                "general": {
                    "title": "सामान्य प्राथमिक उपचार",
                    "steps": ["1. शांत रहा", "2. १०८ ला फोन करा"]
                }
            },
            "gu": {
                "burn": {
                    "title": "દાઝવા પર પ્રાથમિક સારવાર",
                    "steps": ["1. ઠંડા પાણી નીચે રાખો"]
                },
                "cut": {
                    "title": "ઘા પર પ્રાથમિક સારવાર",
                    "steps": ["1. કપડાથી દબાવો"]
                },
                "snake_bite": {
                    "title": "સાપ કરડવા પર પ્રાથમિક સારવાર",
                    "steps": ["1. શાંત રહો", "2. હોસ્પિટલ જાઓ"]
                },
                "cpr": {
                    "title": "સીપીઆર (CPR)",
                    "steps": ["1. ૧૦૮ ને ફોન કરો", "2. છાતી પર દબાવો"]
                },
                "general": {
                    "title": "સામાન્ય પ્રાથમિક સારવાર",
                    "steps": ["1. શાંત રહો", "2. ૧૦૮ ને ફોન કરો"]
                }
            },
            "kn": {
                "burn": {
                    "title": "ಸುಟ್ಟ ಗಾಯಗಳಿಗೆ ಪ್ರಥಮ ಚಿಕಿತ್ಸೆ",
                    "steps": ["1. 10-20 ನಿಮಿಷ ತಣ್ಣೀರಿನಲ್ಲಿ ಇರಿಸಿ"]
                },
                "cut": {
                    "title": "ಗಾಯಗಳಿಗೆ ಪ್ರಥమ ಚಿಕিತ್ಸೆ",
                    "steps": ["1. ಒತ್ತಿ ಹಿಡಿಯಿರಿ"]
                },
                "snake_bite": {
                    "title": "ಹಾವು കಡಿತಕ್ಕೆ ಪ್ರಥಮ ಚಿಕಿತ್ಸೆ",
                    "steps": ["1. ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ"]
                },
                "cpr": {
                    "title": "ಸಿಪಿಆರ್ (CPR)",
                    "steps": ["1. 108 ಕ್ಕ್ಕೆ ಕರೆ ಮಾಡಿ", "2. ಒತ್ತಿರಿ"]
                },
                "general": {
                    "title": "ಸಾಮಾನ್ಯ ಪ್ರಥಮ ಚಿಕಿತ್ಸೆ",
                    "steps": ["1. 108 ಕ್ಕ್ಕೆ ಕರೆ ಮಾಡಿ"]
                }
            },
            "ml": {
                "burn": {
                    "title": "പൊള്ളലേറ്റാൽ ചെയ്യേണ്ടത്",
                    "steps": ["1. വെള്ളത്തിനടിയിൽ വയ്ക്കുക"]
                },
                "cut": {
                    "title": "മുറിവുകൾക്ക് ചെയ്യേണ്ടത്",
                    "steps": ["1. അമർത്തി പിടിക്കുക"]
                },
                "snake_bite": {
                    "title": "പാമ്പ് കടിയേറ്റാൽ",
                    "steps": ["1. ആശുപത്രിയിൽ എത്തിക്കുക"]
                },
                "cpr": {
                    "title": "സിപിആർ (CPR)",
                    "steps": ["1. 108 വിളിക്കുക", "2. അമർത്തുക"]
                },
                "general": {
                    "title": "പൊതുവായ പ്രഥമശുശ്രൂഷ",
                    "steps": ["1. 108 വിളിക്കുക"]
                }
            },
            "pa": {
                "burn": {
                    "title": "ਸੜ ਜਾਣ 'ਤੇ ਮੁਢਲੀ ਸਹਾਇਤਾ",
                    "steps": ["1. ਠੰਡੇ ਪਾਣੀ ਹੇਠ ਰੱਖੋ"]
                },
                "cut": {
                    "title": "ਜ਼ਖਮ ਲਈ ਮੁਢਲੀ ਸਹਾਇਤਾ",
                    "steps": ["1. ਦਬਾਓ"]
                },
                "snake_bite": {
                    "title": "ਸੱਪ ਦੇ ਕੱਟਣ 'ਤੇ",
                    "steps": ["1. ਹਸਪਤਾਲ ਜਾਓ"]
                },
                "cpr": {
                    "title": "ਸੀਪੀਆਰ (CPR)",
                    "steps": ["1. 108 'ਤੇ ਕਾਲ ਕਰੋ", "2. ਦਬਾਓ"]
                },
                "general": {
                    "title": "ਆਮ ਮੁਢਲੀ ਸਹਾਇਤਾ",
                    "steps": ["1. 108 'ਤੇ ਕਾਲ ਕਰੋ"]
                }
            }
        }

        first_aid_db = first_aid_translations.get(language, first_aid_translations["en"])

        emergency_lower = emergency_type.lower()
        selected_info = first_aid_db.get("general")

        for key, info in first_aid_db.items():
            if key in emergency_lower or emergency_lower in key:
                selected_info = info
                break
        
        emergency_numbers = {
            "en": {"Ambulance": "108", "Police": "100", "Fire": "101"},
            "hi": {"एम्बुलेंस": "108", "पुलिस": "100", "अग्नि": "101"},
            "ta": {"ஆம்புலன்ஸ்": "108", "காவல்துறை": "100"},
            "te": {"అంబులెన్స్": "108", "పోలీసు": "100"},
            "bn": {"অ্যাম্বুলেন্স": "108", "পুলিশ": "100"},
            "mr": {"रुग्णवाहिका": "108", "पोलीस": "100"},
            "gu": {"એમ્બ્યુલન્સ": "108", "પોલીસ": "100"},
            "kn": {"ಅಂಬ್ಯುಲೆನ್ಸ್": "108", "ಪొलीस": "100"},
            "ml": {"ആംബുലൻസ്": "108", "പോലീസ്": "100"},
            "pa": {"ਐਂਬੂਲੈਂਸ": "108", "ਪੁਲਿਸ": "100"}
        }
        
        nums = emergency_numbers.get(language, emergency_numbers["en"])
        
        return {
            "title": selected_info["title"],
            "steps": selected_info["steps"],
            "seek_now": selected_info.get("seek_help_if", "Seek professional help if condition persists"),
            "emergency_contacts": nums
        }

    async def get_nutrition_advice(self, query: str = "general", health_condition: str = None, **kwargs) -> Dict:

        condition_advice = {}
        if health_condition:
            condition_lower = health_condition.lower()
            if "diabetes" in condition_lower or "sugar" in condition_lower:
                condition_advice = {
                    "condition": "Diabetes",
                    "eat": ["Whole grains", "Green vegetables", "Bitter gourd", "Fenugreek"],
                    "avoid": ["White rice/bread", "Sweets", "Sugary drinks", "Potato"],
                    "tips": ["Eat at regular times", "Small frequent meals", "Check sugar regularly"]
                }
            elif "bp" in condition_lower or "pressure" in condition_lower:
                condition_advice = {
                    "condition": "High Blood Pressure",
                    "eat": ["Fruits", "Vegetables", "Low-fat dairy", "Whole grains"],
                    "avoid": ["Salt/namak", "Pickles", "Papad", "Processed food"],
                    "tips": ["Limit salt to 1 teaspoon/day", "Exercise regularly"]
                }

        return {
            "tool": "nutrition",
            "status": "success",
            "query": query,
            "condition_specific": condition_advice if condition_advice else None,
            "general_advice": {
                "balanced_plate": "Half vegetables, quarter protein, quarter grains",
                "daily_essentials": ["Green leafy vegetables", "Seasonal fruits", "Dal/legumes",
                                    "Whole grains (roti, brown rice)", "Milk/curd"],
                "hydration": "8-10 glasses of water daily"
            }
        }

    async def check_vaccination_schedule(self, age_months: int = 12, child_name: str = None, language: str = "en", **kwargs) -> Dict:

        schedule = [
            (0, ["BCG", "Hepatitis B (birth)", "OPV 0"]),
            (6, ["OPV 1", "Pentavalent 1", "Rotavirus 1", "PCV 1", "IPV 1"]),
            (10, ["OPV 2", "Pentavalent 2", "Rotavirus 2"]),
            (14, ["OPV 3", "Pentavalent 3", "Rotavirus 3", "PCV 2", "IPV 2"]),
            (36, ["IPV Booster"]),
            (40, ["MR 1 (Measles-Rubella)", "JE 1", "Vitamin A"]),
            (64, ["MR 2", "JE 2", "DPT Booster 1", "OPV Booster"]),
        ]

        translations = {
            "en": {
                "no_vaccines": "No vaccines due currently",
                "check_doctor": "Check with doctor",
                "where_to_go": ["Nearest Anganwadi", "PHC", "Government Hospital"],
                "important": "Vaccination is FREE under Universal Immunization Programme"
            },
            "hi": {
                "no_vaccines": "वर्तमान में कोई टीके देय नहीं",
                "check_doctor": "डॉक्टर से जांच कराएं",
                "where_to_go": ["नजदीकी आंगनवाड़ी", "PHC", "सरकारी अस्पताल"],
                "important": "यूनिवर्सल इम्यूनाइजेशन प्रोग्राम के तहत टीकाकरण मुफ्त है"
            },
            "ta": {
                "no_vaccines": "தற்போது தடுப்பூசிகள் கடமைப்படுத்தப்படவில்லை",
                "check_doctor": "மருத்துவருடன் சரிபார்க்கவும்",
                "where_to_go": ["அருகிலுள்ள அங்கன்வாடி", "PHC", "அரசு மருத்துவமனை"],
                "important": "உலகளாவிய தடுப்பூசி திட்டத்தின் கீழ் தடுப்பூசி இலவசம்"
            },
            "te": {
                "no_vaccines": "ప్రస్తుతం టీకాలు కాలేదు",
                "check_doctor": "వైద్యుడితో తనిఖీ చేయండి",
                "where_to_go": ["సమీప అంగనవాడి", "PHC", "ప్రభుత్వ ఆసుపత్రి"],
                "important": "యూనివర్సల్ ఇమ్యూనైజేషన్ ప్రోగ్రామ్ కింద టీకా ఉచితం"
            },
            "bn": {
                "no_vaccines": "বর্তমানে কোনো টিকা বাকি নেই",
                "check_doctor": "ডাক্তারের সাথে কথা বলুন",
                "where_to_go": ["নিকটস্থ অঙ্গনওয়াড়ি", "পিএইচসি", "সরকারি হাসপাতাল"],
                "important": "ইউনিভার্সাল ইমিউনাইজেশন প্রোগ্রামের অধীনে টিকাকরণ বিনামূল্যে"
            },
            "mr": {
                "no_vaccines": "सध्या कोणतेही लसीकरण बाकी नाही",
                "check_doctor": "डॉक्टरांशी संपर्क साधा",
                "where_to_go": ["जवळपासची अंगणवाडी", "PHC", "सरकारी रुग्णालय"],
                "important": "सार्वत्रिक लसीकरण कार्यक्रमांतर्गत लसीकरण मोफत आहे"
            },
            "gu": {
                "no_vaccines": "હાલમાં કોઈ રસીકરણ બાકી નથી",
                "check_doctor": "ડોક્ટરને બતાવો",
                "where_to_go": ["નજીકની આંગણવાડી", "PHC", "સરકારી હોસ્પિટલ"],
                "important": "સાર્વત્રિક રસીકરણ કાર્યક્રમ હેઠળ રસીકરણ મફત છે"
            },
            "kn": {
                "no_vaccines": "ಪ್ರಸ್ತುತ ಯಾವುದೇ ಲಸಿಕೆ ಬಾಕಿ ಇಲ್ಲ",
                "check_doctor": "ವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಿ",
                "where_to_go": ["ಹತ್ತಿರದ ಅಂಗನವಾಡಿ", "PHC", "ಸರ್ಕಾರಿ ಆಸ್ಪತ್ರೆ"],
                "important": "ಸಾರ್ವತ್ರಿಕ ಲಸಿಕಾ ಕಾರ್ಯಕ್ರಮದ ಅಡಿಯಲ್ಲಿ ಲಸಿಕೆ ಉಚಿತವಾಗಿದೆ"
            },
            "ml": {
                "no_vaccines": "നിലവിൽ വാക്സിനുകളൊന്നും ബാക്കിയില്ല",
                "check_doctor": "ഡോക്ടറെ കാണുക",
                "where_to_go": ["അടുത്തുള്ള അങ്കണവാടി", "PHC", "സർക്കാർ ആശുപത്രി"],
                "important": "സാർവത്രിക രോഗപ്രതിരോധ പരിപാടിയിലൂടെ വാക്സിനേഷൻ സൗജന്യമാണ്"
            },
            "pa": {
                "no_vaccines": "ਫਿਲਹਾਲ ਕੋਈ ਟੀਕਾਕਰਨ ਬਾਕੀ ਨਹੀਂ ਹੈ",
                "check_doctor": "ਡਾਕਟਰ ਨਾਲ ਗੱਲ ਕਰੋ",
                "where_to_go": ["ਨੇੜਲੀ ਆਂਗਣਵਾੜੀ", "PHC", "ਸਰਕਾਰੀ ਹਸਪਤਾਲ"],
                "important": "ਯੂਨੀਵਰਸਲ ਇਮੂਨਾਈਜ਼ੇਸ਼ਨ ਪ੍ਰੋਗਰਾਮ ਦੇ ਤਹਿਤ ਟੀਕਾਕਰਨ ਮੁਫਤ ਹੈ"
            },
            "ta": {
                "no_vaccines": "தற்போது தடுப்பூசிகள் கடமைப்படுத்தப்படவில்லை",
                "check_doctor": "மருத்துவருடன் சரிபார்க்கவும்",
                "where_to_go": ["அருகிலுள்ள அங்கன்வாடி", "PHC", "அரசு மருத்துவமனை"],
                "important": "உலகளாவிய தடுப்பூசி திட்டத்தின் கீழ் தடுப்பூசி இலவசம்"
            },
            "te": {
                "no_vaccines": "ప్రస్తుతం టీకాలు కాలేదు",
                "check_doctor": "వైద్యుడితో తనిఖీ చేయండి",
                "where_to_go": ["సమీప అంగనవాడి", "PHC", "ప్రభుత్వ ఆసుపత్రి"],
                "important": "యూనివర్సల్ ఇమ్యూనైజేషన్ ప్రోగ్రామ్ కింద టీకా ఉచితం"
            }
        }

        due_now = []
        upcoming = []

        for age_week, vaccines in schedule:
            if age_months - 2 <= age_week <= age_months + 2:
                due_now.extend(vaccines)
            elif age_months + 2 < age_week <= age_months + 8:
                upcoming.extend(vaccines)

        t = translations.get(language, translations["en"])

        return {
            "tool": "vaccination",
            "status": "success",
            "child_name": child_name,
            "age_months": age_months,
            "due_now": due_now if due_now else [t["no_vaccines"]],
            "upcoming": upcoming[:5] if upcoming else [t["check_doctor"]],
            "where_to_go": t["where_to_go"],
            "important": t["important"],
            "language": language
        }

    async def get_lab_test_info(self, test_name: str = "general", **kwargs) -> Dict:

        test_db = {
            "cbc": {
                "full_name": "Complete Blood Count",
                "purpose": "Overall health check, detect infections, anemia",
                "preparation": "Usually no fasting required",
                "cost_range": "₹200-500"
            },
            "blood sugar": {
                "full_name": "Blood Glucose Test",
                "purpose": "Screen/monitor diabetes",
                "preparation": "Fasting: No food for 8-12 hours",
                "normal": "Fasting: 70-100 mg/dL",
                "cost_range": "₹50-200"
            }
        }

        test_lower = test_name.lower()
        for key, info in test_db.items():
            if key in test_lower:
                return {"tool": "lab_test_info", "status": "success", "test": test_name, **info}

        return {
            "tool": "lab_test_info",
            "status": "success",
            "test": test_name,
            "message": "Consult doctor for specific test details"
        }

    async def mental_health_support(self, concern: str = "general", language: str = "en", **kwargs) -> Dict:
        translations = {
            "en": {
                "message": "Your mental health matters. It's okay to seek help.",
                "helplines": [
                    {"name": "iCall", "number": "9152987821", "hours": "Mon-Sat, 8am-10pm"},
                    {"name": "Vandrevala Foundation", "number": "1860-2662-345", "hours": "24/7"},
                    {"name": "NIMHANS", "number": "080-46110007", "hours": "24/7"}
                ],
                "self_care": ["Talk to someone you trust", "Maintain regular sleep", "Physical activity helps"],
                "crisis_message": "If having thoughts of self-harm, please call a helpline immediately."
            },
            "hi": {
                "message": "आपका मानसिक स्वास्थ्य महत्वपूर्ण है। मदद मांगना ठीक है।",
                "helplines": [{"name": "iCall", "number": "9152987821"}, {"name": "NIMHANS", "number": "080-46110007"}],
                "self_care": ["किसी भरोसेमंद से बात करें", "नियमित नींद लें"],
                "crisis_message": "यदि खुद को नुकसान पहुंचाने के विचार आ रहे हैं, तो तुरंत हेल्पलाइन पर कॉल करें।"
            },
            "ta": { "message": "உங்கள் மனநலம் முக்கியமானது. உதவி கேட்க தயங்காதீர்கள்." },
            "te": { "message": "మీ మానసిక ఆరోగ్యం ముఖ్యం. సహాయం కోరడం తప్పు కాదు." },
            "bn": { "message": "আপনার মানসিক স্বাস্থ্য গুরুত্বপূর্ণ। সাহায্য চাইতে দ্বিধা করবেন না।" },
            "mr": { "message": "तुमचे मानसिक आरोग्य महत्त्वाचे आहे. मदत मागायला संकोच करू नका." },
            "gu": { "message": "તમારું માનસિક સ્વાસ્થ્ય મહત્વપૂર્ણ છે. મદદ માંગવી યોગ્ય છે." },
            "kn": { "message": "ನಿಮ್ಮ ಮಾನಸಿಕ ಆರೋಗ್ಯ ಮುಖ್ಯ. ಸಹಾಯ ಕೇಳಲು ಹಿಂಜರಿಯಬೇಡಿ." },
            "ml": { "message": "നിങ്ങളുടെ മാനസികാരോഗ്യം പ്രധാനമാണ്. സഹായം ചോദിക്കാൻ മടിക്കരുത്." },
            "pa": { "message": "ਤੁਹਾਡੀ ਮਾਨਸਿਕ ਸਿਹਤ ਮਹੱਤਵਪੂਰਨ ਹੈ। ਮਦਦ ਮੰਗਣੀ ਸਹੀ ਹੈ।" }
        }
        
        t = translations.get(language, translations["en"])
        return {
            "tool": "mental_health",
            "status": "success",
            "message": t.get("message"),
            "helplines": t.get("helplines", translations["en"]["helplines"]),
            "self_care": t.get("self_care", translations["en"]["self_care"]),
            "crisis_message": t.get("crisis_message", translations["en"]["crisis_message"]),
            "language": language
        }

    async def find_anganwadi(self, location: str = "nearby", language: str = "en", **kwargs) -> Dict:
        translations = {
            "en": {
                "services": ["Free vaccination", "Nutrition supplements", "Growth monitoring", "Pre-school education"],
                "eligibility": ["Children 0-6 years", "Pregnant women", "Nursing mothers"],
                "how_to_find": ["Ask local ASHA worker", "Contact nearest PHC", "Call 104"]
            },
            "hi": {
                "services": ["मुफ्त टीकाकरण", "पोषण पूरक", "विकास की निगरानी"],
                "eligibility": ["0-6 वर्ष के बच्चे", "गर्भवती महिलाएं", "धात्री माताएं"],
                "how_to_find": ["स्थानीय आशा कार्यकर्ता से पूछें", "104 पर कॉल करें"]
            }
        }
        
        t = translations.get(language, translations["en"])
        return {
            "tool": "anganwadi_finder",
            "status": "success",
            "services": t["services"],
            "eligibility": t["eligibility"],
            "how_to_find": t["how_to_find"],
            "timing": "Usually 9 AM - 1 PM on weekdays",
            "language": language
        }

    async def pregnancy_care(self, trimester: int = None, concern: str = None, language: str = "en", **kwargs) -> Dict:
        translations = {
            "en": {
                "essential_care": ["At least 4 antenatal visits", "Iron-Folic Acid tablets daily", "TT injections"],
                "warning_signs": ["Heavy bleeding", "Severe headache", "High fever", "Reduced baby movement"],
                "emergency": "Call 102/108 for pregnancy emergencies"
            },
            "hi": {
                "essential_care": ["कम से कम 4 प्रसव पूर्व जांच", "आयरन-फोलिक एसिड की गोलियां", "टीटी इंजेक्शन"],
                "warning_signs": ["भारी रक्तस्राव", "तेज सिरदर्द", "तेज बुखार", "बच्चे की कम हलचल"],
                "emergency": "गर्भावस्था आपातकाल के लिए 102/108 पर कॉल करें"
            }
        }
        
        t = translations.get(language, translations["en"])
        return {
            "tool": "pregnancy_care",
            "status": "success",
            "essential_care": t["essential_care"],
            "warning_signs": t["warning_signs"],
            "free_services": ["Janani Suraksha Yojana - cash assistance", "Free delivery at govt hospitals"],
            "emergency": t["emergency"],
            "language": language
        }

class IntelligentOrchestrator:

    def __init__(self, llm_client, model: str):

        self.groq_client = llm_client
        self.groq_model = model
        self.tools = HealthServiceTools()
        self._gemini_chat = None
        self._tool_map = {
            "symptoms": self.tools.check_symptoms,
            "medicine": self.tools.get_medicine_info,
            "hospital": self.tools.find_nearby_hospitals,
            "first_aid": self.tools.get_first_aid,
            "vaccination": self.tools.check_vaccination_schedule,
            "nutrition": self.tools.get_nutrition_advice,
            "mental_health": self.tools.mental_health_support,
            "weather": self.tools.check_weather_risks,
            "air_quality": self.tools.check_air_quality,
            "anganwadi": self.tools.find_anganwadi,
            "lab_test": self.tools.get_lab_test_info,
            "pregnancy": self.tools.pregnancy_care,
            "general": self.tools.check_symptoms,
        }

    # Prompt used to ask Gemini to classify intent and extract simple entities/symptoms.
    # Request language detection (ISO code) so downstream LLMs can respond in the user's language.
    CLASSIFICATION_PROMPT = (
        "You are a lightweight intent and language classifier for a health assistant. "
        "Given the user message below, respond ONLY with a JSON object containing the following keys:\n"
        "- intent: one of [symptoms, medicine, hospital, first_aid, vaccination, nutrition, lab_test, weather, air_quality, anganwadi, pregnancy, general, menu_selection]\n"
        "- symptoms: an array of symptom keywords (Normalize to standard English terms, e.g., 'stomach pain' for 'pet dard' or 'oet dard')\n"
        "- medicine_name: string if the user asks about a medicine, else empty string\n"
        "- location: string if present, else empty string\n"
        "- language: the detected language code (e.g., en, hi, ta)\n"
        "- confidence: a numeric confidence score 0-1 (optional)\n"
        "- menu_option: if intent is menu_selection, the option number as a string\n"
        "IMPORTANT: If the message is ONLY a single digit (0-10), treat it as a menu_selection intent with menu_option = the digit. Do NOT treat it as a symptom.\n"
        "Make the JSON compact and parseable, with keys exactly as specified. Do NOT include any extra text. "
        "User message: \"{message}\""
    )

    def _get_gemini_model(self):

        if self._gemini_chat is None:
            import google.generativeai as genai
            from app.config.settings import settings

            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._gemini_chat = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 300,
                }
            )

            logger.info(f"Initialized Gemini classifier with model: {settings.GEMINI_MODEL}")

        return self._gemini_chat

    async def _classify_with_gemini(self, message: str) -> Dict:

        try:
            model = self._get_gemini_model()
            prompt = self.CLASSIFICATION_PROMPT.format(message=message)

            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(prompt)
            )

            result_text = response.text.strip()

            if result_text.startswith("```"):
                lines = result_text.split("\n")
                result_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
                result_text = result_text.strip()
            if result_text.startswith("json"):
                result_text = result_text[4:].strip()

            # Try multiple parsing strategies to handle slightly malformed model output
            classification = None
            try:
                classification = json.loads(result_text)
            except json.JSONDecodeError:
                # Attempt to extract JSON substring between first { and last }
                try:
                    start = result_text.index('{')
                    end = result_text.rindex('}')
                    candidate = result_text[start:end+1]
                    classification = json.loads(candidate)
                except Exception:
                    # Try Python literal eval (handles single quotes / python dicts)
                    try:
                        classification = ast.literal_eval(result_text)
                        if not isinstance(classification, dict):
                            classification = None
                    except Exception:
                        classification = None

            # If still None, try a relaxed replacement of single->double quotes and remove trailing commas
            if classification is None:
                try:
                    cleaned = re.sub(r"'(\\s*):", '"\\1":', result_text)
                except Exception:
                    cleaned = result_text
                # Replace single quotes with double quotes as a last resort
                cleaned = cleaned.replace("'", '"')
                # Remove trailing commas before closing braces/brackets
                cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
                try:
                    classification = json.loads(cleaned)
                except Exception:
                    classification = None

            if not isinstance(classification, dict):
                logger.error(f"JSON parse error: could not decode classification, response: {result_text[:200]}")
                return {"intent": "symptoms", "symptoms": [message], "language": "en"}

            # Ensure we have a dict with required keys and sensible defaults
            if "language" not in classification or not classification.get("language"):
                # Try to infer simple language from characters as a fallback
                sample = message[:100]
                if any('\u0900' <= ch <= '\u097F' for ch in sample):
                    classification["language"] = "hi"
                elif any('\u0B80' <= ch <= '\u0BFF' for ch in sample) or any('\u0C00' <= ch <= '\u0C7F' for ch in sample):
                    classification["language"] = "te"
                else:
                    classification["language"] = "en"

            # Normalize some fields
            classification.setdefault("symptoms", [message])
            classification.setdefault("medicine_name", "")
            classification.setdefault("location", "")
            logger.info(f"Gemini classification: {classification}")
            return classification

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}, response: {result_text[:200]}")
            return {"intent": "symptoms", "symptoms": [message]}
        except Exception as e:
            logger.error(f"Gemini classification error: {e}")
            return {"intent": "symptoms", "symptoms": [message]}

    async def _execute_tool(self, intent: str, params: Dict, user_location: Dict = None, language: str = "en") -> Dict:

        tool_func = self._tool_map.get(intent, self.tools.check_symptoms)

        try:
            if intent == "symptoms":
                symptoms = params.get("symptoms", [])
                if not symptoms and "message" in params:
                    symptoms = [params["message"]]

                age = params.get("age")
                if params.get("is_child") and not age:
                    age = 5

                result = await tool_func(symptoms=symptoms, age=age, gender=params.get("gender"), language=language)

            elif intent == "medicine":
                result = await tool_func(medicine_name=params.get("medicine_name", "general"), language=language)

            elif intent == "hospital":
                result = await tool_func(
                    location=params.get("location", "nearby"),
                    emergency=params.get("urgency") == "high",
                    language=language
                )

            elif intent == "first_aid":
                result = await tool_func(emergency_type=params.get("emergency_type", "general"), language=language)

            elif intent == "vaccination":
                age = params.get("age", 12)

                if age and age < 20:
                    age_months = age if age > 12 else age * 4
                else:
                    age_months = age if age else 12
                result = await tool_func(age_months=age_months, child_name=params.get("child_name"), language=language)

            elif intent == "nutrition":
                result = await tool_func(
                    query=params.get("query", "general"),
                    health_condition=params.get("health_condition"),
                    language=language
                )

            elif intent == "lab_test":
                result = await tool_func(test_name=params.get("test_name", "general"), language=language)

            elif intent in ["weather", "air_quality"]:
                # Prefer explicit location from LLM classification; otherwise use user's saved location
                loc_param = params.get("location") if params.get("location") else None
                if loc_param and isinstance(loc_param, str) and loc_param.strip():
                    location_value = loc_param.strip()
                else:
                    location_value = None
                    if user_location:
                        city = user_location.get("city")
                        lat = user_location.get("latitude")
                        lon = user_location.get("longitude")
                        if city:
                            location_value = city
                        elif lat and lon:
                            try:
                                location_value = f"{float(lat)},{float(lon)}"
                            except Exception:
                                location_value = None

                if not location_value:
                    location_value = "Delhi" if intent == "air_quality" else "India"

                result = await tool_func(location=location_value, language=language)

            elif intent == "anganwadi":
                result = await tool_func(location=params.get("location", "nearby"), language=language)

            elif intent == "pregnancy":
                result = await tool_func(trimester=params.get("trimester"), concern=params.get("concern"), language=language)

            elif intent == "mental_health":
                result = await tool_func(concern=params.get("concern", "general"), language=language)

            else:
                result = await tool_func(**{k: v for k, v in params.items() if v is not None}, language=language)

            return result

        except Exception as e:
            logger.error(f"Tool execution error ({intent}): {e}")
            error_messages = {
                "en": f"Error executing {intent} tool: {str(e)}",
                "hi": f"{intent} उपकरण निष्पादित करने में त्रुटि: {str(e)}",
                "ta": f"{intent} கருவியை இயக்குவதில் பிழை: {str(e)}",
                "te": f"{intent} సాధనం అమలు చేయడంలో లోపం: {str(e)}"
            }
            return {"tool": intent, "status": "error", "message": error_messages.get(language, error_messages["en"])}

    async def _generate_response_with_groq(self, user_message: str, tool_result: Dict,
                                           language: str, user_location: Dict) -> str:

        lang_names = {
            "en": "English",
            "hi": "Hindi",
            "ta": "Tamil",
            "te": "Telugu",
            "bn": "Bengali",
            "mr": "Marathi",
            "gu": "Gujarati",
            "kn": "Kannada",
            "ml": "Malayalam",
            "pa": "Punjabi"
        }
        lang_name = lang_names.get(language, "English")

        # Build prompts dynamically so we include the tool output and language instruction
        try:
            system_prompt = (
                "You are Jeevo, a concise and empathetic medical assistant for rural India. "
                f"IMPORTANT: You MUST respond ONLY in {lang_name} language. "
                f"Use the tool output provided to craft a short, actionable response in {lang_name}. "
                "All text, including tool outputs, should be translated and presented in the user's language. "
                "Always include a brief disclaimer and next steps. Keep it under 400 tokens. "
                f"DO NOT use English unless the user's language is English. Respond entirely in {lang_name}."
            )

            # Summarize the tool result into the user prompt for context
            try:
                tool_summary = json.dumps(tool_result, ensure_ascii=False)
            except Exception:
                tool_summary = str(tool_result)

            user_prompt = (
                f"User said: {user_message}\n\n"
                f"Tool result: {tool_summary}\n\n"
                f"Please provide a clear, empathetic medical response in {lang_name}."
            )

            response = self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=400
            )

            try:
                return response.choices[0].message.content
            except Exception:
                return getattr(response.choices[0].message, 'content', str(response))

        except Exception as e:
            logger.error(f"Groq response generation error: {e}")
            return self._format_fallback(tool_result, language)

    def _format_fallback(self, result: Dict, language: str) -> str:

        tool = result.get("tool", "unknown")
        lines = []

        if tool == "symptom_checker":
            lines.append("🏥 *Health Assessment*\n")
            if result.get("possible_conditions"):
                lines.append("Possible: " + ", ".join(result["possible_conditions"][:2]))
            if result.get("home_care_advice"):
                lines.append("\nCare: " + ", ".join(result["home_care_advice"][:3]))
            if result.get("urgent_attention_needed"):
                lines.append("\n⚠️ Please seek medical help!")

        elif tool == "medicine_info":
            lines.append(f"💊 *{result.get('medicine', 'Medicine')}*")
            if result.get("uses"):
                lines.append(f"Uses: {result['uses']}")
            if result.get("dosage"):
                lines.append(f"Dosage: {result['dosage']}")

        elif tool == "hospital_finder":
            lines.append("🏥 Emergency: Call 108")

        elif tool == "mental_health":
            lines.append("🤝 You're not alone. Help is available.")
            if result.get("helplines"):
                lines.append(f"Call: {result['helplines'][0]['number']}")

        lines.append("\n⚠️ Please consult a doctor for medical advice.")
        return "\n".join(lines)

    async def process_with_tools(self, user_message: str, language: str, user_location: Dict = None) -> str:

        if user_location is None:
            user_location = {"city": "Unknown", "state": ""}

        try:
            # Check if message is a menu option (just a number 0-10)
            candidate = user_message.strip().lower()
            
            # Deterministic mapping for standard menu options and keywords to avoid LLM hallucinations
            intent_map = {
                "1": "symptoms", "one": "symptoms", "ek": "symptoms", "symptom check": "symptoms", "check symptoms": "symptoms", "bimaari": "symptoms", "symptoms": "symptoms", "lakshan": "symptoms",
                "2": "first_aid", "two": "first_aid", "do": "first_aid", "first aid": "first_aid", "emergency": "first_aid", "madad": "first_aid", "help": "first_aid", "bachao": "first_aid",
                "3": "vaccination", "three": "vaccination", "teen": "vaccination", "vaccine": "vaccination", "teekakaran": "vaccination", "tikakaran": "vaccination", "tika": "vaccination",
                "4": "hospital", "four": "hospital", "chaar": "hospital", "char": "hospital", "hospitals": "hospital", "clinic": "hospital", "aspataal": "hospital", "aspatal": "hospital", "dawakhana": "hospital", "doctor": "hospital",
                "5": "weather", "five": "weather", "paanch": "weather", "panch": "weather", "weather risk": "weather", "mausam": "weather", "barish": "weather",
                "6": "medicine", "six": "medicine", "che": "medicine", "chhe": "medicine", "medicine info": "medicine", "dawaii": "medicine", "dawa": "medicine", "goli": "medicine",
                "7": "pregnancy", "seven": "pregnancy", "saat": "pregnancy", "pregnancy care": "pregnancy", "garbhavastha": "pregnancy", "pregnant": "pregnancy",
                "8": "anganwadi", "eight": "anganwadi", "aath": "anganwadi", "anganwadi center": "anganwadi", "anganwadi": "anganwadi",
                "9": "mental_health", "nine": "mental_health", "nau": "mental_health", "no": "mental_health", "mental health": "mental_health", "stress": "mental_health", "tanaav": "mental_health",
                "10": "weather", "ten": "weather", "das": "weather"
            }

            intent = None
            # Check for exact matches first
            if candidate in intent_map:
                intent = intent_map[candidate]
                logger.info(f"Deterministic intent detected: {intent} from '{candidate}'")
                classification = {"intent": intent, "language": language}
            else:
                s_lower = candidate.lower()
                # Check for partial matches
                for key, val in intent_map.items():
                    if len(key) > 3 and key in s_lower: # Avoid matching short numbers inside unrelated text
                        intent = val
                        logger.info(f"Deterministic intent detected (partial): {intent} from '{candidate}'")
                        classification = {"intent": intent, "language": language}
                        break
            
            if not intent:
                logger.info(f"Processing message with Gemini: {user_message[:50]}... in language: {language}")
                classification = await self._classify_with_gemini(user_message)
                intent = classification.get("intent", "symptoms")
                logger.info(f"Gemini detected intent: {intent}")

            tool_result = await self._execute_tool(intent, classification, user_location=user_location, language=language)
            logger.info(f"Tool '{intent}' executed, status: {tool_result.get('status')}")

            response = await self._generate_response_with_groq(
                user_message, tool_result, language, user_location
            )
            return response

        except Exception as e:
            logger.error(f"Orchestrator error: {e}", exc_info=True)
            error_messages = {
                "en": "🙏 I apologize, I encountered an issue. Please try again or call 104 (Health Helpline) for assistance.",
                "hi": "🙏 मुझे खेद है, मुझे एक समस्या आई। कृपया पुनः प्रयास करें या 104 (स्वास्थ्य हेल्पलाइन) पर कॉल करें।",
                "ta": "🙏 மன்னிக்கவும், ஒரு சிக்கல் ஏற்பட்டது. தயவுசெய்து மீண்டும் முயற்சிக்கவும் அல்லது 104 (சுகாதார உதவி வரி) அழைக்கவும்।",
                "te": "🙏 క్షమించండి, నాకు సమస్య ఎదురైంది. దయచేసి మళ్లీ ప్రయత్నించండి లేదా 104 (ఆరోగ్య హెల్ప్‌లైన్) కి కాల్ చేయండి।",
                "bn": "🙏 আমি দুঃখিত, একটি সমস্যা হয়েছে। অনুগ্রহ করে আবার চেষ্টা করুন বা 104 (স্বাস্থ্য হেল্পলাইন) কল করুন।",
                "mr": "🙏 माफ करा, मला एक समस्या आली. कृपया पुन्हा प्रयत्न करा किंवा 104 (आरोग्य हेल्पलाइन) कॉल करा.",
                "gu": "🙏 માફ કરો, મને એક સમસ્યા આવી. કૃપા કરીને ફરીથી પ્રયાસ કરો અથવા 104 (સ્વાસ્થ્ય હેલ્પલાઇન) પર કૉલ કરો.",
                "kn": "🙏 ಕ್ಷಮಿಸಿ, ನನಗೆ ಸಮಸ್ಯೆ ಸಂಭವಿಸಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ ಅಥವಾ 104 (ಆರೋಗ್ಯ ಹೆಲ್ಪ್ಲೈನ್) ಗೆ ಕರೆ ಮಾಡಿ.",
                "ml": "🙏 ക്ഷമിക്കണം, എനിക്ക് ഒരു പ്രശ്നം ഉണ്ടായി. ദയവായി വീണ്ടും ശ്രമിക്കുക അല്ലെങ്കിൽ 104 (ആരോഗ്യ ഹെൽപ്പ്‌ലൈൻ) എന്നതിലേക്ക് കോൾ ചെയ്യുക.",
                "pa": "🙏 ਮਾਫ਼ ਕਰੋ, ਮੈਨੂੰ ਇੱਕ ਸਮੱਸਿਆ ਆਈ। ਕਿਰਪਾ ਕਰਕੇ ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ ਜਾਂ 104 (ਸਿਹਤ ਹੈਲਪਲਾਈਨ) 'ਤੇ ਕਾਲ ਕਰੋ।"
            }
            return error_messages.get(language, error_messages["en"])

orchestrator = None

def get_orchestrator(llm_client, model: str):

    global orchestrator
    if orchestrator is None:
        orchestrator = IntelligentOrchestrator(llm_client, model)
    return orchestrator