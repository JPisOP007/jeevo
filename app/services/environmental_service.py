
import httpx
import logging
import os
from typing import Dict, Optional
from datetime import datetime

from app.config.settings import settings

logger = logging.getLogger(__name__)

class EnvironmentalService:

    def __init__(self):
        self.openweather_key = settings.OPENWEATHER_API_KEY or ""
        self.use_mock_aqi = os.getenv("USE_MOCK_AQI", "false").lower() == "true"

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
            logger.warning("OpenWeather AQI API key not configured")
            if self.use_mock_aqi:
                return self._mock_aqi_data(city)
            return {
                "city": city,
                "risk_level": "unknown",
                "alerts": [],
                "error": "AQI API not configured",
                "timestamp": datetime.utcnow().isoformat()
            }

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
                    components = data["list"][0]["components"]
                    
                    # Calculate accurate US EPA AQI from PM2.5 concentration
                    pm25 = components.get("pm2_5", 0)
                    if pm25 > 0:
                        aqi_value = self._calculate_us_aqi_from_pm25(pm25)
                    else:
                        # Fallback to index-based mapping if PM2.5 is unavailable
                        aqi_level = data["list"][0]["main"]["aqi"]
                        aqi_map = {1: 50, 2: 100, 3: 150, 4: 250, 5: 350}
                        aqi_value = aqi_map.get(aqi_level, 150)
                    
                    return self._analyze_aqi_risks(aqi_value, city)

                logger.warning(
                    "AQI API error %s: %s", response.status_code, response.text
                )
                if self.use_mock_aqi:
                    return self._mock_aqi_data(city)
                return {
                    "city": city,
                    "risk_level": "unknown",
                    "alerts": [],
                    "error": f"AQI API error {response.status_code}",
                    "timestamp": datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"AQI API error: {e}")
            if self.use_mock_aqi:
                return self._mock_aqi_data(city)
            return {
                "city": city,
                "risk_level": "unknown",
                "alerts": [],
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

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

    def _calculate_us_aqi_from_pm25(self, pm25: float) -> int:
        """
        Calculate US EPA AQI from PM2.5 concentration (μg/m³).
        Based on official EPA breakpoints for accurate AQI calculation.
        
        Reference: https://www.airnow.gov/aqi/aqi-calculator-concentration/
        """
        # EPA AQI breakpoints for PM2.5 (24-hour average)
        # Format: (C_low, C_high, I_low, I_high)
        breakpoints = [
            (0.0, 12.0, 0, 50),        # Good
            (12.1, 35.4, 51, 100),     # Moderate
            (35.5, 55.4, 101, 150),    # Unhealthy for Sensitive Groups
            (55.5, 150.4, 151, 200),   # Unhealthy
            (150.5, 250.4, 201, 300),  # Very Unhealthy
            (250.5, 350.4, 301, 400),  # Hazardous
            (350.5, 500.4, 401, 500),  # Hazardous (higher)
        ]
        
        for c_low, c_high, i_low, i_high in breakpoints:
            if c_low <= pm25 <= c_high:
                # Linear interpolation formula:
                # AQI = [(I_high - I_low) / (C_high - C_low)] * (C - C_low) + I_low
                aqi = ((i_high - i_low) / (c_high - c_low)) * (pm25 - c_low) + i_low
                return int(round(aqi))
        
        # If PM2.5 exceeds all breakpoints, return maximum AQI
        if pm25 > 500.4:
            return 500
        
        # Default fallback
        return 150

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