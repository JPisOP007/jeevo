ERROR_MESSAGES = {
    "location_required": {
        "en": "📍 Please share your location first so I can find nearby hospitals and provide location-specific health advice.\n\nHow to share:\n1. Click 📎 (attachment icon)\n2. Select Location\n3. Share your current location",
        "hi": "📍 कृपया पहले अपना स्थान साझा करें ताकि मैं आपके पास के अस्पताल खोज सकूं।\n\nकैसे शेयर करें:\n1. 📎 (अटैचमेंट) दबाएं\n2. Location चुनें\n3. अपना स्थान शेयर करें",
    },
    "network_error": {
        "en": "🌐 Internet connection issue. Please check your connection and try again.",
        "hi": "🌐 इंटरनेट कनेक्शन समस्या। कृपया अपने कनेक्शन की जांच करें और दोबारा कोशिश करें।",
    },
    "tts_failed": {
        "en": "🔊 Voice message not available. Sending text response instead.",
        "hi": "🔊 वॉयस संदेश उपलब्ध नहीं। पाठ प्रतिक्रिया भेजी जा रही है।",
    },
    "medical_uncertain": {
        "en": "⚠️ This sounds serious. Please visit a doctor or call 108 (ambulance) for emergency.",
        "hi": "⚠️ यह गंभीर लग रहा है। कृपया डॉक्टर से मिलें या आपातकालीन के लिए 108 कॉल करें।",
    },
    "processing_error": {
        "en": "❌ An error occurred while processing your message. Please try again later.",
        "hi": "❌ आपके संदेश को संसाधित करने में त्रुटि हुई। कृपया बाद में दोबारा कोशिश करें।",
    },
    "voice_upload_failed": {
        "en": "🎤 Failed to upload voice message. Sending text response.",
        "hi": "🎤 वॉयस संदेश अपलोड करने में विफल। पाठ प्रतिक्रिया भेजी जा रही है।",
    },
    "hospital_not_found": {
        "en": "🏥 Could not find nearby hospitals. Please check your location or contact local authorities.",
        "hi": "🏥 पास के अस्पताल नहीं मिले। कृपया अपना स्थान जांचें या स्थानीय अधिकारियों से संपर्क करें।",
    },
    "language_not_supported": {
        "en": "🗣️ Language not yet supported. Please try English or Hindi.",
        "hi": "🗣️ भाषा अभी समर्थित नहीं है। कृपया अंग्रेजी या हिंदी का प्रयास करें।",
    },
    "age_required": {
        "en": "👶 Please provide the age of the child for vaccination tracking.",
        "hi": "👶 कृपया टीकाकरण ट्रैकिंग के लिए बच्चे की उम्र प्रदान करें।",
    },
    "service_timeout": {
        "en": "⏱️ Request took too long. Please try again.",
        "hi": "⏱️ अनुरोध में बहुत समय लगा। कृपया दोबारा कोशिश करें।",
    },
}

def get_error_message(error_key: str, language: str = "en") -> str:
    error_dict = ERROR_MESSAGES.get(error_key, {})
    return error_dict.get(language, error_dict.get("en", f"An error occurred: {error_key}"))
