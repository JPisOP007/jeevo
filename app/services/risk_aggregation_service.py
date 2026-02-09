import logging
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class RiskAggregationService:
    """Aggregates data from multiple sources to calculate overall risk level"""

    RISK_WEIGHTS = {
        "aqi": 0.35,
        "weather": 0.25,
        "disease": 0.30,
        "historical": 0.10
    }

    @staticmethod
    def calculate_overall_risk(
        aqi_data: Optional[Dict] = None,
        weather_data: Optional[Dict] = None,
        disease_data: Optional[Dict] = None,
        historical_data: Optional[Dict] = None
    ) -> Dict:
        """
        Calculate overall risk by weighing multiple data sources.
        Returns: {risk_level, score, components, alerts, recommendations}
        """

        scores = {}

        if aqi_data:
            scores["aqi"] = RiskAggregationService._score_aqi(aqi_data)
        if weather_data:
            scores["weather"] = RiskAggregationService._score_weather(weather_data)
        if disease_data:
            scores["disease"] = RiskAggregationService._score_disease(disease_data)
        if historical_data:
            scores["historical"] = RiskAggregationService._score_historical(historical_data)

        weighted_score = sum(
            scores.get(key, 0) * weight
            for key, weight in RiskAggregationService.RISK_WEIGHTS.items()
        )

        risk_level = RiskAggregationService._score_to_risk_level(weighted_score)

        alerts = RiskAggregationService._generate_alerts(
            aqi_data, weather_data, disease_data, risk_level
        )

        recommendations = RiskAggregationService._generate_recommendations(
            risk_level, alerts
        )

        return {
            "risk_level": risk_level,
            "score": round(weighted_score, 2),
            "components": scores,
            "alerts": alerts,
            "recommendations": recommendations,
            "timestamp": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat()
        }

    @staticmethod
    def _score_aqi(aqi_data: Dict) -> float:
        """Score AQI data (0-10)"""
        if "aqi" not in aqi_data:
            return 5.0

        aqi_value = aqi_data["aqi"]
        if aqi_value > 300:
            return 10.0
        elif aqi_value > 200:
            return 8.5
        elif aqi_value > 150:
            return 7.0
        elif aqi_value > 100:
            return 5.5
        else:
            return 2.0

    @staticmethod
    def _score_weather(weather_data: Dict) -> float:
        """Score weather data (0-10)"""
        score = 3.0

        if weather_data.get("risk_level") == "red":
            score += 7.0
        elif weather_data.get("risk_level") == "yellow":
            score += 4.0

        temp = weather_data.get("temp", 20)
        if temp > 40 or temp < 5:
            score += 1.5

        humidity = weather_data.get("humidity", 50)
        if humidity > 85:
            score += 0.5

        return min(score, 10.0)

    @staticmethod
    def _score_disease(disease_data: Dict) -> float:
        """Score disease prevalence data (0-10)"""
        if not disease_data or not disease_data.get("active_diseases"):
            return 3.0

        severity = disease_data.get("severity_level", "low")
        if severity == "high":
            return 8.0
        elif severity == "moderate":
            return 5.5
        else:
            return 2.5

    @staticmethod
    def _score_historical(historical_data: Dict) -> float:
        """Score historical trend data (0-10)"""
        if not historical_data:
            return 5.0

        trending_up = historical_data.get("trending", "stable") == "increasing"
        current_level = historical_data.get("current_level", 5.0)

        if trending_up:
            current_level += 1.5

        return min(current_level, 10.0)

    @staticmethod
    def _score_to_risk_level(score: float) -> RiskLevel:
        """Convert numeric score to risk level"""
        if score >= 7.0:
            return RiskLevel.RED
        elif score >= 4.5:
            return RiskLevel.YELLOW
        else:
            return RiskLevel.GREEN

    @staticmethod
    def _generate_alerts(
        aqi_data: Optional[Dict],
        weather_data: Optional[Dict],
        disease_data: Optional[Dict],
        risk_level: RiskLevel
    ) -> List[str]:
        """Generate alerts based on data sources"""
        alerts = []

        if aqi_data and aqi_data.get("risk_level") == "red":
            alerts.append("🚨 SEVERE Air Pollution Alert")

        if weather_data and weather_data.get("risk_level") == "red":
            alerts.extend(weather_data.get("alerts", []))

        if disease_data and disease_data.get("severity_level") == "high":
            diseases = list(disease_data.get("active_diseases", {}).keys())
            if diseases:
                alerts.append(f"⚠️ High disease prevalence detected: {', '.join(diseases)}")

        if risk_level == RiskLevel.RED:
            alerts.append("🔴 OVERALL RISK LEVEL: RED - Essential outings only")
        elif risk_level == RiskLevel.YELLOW:
            alerts.append("🟡 OVERALL RISK LEVEL: YELLOW - Caution advised")

        return alerts

    @staticmethod
    def _generate_recommendations(risk_level: RiskLevel, alerts: List[str]) -> List[str]:
        """Generate health recommendations based on risk level"""

        if risk_level == RiskLevel.RED:
            return [
                "🏠 Stay indoors if possible",
                "😷 Wear N95 masks if outdoors",
                "💧 Stay hydrated",
                "⏰ Limit outdoor exposure to essential activities only",
                "👨‍👩‍👧 Keep children and elderly indoors",
                "📞 Keep emergency contacts ready"
            ]
        elif risk_level == RiskLevel.YELLOW:
            return [
                "⚠️ Exercise caution outdoors",
                "😷 Wear masks in crowded areas",
                "💨 Limit strenuous outdoor activities",
                "🧴 Maintain hygiene protocols",
                "👶 Extra care for vulnerable groups",
                "🥗 Maintain healthy diet and hydration"
            ]
        else:
            return [
                "✅ Risk level is manageable",
                "🚶 Normal outdoor activities are fine",
                "💪 Maintain regular exercise",
                "🧘 Continue normal health practices",
                "📊 Monitor local alerts for changes"
            ]

    @staticmethod
    def format_heatmap_display(aggregated_risk: Dict, city: str, lang: str = "en") -> str:
        """Format aggregated risk data for WhatsApp display in user's language"""

        score = aggregated_risk.get("score", 0)
        risk_level = aggregated_risk.get("risk_level", "unknown")
        components = aggregated_risk.get("components", {})
        alerts = aggregated_risk.get("alerts", [])
        recommendations = aggregated_risk.get("recommendations", [])

        # Language strings
        translations = {
            "hi": {
                "title": "🗺️ *स्वास्थ्य जोखिम मूल्यांकन*",
                "overall_risk": "*समग्र जोखिम स्तर*",
                "risk_score": "जोखिम स्कोर",
                "components": "*📊 जोखिम घटक:*",
                "air_quality": "वायु गुणवत्ता",
                "weather": "मौसम",
                "disease_prev": "रोग प्रचलितता",
                "historical": "ऐतिहासिक प्रवृत्ति",
                "alerts": "*⚠️ सतर्कताएं:*",
                "recommendations": "*💡 सुझाव:*"
            },
            "en": {
                "title": "🗺️ *Health Risk Assessment*",
                "overall_risk": "*Overall Risk Level*",
                "risk_score": "Risk Score",
                "components": "*📊 Risk Components:*",
                "air_quality": "Air Quality",
                "weather": "Weather",
                "disease_prev": "Disease Prevalence",
                "historical": "Historical Trend",
                "alerts": "*⚠️ Alerts:*",
                "recommendations": "*💡 Recommendations:*"
            },
            "mr": {
                "title": "🗺️ *आरोग्य जोखिम मूल्यांकन*",
                "overall_risk": "*एकूण जोखिम स्तर*",
                "risk_score": "जोखिम स्कोर",
                "components": "*📊 जोखिम घटक:*",
                "air_quality": "हवेचे गुणवत्ता",
                "weather": "हवामान",
                "disease_prev": "रोग प्रसार",
                "historical": "ऐतिहासिक प्रवृत्ती",
                "alerts": "*⚠️ सतर्कता:*",
                "recommendations": "*💡 सुझाव:*"
            },
            "gu": {
                "title": "🗺️ *આરોગ્ય જોખમ મૂલ્યાંકન*",
                "overall_risk": "*સામગ્રિક જોખમ સ્તર*",
                "risk_score": "જોખમ સ્કોર",
                "components": "*📊 જોખમ ઘટન:*",
                "air_quality": "હવા ગુણવત્તા",
                "weather": "હવામાન",
                "disease_prev": "રોગ વ્યાપ",
                "historical": "ઐતિહાસિક વલણ",
                "alerts": "*⚠️ ચેતવણીઓ:*",
                "recommendations": "*💡 ટિપ્સ:*"
            },
            "bn": {
                "title": "🗺️ *স্বাস্থ্য ঝুঁকি মূল্যায়ন*",
                "overall_risk": "*সামগ্রিক ঝুঁকি স্তর*",
                "risk_score": "ঝুঁকি স্কোর",
                "components": "*📊 ঝুঁকি উপাদান:*",
                "air_quality": "বায়ু গুণমান",
                "weather": "আবহাওয়া",
                "disease_prev": "রোগ প্রাধান্য",
                "historical": "ঐতিহাসিক প্রবণতা",
                "alerts": "*⚠️ সতর্কতা:*",
                "recommendations": "*💡 সুপারিশ:*"
            },
            "ta": {
                "title": "🗺️ *சுகாதার ஆபத்து மதிப்பீடு*",
                "overall_risk": "*ஒட்டுமொத்த ஆபத்து நிலை*",
                "risk_score": "ஆபத்து மதிப்பு",
                "components": "*📊 ஆபத்து கூறுகள்:*",
                "air_quality": "காற்று பண்பு",
                "weather": "வானிலை",
                "disease_prev": "நோய் பரவல்",
                "historical": "வரலாற்று போக்கு",
                "alerts": "*⚠️ எச்சரிக்கைகள்:*",
                "recommendations": "*💡 பரிந்துரைகள்:*"
            },
            "te": {
                "title": "🗺️ *ఆరోగ్య ఆపద్ బంధన*",
                "overall_risk": "*సামాన్య ఆపద్ స్థాయి*",
                "risk_score": "ఆపద్ స్కోర్",
                "components": "*📊 ఆపద్ భాగాలు:*",
                "air_quality": "గాలి గుణవత్త",
                "weather": "వాతావరణం",
                "disease_prev": "వ్యాధి ప్రభావం",
                "historical": "చారిత్రక ధోరణి",
                "alerts": "*⚠️ ఎచ్చరికలు:*",
                "recommendations": "*💡 సిఫారసులు:*"
            },
            "kn": {
                "title": "🗺️ *ಆರೋಗ್ಯ ಅಪಾಯ ಮೂಲ್ಯಮಾಪನ*",
                "overall_risk": "*ಸಮಗ್ರ ಅಪಾಯ ಮಟ್ಟ*",
                "risk_score": "ಅಪಾಯ ಸ್ಕೋರ್",
                "components": "*📊 ಅಪಾಯ ಘಟಕಗಳು:*",
                "air_quality": "ಗಾಳಿ ಗುಣಮಾನ",
                "weather": "ಹವಾಮಾನ",
                "disease_prev": "ರೋಗ ವ್ಯಾಪ್ತಿ",
                "historical": "ಐತಿಹಾಸಿಕ ಪ್ರವೃತ್ತಿ",
                "alerts": "*⚠️ ಎಚ್ಚರಿಕೆಗಳು:*",
                "recommendations": "*💡 ಸಲಹೆ:*"
            },
            "ml": {
                "title": "🗺️ *ആരോഗ്യ അപകട വിലയിരുത്തൽ*",
                "overall_risk": "*മൊത്ത അപകട തലം*",
                "risk_score": "അപകട സ്കോർ",
                "components": "*📊 അപകട ഘടകങ്ങൾ:*",
                "air_quality": "വായുവിന്റെ ഗുണനിലവാര",
                "weather": "കാലാവസ്ഥ",
                "disease_prev": "രോഗ വ്യാപ്തി",
                "historical": "ചരിത്രപരമായ പ്രവണത",
                "alerts": "*⚠️ മുന്നറിപ്പ്:*",
                "recommendations": "*💡 ശുപാര്ശകൾ:*"
            },
            "pa": {
                "title": "🗺️ *ਸਿਹਤ ਦੁਖ ਮੁਲਾਂਕਣ*",
                "overall_risk": "*ਕੁੱਲ ਜੋਖਮ ਪੱਧਰ*",
                "risk_score": "ਜੋਖਮ ਸਕੋਰ",
                "components": "*📊 ਜੋਖਮ ਭਾਗ:*",
                "air_quality": "ਹਵਾ ਗੁਣਵੱਤਾ",
                "weather": "ਮੌਸਮ",
                "disease_prev": "ਰੋਗ ਫੈਲਾਓ",
                "historical": "ਰੁਜ਼ ਪ੍ਰਵਿਰਤੀ",
                "alerts": "*⚠️ ਸਚੇਤੀ:*",
                "recommendations": "*💡 ਸਲਾਹ:*"
            }
        }

        t = translations.get(lang, translations["en"])

        msg = f"{t['title']} - {city}\n\n"

        risk_emoji = {"red": "🔴", "yellow": "🟡", "green": "🟢"}.get(risk_level, "⚪")
        msg += f"{risk_emoji} {t['overall_risk']}: {risk_level.upper()}\n"
        msg += f"   {t['risk_score']}: {score}/10\n\n"

        msg += f"{t['components']}\n"
        if components.get("aqi"):
            msg += f"  • {t['air_quality']}: {components['aqi']:.1f}/10\n"
        if components.get("weather"):
            msg += f"  • {t['weather']}: {components['weather']:.1f}/10\n"
        if components.get("disease"):
            msg += f"  • {t['disease_prev']}: {components['disease']:.1f}/10\n"
        if components.get("historical"):
            msg += f"  • {t['historical']}: {components['historical']:.1f}/10\n"

        msg += f"\n{t['alerts']}\n"
        for alert in alerts[:3]:
            msg += f"{alert}\n"

        msg += f"\n{t['recommendations']}\n"
        for rec in recommendations[:4]:
            msg += f"{rec}\n"

        return msg
