#!/usr/bin/env python3
"""
Audio Reply Fix - Testing & Verification Guide
Complete step-by-step instructions to verify audio replies are working
"""

print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║              🎙️  HOW TO CHECK IF AUDIO REPLY IS WORKING                    ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝

There are 4 ways to verify the audio reply fix is working:

  1. QUICK TEST (2 minutes)          - Send voice message, check if you get audio
  2. LOG MONITORING (5 minutes)      - Watch real-time logs for success tags
  3. DETAILED DEBUGGING (10 minutes) - Check each step of the audio flow
  4. AUTOMATED TESTING (15 minutes)  - Run validation and diagnostic scripts


════════════════════════════════════════════════════════════════════════════════
METHOD 1: QUICK TEST (Fastest - 2 minutes)
════════════════════════════════════════════════════════════════════════════════

STEP 1: Make sure the app is running
   $ docker-compose ps
   
   Expected output:
   jeevo-backend    Up
   jeevo-postgres   Up
   jeevo-redis      Up

STEP 2: Send a voice message from WhatsApp
   ├─ Open WhatsApp
   ├─ Send voice message to your Jeevo number
   ├─ Message content: "बुखार है" or "I have fever"
   └─ Wait 5-10 seconds

STEP 3: Check what you received
   ✅ You received TEXT response?           → Good sign
   ✅ You received AUDIO response?          → Issue is FIXED! ✅
   ❌ You received only TEXT?               → Issue still exists
   ❌ You received nothing?                 → Check if app is running


════════════════════════════════════════════════════════════════════════════════
METHOD 2: LOG MONITORING (Recommended - 5 minutes)
════════════════════════════════════════════════════════════════════════════════

STEP 1: Start monitoring logs in Terminal 1
   $ docker logs -f jeevo-backend 2>&1 | grep -E "\\[AUDIO\\]|\\[VOICE\\]|\\[TTS\\]"

STEP 2: Send voice message in Terminal 2 (new terminal)
   ├─ Open WhatsApp
   ├─ Send voice: "बुखार है" (fever) or "दर्द है" (pain)
   └─ Go back to Terminal 1 to watch logs

STEP 3: Watch for these LOG MESSAGES in Terminal 1:

   ✅ EXPECTED SUCCESS LOGS:
   ──────────────────────────
   [AUTO-VOICE] Generating audio for medical response in hi
   [AUTO-VOICE] Response text length: XXX characters
   [TTS] Attempting TTS with fallback chain
   [TTS] ✅ ElevenLabs TTS succeeded - Generated XXXXX bytes
   [AUTO-VOICE] ✅ Audio file created: temp/auto_voice_xxx.ogg (XXXXX bytes)
   [VOICE] Sending audio message to +919999999999 (audio input)
   [AUDIO] Uploading audio file: temp/auto_voice_xxx.ogg
   [AUDIO] File size: XXXXX bytes
   [AUDIO] Upload response status: 200
   [AUDIO] ✅ Audio uploaded successfully with ID: 123456789
   [AUDIO] Using uploaded media ID: 123456789
   [AUDIO] ✅ Audio message sent successfully to +919999999999
   [VOICE] ✅ Audio message sent successfully

   🎉 If you see these logs → AUDIO REPLY IS WORKING! ✅

   ❌ ERROR LOGS to watch for:
   ─────────────────────────
   [AUDIO] Audio file too small         → TTS failed
   [AUDIO] Upload failed with status    → WhatsApp API issue
   [TTS] ❌ All TTS providers failed    → No audio provider working
   [VOICE] Failed to send voice message → Upload problem


════════════════════════════════════════════════════════════════════════════════
METHOD 3: DETAILED DEBUGGING (Step-by-step - 10 minutes)
════════════════════════════════════════════════════════════════════════════════

Check Each Step:

STEP 1: Verify app is running
   $ docker-compose ps | grep jeevo
   Expected: All containers "Up"

STEP 2: Check credentials
   $ grep -E "WHATSAPP_|ELEVENLABS" .env | head -5
   Expected: All fields have values (not empty)

STEP 3: Check audio files are being created
   $ ls -la temp/auto_voice_*.ogg
   Expected: Recent files with size > 10KB

STEP 4: Check upload logs for WhatsApp errors
   $ docker logs jeevo-backend | grep "\\[AUDIO\\]" | tail -20
   
   ✅ GOOD: "[AUDIO] ✅ Audio uploaded successfully"
   ❌ BAD:  "[AUDIO] Upload failed with status 401" → Check token
   ❌ BAD:  "[AUDIO] Upload failed with status 403" → Check phone ID

STEP 5: Check TTS logs
   $ docker logs jeevo-backend | grep "\\[TTS\\]" | tail -10
   
   ✅ GOOD: "[TTS] ✅ ElevenLabs TTS succeeded"
   ❌ BAD:  "[TTS] ❌ All TTS providers failed" → Check API key

STEP 6: Verify file cleanup happens
   $ docker logs jeevo-backend | grep "Cleaned up temp file" | tail -5
   Expected: Multiple cleanup entries


════════════════════════════════════════════════════════════════════════════════
METHOD 4: AUTOMATED TESTING (Complete validation - 15 minutes)
════════════════════════════════════════════════════════════════════════════════

STEP 1: Validate all fixes are applied
   $ python validate_audio_fixes.py
   
   Expected output:
   ✅ PASS: WhatsApp Audio Upload
   ✅ PASS: Webhook File Cleanup
   ✅ PASS: TTS Fallback Logging
   Result: 3/3 checks passed ✅

STEP 2: Run comprehensive verification
   $ python VERIFY_AUDIO_FIX.py
   
   Expected output:
   ✅ VERIFIED: Wait time increased from 0.5s to 2.0s
   ✅ VERIFIED: File size validation added
   ✅ VERIFIED: WhatsApp API error extraction added
   ✅ VERIFIED: MIME type auto-detection from file extension

STEP 3: Monitor logs in real-time
   $ python monitor_audio_logs.py
   
   This shows:
   - Live audio upload attempts
   - Success/failure status
   - Audio bytes generated
   - Session summary

STEP 4: End-to-end test
   $ python test_audio_flow.py
   
   This tests:
   - TTS generation
   - File creation
   - WhatsApp API connectivity


════════════════════════════════════════════════════════════════════════════════
QUICK REFERENCE: What to Look For
════════════════════════════════════════════════════════════════════════════════

✅ SIGNS AUDIO IS WORKING:
  1. Text response arrives immediately
  2. Audio response arrives within 5-10 seconds
  3. Logs show "[AUDIO] ✅ Audio message sent successfully"
  4. Logs show "[VOICE] ✅ Audio message sent successfully"
  5. No error messages in logs
  6. Temp audio files get cleaned up

❌ SIGNS AUDIO IS NOT WORKING:
  1. Only text response, no audio
  2. Logs show "[AUDIO] Upload failed"
  3. Logs show "[TTS] ❌ All TTS providers failed"
  4. Error: "Audio file too small"
  5. Error: "File not found"
  6. Temp files keep accumulating


════════════════════════════════════════════════════════════════════════════════
COMMON ISSUES & FIXES
════════════════════════════════════════════════════════════════════════════════

ISSUE 1: Only text arrives, no audio
─────────────────────────────────────
Check logs for:
  $ docker logs jeevo-backend | grep "\\[AUDIO\\].*failed"

If you see: "[AUDIO] Upload failed with status 401"
  → Fix: Check WHATSAPP_ACCESS_TOKEN in .env

If you see: "[AUDIO] Upload failed with status 403"
  → Fix: Check WHATSAPP_PHONE_NUMBER_ID in .env

If you see: "[AUDIO] Audio file too small"
  → Fix: ElevenLabs API issue, check ELEVENLABS_API_KEY in .env


ISSUE 2: No response at all (text or audio)
────────────────────────────────────────────
Check if app is running:
  $ docker-compose ps
  → If not running: docker-compose up -d

Check for webhook errors:
  $ docker logs jeevo-backend | grep "\\[WEBHOOK\\]"


ISSUE 3: App crashes when audio is sent
────────────────────────────────────────
Check app logs:
  $ docker logs jeevo-backend | tail -50

Restart app:
  $ docker-compose down && docker-compose up -d


════════════════════════════════════════════════════════════════════════════════
VERIFICATION CHECKLIST
════════════════════════════════════════════════════════════════════════════════

After following any test method, verify these:

□ All 3/3 validation checks pass (validate_audio_fixes.py)
□ Text messages reach user immediately
□ Voice message triggers audio generation
□ Audio file is created (size > 10KB)
□ Audio uploaded to WhatsApp successfully
□ Audio message reaches user
□ Logs show [AUDIO] ✅ tags
□ No [AUDIO] ❌ error tags
□ Temp files are cleaned up
□ No database errors
□ No Redis connection errors

If all boxes are checked ✅ → Audio reply is WORKING!


════════════════════════════════════════════════════════════════════════════════
TESTING SCENARIOS
════════════════════════════════════════════════════════════════════════════════

SCENARIO 1: Medical voice query (should get audio)
──────────────────────────────────────────────────
Send voice message: "बुखार है" or "I have fever"
Expected:
  ✅ Text response (medical advice)
  ✅ Audio response (same text as audio)
Logs:
  ✅ [AUTO-VOICE] Creating audio
  ✅ [AUDIO] Upload successful


SCENARIO 2: Non-medical voice query (should get text only)
──────────────────────────────────────────────────────────
Send voice message: "नमस्ते" or "Hello"
Expected:
  ✅ Text response
  ❌ NO audio response (by design)
Logs:
  ❌ No [AUTO-VOICE] tags (not medical)
  ❌ No [AUDIO] upload attempts


SCENARIO 3: Long medical query
──────────────────────────────
Send voice: "मुझे तेज़ बुखार है, पिछले 2 दिन से। सिर में दर्द भी है।"
Expected:
  ✅ Detailed text response
  ✅ Audio response
  ✅ Longer audio file (may take 10+ seconds)
Logs:
  ✅ [AUTO-VOICE] Response text length: XXX (should be high)
  ✅ [TTS] Generated XXXXX bytes (larger file)


════════════════════════════════════════════════════════════════════════════════
PERFORMANCE METRICS
════════════════════════════════════════════════════════════════════════════════

Expected timing:
  1. Message received:         0-1 seconds
  2. Transcribed:             1-3 seconds
  3. LLM response:            3-5 seconds
  4. Audio generated:         5-8 seconds
  5. Audio uploaded:          8-12 seconds
  6. Audio delivered:         12-15 seconds
  ────────────────────────────────────────
  Total expected time:        15 seconds

If taking longer:
  ❌ Check network speed
  ❌ Check TTS provider load
  ❌ Check WhatsApp API delays


════════════════════════════════════════════════════════════════════════════════
NEED HELP?
════════════════════════════════════════════════════════════════════════════════

1. Check logs:
   docker logs jeevo-backend | grep -E "\\[AUDIO\\]|ERROR"

2. Run validation:
   python validate_audio_fixes.py

3. Check credentials:
   grep WHATSAPP .env | grep -v "^#"
   grep ELEVENLABS .env

4. Check files:
   ls -la temp/ | grep auto_voice

5. Restart app:
   docker-compose down && docker-compose up -d

6. Monitor in real-time:
   python monitor_audio_logs.py


════════════════════════════════════════════════════════════════════════════════

✅ Once you verify using ANY of these 4 methods and see the success indicators,
   the audio reply fix is working correctly!

""")
