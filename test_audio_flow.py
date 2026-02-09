#!/usr/bin/env python3
"""
Test script to verify audio reply flow end-to-end
This tests:
1. TTS generation
2. Audio file creation
3. WhatsApp API audio sending capability
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.ai.elevenlabs_tts import ElevenLabsTTS
from app.services.tts_fallback_service import tts_fallback_service
from app.services.whatsapp_service import whatsapp_service
from app.config.settings import settings
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_tts_generation():
    """Test 1: TTS Generation"""
    print("\n" + "="*60)
    print("TEST 1: TTS Generation")
    print("="*60)
    
    test_text = "नमस्ते! यह एक परीक्षण संदेश है।"
    
    try:
        audio_bytes, provider = await tts_fallback_service.text_to_speech_with_fallback(
            text=test_text,
            language="hi",
            gender="female"
        )
        
        if audio_bytes:
            print(f"✅ TTS Generation SUCCESS via {provider}")
            print(f"   Audio size: {len(audio_bytes)} bytes")
            
            # Save test audio file
            test_audio_path = "temp/test_audio.ogg"
            os.makedirs("temp", exist_ok=True)
            with open(test_audio_path, "wb") as f:
                f.write(audio_bytes)
            print(f"   Saved to: {test_audio_path}")
            return test_audio_path
        else:
            print(f"❌ TTS Generation FAILED - No audio generated")
            return None
            
    except Exception as e:
        print(f"❌ TTS Generation ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

async def test_whatsapp_audio_send(audio_path: str):
    """Test 2: WhatsApp Audio Send API"""
    print("\n" + "="*60)
    print("TEST 2: WhatsApp Audio Send API")
    print("="*60)
    
    if not audio_path or not os.path.exists(audio_path):
        print(f"❌ Audio file not found: {audio_path}")
        return False
    
    # Check configuration
    print(f"WhatsApp Config Check:")
    print(f"  API URL: {settings.WHATSAPP_API_URL}")
    print(f"  Phone Number ID: {'✓' if settings.WHATSAPP_PHONE_NUMBER_ID else '✗ MISSING'}")
    print(f"  Access Token: {'✓' if settings.WHATSAPP_ACCESS_TOKEN else '✗ MISSING'}")
    
    if not settings.WHATSAPP_PHONE_NUMBER_ID or not settings.WHATSAPP_ACCESS_TOKEN:
        print("❌ WhatsApp credentials missing!")
        return False
    
    # Try to send test audio
    test_number = "+919999999999"  # Placeholder
    
    try:
        print(f"\nAttempting to send audio to {test_number}...")
        result = await whatsapp_service.send_audio_message(
            to_number=test_number,
            audio_path=audio_path
        )
        
        if result and "messages" in result:
            print(f"✅ WhatsApp API Response: SUCCESS")
            print(f"   Message ID: {result['messages'][0].get('id', 'N/A')}")
            return True
        else:
            print(f"⚠️ WhatsApp API Response: {result}")
            return False
            
    except Exception as e:
        print(f"❌ WhatsApp Audio Send ERROR: {e}")
        if "invalid" in str(e).lower() or "auth" in str(e).lower():
            print("   → Could be credential issue or invalid phone number format")
        return False

async def test_elevenlabs_audio():
    """Test 3: Check ElevenLabs API directly"""
    print("\n" + "="*60)
    print("TEST 3: ElevenLabs Direct Check")
    print("="*60)
    
    try:
        elevenlabs = ElevenLabsTTS()
        
        if not elevenlabs.client:
            print(f"❌ ElevenLabs client NOT initialized")
            print(f"   Check: ELEVENLABS_API_KEY in .env")
            return False
        
        print(f"✅ ElevenLabs client initialized")
        print(f"   Voices available: {len(elevenlabs.voices)}")
        
        # Try Hindi voice
        test_text = "परीक्षण"
        try:
            audio = elevenlabs.text_to_speech(test_text, language="hi", gender="female")
            print(f"✅ Hindi TTS works: {len(audio)} bytes generated")
            return True
        except Exception as e:
            print(f"❌ Hindi TTS failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ ElevenLabs check ERROR: {e}")
        return False

def print_audio_flow_diagram():
    """Print visual representation of audio flow"""
    print("\n" + "="*70)
    print("AUDIO REPLY FLOW DIAGRAM")
    print("="*70)
    
    flow = """
    USER SENDS VOICE
         ↓
    [Webhook] receive_webhook()
         ↓
    [Whisper] download_media() + STT transcribe
         ↓
    [LLM] get_medical_response()
         ↓
    [TTS] tts_fallback_service.text_to_speech_with_fallback()
         ↓
         ├─→ Try: ElevenLabs TTS
         │   (generates OGG bytes)
         └─→ Fallback: gTTS
             (generates MP3 bytes)
         ↓
    [Save] Write bytes to temp/auto_voice_*.ogg
         ↓
    [WhatsApp] send_audio_message()
         ├─→ Upload to /media endpoint
         ├─→ Get media_id back
         └─→ Send message with audio
         ↓
    USER RECEIVES AUDIO ✅ (or ❌ STOPS HERE)
    """
    
    print(flow)

def main():
    """Run all tests"""
    print_audio_flow_diagram()
    
    try:
        # Test 1: TTS Generation
        audio_path = asyncio.run(test_tts_generation())
        
        # Test 2: ElevenLabs
        asyncio.run(test_elevenlabs_audio())
        
        # Test 3: WhatsApp API (only if we have audio)
        if audio_path:
            asyncio.run(test_whatsapp_audio_send(audio_path))
        
        print("\n" + "="*60)
        print("DIAGNOSIS SUMMARY")
        print("="*60)
        print("""
        ✅ = Working
        ❌ = Not working
        ⚠️  = Needs investigation
        
        COMMON ISSUES:
        1. ElevenLabs API key missing or invalid
        2. WhatsApp credentials (phone_id, access_token) wrong
        3. Test phone number format incorrect (should be with country code)
        4. WhatsApp Business Account not configured
        5. WhatsApp number not verified
        """)
        
    except Exception as e:
        print(f"Test ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
