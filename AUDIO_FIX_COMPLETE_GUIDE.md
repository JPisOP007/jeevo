# 🎙️ AUDIO REPLY FIX - COMPLETE GUIDE

## ✅ What Was Fixed

### **Fix #1: Enhanced WhatsApp Audio Upload**
**File**: `app/services/whatsapp_service.py`

✅ **Improvements**:
- Added file size validation (100 bytes min, 16MB max)
- Detect MIME type from file extension
- Better error logging with WhatsApp error extraction
- Cleaner media ID tracking
- Added `[AUDIO]` debug tags for easy log filtering

**Before**:
```python
files = {"file": (os.path.basename(audio_path), audio_file, "audio/ogg")}
```

**After**:
```python
file_size = os.path.getsize(audio_path)
if file_size < 100:
    raise ValueError(f"Audio file too small ({file_size} bytes)")
    
file_ext = os.path.splitext(audio_path)[1].lower()
mime_type = "audio/ogg" if file_ext == ".ogg" else "audio/mpeg"
files = {"file": (os.path.basename(audio_path), audio_content, mime_type)}
```

---

### **Fix #2: Fixed File Cleanup Race Condition**
**File**: `app/routes/webhook.py`

✅ **Improvements**:
- Increased wait time from **0.5s to 2.0s** before file deletion
- WhatsApp needs time to complete media upload
- Both audio response handlers updated

**Before**:
```python
await asyncio.sleep(0.5)  # Too short!
```

**After**:
```python
await asyncio.sleep(2.0)  # Sufficient time for upload
```

---

### **Fix #3: Better TTS Logging**
**File**: `app/services/tts_fallback_service.py`

✅ **Improvements**:
- Added `[TTS]` prefix for easy filtering
- Log text length before generation
- Verify audio bytes aren't empty
- Better error messages

**Before**:
```python
logger.info("✅ ElevenLabs TTS succeeded")
```

**After**:
```python
logger.info(f"[TTS] ✅ ElevenLabs TTS succeeded - Generated {len(audio_bytes)} bytes")
```

---

### **Fix #4: Enhanced Audio Generation Logging**
**File**: `app/routes/webhook.py`

✅ **Improvements**:
- Log response text length
- Verify audio file was actually created
- Add traceback on failure
- Better state tracking

**Before**:
```python
logger.info(f"[AUTO-VOICE] Generated audio via {provider}")
```

**After**:
```python
file_size = os.path.getsize(output_path)
logger.info(f"[AUTO-VOICE] ✅ Audio file created: {output_path} ({file_size} bytes)")
```

---

## 🚀 How to Test Audio Reply

### **Step 1: Check Logs for [AUDIO], [VOICE], and [TTS] tags**

```bash
# Watch logs in real-time
docker logs -f jeevo-backend 2>&1 | grep -E "\[AUDIO\]|\[VOICE\]|\[TTS\]|\[AUTO-VOICE\]"
```

Expected flow:
```
[AUDIO] Uploading audio file: temp/auto_voice_abc123.ogg
[AUDIO] File size: 45678 bytes
[AUDIO] Upload response status: 200
[AUDIO] ✅ Audio uploaded successfully with ID: 123456789
[AUDIO] Using uploaded media ID: 123456789
[AUDIO] ✅ Audio message sent successfully to +919999999999
```

---

### **Step 2: Send Test Voice Message**

```
1. Open WhatsApp
2. Send a voice message to your Jeevo number
3. Example messages that trigger voice response:
   - "मुझे बुखार है" (I have fever)
   - "मुझे दर्द हो रहा है" (I'm in pain)
   - "Doctor ke pas jana chahiye?" (Should I see a doctor?)
```

---

### **Step 3: Verify Response**

You should receive:
1. ✅ Text response (always)
2. ✅ Audio response (if medical-related)

---

## 🔍 Troubleshooting

### **Issue: Text arrives but audio doesn't**

```bash
# Check logs for errors
docker logs jeevo-backend 2>&1 | grep -i "audio.*error\|upload.*failed"

# Look for:
# [AUDIO] Upload failed with status 401 → Check access token
# [AUDIO] Upload failed with status 403 → Check phone number ID
# [AUDIO] Upload failed with status 400 → Check file format
```

### **Issue: "Audio file too small" error**

This means TTS didn't generate audio. Check:
```bash
docker logs jeevo-backend 2>&1 | grep "\[TTS\]"
```

**Possible causes**:
- ElevenLabs API key missing
- API rate limit exceeded
- Text too short (minimum ~20 characters recommended)

### **Issue: File cleanup error**

```bash
docker logs jeevo-backend 2>&1 | grep "Failed to clean up"
```

This is usually harmless - file may already be deleted.

---

## 📊 Logging Guide

### **Tag Reference**

| Tag | Meaning | When |
|-----|---------|------|
| `[AUDIO]` | Audio upload/send | WhatsApp API calls |
| `[VOICE]` | Voice response | Sending audio to user |
| `[TTS]` | Text-to-speech | Converting text to audio |
| `[AUTO-VOICE]` | Auto voice generation | Medical response audio |

### **Example Log Trace**

```
1. User sends voice: "बुखार है"
   [WEBHOOK] Received audio message from +919999999999
   
2. Transcribe audio:
   [WHISPER] Transcribed: "बुखार है" in hi
   
3. Generate response:
   [LLM] Generated medical response (234 chars)
   
4. Create audio:
   [AUTO-VOICE] Generating audio for medical response in hi (audio input)
   [AUTO-VOICE] Response text length: 234 characters
   [TTS] Attempting TTS with fallback chain for language: hi
   [TTS] ✅ ElevenLabs TTS succeeded - Generated 45678 bytes
   [AUTO-VOICE] ✅ Audio file created: temp/auto_voice_abc123.ogg (45678 bytes)
   
5. Send to user:
   [VOICE] Sending audio message to +919999999999 (audio input)
   [AUDIO] Uploading audio file: temp/auto_voice_abc123.ogg
   [AUDIO] File size: 45678 bytes
   [AUDIO] Upload response status: 200
   [AUDIO] ✅ Audio uploaded successfully with ID: 123456789
   [AUDIO] Using uploaded media ID: 123456789
   [AUDIO] ✅ Audio message sent successfully to +919999999999
   [VOICE] ✅ Audio message sent successfully
```

---

## ✅ Verification Checklist

After applying fixes and restarting, verify:

- [ ] Text messages still working
- [ ] Text messages reach user immediately
- [ ] Voice messages reach user (with text)
- [ ] Audio response generated for medical questions
- [ ] Audio response uploaded to WhatsApp
- [ ] Audio message reaches user within 5 seconds of text
- [ ] No "upload failed" errors in logs
- [ ] Temp files cleaned up properly

---

## 🔧 Advanced Debugging

### **Manual Audio Test**

```bash
# Create test audio (16 bytes silence - will fail)
dd if=/dev/zero bs=1 count=16 of=test_small.ogg

# Create test audio (1MB - should work)
dd if=/dev/zero bs=1 count=1000000 of=test_large.ogg

# Test with script (coming soon)
python test_audio_upload.py
```

### **Check WhatsApp API Version**

```python
# In Python shell
from app.config.settings import settings
print(f"API URL: {settings.WHATSAPP_API_URL}")
# Should show: https://graph.facebook.com/v24.0
# (or v20.0, v23.0 - version may vary)
```

### **Verify Credentials**

```bash
# Check .env file for required values
grep -E "WHATSAPP_PHONE_NUMBER_ID|WHATSAPP_ACCESS_TOKEN|ELEVENLABS_API_KEY" .env

# Should not be empty
```

---

## 🎯 Known Limitations

1. **Max file size**: 16MB (WhatsApp limit)
2. **Max text length**: Depends on TTS provider (usually 5000 chars)
3. **Audio only for medical messages**: By design (prevents spam)
4. **Language support**: Limited by TTS provider (currently 10 Indian languages)

---

## 📞 Support

If audio still doesn't work after all fixes:

1. ✅ Check all fixes are applied: `python validate_audio_fixes.py`
2. ✅ Check credentials in `.env`
3. ✅ Check logs for `[AUDIO]`, `[VOICE]`, `[TTS]` tags
4. ✅ Test with longer medical query (minimum ~30 chars)
5. ✅ Ensure WhatsApp Business Account is verified
6. ✅ Check WhatsApp number can send text (if text works, API is OK)

