from fastapi import APIRouter, Request, HTTPException, Query, Depends
from fastapi.responses import PlainTextResponse
from typing import Dict, Any
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.services.whatsapp_service import whatsapp_service
from app.services.cache_service import cache_service
from app.database.base import get_db
from app.database.repositories import UserRepository, ConversationRepository
from app.utils.helpers import (
    generate_welcome_message,
    generate_echo_response,
    is_webhook_valid,
    log_incoming_message
)

logger = logging.getLogger(__name__)
router = APIRouter()


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
    Process incoming message and send appropriate response
    Now with database integration!
    """
    try:
        # Get or create user
        user, is_new = await UserRepository.get_or_create_user(
            db,
            phone_number=message.from_number
        )
        
        logger.info(f"[USER] {'New user created' if is_new else 'Existing user'}: {user.phone_number}")
        
        # Check cache for user context
        user_context = await cache_service.get_user_context(message.from_number)
        if user_context:
            logger.info(f"[CACHE] Retrieved context for {message.from_number}")
        
        # Generate response
        if message.message_type == "text" and message.text_content:
            text_lower = message.text_content.lower().strip()
            
            if text_lower in ["hi", "hello", "start", "namaste", "hey"] or is_new:
                response_text = generate_welcome_message(user.name)
            else:
                response_text = generate_echo_response(
                    message.message_type,
                    message.text_content
                )
        else:
            response_text = generate_echo_response(message.message_type)
        
        # Send response
        await whatsapp_service.send_text_message(
            to_number=message.from_number,
            text=response_text
        )
        
        # Save conversation to database
        await ConversationRepository.create_conversation(
            db,
            user_id=user.id,
            message_id=message.message_id,
            message_type=message.message_type,
            user_message=message.text_content,
            bot_response=response_text,
            media_id=message.media_id
        )
        
        # Update user context in cache
        new_context = {
            "last_message_type": message.message_type,
            "last_message_time": message.timestamp,
            "conversation_state": "active"
        }
        await cache_service.set_user_context(message.from_number, new_context)
        
        logger.info(f"[RESPONSE] Sent to {message.from_number} and saved to DB")
    
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