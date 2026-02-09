
import openai
import base64
from typing import Union
import os
import logging

logger = logging.getLogger(__name__)

VISION_SYSTEM_PROMPT = """You are a medical image analysis assistant for Jeevo health platform serving rural India. Your role is to:

1. ANALYZE MEDICAL IMAGES
   - Examine skin conditions, wounds, visible symptoms
   - Describe visible abnormalities in simple terms
   - Provide preliminary assessment (NOT a diagnosis)
   - Recommend professional medical consultation

2. COMMUNICATION
   - Use simple, non-technical language
   - Respond in the user's language
   - Be empathetic and reassuring
   - Avoid alarming users unnecessarily

3. SAFETY PROTOCOLS
   - Always disclaim that you're providing preliminary assessment only
   - Strongly recommend professional doctor consultation
   - Flag urgent symptoms (severe redness, pus, swelling, deformity)
   - For unclear images, ask for better photo or recommend in-person visit

4. LIMITATIONS
   - Cannot detect internal diseases from external images
   - Cannot provide definitive diagnosis
   - Cannot be used for legal/insurance purposes
   - Always defer to qualified doctors

5. RESPONSE FORMAT
   - Start with image quality assessment (clear/unclear)
   - Describe visible observations
   - Provide possible causes (not diagnosis)
   - Recommend next steps
   - Include medical disclaimer
   - Keep under 600 characters

Remember: This is preliminary assessment only. Always encourage professional consultation."""

class VisionAnalyzer:

    def __init__(self, api_key: str = None):
        from app.config.settings import settings

        use_groq = settings.USE_GROQ
        groq_api_key = settings.GROQ_API_KEY
        openai_api_key = settings.OPENAI_API_KEY

        if use_groq:
            api_key = api_key or groq_api_key
            if not api_key:
                logger.warning("Groq API key missing for Vision, checking OpenAI...")
                if openai_api_key:
                    self.client = openai.OpenAI(api_key=openai_api_key)
                    self.model = settings.OPENAI_VISION_MODEL
                    logger.info(f"Initialized Vision analyzer with OpenAI (Fallback): {self.model}")
                    return
                else:
                    raise ValueError("Groq API key missing for Vision (and no OpenAI key found)")

            self.client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            self.model = settings.GROQ_VISION_MODEL
            logger.info(f"Initialized Vision analyzer with Groq: {self.model}")
        else:
            api_key = api_key or openai_api_key
            if not api_key:
                 # Standard fallback logic: if OpenAI wanted but missing, try Groq
                if groq_api_key:
                    logger.warning("OpenAI key missing for Vision, falling back to Groq")
                    self.client = openai.OpenAI(
                        api_key=groq_api_key,
                        base_url="https://api.groq.com/openai/v1"
                    )
                    self.model = settings.GROQ_VISION_MODEL
                    logger.info(f"Initialized Vision analyzer with Groq (Fallback): {self.model}")
                else:
                    raise ValueError("OpenAI API key missing for Vision (and no Groq key found)")
            else:
                self.client = openai.OpenAI(api_key=api_key)
                self.model = settings.OPENAI_VISION_MODEL
                logger.info(f"Initialized Vision analyzer with OpenAI: {self.model}")

    def analyze_image(self, image_path: str, query: str = "Analyze this medical image",
                     language: str = "en") -> str:

        language_names = {
            "en": "English",
            "hi": "Hindi (हिंदी)",
            "ta": "Tamil (தமிழ்)",
            "te": "Telugu (తెలుగు)",
            "bn": "Bengali (বাংলা)",
            "mr": "Marathi (मराठी)",
            "gu": "Gujarati (ગુજરાતી)",
            "kn": "Kannada (ಕನ್ನಡ)",
            "ml": "Malayalam (മലയാളം)",
            "pa": "Punjabi (ਪੰਜਾਬੀ)"
        }
        lang_name = language_names.get(language, "English")

        try:
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error reading image {image_path}: {e}")
            error_messages = {
                "en": f"⚠️ Error reading image: {str(e)}",
                "hi": f"⚠️ इमेज पढ़ने में त्रुटि: {str(e)}",
                "ta": f"⚠️ படத்தைப் படிப்பதில் பிழை: {str(e)}",
                "te": f"⚠️ చిత్రాన్ని చదవడంలో లోపం: {str(e)}",
                "bn": f"⚠️ ছবি পড়তে ত্রুটি: {str(e)}",
                "mr": f"⚠️ प्रतिमा वाचण्यात त्रुटी: {str(e)}",
                "gu": f"⚠️ છબી વાંચવામાં ભૂલ: {str(e)}",
                "kn": f"⚠️ ಚಿತ್ರ ಓದುವಲ್ಲಿ ದೋಷ: {str(e)}",
                "ml": f"⚠️ ചിത്രം വായിക്കുന്നതിൽ പിശക്: {str(e)}",
                "pa": f"⚠️ ਤਸਵੀਰ ਪੜ੍ਹਨ ਵਿੱਚ ਗਲਤੀ: {str(e)}"
            }
            return error_messages.get(language, error_messages["en"])

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            VISION_SYSTEM_PROMPT
                            + f"\n\nIMPORTANT: You MUST respond ONLY in {lang_name}. "
                            + f"Do NOT use any other language."
                        )
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"{query}\n\nRespond only in {lang_name}."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=600
            )

            logger.info("Successfully analyzed image")
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            error_messages = {
                "en": f"⚠️ Error analyzing image: {str(e)}",
                "hi": f"⚠️ इमेज का विश्लेषण करने में त्रुटि: {str(e)}",
                "ta": f"⚠️ படத்தை பகுப்பாய்வு செய்வதில் பிழை: {str(e)}",
                "te": f"⚠️ చిత్రాన్ని విశ్లేషించడంలో లోపం: {str(e)}",
                "bn": f"⚠️ ছবি বিশ্লেষণে ত্রুটি: {str(e)}",
                "mr": f"⚠️ प्रतिमा विश्लेषणात त्रुटी: {str(e)}",
                "gu": f"⚠️ છબી વિશ્લેષણમાં ભૂલ: {str(e)}",
                "kn": f"⚠️ ಚಿತ್ರ ವಿಶ್ಲೇಷಣೆಯಲ್ಲಿ ದೋಷ: {str(e)}",
                "ml": f"⚠️ ചിത്ര വിശകലനത്തിൽ പിശക്: {str(e)}",
                "pa": f"⚠️ ਤਸਵੀਰ ਵਿਸ਼ਲੇਸ਼ਣ ਵਿੱਚ ਗਲਤੀ: {str(e)}"
            }
            return error_messages.get(language, error_messages["en"])

    def analyze_from_url(self, image_url: str, query: str, language: str = "en") -> str:

        language_names = {
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
        lang_name = language_names.get(language, "English")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            VISION_SYSTEM_PROMPT
                            + f"\n\nIMPORTANT: You MUST respond ONLY in {lang_name}. "
                            + f"Do NOT use any other language."
                        )
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"{query}\n\nRespond only in {lang_name}."},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]
                    }
                ],
                max_tokens=600
            )

            logger.info("Successfully analyzed image from URL")
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error analyzing image from URL: {e}")
            error_messages = {
                "en": f"⚠️ Error: {str(e)}",
                "hi": f"⚠️ त्रुटि: {str(e)}",
                "ta": f"⚠️ பிழை: {str(e)}",
                "te": f"⚠️ లోపం: {str(e)}",
                "bn": f"⚠️ ত্রুটি: {str(e)}",
                "mr": f"⚠️ त्रुटी: {str(e)}",
                "gu": f"⚠️ ભૂલ: {str(e)}",
                "kn": f"⚠️ ದೋಷ: {str(e)}",
                "ml": f"⚠️ പിശക്: {str(e)}",
                "pa": f"⚠️ ਗਲਤੀ: {str(e)}"
            }
            return error_messages.get(language, error_messages["en"])