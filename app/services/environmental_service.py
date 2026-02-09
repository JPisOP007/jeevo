
import httpx
import logging
import os
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class EnvironmentalService:

    def __init__(self):
        self.openweather_key = os.getenv("OPENWEATHER_API_KEY", "")

    async def get_weather_health_risks(self, lat: float, lon: float) -> Dict:

        if not self.openweather_key:
            logger.warning("OpenWeather API key not configured")
            return {"error": "Weather API not configured", "risk_level": "unknown", "alerts": []}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={
                        "lat": lat,
                        "lon": lon,
                        "appid": self.openweather_key,
                        "units": "metric"
                    },
                    timeout=10
                )

                if response.status_code != 200:
                    return {"error": f"API error {response.status_code}", "risk_level": "unknown", "alerts": []}

                data = response.json()
                return self._analyze_weather_risks(data)

        except Exception as e:
            logger.error(f"Weather API error: {e}")
            return {"error": str(e), "risk_level": "unknown", "alerts": []}

    def _analyze_weather_risks(self, weather_data: Dict) -> Dict:

        risk_level = "green"
        alerts = []

        weather_main = weather_data["weather"][0]["main"]
        temp = weather_data["main"]["temp"]
        humidity = weather_data["main"]["humidity"]

        if weather_main in ["Rain", "Thunderstorm", "Drizzle"]:
            risk_level = "yellow"
            alerts.append("🌧️ Heavy rainfall - Risk of waterborne diseases")
            alerts.append("⚠️ Clean stagnant water to prevent dengue & malaria")
            alerts.append("💧 Ensure safe drinking water")

        if temp > 35:
            risk_level = "yellow" if risk_level == "green" else "red"
            alerts.append("🌡️ High temperature - Stay hydrated")
            alerts.append("☀️ Avoid direct sunlight 12-4 PM")
            alerts.append("💦 Risk of heat stroke")
        elif temp < 10:
            risk_level = "yellow" if risk_level == "green" else "red"
            alerts.append("🥶 Cold weather - Dress warmly")
            alerts.append("🧥 Protect children & elderly from cold")

        if humidity > 80:
            alerts.append("💧 High humidity - Keep skin dry")
            alerts.append("⚠️ Risk of fungal infections")

        return {
            "location": weather_data.get("name", "Unknown"),
            "temp": temp,
            "humidity": humidity,
            "weather": weather_main,
            "description": weather_data["weather"][0]["description"],
            "risk_level": risk_level,
            "alerts": alerts,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def get_aqi_health_risks(self, lat: float, lon: float, city: str = "Unknown") -> Dict:

        if not self.openweather_key:

            return self._mock_aqi_data(city)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.openweathermap.org/data/2.5/air_pollution",
                    params={
                        "lat": lat,
                        "lon": lon,
                        "appid": self.openweather_key
                    },
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    aqi_level = data["list"][0]["main"]["aqi"]

                    aqi_map = {1: 50, 2: 100, 3: 150, 4: 250, 5: 350}
                    aqi_value = aqi_map.get(aqi_level, 150)
                    return self._analyze_aqi_risks(aqi_value, city)
                else:
                    return self._mock_aqi_data(city)

        except Exception as e:
            logger.error(f"AQI API error: {e}")
            return self._mock_aqi_data(city)

    def _analyze_aqi_risks(self, aqi_value: int, city: str) -> Dict:

        risk_level = "green"
        alerts = []

        if aqi_value > 300:
            risk_level = "red"
            alerts.append("🚨 SEVERE Air Pollution - Hazardous")
            alerts.append("🏠 Stay indoors, avoid outdoor activities")
            alerts.append("😷 Wear N95 masks if you must go out")
            alerts.append("💨 Use air purifiers indoors")
        elif aqi_value > 200:
            risk_level = "red"
            alerts.append("🚨 Very Unhealthy Air Quality")
            alerts.append("😷 Everyone should wear masks outdoors")
            alerts.append("⚠️ Limit outdoor exposure")
        elif aqi_value > 150:
            risk_level = "yellow"
            alerts.append("⚠️ Unhealthy Air Quality")
            alerts.append("😷 Sensitive groups limit outdoor activities")
        elif aqi_value > 100:
            risk_level = "yellow"
            alerts.append("⚠️ Moderate Air Quality")
            alerts.append("💨 Limit prolonged outdoor exertion")
        else:
            alerts.append("✅ Good Air Quality")

        return {
            "city": city,
            "aqi": aqi_value,
            "risk_level": risk_level,
            "alerts": alerts,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _mock_aqi_data(self, city: str) -> Dict:

        import random
        aqi_value = random.randint(80, 180)
        return self._analyze_aqi_risks(aqi_value, city)

    async def get_comprehensive_risk_assessment(self, user_location: Dict) -> Dict:

        lat = user_location.get("latitude")
        lon = user_location.get("longitude")
        city = user_location.get("city", "Unknown")

        risk_data = {
            "location": f"{city}, {user_location.get('state', '')}",
            "overall_risk": "green",
            "alerts": [],
            "timestamp": datetime.utcnow().isoformat()
        }

        if not lat or not lon:
            return risk_data

        weather_risks = await self.get_weather_health_risks(float(lat), float(lon))
        if "alerts" in weather_risks:
            risk_data["alerts"].extend(weather_risks["alerts"])
            if weather_risks["risk_level"] == "red":
                risk_data["overall_risk"] = "red"
            elif weather_risks["risk_level"] == "yellow" and risk_data["overall_risk"] == "green":
                risk_data["overall_risk"] = "yellow"

        aqi_risks = await self.get_aqi_health_risks(float(lat), float(lon), city)
        if "alerts" in aqi_risks:
            risk_data["alerts"].extend(aqi_risks["alerts"])
            if aqi_risks["risk_level"] == "red":
                risk_data["overall_risk"] = "red"
            elif aqi_risks["risk_level"] == "yellow" and risk_data["overall_risk"] == "green":
                risk_data["overall_risk"] = "yellow"

        return risk_data

environmental_service = EnvironmentalService()