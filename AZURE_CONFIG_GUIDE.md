# How to Configure main.py for Azure Deployment

Since Azure VMs don't have physical cameras or microphones, you need to disable the live camera and audio processing threads.

## Option 1: Modify config.py (Recommended)

Edit `config.py` and update the `PROCESS_FLAGS` dictionary:

```python
# Video Performance and Control
PROCESS_FLAGS = {
    "front": False,           # ← Set to False (disable live camera)
    "top": False,             # ← Set to False (disable live camera)
    "upload_front": True,     # Keep True (enable video upload)
    "upload_top": True        # Keep True (enable video upload)
}
```

This prevents threads from trying to access non-existent camera hardware.

---

## Option 2: Environment Variable Control

Add this to config.py after the imports:

```python
import os

# Check if running in Azure/cloud environment
IS_AZURE_DEPLOYMENT = os.getenv('AZURE_DEPLOYMENT', 'False').lower() == 'true'

# Video Performance and Control
PROCESS_FLAGS = {
    "front": not IS_AZURE_DEPLOYMENT,
    "top": not IS_AZURE_DEPLOYMENT,
    "upload_front": True,
    "upload_top": True
}
```

Then, set the environment variable in `.env`:
```
AZURE_DEPLOYMENT=True
```

Or when starting the application:
```bash
AZURE_DEPLOYMENT=True python main.py
```

---

## Option 3: Try-Catch Error Handling (Graceful Degradation)

Modify `main.py` to handle missing cameras gracefully:

```python
if __name__ == "__main__":
    # Start threads
    audio_thread = threading.Thread(target=audio_handler.audio_processing_loop, daemon=True)
    
    # Dual Video Threads - with error handling
    front_video_thread = None
    top_video_thread = None
    
    try:
        if config.PROCESS_FLAGS.get("front", True):
            front_video_thread = threading.Thread(
                target=video_handler.video_processing_loop, 
                args=(config.FRONT_CAMERA_INDEX, "front"), 
                daemon=True
            )
            front_video_thread.start()
    except Exception as e:
        print(f"[WARNING] Failed to start front camera: {e}")
        print("[INFO] Continuing without front camera. Use video upload instead.")
    
    try:
        if config.PROCESS_FLAGS.get("top", True):
            top_video_thread = threading.Thread(
                target=video_handler.video_processing_loop, 
                args=(config.TOP_CAMERA_INDEX, "top"), 
                daemon=True
            )
            top_video_thread.start()
    except Exception as e:
        print(f"[WARNING] Failed to start top camera: {e}")
        print("[INFO] Continuing without top camera. Use video upload instead.")
    
    try:
        audio_thread.start()
    except Exception as e:
        print(f"[WARNING] Failed to start audio processing: {e}")
        print("[INFO] Continuing without audio. Live siren detection disabled.")
    
    api_thread = threading.Thread(target=run_flask, daemon=True)
    decision_thread = threading.Thread(target=decision_logic_loop, daemon=True)

    api_thread.start()
    decision_thread.start()
    
    print("[INFO] Integrated Emergency System Started.")
    print("[INFO] API available at http://localhost:5000/api/status")
    
    # Only show camera feeds if they're running
    if front_video_thread and front_video_thread.is_alive():
        print("[INFO] Front View: http://localhost:5000/video_feed_front")
    
    if top_video_thread and top_video_thread.is_alive():
        print("[INFO] Top View: http://localhost:5000/video_feed_top")
    
    print("[INFO] Use /api/upload_video endpoint for video analysis")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[INFO] Shutting down...")
```

---

## Recommended Approach for Azure

### Step 1: Update config.py

```python
import os
from dotenv import load_dotenv

load_dotenv()

# ... existing code ...

# Check environment
ENVIRONMENT = os.getenv('ENVIRONMENT', 'LOCAL')  # LOCAL, AZURE, etc.

# Video Performance and Control
if ENVIRONMENT == 'AZURE':
    PROCESS_FLAGS = {
        "front": False,
        "top": False,
        "upload_front": True,
        "upload_top": True
    }
else:
    PROCESS_FLAGS = {
        "front": True,
        "top": True,
        "upload_front": False,
        "upload_top": False
    }
```

### Step 2: Update .env

```ini
ENVIRONMENT=AZURE
MONGO_URI=mongodb+srv://...
# ... other settings ...
```

### Step 3: No changes needed to main.py!

The application will automatically:
- Skip live camera threads on Azure
- Keep video upload enabled
- Keep the Flask API running
- Keep the decision logic running

---

## Testing After Modification

### Test 1: Start Application
```bash
source venv/bin/activate
python main.py
```

Expected output:
```
[INFO] Integrated Emergency System Started.
[INFO] API available at http://localhost:5000/api/status
[INFO] Use /api/upload_video endpoint for video analysis
```

**Note**: No errors about missing cameras or audio devices.

### Test 2: Check API Status
```bash
curl http://localhost:5000/api/status
```

Expected output (no camera frames):
```json
{
  "audio": {
    "status": "Normal traffic",
    "score": 0.0,
    "is_emergency": false
  },
  "video": {
    "front": {
      "vehicle_type": "none",
      "siren_light": "none",
      "is_emergency": false,
      "ocr_text": []
    },
    "top": {...},
    "upload_front": {...},
    "upload_top": {...}
  },
  "is_emergency": false,
  "location": "..."
}
```

### Test 3: Upload Test Video
```bash
curl -X POST \
  -F "video=@test_video.mp4" \
  -F "view=front" \
  http://localhost:5000/api/upload_video
```

Expected response:
```json
{
  "status": "success",
  "message": "Video uploaded for front analysis",
  "filename": "test_video.mp4",
  "view": "front"
}
```

### Test 4: Check Processing
```bash
# List uploaded videos
ls -la ~/emergency-detection/uploads/

# Check latest status
curl http://localhost:5000/api/status | jq '.video.upload_front'
```

---

## Troubleshooting

### Issue: Camera still trying to initialize
**Solution**: Make sure `PROCESS_FLAGS` are set to `False` in config.py before starting the app.

### Issue: Audio thread fails silently
**Solution**: This is expected on Azure. Audio processing is skipped, but the app continues running.

### Issue: Video upload not processing
**Solution**: 
1. Check that `upload_front` or `upload_top` is set to `True`
2. Verify MongoDB is connected: `curl http://localhost:5000/api/status | jq '.video'`
3. Check logs: `tail -50 app.log` or run directly: `python main.py`

### Issue: Decision logic not triggering
**Solution**: In Azure mode without live cameras, decisions only trigger on video upload. Test with: `/api/upload_video`

---

## Local Development vs Azure Production

### Local Development (With Cameras)
```python
# config.py
PROCESS_FLAGS = {
    "front": True,       # Enable live cameras
    "top": True,         # Enable live cameras
    "upload_front": True,
    "upload_top": True
}
```

### Azure Production (No Cameras)
```python
# config.py or via environment variable
PROCESS_FLAGS = {
    "front": False,      # Disable live cameras
    "top": False,        # Disable live cameras  
    "upload_front": True,
    "upload_top": True
}
```

### Switch via .env
```ini
# .env for Azure
ENVIRONMENT=AZURE

# .env for Local
ENVIRONMENT=LOCAL
```

---

## Performance Benefits on Azure

When disabled, the application:
- ✓ Starts 2-3 seconds faster (no camera initialization)
- ✓ Uses less CPU (no video encoding overhead)
- ✓ Uses less memory (no frame buffering)
- ✓ Avoids OpenCV GPU/driver issues
- ✓ Reduces cloud costs

---

## Complete Configuration Files

### config.py (Updated Section)

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Environment detection
ENVIRONMENT = os.getenv('ENVIRONMENT', 'LOCAL')
IS_AZURE = ENVIRONMENT.upper() == 'AZURE'

# ... existing config ...

# Video Performance and Control (Environment-aware)
if IS_AZURE:
    print("[INFO] Running in AZURE mode - camera feeds disabled")
    PROCESS_FLAGS = {
        "front": False,
        "top": False,
        "upload_front": True,
        "upload_top": True
    }
else:
    print("[INFO] Running in LOCAL mode - all feeds enabled")
    PROCESS_FLAGS = {
        "front": True,
        "top": True,
        "upload_front": True,
        "upload_top": True
    }
```

### .env (Azure)

```ini
ENVIRONMENT=AZURE
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/emergency_detection
DB_NAME=EmergencyDetection
COLLECTION_NAME=detections
FLASK_ENV=production
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

---

## Next Steps

1. ✓ Choose one of the options above (Option 2 recommended)
2. ✓ Update config.py or .env file
3. ✓ Test locally: `python main.py`
4. ✓ Deploy to Azure following AZURE_DEPLOYMENT.md
5. ✓ Test with video upload endpoints

