
import json
import ast
import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import httpx
import asyncio

logger = logging.getLogger(__name__)

# Medical RAG integration
try:
    from app.services.medical_rag_service import get_medical_rag_service
    MEDICAL_RAG_AVAILABLE = True
    logger.info("✅ Medical RAG service available")
except ImportError as e:
    logger.warning(f"⚠️ Medical RAG not available: {e}")
    MEDICAL_RAG_AVAILABLE = False

class HealthServiceTools:

    def __init__(self):
        from app.config.settings import settings
        self.openweather_key = settings.OPENWEATHER_API_KEY
        self.google_maps_key = settings.GOOGLE_MAPS_API_KEY
        # Optional: if your Google key exposes weather/aqi endpoints, configure URLs in settings
        self.google_weather_url = getattr(settings, "GOOGLE_WEATHER_API_URL", None)
        self.google_aqi_url = getattr(settings, "GOOGLE_AQI_API_URL", None)

    async def check_weather_risks(self, location: str = "India", **kwargs) -> Dict:
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

                    if weather in ["Rain", "Thunderstorm"]:
                        risks.append("Heavy rainfall - Risk of dengue/malaria from stagnant water")
                    if temp > 35:
                        risks.append(f"High temperature {temp}°C - Stay hydrated, avoid sun")
                    if humidity > 80:
                        risks.append("High humidity - Risk of fungal infections")

                    return {
                        "tool": "weather_risks",
                        "status": "success",
                        "location": location,
                        "temp": temp,
                        "humidity": humidity,
                        "weather": weather,
                        "risks": risks if risks else ["Weather conditions normal"]
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

        return {"tool": "weather_risks", "status": "error", "message": "Could not fetch weather data"}

    async def check_air_quality(self, location: str = "Delhi", **kwargs) -> Dict:
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

                    aqi_labels = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}
                    health_advice = {
                        1: "Air quality is good. Enjoy outdoor activities!",
                        2: "Acceptable for most. Sensitive individuals should limit outdoor exertion.",
                        3: "Moderate pollution. Reduce outdoor activities if you have respiratory issues.",
                        4: "Poor air quality. Limit outdoor activities, wear mask outside.",
                        5: "Very poor air quality. Avoid outdoor activities, keep windows closed."
                    }

                    return {
                        "tool": "air_quality",
                        "status": "success",
                        "location": location,
                        "aqi": aqi,
                        "aqi_label": aqi_labels.get(aqi, "Unknown"),
                        "pm2_5": components.get("pm2_5", 0),
                        "pm10": components.get("pm10", 0),
                        "health_advice": health_advice.get(aqi, "Check local advisories")
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

                    aqi_labels = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}
                    health_advice = {
                        1: "Air quality is good. Enjoy outdoor activities!",
                        2: "Acceptable for most. Sensitive individuals should limit outdoor exertion.",
                        3: "Moderate pollution. Reduce outdoor activities if you have respiratory issues.",
                        4: "Poor air quality. Limit outdoor activities, wear mask outside.",
                        5: "Very poor air quality. Avoid outdoor activities, keep windows closed."
                    }

                    return {
                        "tool": "air_quality",
                        "status": "success",
                        "location": location,
                        "aqi": aqi,
                        "aqi_label": aqi_labels.get(aqi, "Unknown"),
                        "pm2_5": pm25,
                        "pm10": pm10,
                        "health_advice": health_advice.get(aqi, "Check local advisories"),
                        "source": "google_direct"
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

                        aqi_labels = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}
                        health_advice = {
                            1: "Air quality is good. Enjoy outdoor activities!",
                            2: "Acceptable for most. Sensitive individuals should limit outdoor exertion.",
                            3: "Moderate pollution. Reduce outdoor activities if you have respiratory issues.",
                            4: "Poor air quality. Limit outdoor activities, wear mask outside.",
                            5: "Very poor air quality. Avoid outdoor activities, keep windows closed."
                        }

                        return {
                            "tool": "air_quality",
                            "status": "success",
                            "location": location,
                            "aqi": aqi_val,
                            "aqi_label": aqi_labels.get(aqi_val, "Unknown"),
                            "pm2_5": pm25,
                            "pm10": pm10,
                            "health_advice": health_advice.get(aqi_val, "Check local advisories")
                        }
            except Exception as e:
                logger.error(f"Google/Open-Meteo air quality error: {e}")

        return {"tool": "air_quality", "status": "error", "message": "Could not fetch air quality data"}

    async def find_nearby_hospitals(self, location: str = "nearby", emergency: bool = False, **kwargs) -> Dict:

        return {
            "tool": "hospital_finder",
            "status": "success",
            "emergency_number": "108",
            "hospitals": [
                {"name": "Government Hospital", "distance": "2 km", "phone": "108", "type": "Emergency"},
                {"name": "Primary Health Center (PHC)", "distance": "1 km", "phone": "102", "type": "PHC"},
                {"name": "Community Health Center", "distance": "3 km", "phone": "104", "type": "CHC"}
            ],
            "advice": "For emergencies, call 108 immediately"
        }

    async def get_medicine_info(self, medicine_name: str = "general", **kwargs) -> Dict:

        medicine_db = {
            "paracetamol": {
                "names": ["Crocin", "Dolo", "Calpol"],
                "uses": "Fever, headache, body pain",
                "dosage": "Adults: 500-1000mg every 4-6 hours (max 4g/day). Children: 10-15mg/kg",
                "side_effects": "Rare: liver issues with overdose",
                "warnings": "Do not exceed recommended dose. Avoid alcohol."
            },
            "ibuprofen": {
                "names": ["Brufen", "Combiflam"],
                "uses": "Pain, inflammation, fever",
                "dosage": "Adults: 200-400mg every 4-6 hours",
                "side_effects": "Stomach upset, ulcers with prolonged use",
                "warnings": "Take with food. Not for children under 12."
            },
            "ors": {
                "names": ["Electral", "ORS"],
                "uses": "Dehydration, diarrhea, vomiting",
                "dosage": "Dissolve 1 packet in 1 liter clean water. Sip frequently.",
                "side_effects": "None when used correctly",
                "warnings": "Use clean water only. Discard after 24 hours."
            },
            "azithromycin": {
                "names": ["Azee", "Zithromax"],
                "uses": "Bacterial infections (respiratory, skin, ear)",
                "dosage": "As prescribed by doctor - usually 500mg once daily for 3 days",
                "side_effects": "Nausea, diarrhea, stomach pain",
                "warnings": "Complete full course. Prescription required."
            },
            "cetirizine": {
                "names": ["Zyrtec", "Alerid"],
                "uses": "Allergies, cold symptoms, itching",
                "dosage": "Adults: 10mg once daily",
                "side_effects": "Drowsiness",
                "warnings": "Avoid driving if drowsy"
            }
        }

        med_lower = medicine_name.lower().strip()
        for key, info in medicine_db.items():
            if med_lower in key or any(med_lower in n.lower() for n in info.get("names", [])):
                return {
                    "tool": "medicine_info",
                    "status": "success",
                    "medicine": medicine_name,
                    **info,
                    "disclaimer": "Always consult a doctor before taking medicines."
                }

        return {
            "tool": "medicine_info",
            "status": "success",
            "medicine": medicine_name,
            "message": "Please consult a doctor or pharmacist for specific medicine information",
            "general_advice": "Never self-medicate with antibiotics. Follow prescription.",
            "disclaimer": "Always consult a doctor before taking medicines."
        }

    async def check_symptoms(self, symptoms: List[str] = None, age: int = None,
                             gender: str = None, duration: str = None, **kwargs) -> Dict:

        if not symptoms:
            symptoms = ["general discomfort"]

        symptoms_str = " ".join(symptoms).lower()

        conditions = []
        severity = "mild"
        urgent = False
        home_care = ["Rest adequately", "Stay hydrated", "Monitor symptoms"]
        seek_doctor = ["Symptoms worsen", "No improvement in 2-3 days"]

        if any(s in symptoms_str for s in ["fever", "temperature", "bukhar", "taap", "jwar", "buxar"]):
            conditions.append("Viral fever / Flu")
            home_care.extend(["Paracetamol for fever (as per dosage)", "Lukewarm sponging", "Light food"])
            if age and age < 2:
                severity = "moderate"
                seek_doctor.insert(0, "Fever in infants - consult doctor immediately")
                urgent = True

        if any(s in symptoms_str for s in ["cough", "cold", "khansi", "zukam", "sardi", "sneeze"]):
            conditions.append("Upper respiratory infection / Common cold")
            home_care.extend(["Steam inhalation", "Warm water with honey", "Ginger tea"])

        if any(s in symptoms_str for s in ["breathing", "saans", "breathless", "wheeze", "asthma"]):
            conditions.append("Respiratory distress - needs evaluation")
            severity = "severe"
            urgent = True
            seek_doctor.insert(0, "Difficulty breathing - seek immediate help")

        if any(s in symptoms_str for s in ["vomiting", "ulti", "nausea", "diarrhea", "loose motion",
                                           "dast", "stomach", "pet dard", "acidity", "pet"]):
            conditions.append("Gastroenteritis / Food poisoning")
            severity = "moderate"
            home_care = ["ORS solution frequently", "BRAT diet (banana, rice, apple, toast)",
                        "Avoid spicy/oily food", "Small frequent meals"]
            seek_doctor.extend(["Blood in stool/vomit", "Unable to keep fluids down", "Signs of dehydration"])

        if any(s in symptoms_str for s in ["headache", "head pain", "sir dard", "migraine", "sar dard"]):
            conditions.append("Tension headache / Migraine")
            home_care.extend(["Rest in dark quiet room", "Cold compress", "Paracetamol if needed"])

        if any(s in symptoms_str for s in ["rash", "itching", "khujli", "skin", "allergy", "hives"]):
            conditions.append("Allergic reaction / Skin condition")
            home_care.extend(["Avoid scratching", "Calamine lotion", "Antihistamine if needed"])

        if any(s in symptoms_str for s in ["mumps", "swelling jaw", "parotid", "gland swelling", "kan ke neeche"]):
            conditions = ["Mumps (viral parotitis)"]
            severity = "moderate"
            home_care = ["Complete rest", "Soft foods", "Cold/warm compress on swelling",
                        "Paracetamol for pain/fever", "Isolation for 5 days (contagious)"]
            seek_doctor = ["High fever persists", "Severe headache", "Abdominal pain",
                         "Difficulty swallowing", "Signs of complications"]

        if any(s in symptoms_str for s in ["dengue", "malaria", "chikungunya", "typhoid"]):
            severity = "moderate"
            urgent = True
            seek_doctor.insert(0, "Get tested immediately - these need proper diagnosis")

        if any(s in symptoms_str for s in ["chest pain", "seene mein dard", "heart", "dil"]):
            conditions = ["Chest pain - requires immediate evaluation"]
            severity = "severe"
            urgent = True
            seek_doctor = ["CALL 108 IMMEDIATELY if chest pain with sweating/breathlessness"]

        if not conditions:
            conditions = ["General illness - monitor symptoms"]

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
            "disclaimer": "This is general guidance only. Not a diagnosis. Please consult a healthcare provider."
        }

    async def get_first_aid(self, emergency_type: str = "general", **kwargs) -> Dict:

        first_aid_db = {
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
            }
        }

        emergency_lower = emergency_type.lower()
        for key, info in first_aid_db.items():
            if key in emergency_lower or emergency_lower in key:
                return {
                    "tool": "first_aid",
                    "status": "success",
                    "emergency_type": emergency_type,
                    **info,
                    "emergency_numbers": {"Ambulance": "108", "Health": "104"}
                }

        return {
            "tool": "first_aid",
            "status": "success",
            "emergency_type": emergency_type,
            "title": "General Emergency First Aid",
            "steps": [
                "1. Stay calm and assess situation",
                "2. Call 108 for emergencies",
                "3. Do not move person if spinal injury suspected",
                "4. Check breathing and consciousness",
                "5. Keep person warm and comfortable"
            ],
            "emergency_numbers": {"Ambulance": "108", "Health Helpline": "104"}
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

    async def check_vaccination_schedule(self, age_months: int = 12, child_name: str = None, **kwargs) -> Dict:

        schedule = [
            (0, ["BCG", "Hepatitis B (birth)", "OPV 0"]),
            (6, ["OPV 1", "Pentavalent 1", "Rotavirus 1", "PCV 1", "IPV 1"]),
            (10, ["OPV 2", "Pentavalent 2", "Rotavirus 2"]),
            (14, ["OPV 3", "Pentavalent 3", "Rotavirus 3", "PCV 2", "IPV 2"]),
            (36, ["IPV Booster"]),
            (40, ["MR 1 (Measles-Rubella)", "JE 1", "Vitamin A"]),
            (64, ["MR 2", "JE 2", "DPT Booster 1", "OPV Booster"]),
        ]

        due_now = []
        upcoming = []

        for age_week, vaccines in schedule:
            if age_months - 2 <= age_week <= age_months + 2:
                due_now.extend(vaccines)
            elif age_months + 2 < age_week <= age_months + 8:
                upcoming.extend(vaccines)

        return {
            "tool": "vaccination",
            "status": "success",
            "child_name": child_name,
            "age_months": age_months,
            "due_now": due_now if due_now else ["No vaccines due currently"],
            "upcoming": upcoming[:5] if upcoming else ["Check with doctor"],
            "where_to_go": ["Nearest Anganwadi", "PHC", "Government Hospital"],
            "important": "Vaccination is FREE under Universal Immunization Programme"
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

    async def mental_health_support(self, concern: str = "general", **kwargs) -> Dict:

        return {
            "tool": "mental_health",
            "status": "success",
            "message": "Your mental health matters. It's okay to seek help.",
            "helplines": [
                {"name": "iCall", "number": "9152987821", "hours": "Mon-Sat, 8am-10pm"},
                {"name": "Vandrevala Foundation", "number": "1860-2662-345", "hours": "24/7"},
                {"name": "NIMHANS", "number": "080-46110007", "hours": "24/7"}
            ],
            "self_care": ["Talk to someone you trust", "Maintain regular sleep", "Physical activity helps"],
            "crisis_message": "If having thoughts of self-harm, please call a helpline immediately."
        }

    async def find_anganwadi(self, location: str = "nearby", **kwargs) -> Dict:

        return {
            "tool": "anganwadi_finder",
            "status": "success",
            "services": ["Free vaccination", "Nutrition supplements", "Growth monitoring", "Pre-school education"],
            "eligibility": ["Children 0-6 years", "Pregnant women", "Nursing mothers"],
            "how_to_find": ["Ask local ASHA worker", "Contact nearest PHC", "Call 104"],
            "timing": "Usually 9 AM - 1 PM on weekdays"
        }

    async def pregnancy_care(self, trimester: int = None, concern: str = None, **kwargs) -> Dict:

        return {
            "tool": "pregnancy_care",
            "status": "success",
            "essential_care": {
                "checkups": "At least 4 antenatal visits",
                "supplements": ["Iron-Folic Acid tablets daily", "Calcium tablets"],
                "vaccinations": ["TT injections as per schedule"]
            },
            "warning_signs": ["Heavy bleeding", "Severe headache", "High fever", "Reduced baby movement"],
            "free_services": ["Janani Suraksha Yojana - cash assistance", "Free delivery at govt hospitals"],
            "emergency": "Call 102/108 for pregnancy emergencies"
        }

class IntelligentOrchestrator:

    def __init__(self, llm_client, model: str):

        self.groq_client = llm_client
        self.groq_model = model
        self.tools = HealthServiceTools()
        self._gemini_chat = None
        
        # Initialize Medical RAG service
        self.medical_rag = get_medical_rag_service() if MEDICAL_RAG_AVAILABLE else None
        
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
        "- symptoms: an array of symptom keywords (may be empty)\n"
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

    async def _execute_tool(self, intent: str, params: Dict, user_location: Dict = None) -> Dict:

        tool_func = self._tool_map.get(intent, self.tools.check_symptoms)

        try:
            if intent == "symptoms":
                symptoms = params.get("symptoms", [])
                if not symptoms and "message" in params:
                    symptoms = [params["message"]]

                age = params.get("age")
                if params.get("is_child") and not age:
                    age = 5

                result = await tool_func(symptoms=symptoms, age=age, gender=params.get("gender"))

            elif intent == "medicine":
                result = await tool_func(medicine_name=params.get("medicine_name", "general"))

            elif intent == "hospital":
                result = await tool_func(
                    location=params.get("location", "nearby"),
                    emergency=params.get("urgency") == "high"
                )

            elif intent == "first_aid":
                result = await tool_func(emergency_type=params.get("emergency_type", "general"))

            elif intent == "vaccination":
                age = params.get("age", 12)

                if age and age < 20:
                    age_months = age if age > 12 else age * 4
                else:
                    age_months = age if age else 12
                result = await tool_func(age_months=age_months)

            elif intent == "nutrition":
                result = await tool_func(
                    query=params.get("query", "general"),
                    health_condition=params.get("health_condition")
                )

            elif intent == "lab_test":
                result = await tool_func(test_name=params.get("test_name", "general"))

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

                result = await tool_func(location=location_value)

            else:
                result = await tool_func(**{k: v for k, v in params.items() if v is not None})

            return result

        except Exception as e:
            logger.error(f"Tool execution error ({intent}): {e}")
            return {"tool": intent, "status": "error", "message": str(e)}

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
                f"Use the tool output provided to craft a short, actionable response in {lang_name}. "
                "Always include a brief disclaimer and next steps. Keep it under 400 tokens."
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
            # This is a safety net - menu options should normally be handled by the webhook before reaching here
            candidate = user_message.strip()
            if candidate.isdigit() and int(candidate) in range(0, 11):
                logger.warning(f"Menu option {candidate} reached orchestrator (should have been handled by webhook). This is a sanity check - please ensure webhook menu handlers are working correctly.")
                # Return a placeholder response - this message should never reach the user
                return ""
            
            logger.info(f"Processing message: {user_message[:50]}...")
            
            # Try Medical RAG first for medical queries
            if self.medical_rag and self.medical_rag.is_available():
                if self.medical_rag.is_medical_query(user_message):
                    logger.info("🏥 Detected medical query - using RAG")
                    rag_result = self.medical_rag.get_grounded_response(
                        user_message,
                        top_k=3,
                        min_confidence="low"
                    )
                    
                    if rag_result and rag_result.get('answer'):
                        logger.info(f"✅ RAG response | Confidence: {rag_result['confidence']} | Sources: {len(rag_result['sources'])}")
                        return rag_result['answer']
                    else:
                        logger.info("⚠️ RAG didn't provide answer, falling back to tools")
            
            classification = await self._classify_with_gemini(user_message)
            intent = classification.get("intent", "symptoms")
            logger.info(f"Gemini detected intent: {intent}")

            tool_result = await self._execute_tool(intent, classification, user_location=user_location)
            logger.info(f"Tool '{intent}' executed, status: {tool_result.get('status')}")

            response = await self._generate_response_with_groq(
                user_message, tool_result, language, user_location
            )
            return response

        except Exception as e:
            logger.error(f"Orchestrator error: {e}", exc_info=True)
            return "🙏 I apologize, I encountered an issue. Please try again or call 104 (Health Helpline) for assistance."

orchestrator = None

def get_orchestrator(llm_client, model: str):

    global orchestrator
    if orchestrator is None:
        orchestrator = IntelligentOrchestrator(llm_client, model)
    return orchestrator