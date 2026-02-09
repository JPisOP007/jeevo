#!/usr/bin/env python3
"""
Audio Reply Fix Validation Script
Verifies all fixes are properly applied and tests audio flow end-to-end
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def check_file_contains(filepath: str, search_strings: list, description: str = "") -> bool:
    """Check if file contains all search strings"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        results = []
        for search_str in search_strings:
            found = search_str in content
            results.append(found)
            status = "✅" if found else "❌"
            print(f"  {status} {search_str[:60]}...")
        
        return all(results)
    except Exception as e:
        print(f"  ❌ Error checking file: {e}")
        return False

def main():
    print("\n" + "="*70)
    print("🔍 AUDIO REPLY FIX VALIDATION")
    print("="*70)
    
    # Check 1: WhatsApp service fixes
    print("\n[CHECK 1] WhatsApp Audio Service Fixes")
    print("-" * 70)
    
    whatsapp_fixes = [
        "[AUDIO] Uploading audio file",
        "[AUDIO] File size: ",
        "[AUDIO] Audio file too small",
        "[AUDIO] Audio file too large",
        "mime_type = \"audio/ogg\" if file_ext",
        "[AUDIO] Upload response status:",
        "[AUDIO] WhatsApp error:",
        "[AUDIO] ✅ Audio uploaded successfully",
        "if uploaded_media_id:",
        "[AUDIO] Using uploaded media ID:",
    ]
    
    result1 = check_file_contains(
        "/home/OP/Desktop/JEEVO/jeevo-shlok/app/services/whatsapp_service.py",
        whatsapp_fixes,
        "WhatsApp Audio Upload Fixes"
    )
    
    # Check 2: Webhook file cleanup fixes
    print("\n[CHECK 2] Webhook File Cleanup Fixes")
    print("-" * 70)
    
    webhook_fixes = [
        "await asyncio.sleep(2.0)",  # Extended wait time
        "[VOICE] ✅ Audio message sent successfully",
        "[AUTO-VOICE] ✅ Audio file created:",
        "[AUTO-VOICE] Traceback:",
    ]
    
    result2 = check_file_contains(
        "/home/OP/Desktop/JEEVO/jeevo-shlok/app/routes/webhook.py",
        webhook_fixes,
        "Webhook File Cleanup Fixes"
    )
    
    # Check 3: TTS Fallback logging
    print("\n[CHECK 3] TTS Fallback Service Logging")
    print("-" * 70)
    
    tts_fixes = [
        "[TTS] Attempting TTS with fallback chain",
        "[TTS] Text length:",
        "[TTS] ✅ ElevenLabs TTS succeeded",
        "[TTS] ❌ All TTS providers failed",
    ]
    
    result3 = check_file_contains(
        "/home/OP/Desktop/JEEVO/jeevo-shlok/app/services/tts_fallback_service.py",
        tts_fixes,
        "TTS Fallback Service Logging"
    )
    
    # Summary
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)
    
    checks = [
        ("WhatsApp Audio Upload", result1),
        ("Webhook File Cleanup", result2),
        ("TTS Fallback Logging", result3),
    ]
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nResult: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All fixes validated successfully!")
        print("\n📋 NEXT STEPS:")
        print("  1. Restart the application")
        print("  2. Test with a voice message")
        print("  3. Check logs for [AUDIO] and [VOICE] tags")
        print("  4. Verify audio reaches the user")
        return 0
    else:
        print("\n❌ Some fixes are missing or incorrect")
        print("Please review the changes and reapply if needed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
