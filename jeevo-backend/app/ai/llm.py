"""Medical LLM for healthcare guidance"""

import openai
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)


class MedicalLLM:
    """Medical Language Model for healthcare responses"""
    
    def __init__(self, api_key: str = None):
        """Initialize LLM with Groq or OpenAI support"""
        use_groq = os.getenv("USE_GROQ", "false").lower() == "true"
        
        if use_groq:
            api_key = api_key or os.getenv("GROQ_API_KEY")
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
            logger.info(f"Initialized Medical LLM with Groq: {self.model}")
        else:
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            self.client = openai.OpenAI(api_key=api_key)
            self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            logger.info(f"Initialized Medical LLM with OpenAI: {self.model}")
        
    def get_medical_response(self, user_message: str, language: str = "en") -> str:
        """Generate medical guidance response in specified language"""
        
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
        
        system_prompt = f"""You are Jeevo, a helpful healthcare assistant for rural and semi-urban communities in India.
        
        Guidelines:
        - Provide clear, simple medical guidance
        - Always add disclaimer: "⚠️ This is general guidance. Please consult a qualified doctor for proper diagnosis and treatment."
        - Be empathetic and supportive
        - Respond in {lang_name} language
        - For emergencies (severe symptoms, injuries), immediately advise seeking emergency medical care
        - Keep responses concise and actionable (max 400 words)
        - Use simple language that's easy to understand
        - Suggest basic home remedies when appropriate
        - Recommend when to see a doctor
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=600
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return f"⚠️ Sorry, I encountered an error processing your request. Please try again."

    def get_medical_reply(self, user_message: str, language: str = "en") -> str:
        """Alias for get_medical_response for backward compatibility"""
        return self.get_medical_response(user_message, language)
