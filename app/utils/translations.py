# Translation constants for all 10 supported languages
# en, hi, ta, te, bn, mr, gu, kn, ml, pa

ALL_LANGUAGES = ["en", "hi", "ta", "te", "bn", "mr", "gu", "kn", "ml", "pa"]

# Emergency numbers (same across India)
EMERGENCY_NUMBERS = {
    "ambulance": "108",
    "health_helpline": "104",
    "women_helpline": "1091",
    "child_helpline": "1098",
    "police": "100"
}

def get_translation(translations: dict, language: str, fallback: str = "en") -> str:
    """Get translation for a language with fallback to English."""
    return translations.get(language, translations.get(fallback, ""))

def get_emergency_numbers_text(language: str) -> dict:
    """Get emergency numbers with translated labels."""
    labels = {
        "en": {"Ambulance": "108", "Health Helpline": "104"},
        "hi": {"एम्बुलेंस": "108", "स्वास्थ्य हेल्पलाइन": "104"},
        "ta": {"ஆம்புலன்ஸ்": "108", "சுகாதார உதவி": "104"},
        "te": {"అంబులెన్స్": "108", "ఆరోగ్య హెల్ప్‌లైన్": "104"},
        "bn": {"অ্যাম্বুলেন্স": "108", "স্বাস্থ্য হেল্পলাইন": "104"},
        "mr": {"रुग्णवाहिका": "108", "आरोग्य हेल्पलाइन": "104"},
        "gu": {"એમ્બ્યુલન્સ": "108", "આરોગ્ય હેલ્પલાઇન": "104"},
        "kn": {"ಆಂಬುಲೆನ್ಸ್": "108", "ಆರೋಗ್ಯ ಸಹಾಯವಾಣಿ": "104"},
        "ml": {"ആംബുലൻസ്": "108", "ആരോഗ്യ ഹെൽപ്പ്‌ലൈൻ": "104"},
        "pa": {"ਐਂਬੂਲੈਂਸ": "108", "ਸਿਹਤ ਹੈਲਪਲਾਈਨ": "104"}
    }
    return labels.get(language, labels["en"])
