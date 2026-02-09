
import openai
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)

MEDICAL_SYSTEM_PROMPT = """You are Jeevo, a qualified medical health assistant for rural India. Your role is to:

1. PROVIDE HEALTH GUIDANCE
   - Offer symptom assessment and preliminary health advice
   - Connect local health issues to prevention and treatment
   - Always recommend professional medical consultation for serious conditions

2. COMMUNICATION STYLE
   - Be empathetic, clear, and use simple language
   - Respond in the user's language
   - Use emojis to make responses friendly and accessible
   - Break information into digestible chunks

3. SAFETY GUIDELINES
   - Always include medical disclaimers
   - Recommend visiting a doctor for persistent symptoms
   - Never replace professional medical advice
   - Escalate emergency cases (chest pain, difficulty breathing, severe bleeding) to call 108

4. CONTEXT AWARENESS
   - Consider local health issues (malaria in monsoon, heatstroke in summer)
   - Know about immunization schedules in India
   - Provide information suitable for resource-limited settings

5. MULTILINGUAL
   - Support 10 Indian languages (English, Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi)
   - Translate medical terms accurately
   - Respect cultural health practices

6. RESPONSE FORMAT
   - Keep responses under 600 characters
   - Use structured text with bullet points
   - End with clear next steps
   - Include relevant emojis

Remember: You are a health assistant, not a doctor. Always encourage professional consultation."""

class MedicalLLM:

    def __init__(self, api_key: str = None):
        from app.config.settings import settings

        use_groq = settings.USE_GROQ
        groq_api_key = settings.GROQ_API_KEY
        openai_api_key = settings.OPENAI_API_KEY

        # Auto-detect: Use Groq if explicitly requested OR if OpenAI key is missing but Groq key exists
        if use_groq or (not openai_api_key and groq_api_key):
            api_key = api_key or groq_api_key
            if not api_key:
                raise ValueError("Groq API key missing (USE_GROQ=true or fallback)")

            self.client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            self.model = settings.GROQ_MODEL
            logger.info(f"Initialized Medical LLM with Groq: {self.model}")
        else:
            api_key = api_key or openai_api_key
            if not api_key:
                # If OpenAI missing, try Groq fallback
                if groq_api_key:
                    logger.warning("OpenAI key missing for LLM, falling back to Groq")
                    self.client = openai.OpenAI(
                        api_key=groq_api_key,
                        base_url="https://api.groq.com/openai/v1"
                    )
                    self.model = settings.GROQ_MODEL
                    logger.info(f"Initialized Medical LLM with Groq (Fallback): {self.model}")
                else:
                    raise ValueError("OpenAI API key missing and no Groq key found for LLM. Please check .env file.")
            else:
                self.client = openai.OpenAI(api_key=api_key)
                self.model = settings.OPENAI_MODEL
                logger.info(f"Initialized Medical LLM with OpenAI: {self.model}")

    def get_medical_response(self, user_message: str, language: str = "en") -> str:

        language_names = {
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
        }

        lang_name = language_names.get(language, "English")

        # Explicitly instruct the model which language to respond in to avoid defaults.
        language_instruction = f"Please respond in {lang_name}. If you cannot, reply in English and mark that translation was necessary."

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": MEDICAL_SYSTEM_PROMPT},
                    {"role": "system", "content": language_instruction},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=600
            )

            # Different OpenAI-compatible clients return content differently; guard access
            try:
                return response.choices[0].message.content
            except Exception:
                # Fallback for other client shapes
                return getattr(response.choices[0].message, 'content', str(response))

        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return "⚠️ Sorry, I encountered an error processing your request. Please try again."

    def get_medical_reply(self, user_message: str, language: str = "en") -> str:

        return self.get_medical_response(user_message, language)