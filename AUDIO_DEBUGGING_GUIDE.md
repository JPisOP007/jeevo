# 🎙️ JEEVO Audio Reply - Debugging Guide

## 📊 Current Status: `Audio NOT Reaching User`

---

## 🔍 Root Cause Analysis

### **Flow Trace: Text Voice Message → Audio Reply**

```
1. User sends voice message (WhatsApp)
   ↓
2. Webhook receives & downloads audio
   ✅ WORKING: `whatsapp_service.download_media()`
   ✅ WORKING: Whisper STT transcribes to text
   ✅ WORKING: LLM generates response text
   ↓
3. Auto-generate audio response
   ⚠️ ISSUE: `tts_fallback_service.text_to_speech_with_fallback()`
   ↓
4. Save audio to temp file
   ✅ WORKING: Creates `temp/auto_voice_*.ogg`
   ↓
5. Upload to WhatsApp
   ❌ BLOCKING: `whatsapp_service.send_audio_message()`
   ↓
6. User receives audio
   ❌ FAILS HERE - Audio not arriving
```

---

## 🎯 Critical Issues

### **Issue 1: ElevenLabs TTS Format**
- **Status**: ⚠️ Partially Configured
- **Location**: `app/ai/elevenlabs_tts.py`
- **Current**: Returns raw Opus/OGG bytes
- **Problem**: No format validation or error handling
- **Fix Needed**: Verify audio format before sending

### **Issue 2: WhatsApp Media Upload Endpoint**
- **Status**: ❌ Likely Wrong
- **Location**: `app/services/whatsapp_service.py` line 175
- **Current**: 
  ```python
  upload_url = f"{self.api_url}/{self.phone_number_id}/media"
  ```
- **Problem**: This endpoint might not exist or work differently
- **WhatsApp Correct Endpoint**: 
  ```
  POST /v20.0/{phone-number-id}/media
  Content-Type: multipart/form-data
  ```

### **Issue 3: Audio File Cleanup Too Early**
- **Status**: ⚠️ Race Condition
- **Location**: `app/routes/webhook.py` line 1013
- **Problem**: File deleted before upload completes
- **Current**:
  ```python
  await asyncio.sleep(0.5)  # Only 500ms wait
  if os.path.exists(response["audio_path"]):
      os.remove(response["audio_path"])
  ```
- **Fix**: Increase wait time or delete after confirmation

### **Issue 4: No Logging of Audio Upload Errors**
- **Status**: ❌ Missing Diagnostics
- **Location**: `app/services/whatsapp_service.py` line 191-205
- **Problem**: Upload errors not properly logged
- **Impact**: Can't debug upload failures

### **Issue 5: Missing gTTS Fallback Verification**
- **Status**: ⚠️ Untested
- **Location**: `app/services/tts_fallback_service.py`
- **Problem**: Fallback to gTTS may not work if module missing
- **Current Check**:
  ```python
  def _can_use_gtts(self) -> bool:
      try:
          import gtts
          return True
      except ImportError:
          return False
  ```

---

## 🧪 How to Test

### **Step 1: Test TTS Generation**
```bash
cd /home/OP/Desktop/JEEVO/jeevo-shlok
python test_audio_flow.py
```

This will:
- ✅ Test ElevenLabs TTS initialization
- ✅ Test Hindi/English text-to-speech
- ✅ Test gTTS fallback
- ✅ Save test audio file
- ✅ Check WhatsApp credentials

### **Step 2: Manual Audio Test**
```bash
# Send a test voice message to your WhatsApp number
# Check if you receive:
# - Text response ✓
# - Audio response ✓
# Watch logs for errors
```

### **Step 3: Check Logs**
```bash
docker logs jeevo-backend | grep -i "VOICE\|AUDIO\|TTS"
```

---

## 🔧 Fixes to Apply

### **Fix 1: Verify WhatsApp Media Upload Endpoint**

The current endpoint might be wrong. WhatsApp Cloud API expects:
```
POST /v{version}/{phone-number-id}/media
```

But we're using:
```python
upload_url = f"{self.api_url}/{self.phone_number_id}/media"
```

**This should be**:
```python
# If self.api_url is "https://graph.facebook.com/v24.0"
# Then upload_url = "https://graph.facebook.com/v24.0/{phone_number_id}/media"
# Which is CORRECT
```

**Actual problem**: Need to check if we're using the right version (v24.0 vs v20.0, etc.)

### **Fix 2: Extend File Cleanup Wait Time**

```python
# CURRENT (line 1013-1014)
await asyncio.sleep(0.5)
if os.path.exists(response["audio_path"]):
    os.remove(response["audio_path"])

# SHOULD BE
await asyncio.sleep(2.0)  # Increase to 2 seconds
if os.path.exists(response["audio_path"]):
    os.remove(response["audio_path"])
```

### **Fix 3: Add Better Error Logging**

In `app/services/whatsapp_service.py`, enhance the upload error handling:

```python
if upload_response.status_code not in [200, 201]:
    error_detail = upload_response.text
    logger.error(f"Upload failed with {upload_response.status_code}: {error_detail}")
    # ADD THIS:
    try:
        error_json = upload_response.json()
        logger.error(f"WhatsApp Error: {error_json.get('error', {})}")
    except:
        pass
    raise ValueError(f"Media upload failed: {error_detail}")
```

### **Fix 4: Verify Audio File Before Upload**

```python
# ADD this before attempting upload:
if not os.path.exists(audio_path):
    logger.error(f"Audio file missing: {audio_path}")
    raise FileNotFoundError(f"Audio file not found: {audio_path}")

file_size = os.path.getsize(audio_path)
logger.debug(f"Audio file size: {file_size} bytes")

if file_size < 100:  # Minimum audio size
    logger.error(f"Audio file too small: {file_size} bytes")
    raise ValueError("Audio file appears corrupted or too small")
```

---

## 📋 Checklist for Diagnosis

- [ ] Is `ELEVENLABS_API_KEY` in `.env`?
- [ ] Is `WHATSAPP_PHONE_NUMBER_ID` correct?
- [ ] Is `WHATSAPP_ACCESS_TOKEN` valid?
- [ ] Is WhatsApp Business Account verified?
- [ ] Is the phone number being tested registered?
- [ ] Are text messages reaching the user? (If yes, API credentials work)
- [ ] Are temp audio files being created? (Check `temp/` folder)
- [ ] What are the logs showing?

---

## 🚀 Quick Fix Priority

### **Priority 1: CRITICAL** (Do First)
1. Run `test_audio_flow.py` to identify exact failure point
2. Check WhatsApp logs for upload errors
3. Verify credentials in `.env`

### **Priority 2: HIGH** (Do Second)
1. Extend file cleanup wait time from 0.5s to 2.0s
2. Add better error logging in upload function
3. Verify audio file before upload

### **Priority 3: MEDIUM** (Do After)
1. Test gTTS fallback
2. Add retry logic for failed uploads
3. Implement audio format conversion if needed

---

## 📞 Next Steps

1. **Run the test script** to identify exact issue
2. **Share the output** so we can see where it fails
3. **Check `.env`** file for missing credentials
4. **Apply fixes** based on test results

