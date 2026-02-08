"""Vision analysis using GPT-4 Vision or Groq Vision"""

import openai
import base64
from typing import Union
import os
import logging

logger = logging.getLogger(__name__)


class VisionAnalyzer:
    """Medical image analysis service"""
    
    def __init__(self, api_key: str = None):
        """Initialize Vision analyzer with Groq or OpenAI support"""
        use_groq = os.getenv("USE_GROQ", "false").lower() == "true"
        
        if use_groq:
            api_key = api_key or os.getenv("GROQ_API_KEY")
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            self.model = os.getenv("GROQ_VISION_MODEL", "llama-3.2-90b-vision-preview")
            logger.info(f"Initialized Vision analyzer with Groq: {self.model}")
        else:
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            self.client = openai.OpenAI(api_key=api_key)
            self.model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
            logger.info(f"Initialized Vision analyzer with OpenAI: {self.model}")
    
    def analyze_image(self, image_path: str, query: str = "Analyze this medical image", 
                     language: str = "en") -> str:
        """
        Analyze medical images (rashes, wounds, pills, reports, etc.)
        
        Args:
            image_path: Path to image file
            query: Question/query about the image
            language: Language code for response
            
        Returns:
            Analysis text
        """
        
        language_names = {
            "en": "English",
            "hi": "Hindi (हिंदी)",
            "ta": "Tamil (தமிழ்)",
            "te": "Telugu (తెలుగు)",
            "bn": "Bengali (বাংলা)"
        }
        lang_name = language_names.get(language, "English")
        
        # Read and encode image
        try:
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error reading image {image_path}: {e}")
            return f"Error reading image: {str(e)}"
        
        system_prompt = f"""You are a medical image analyzer for Jeevo healthcare assistant.
        
        Guidelines:
        - Describe what you see in the image clearly
        - Provide preliminary assessment (NOT a diagnosis)
        - Suggest whether medical attention is needed and urgency level
        - Respond in {lang_name} language
        - Keep response concise and actionable
        - Always add: "⚠️ This is not a medical diagnosis. Please consult a doctor for proper evaluation."
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": query},
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
            return f"⚠️ Error analyzing image: {str(e)}"
    
    def analyze_from_url(self, image_url: str, query: str, language: str = "en") -> str:
        """
        Analyze image from URL (for WhatsApp media)
        
        Args:
            image_url: URL of the image
            query: Question about the image
            language: Language code
            
        Returns:
            Analysis text
        """
        
        language_names = {
            "en": "English",
            "hi": "Hindi",
            "ta": "Tamil",
            "te": "Telugu"
        }
        lang_name = language_names.get(language, "English")
        
        system_prompt = f"""You are a medical image analyzer for Jeevo.
        Provide assessment in {lang_name}. 
        Always add medical disclaimer: "This is not a diagnosis. Consult a doctor."
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": query},
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
            return f"⚠️ Error: {str(e)}"
