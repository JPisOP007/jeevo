"""Language detection and management for multilingual support"""

from typing import Dict, Optional
import re
import logging

logger = logging.getLogger(__name__)


class LanguageManager:
    """Manage multilingual support for Indian languages"""
    
    def __init__(self):
        """Initialize language manager with supported languages"""
        self.supported_languages = {
            "en": "English",
            "hi": "Hindi (हिंदी)",
            "bn": "Bengali (বাংলা)",
            "te": "Telugu (తెలుగు)",
            "mr": "Marathi (मराठी)",
            "ta": "Tamil (தமிழ்)",
            "gu": "Gujarati (ગુજરાતી)",
            "kn": "Kannada (ಕನ್ನಡ)",
            "ml": "Malayalam (മലയാളം)",
            "pa": "Punjabi (ਪੰਜਾਬੀ)",
            "or": "Odia (ଓଡ଼ିଆ)"
        }
        
        # Language detection patterns (Unicode ranges for Indian scripts)
        self.language_patterns = {
            "hi": re.compile(r'[\u0900-\u097F]'),  # Devanagari (Hindi, Marathi)
            "bn": re.compile(r'[\u0980-\u09FF]'),  # Bengali
            "te": re.compile(r'[\u0C00-\u0C7F]'),  # Telugu
            "ta": re.compile(r'[\u0B80-\u0BFF]'),  # Tamil
            "gu": re.compile(r'[\u0A80-\u0AFF]'),  # Gujarati
            "kn": re.compile(r'[\u0C80-\u0CFF]'),  # Kannada
            "ml": re.compile(r'[\u0D00-\u0D7F]'),  # Malayalam
            "pa": re.compile(r'[\u0A00-\u0A7F]'),  # Punjabi (Gurmukhi)
            "or": re.compile(r'[\u0B00-\u0B7F]'),  # Odia
        }
        
        logger.info(f"Language Manager initialized with {len(self.supported_languages)} languages")
    
    def detect_language(self, text: str) -> str:
        """
        Detect language from text using Unicode script detection
        
        Args:
            text: Input text
            
        Returns:
            Language code (e.g., 'hi', 'en', 'ta')
        """
        if not text or len(text.strip()) == 0:
            return "en"
        
        # Check for Indian language scripts
        for lang_code, pattern in self.language_patterns.items():
            if pattern.search(text):
                logger.info(f"Detected language: {lang_code}")
                return lang_code
        
        # Default to English
        logger.info("Detected language: en (default)")
        return "en"
    
    def get_user_language(self, phone_number: str, db_session=None) -> str:
        """
        Get user's preferred language from database
        
        Args:
            phone_number: User's phone number
            db_session: Database session (optional)
            
        Returns:
            Language code
        """
        # TODO: Query user preferences from database when needed
        # For now, return Hindi as default for India
        if db_session:
            try:
                # This would query your users table for language preference
                # user = db_session.query(User).filter_by(phone_number=phone_number).first()
                # if user and user.preferred_language:
                #     return user.preferred_language
                pass
            except Exception as e:
                logger.error(f"Error fetching user language: {e}")
        
        return "hi"  # Default to Hindi for Indian users
    
    def set_user_language(self, phone_number: str, language: str, db_session):
        """
        Save user's language preference to database
        
        Args:
            phone_number: User's phone number
            language: Language code
            db_session: Database session
        """
        # TODO: Implement when needed
        # user = db_session.query(User).filter_by(phone_number=phone_number).first()
        # if user:
        #     user.preferred_language = language
        #     db_session.commit()
        pass
    
    def get_system_message(self, key: str, language: str = "en") -> str:
        """
        Get system messages in user's language
        
        Args:
            key: Message key ('welcome', 'error', 'choose_language')
            language: Language code
            
        Returns:
            Localized message
        """
        messages = {
            "welcome": {
                "en": "🙏 Namaste! Welcome to Jeevo - your personal health assistant.\n\n"
                      "I can help you with:\n"
                      "✅ Health queries (text, voice, or images)\n"
                      "✅ Medical information in your language\n"
                      "✅ Symptom assessment\n\n"
                      "How can I assist you today?",
                      
                "hi": "🙏 नमस्ते! जीवो में आपका स्वागत है - आपका व्यक्तिगत स्वास्थ्य सहायक।\n\n"
                      "मैं आपकी मदद कर सकता हूं:\n"
                      "✅ स्वास्थ्य संबंधी प्रश्न (टेक्स्ट, वॉयस या इमेज)\n"
                      "✅ आपकी भाषा में चिकित्सा जानकारी\n"
                      "✅ लक्षणों का आकलन\n\n"
                      "आज मैं आपकी कैसे मदद कर सकता हूं?",
                      
                "ta": "🙏 வணக்கம்! ஜீவோவிற்கு வரவேற்கிறோம் - உங்கள் தனிப்பட்ட சுகாதார உதவியாளர்.\n\n"
                      "நான் உங்களுக்கு உதவ முடியும்:\n"
                      "✅ சுகாதார கேள்விகள் (உரை, குரல் அல்லது படங்கள்)\n"
                      "✅ உங்கள் மொழியில் மருத்துவ தகவல்\n"
                      "✅ அறிகுறி மதிப்பீடு\n\n"
                      "இன்று நான் உங்களுக்கு எப்படி உதவ முடியும்?",
                      
                "te": "🙏 నమస్కారం! జీవోకు స్వాగతం - మీ వ్యక్తిగత ఆరోగ్య సహాయకుడు.\n\n"
                      "నేను మీకు సహాయం చేయగలను:\n"
                      "✅ ఆరోగ్య ప్రశ్నలు (టెక్స్ట్, వాయిస్ లేదా చిత్రాలు)\n"
                      "✅ మీ భాషలో వైద్య సమాచారం\n"
                      "✅ లక్షణాల అంచనా\n\n"
                      "ఈరోజు నేను మీకు ఎలా సహాయం చేయగలను?",
                      
                "bn": "🙏 নমস্কার! জীবোতে স্বাগতম - আপনার ব্যক্তিগত স্বাস্থ্য সহায়ক।\n\n"
                      "আমি আপনাকে সাহায্য করতে পারি:\n"
                      "✅ স্বাস্থ্য প্রশ্ন (টেক্সট, ভয়েস বা ছবি)\n"
                      "✅ আপনার ভাষায় চিকিৎসা তথ্য\n"
                      "✅ লক্ষণ মূল্যায়ন\n\n"
                      "আজ আমি আপনাকে কীভাবে সাহায্য করতে পারি?",
            },
            
            "error": {
                "en": "⚠️ Sorry, I couldn't process that. Please try again.",
                "hi": "⚠️ क्षमा करें, मैं इसे संसाधित नहीं कर सका। कृपया पुनः प्रयास करें।",
                "ta": "⚠️ மன்னிக்கவும், என்னால் அதை செயலாக்க முடியவில்லை. தயவுசெய்து மீண்டும் முயற்சிக்கவும்.",
                "te": "⚠️ క్షమించండి, నేను దానిని ప్రాసెస్ చేయలేకపోయాను. దయచేసి మళ్లీ ప్రయత్నించండి.",
                "bn": "⚠️ দুঃখিত, আমি এটি প্রক্রিয়া করতে পারিনি। অনুগ্রহ করে আবার চেষ্টা করুন।",
            },
            
            "choose_language": {
                "en": "Please choose your preferred language:\n"
                      "1. English\n"
                      "2. हिंदी (Hindi)\n"
                      "3. தமிழ் (Tamil)\n"
                      "4. తెలుగు (Telugu)\n"
                      "5. বাংলা (Bengali)\n"
                      "6. मराठी (Marathi)",
                      
                "hi": "कृपया अपनी पसंदीदा भाषा चुनें:\n"
                      "1. English\n"
                      "2. हिंदी (Hindi)\n"
                      "3. தமிழ் (Tamil)\n"
                      "4. తెలుగు (Telugu)\n"
                      "5. বাংলা (Bengali)\n"
                      "6. मराठी (Marathi)",
            }
        }
        
        # Get message for given key and language, fallback to English
        return messages.get(key, {}).get(language, messages.get(key, {}).get("en", ""))
    
    def is_supported_language(self, language: str) -> bool:
        """Check if language is supported"""
        return language in self.supported_languages
