import httpx
import logging
from typing import Dict, Any
from app.config.settings import settings
from app.models.message import WhatsAppMessage, WhatsAppResponse

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service to handle WhatsApp API interactions"""
    
    def __init__(self):
        self.api_url = settings.WHATSAPP_API_URL
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    def parse_incoming_message(self, webhook_data: Dict[str, Any]) -> WhatsAppMessage:
        """Parse incoming webhook data into WhatsAppMessage model"""
        try:
            entry = webhook_data["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]
            
            # Get message data
            message_data = value["messages"][0]
            
            message_id = message_data["id"]
            from_number = message_data["from"]
            timestamp = message_data["timestamp"]
            message_type = message_data["type"]
            
            # Extract content based on message type
            text_content = None
            media_url = None
            media_id = None
            mime_type = None
            
            if message_type == "text":
                text_content = message_data["text"]["body"]
            
            elif message_type == "audio":
                media_id = message_data["audio"]["id"]
                mime_type = message_data["audio"]["mime_type"]
            
            elif message_type == "image":
                media_id = message_data["image"]["id"]
                mime_type = message_data["image"]["mime_type"]
                # Caption if available
                text_content = message_data["image"].get("caption")
            
            elif message_type == "video":
                media_id = message_data["video"]["id"]
                mime_type = message_data["video"]["mime_type"]
            
            elif message_type == "document":
                media_id = message_data["document"]["id"]
                mime_type = message_data["document"]["mime_type"]
            
            return WhatsAppMessage(
                message_id=message_id,
                from_number=from_number,
                timestamp=timestamp,
                message_type=message_type,
                text_content=text_content,
                media_url=media_url,
                media_id=media_id,
                mime_type=mime_type
            )
        
        except (KeyError, IndexError) as e:
            logger.error(f"Error parsing webhook data: {e}")
            raise ValueError(f"Invalid webhook data structure: {e}")
    
    async def send_text_message(self, to_number: str, text: str) -> Dict[str, Any]:
        """Send a text message via WhatsApp"""
        url = f"{self.api_url}/{self.phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": text
            }
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                logger.info(f"Message sent to {to_number}")
                return response.json()
            
            except httpx.HTTPError as e:
                logger.error(f"Error sending message: {e}")
                raise
    
    async def send_audio_message(self, to_number: str, audio_url: str) -> Dict[str, Any]:
        """Send an audio message via WhatsApp"""
        url = f"{self.api_url}/{self.phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "audio",
            "audio": {
                "link": audio_url
            }
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                logger.info(f"Audio message sent to {to_number}")
                return response.json()
            
            except httpx.HTTPError as e:
                logger.error(f"Error sending audio: {e}")
                raise
    
    async def mark_message_as_read(self, message_id: str) -> Dict[str, Any]:
        """Mark a message as read"""
        url = f"{self.api_url}/{self.phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            
            except httpx.HTTPError as e:
                logger.error(f"Error marking message as read: {e}")
                raise


# Create global service instance
whatsapp_service = WhatsAppService()