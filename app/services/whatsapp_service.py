import httpx
import logging
import os
import asyncio
from typing import Dict, Any, List
from app.config.settings import settings
from app.models.message import WhatsAppMessage, WhatsAppResponse

logger = logging.getLogger(__name__)

class WhatsAppService:

    def __init__(self):
        self.api_url = settings.WHATSAPP_API_URL
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def parse_incoming_message(self, webhook_data: Dict[str, Any]) -> WhatsAppMessage:

        try:
            entry = webhook_data["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]

            message_data = value["messages"][0]

            message_id = message_data["id"]
            from_number = message_data["from"]
            timestamp = message_data["timestamp"]
            message_type = message_data["type"]

            text_content = None
            media_url = None
            media_id = None
            mime_type = None

            if message_type == "text":
                text_content = message_data["text"]["body"]

            elif message_type == "interactive":
                # Interactive responses (button replies, list replies)
                # Extract button ID and convert to numeric option for routing
                interactive = message_data.get("interactive", {})
                interaction_type = interactive.get("type")
                text_content = ""

                if interaction_type == "button_reply":
                    # Button reply has structure: { "button_reply": { "id": "btn_0", "title": "Health" } }
                    btn_reply = interactive.get("button_reply", {})
                    btn_id = btn_reply.get("id", "")
                    # Convert "btn_0" -> "1", "btn_1" -> "2", etc. (map to 1-indexed menu options)
                    if btn_id.startswith("btn_"):
                        try:
                            idx = int(btn_id.replace("btn_", ""))
                            text_content = str(idx + 1)  # Convert 0-indexed to 1-indexed menu option
                        except (ValueError, IndexError):
                            text_content = btn_reply.get("title", "")
                    else:
                        text_content = btn_reply.get("title", "")
                elif interaction_type == "list_reply":
                    # List reply: { "list_reply": { "id": "option_0", "title": "Health" } }
                    list_reply = interactive.get("list_reply", {})
                    list_id = list_reply.get("id", "")
                    # Convert "option_0" -> "1", "option_1" -> "2", etc. (map to 1-indexed menu options)
                    if list_id.startswith("option_"):
                        try:
                            idx = int(list_id.replace("option_", ""))
                            text_content = str(idx + 1)  # Convert 0-indexed to 1-indexed menu option
                        except (ValueError, IndexError):
                            text_content = list_reply.get("title", "")
                    else:
                        text_content = list_reply.get("title", "")
                else:
                    # Fallback
                    text_content = interactive.get("body", {}).get("text", "")

                # Treat interactive as text for routing convenience
                message_type = "text"

            elif message_type == "audio":
                media_id = message_data["audio"]["id"]
                mime_type = message_data["audio"]["mime_type"]

            elif message_type == "image":
                media_id = message_data["image"]["id"]
                mime_type = message_data["image"]["mime_type"]

                text_content = message_data["image"].get("caption")

            elif message_type == "location":
                # Location payload contains latitude, longitude and optional name/address
                loc = message_data.get("location", {})
                lat = loc.get("latitude")
                lon = loc.get("longitude")
                name = loc.get("name")
                address = loc.get("address")
                # Build a human-friendly text content for downstream parsing
                parts = []
                if name:
                    parts.append(name)
                if address:
                    parts.append(address)
                if lat and lon:
                    parts.append(f"{lat},{lon}")
                text_content = " - ".join(parts) if parts else ""
                # Normalize to text for routing convenience
                message_type = "text"

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

    async def send_audio_message(self, to_number: str, audio_path: str = None, audio_url: str = None) -> Dict[str, Any]:

        url = f"{self.api_url}/{self.phone_number_id}/messages"

        if audio_path and not audio_url:
            try:
                logger.info(f"Uploading audio file: {audio_path}")
                
                if not os.path.exists(audio_path):
                    raise FileNotFoundError(f"Audio file not found: {audio_path}")
                
                with open(audio_path, "rb") as audio_file:
                    upload_url = f"{self.api_url}/{self.phone_number_id}/media"
                    
                    files = {
                        "file": (os.path.basename(audio_path), audio_file, "audio/ogg")
                    }
                    
                    async with httpx.AsyncClient() as client:
                        logger.debug(f"Posting to {upload_url}")
                        upload_response = await client.post(
                            upload_url,
                            headers={
                                "Authorization": self.headers["Authorization"],
                            },
                            data={"messaging_product": "whatsapp"},
                            files=files,
                            timeout=120.0
                        )
                        
                        if upload_response.status_code not in [200, 201]:
                            error_detail = upload_response.text
                            logger.error(f"Upload failed with {upload_response.status_code}: {error_detail}")
                            raise ValueError(f"Media upload failed: {error_detail}")
                        
                        upload_data = upload_response.json()
                        logger.debug(f"Upload response: {upload_data}")
                        
                        # WhatsApp returns media ID in the response
                        media_id = upload_data.get("id") or upload_data.get("h")
                        
                        if not media_id:
                            logger.error(f"No media ID in response: {upload_data}")
                            raise ValueError(f"Failed to get media ID from upload response")
                        
                        logger.info(f"Audio uploaded successfully with ID: {media_id}")
                        
                        # Fetch the media URL using the media ID
                        media_url_endpoint = f"{self.api_url}/{media_id}"
                        media_response = await client.get(
                            media_url_endpoint,
                            headers=self.headers,
                            timeout=30.0
                        )
                        
                        if media_response.status_code == 200:
                            media_info = media_response.json()
                            audio_url = media_info.get("url")
                            if audio_url:
                                logger.info(f"Retrieved media URL: {audio_url}")
                            else:
                                logger.warning(f"No URL in media response, will try using media ID")
                        else:
                            logger.warning(f"Could not fetch media URL, will use media ID as fallback")
                        
                        # Preserve media_id and prefer sending by media ID when possible
                        uploaded_media_id = media_id
                        # If no URL, keep audio_url as None so we send by id
                        if not audio_url:
                            audio_url = None
            
            except FileNotFoundError as e:
                logger.error(f"Audio file error: {e}")
                raise ValueError(f"Audio file not found: {str(e)}")
            except Exception as e:
                logger.error(f"Error uploading audio file: {e}", exc_info=True)
                raise ValueError(f"Could not upload audio file: {str(e)}")

        if not audio_url:
            raise ValueError("Must provide either audio_path or audio_url")

        # Build payload: prefer sending using uploaded media ID (more reliable),
        # otherwise use a public link. If the audio is OGG/Opus, include "voice": true
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "audio",
        }

        # Determine if this should be treated as a native voice message
        is_voice_native = False
        try:
            if audio_path and isinstance(audio_path, str) and audio_path.lower().endswith('.ogg'):
                is_voice_native = True
            elif audio_url and isinstance(audio_url, str) and audio_url.lower().endswith('.ogg'):
                is_voice_native = True
        except Exception:
            is_voice_native = False

        if 'uploaded_media_id' in locals() and uploaded_media_id:
            audio_obj = {"id": uploaded_media_id}
            if is_voice_native:
                audio_obj["voice"] = True
            payload["audio"] = audio_obj
        else:
            audio_obj = {"link": audio_url}
            if is_voice_native:
                audio_obj["voice"] = True
            payload["audio"] = audio_obj

        async with httpx.AsyncClient() as client:
            try:
                logger.debug(f"Sending audio message to {to_number}")
                logger.debug(f"Payload: {payload}")
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                logger.info(f"Audio message sent successfully to {to_number}")
                return response.json()

            except httpx.HTTPStatusError as e:
                logger.error(f"Error sending audio message: {e}")
                logger.error(f"Response text: {e.response.text}")
                raise
            except httpx.HTTPError as e:
                logger.error(f"Error sending audio message: {e}", exc_info=True)
                raise

    async def download_media(self, media_id: str, media_type: str) -> str:

        try:

            media_url_endpoint = f"{self.api_url}/{media_id}"

            async with httpx.AsyncClient() as client:

                response = await client.get(
                    media_url_endpoint,
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                media_info = response.json()
                media_url = media_info.get("url")

                if not media_url:
                    raise ValueError("Media URL not found in response")

                media_response = await client.get(
                    media_url,
                    headers=self.headers,
                    timeout=60.0
                )
                media_response.raise_for_status()

                extension_map = {
                    "audio": "ogg",
                    "image": "jpg",
                    "video": "mp4",
                    "document": "pdf"
                }
                extension = extension_map.get(media_type, "bin")

                os.makedirs("temp", exist_ok=True)

                filepath = f"temp/media_{media_id}.{extension}"

                with open(filepath, "wb") as f:
                    f.write(media_response.content)

                logger.info(f"Downloaded {media_type} to {filepath}")
                return filepath

        except Exception as e:
            logger.error(f"Error downloading media {media_id}: {e}")
            raise

    async def mark_message_as_read(self, message_id: str) -> Dict[str, Any]:

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

    async def send_message_with_suggestions(
        self, 
        to_number: str, 
        text: str,
        suggestions: List[str] = None
    ) -> Dict[str, Any]:

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

        if suggestions:
            payload["type"] = "interactive"
            
            buttons = []
            for i, suggestion in enumerate(suggestions[:3]):
                if isinstance(suggestion, dict):
                    btn_id = suggestion.get("id", f"btn_{i}")
                    btn_title = suggestion.get("title", "")
                else:
                    btn_id = f"btn_{i}"
                    btn_title = suggestion
                
                buttons.append({
                    "type": "reply",
                    "reply": {
                        "id": btn_id,
                        "title": btn_title[:20]
                    }
                })

            payload["interactive"] = {
                "type": "button",
                "body": {"text": text},
                "action": {
                    "buttons": buttons
                }
            }
            payload.pop("text")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                logger.info(f"Interactive message sent to {to_number}")
                return response.json()

            except httpx.HTTPError as e:
                logger.error(f"Error sending interactive message: {e}")
                raise

whatsapp_service = WhatsAppService()