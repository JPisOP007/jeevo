from fastapi import APIRouter, Request, HTTPException, Query, Depends
from fastapi.responses import PlainTextResponse
from typing import Dict, Any
import logging
import os
import time
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.services.whatsapp_service import whatsapp_service
from app.services.cache_service import cache_service
from app.database.base import get_db
from app.database.repositories import UserRepository, ConversationRepository
from app.logic.multimodal_router import MultimodalRouter
from app.logic.language_manager import LanguageManager
from app.utils.helpers import (
    is_webhook_valid,
    log_incoming_message
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize multimodal router and language manager
multimodal_router = MultimodalRouter()
language_manager = LanguageManager()


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    request: Request,
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge")
):
    """
    Webhook verification endpoint for WhatsApp Cloud API
    """
    logger.info(f"[WEBHOOK VERIFICATION] Mode: {mode}, Token received: {token[:10]}...")
    
    if mode == "subscribe" and token == settings.WEBHOOK_VERIFY_TOKEN:
        logger.info("[WEBHOOK VERIFICATION] ✅ Success - Returning challenge")
        return challenge
    else:
        logger.warning("[WEBHOOK VERIFICATION] ❌ Failed - Invalid token")
        raise HTTPException(status_code=403, detail="Verification token mismatch")


@router.post("/webhook")
async def receive_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Main webhook endpoint to receive incoming WhatsApp messages
    """
    try:
        webhook_data: Dict[str, Any] = await request.json()
        
        logger.info(f"[WEBHOOK] Received data")
        
        if not is_webhook_valid(webhook_data):
            logger.warning("[WEBHOOK] Invalid webhook structure")
            return {"status": "ignored", "reason": "invalid_structure"}
        
        entry = webhook_data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        
        if "statuses" in value:
            logger.info("[WEBHOOK] Status update received - ignoring")
            return {"status": "ok", "type": "status_update"}
        
        try:
            message = whatsapp_service.parse_incoming_message(webhook_data)
            log_incoming_message(message)
        except ValueError as e:
            logger.error(f"[WEBHOOK] Error parsing message: {e}")
            return {"status": "error", "message": str(e)}
        
        try:
            await whatsapp_service.mark_message_as_read(message.message_id)
        except Exception as e:
            logger.warning(f"[WEBHOOK] Could not mark message as read: {e}")
        
        # Process the message with database
        await process_message(message, db)
        
        return {"status": "ok", "message_id": message.message_id}
    
    except Exception as e:
        logger.error(f"[WEBHOOK] Unexpected error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


async def process_message(message: 'WhatsAppMessage', db: AsyncSession) -> None:
    """
    Process incoming message with AI/multimodal capabilities
    """
    start_time = time.time()
    
    try:
        # Get or create user
        user, is_new = await UserRepository.get_or_create_user(
            db,
            phone_number=message.from_number
        )
        
        logger.info(f"[USER] {'New user created' if is_new else 'Existing user'}: {user.phone_number}")
        
        # Get user's preferred language
        user_language = user.language.value if user.language else "hi"
        
        # Detect language from text if available
        if message.message_type == "text" and message.text_content:
            detected_lang = language_manager.detect_language(message.text_content)
            
            # Check for greeting messages
            text_lower = message.text_content.lower().strip()
            if text_lower in ["hi", "hello", "start", "namaste", "hey", "नमस्ते", "வணக்கம்", "నమస్కారం"] or is_new:
                # Send welcome message in detected language
                welcome_msg = language_manager.get_system_message("welcome", detected_lang)
                
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=welcome_msg
                )
                
                # Save to database
                await ConversationRepository.create_conversation(
                    db,
                    user_id=user.id,
                    message_id=message.message_id,
                    message_type=message.message_type,
                    user_message=message.text_content,
                    bot_response=welcome_msg,
                    media_id=message.media_id,
                    response_time_ms=int((time.time() - start_time) * 1000)
                )
                
                logger.info(f"[RESPONSE] Sent welcome message to {message.from_number}")
                return
            
            # Update user language if different
            if detected_lang != user_language:
                user.language = detected_lang
                await db.commit()
                user_language = detected_lang
        
        # Prepare content for multimodal router
        content = message.text_content
        caption = ""
        
        # Handle media messages by downloading them
        if message.media_id:
            try:
                # Download media file
                media_path = await whatsapp_service.download_media(message.media_id, message.message_type)
                content = media_path
                
                # For images, use caption if available
                if message.message_type == "image" and message.text_content:
                    caption = message.text_content
                
                logger.info(f"[MEDIA] Downloaded {message.message_type} to {media_path}")
            except Exception as e:
                logger.error(f"[MEDIA] Failed to download media: {e}")
                error_msg = language_manager.get_system_message("error", user_language)
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=error_msg
                )
                return
        
        # Route message through multimodal router
        logger.info(f"[ROUTER] Processing {message.message_type} message in {user_language}")
        response = multimodal_router.route_message(
            message_type=message.message_type,
            content=content,
            caption=caption,
            language=user_language
        )
        
        # Handle response based on type
        if response["type"] == "text":
            # Send text response
            await whatsapp_service.send_text_message(
                to_number=message.from_number,
                text=response["content"]
            )
            
            bot_response = response["content"]
            
        elif response["type"] == "voice":
            # Send voice response (if audio was generated)
            if response.get("audio_path"):
                try:
                    await whatsapp_service.send_audio_message(
                        to_number=message.from_number,
                        audio_path=response["audio_path"]
                    )
                    bot_response = f"[Voice Response] {response['content']}"
                    
                    # Clean up temporary audio file
                    try:
                        os.remove(response["audio_path"])
                    except:
                        pass
                except Exception as e:
                    logger.error(f"[VOICE] Failed to send voice: {e}")
                    # Fallback to text
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=response["content"]
                    )
                    bot_response = response["content"]
            else:
                # Send as text
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=response["content"]
                )
                bot_response = response["content"]
                
        else:
            # Error response
            error_msg = language_manager.get_system_message("error", user_language)
            await whatsapp_service.send_text_message(
                to_number=message.from_number,
                text=error_msg
            )
            bot_response = error_msg
        
        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Save conversation to database
        await ConversationRepository.create_conversation(
            db,
            user_id=user.id,
            message_id=message.message_id,
            message_type=message.message_type,
            user_message=message.text_content or f"[{message.message_type}]",
            bot_response=bot_response,
            media_id=message.media_id,
            response_time_ms=response_time_ms
        )
        
        # Update user context in cache
        new_context = {
            "last_message_type": message.message_type,
            "last_message_time": message.timestamp,
            "conversation_state": "active",
            "language": user_language
        }
        await cache_service.set_user_context(message.from_number, new_context)
        
        logger.info(f"[RESPONSE] Sent to {message.from_number} (took {response_time_ms}ms)")
    
    except Exception as e:
        logger.error(f"[PROCESS] Error processing message: {e}", exc_info=True)
        
        try:
            error_message = "⚠️ Sorry, I encountered an error. Please try again in a moment."
            await whatsapp_service.send_text_message(
                to_number=message.from_number,
                text=error_message
            )
        except Exception as send_error:
            logger.error(f"[PROCESS] Could not send error message: {send_error}")


