import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def generate_welcome_message(user_name: str = None) -> str:
    """Generate a welcome message for new users"""
    if user_name:
        return f"🙏 Namaste {user_name}! Welcome to Jeevo - your personal health assistant.\n\n" \
               f"I can help you with:\n" \
               f"✅ Health queries (text, voice, or images)\n" \
               f"✅ Medical reminders\n" \
               f"✅ Local health alerts\n\n" \
               f"How can I assist you today?"
    else:
        return "🙏 Namaste! Welcome to Jeevo - your personal health assistant.\n\n" \
               "I can help you with:\n" \
               "✅ Health queries (text, voice, or images)\n" \
               "✅ Medical reminders\n" \
               "✅ Local health alerts\n\n" \
               "How can I assist you today?"


def generate_echo_response(message_type: str, content: str = None) -> str:
    """Generate echo response based on message type (for testing)"""
    responses = {
        "text": f"📝 I received your text message: '{content}'\n\n⚠️ AI features coming soon!",
        "audio": "🎤 I received your voice message!\n\n⚠️ Voice processing coming soon!",
        "image": "📸 I received your image!\n\n⚠️ Image analysis coming soon!",
        "video": "🎥 I received your video!\n\n⚠️ Video processing coming soon!",
        "document": "📄 I received your document!\n\n⚠️ Document processing coming soon!"
    }
    
    return responses.get(message_type, "✅ Message received!")


def add_medical_disclaimer(response: str) -> str:
    """Add medical disclaimer to AI responses"""
    disclaimer = "⚠️ This is AI-generated guidance. Please consult a qualified doctor for serious health issues."
    return f"{response}\n\n{disclaimer}"


def is_webhook_valid(webhook_data: Dict[str, Any]) -> bool:
    """Validate incoming webhook data structure"""
    try:
        required_keys = ["entry"]
        if not all(key in webhook_data for key in required_keys):
            return False
        
        entry = webhook_data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        
        # Check if it contains messages
        if "messages" in value:
            return True
        
        # It might be a status update, which is also valid
        if "statuses" in value:
            return True
        
        return False
    
    except (KeyError, IndexError, TypeError):
        return False


def log_incoming_message(message: 'WhatsAppMessage') -> None:
    """Log incoming message details"""
    logger.info(f"[INCOMING] Type: {message.message_type} | From: {message.from_number} | ID: {message.message_id}")
    if message.text_content:
        logger.info(f"[CONTENT] {message.text_content}")