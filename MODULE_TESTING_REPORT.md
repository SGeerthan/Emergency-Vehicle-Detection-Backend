# Emergency Detection System - Module Testing Report

**Project:** Integrated Emergency Vehicle Detection System  
**Date:** April 28, 2026  
**System Type:** Multi-Modal Detection (Audio + Video)  

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Module Breakdown](#module-breakdown)
3. [API Endpoints](#api-endpoints)
4. [Testing Guidelines](#testing-guidelines)

---

## System Overview

This is a comprehensive emergency vehicle detection system that uses multiple sensors and AI models to identify emergency vehicles (ambulances, fire trucks, police vehicles) through:
- **Audio Detection**: Siren recognition using YAMNet ML model
- **Video Detection**: Vehicle classification using YOLO and light blinking detection
- **Text Recognition**: OCR-based keyword detection (ambulance, police, etc.)
- **Location-based Alerting**: SMS notifications to on-duty staff

---

## Module Breakdown

### 1. **audio_handler.py**

#### Purpose
Processes real-time audio from microphone to detect emergency sirens using Google's YAMNet acoustic model.

#### Key Components
- **YAMNet Model**: Pretrained TensorFlow Hub model for audio classification
- **Frequency Analysis**: Analyzes dominant frequency and wavelength of audio
- **Temporal Smoothing**: Reduces false positives using temporal counter (default: 1 frame = instant response)
- **Siren Classification**: Detects keywords like "siren", "police car (siren)", "ambulance (siren)"

#### Configuration Parameters
```
SAMPLE_RATE = 16000 Hz
BLOCK_DURATION = 0.96 seconds
LOWCUT = 100 Hz (frequency filter lower bound)
HIGHCUT = 8000 Hz (frequency filter upper bound)
CONF_THRESHOLD_AUDIO = 0.05
SIREN_SCORE_THRESHOLD = 0.05
TEMPORAL_FRAMES = 1 (instant trigger)
```

#### How It Works
1. Captures audio blocks from microphone (960 samples at 16kHz)
2. Maintains rolling 1-second buffer for context
3. Passes buffer through YAMNet to get classification scores
4. Calculates aggregate siren score from relevant classes
5. Detects dominant frequency and wavelength
6. Updates global state with status (SIREN DETECTED / Normal traffic)

#### Output Data Structure
```json
{
  "status": "SIREN DETECTED" or "Normal traffic",
  "confidence": 0.75,
  "label": "police car (siren)",
  "category": "SIREN" or "NORMAL TRAFFIC",
  "dominant_freq": 450.5,
  "valid_frequency": true,
  "wavelength": 0.7622
}
```

#### Test Cases
- [ ] Test with live siren audio
- [ ] Test with background traffic noise
- [ ] Verify frequency analysis accuracy
- [ ] Check false positive rate during normal traffic
- [ ] Validate temporal smoothing with TEMPORAL_FRAMES=1

---

### 2. **video_handler.py**

#### Purpose
Processes video streams from dual cameras (front and top) to detect emergency vehicles, identify siren lights, and recognize emergency text using YOLO and OCR.

#### Key Components
- **YOLO Model**: `bestAllVehicle.pt` - Custom trained model for vehicle detection
- **Emergency Vehicle Classes**: Ambulance, Firetruck, Police
- **Siren Light Detection**: Identifies red/blue/amber blinking lights
- **OCR Reader**: EasyOCR for text recognition on vehicles
- **Blinking Detection**: Analyzes historical frames for light pattern

#### Configuration Parameters
```
MODEL_PATH = "bestAllVehicle.pt"
FRAME_SKIP = 4 (Run YOLO every 4th frame)
OCR_INTERVAL = 10 (Run OCR every 10th frame if vehicle detected)
INFERENCE_SIZE = (320, 320)
MAX_FPS = 30
BRIGHTNESS_THRESHOLD = 200
BLINK_HISTORY = 18 frames
BLINK_MIN_RATIO = 0.25
BLINK_MAX_RATIO = 0.75
MIN_CONTOUR_AREA = 120 pixels
MAX_CONTOUR_AREA = 4000 pixels
```

#### How It Works
1. Captures frames from camera (or video file if uploaded)
2. Resizes to inference size (320x320) for faster processing
3. Runs YOLO detection every FRAME_SKIP frames
4. For each detected vehicle:
   - Classifies vehicle type (ambulance, police, firetruck)
   - Crops ROI and analyzes for siren lights
   - Detects red/blue/amber blinking patterns
   - Runs OCR every OCR_INTERVAL frames to find emergency keywords
5. Updates video state with vehicle type, light status, OCR text

#### Siren Light Detection Logic
- **Red Detection**: HSV range [0-10, 120-255, 180-255] + [170-180, 120-255, 180-255]
- **Blue Detection**: HSV range [90-130, 120-255, 180-255]
- **Amber Detection**: HSV range [10-28, 120-255, 180-255]
- **Blinking Criteria**: 25-75% of frames in history show light (indicates flashing)

#### OCR Keywords Detected
```
ambulance, emergency, hospital, medical,
suwasariya, 1990, first aid,
police, traffic, 119, fire, rescue,
vip, municipal council
```

#### Output Data Structure
```json
{
  "vehicle_type": "ambulance",
  "siren_light": "red blinking",
  "ocr_text": ["ambulance", "emergency"],
  "is_emergency": true,
  "running": true
}
```

#### Camera Configuration
- **Front Camera**: Index 1 (Usually mounted at vehicle front)
- **Top Camera**: Index 2 (Usually mounted on top of vehicle/pole)

#### Test Cases
- [ ] Test with live vehicle detection
- [ ] Test uploaded video files (MP4, AVI, MOV, MKV)
- [ ] Verify YOLO accuracy on emergency vehicles
- [ ] Test siren light blinking detection
- [ ] Test OCR on license plates and vehicle text
- [ ] Verify frame skipping performance optimization
- [ ] Test with front camera only
- [ ] Test with top camera only

---

### 3. **db_handler.py**

#### Purpose
Manages all database operations with MongoDB for storing detections, alerts, and emergency information.

#### Collections
1. **Traffic_Signals_IOT**: Main detection events
2. **all_vehicle_detections**: Generic vehicle detection analytics
3. **emergency_information**: Complete emergency event JSON snapshots
4. **SUMOinjections**: Traffic simulation data for SUMO

#### Key Functions

##### `save_detection()`
Logs individual detection events with full details.

```python
def save_detection(view_name, vehicle_type, siren_light, 
                   ocr_text, is_emergency, audio_status="Normal traffic")
```

Fields Saved:
- timestamp
- camera_view (front/top/upload_front/upload_top)
- vehicle_type (ambulance/police/firetruck)
- siren_light (red/blue/amber blinking or None)
- ocr_text (extracted text from vehicle)
- is_emergency (boolean)
- audio_status (SIREN DETECTED / Normal traffic)

##### `save_generic_detection()`
Saves aggregated detection data for analytics.

```python
def save_generic_detection(vehicle_type, is_emergency, siren_light="None")
```

##### `save_emergency_info()`
Saves complete sensor data JSON snapshot when emergency detected.

```python
def save_emergency_info(info_dict)
```

Includes entire `config.latest_data` structure with all audio/video states.

##### `save_final_decision()`
Logs final decision after emergency confirmation.

```python
def save_final_decision(confirmed_type, location, details)
```

##### `save_sumo_injection()`
Stores data for traffic simulation system.

```python
def save_sumo_injection(vehicle_type, entry_point="-E4")
```

##### `get_analytics_data(date_str)`
Retrieves detection statistics for a specific date.

##### `get_recent_alerts()`
Returns recent emergency alerts.

##### `get_latest_detection()`
Returns most recent detection event.

##### `delete_alert(alert_id)`
Removes an alert from database.

#### Database Connection
```
MONGO_URI: From environment variable
DB_NAME: "EmergencyDetection" (default)
COLLECTION_NAME: "Traffic_Signals_IOT"
```

#### Test Cases
- [ ] Test MongoDB connection
- [ ] Verify save_detection() records all fields correctly
- [ ] Verify timestamps are accurate
- [ ] Test emergency info JSON storage
- [ ] Test analytics data retrieval
- [ ] Test alert deletion
- [ ] Verify data integrity in database

---

### 4. **staff_handler.py**

#### Purpose
Manages on-duty staff database and sends SMS alerts to relevant personnel when emergencies are detected.

#### Key Functions

##### `init_staff_file()`
Initializes CSV file if not exists: `policemen_duty.csv`

Headers: Name, Phone, Location

##### `add_staff(name, phone, location)`
Adds new staff member to records.

```python
def add_staff(name: str, phone: str, location: str) -> bool
```

##### `get_all_staff()`
Returns list of all staff members as dictionaries.

```python
def get_all_staff() -> List[Dict]
```

##### `get_staff_by_location(location)`
Finds all staff members registered for a specific location.
- Case-insensitive matching
- Partial location name matching

```python
def get_staff_by_location(location: str) -> List[str]
```

Returns: List of phone numbers

##### `send_sms_alert(phone_number, vehicle_type, location)`
Sends SMS via smsapi.lk gateway or mock mode.

```python
def send_sms_alert(phone_number: str, vehicle_type: str, location: str) -> bool
```

Message Format:
```
EMERGENCY! {vehicle_type} detected at {location}. Please clear traffic immediately.
```

Mock Mode (when SMS_API_KEY = "YOUR_API_KEY_HERE"):
```
[MOCK SMS] To: 94xxxxxxxxxx | Message: EMERGENCY! Ambulance detected at Colombo, Western. Please clear traffic.
```

##### `trigger_location_alerts(vehicle_type, location)`
Sends SMS to all on-duty staff at a location when emergency detected.

```python
def trigger_location_alerts(vehicle_type: str, location: str)
```

#### Configuration
```
STAFF_FILE_PATH = "policemen_duty.csv"
SMS_API_KEY = From environment variable
SMS_SENDER_ID = From environment variable
SMS_GATEWAY_URL = "https://api.smsapi.lk/Send"
```

#### SMS Gateway
- **Provider**: smsapi.lk
- **Timeout**: 10 seconds
- **Expected Response**: `{"status": "success"}`

#### Test Cases
- [ ] Test CSV file initialization
- [ ] Test adding staff members
- [ ] Test retrieving all staff
- [ ] Test location-based staff filtering
- [ ] Test SMS sending (mock mode)
- [ ] Test SMS error handling
- [ ] Test alert triggering with mock SMS

---

### 5. **config.py**

#### Purpose
Central configuration file storing all system parameters, constants, and shared state.

#### Audio Configuration
```python
SAMPLE_RATE = 16000
BLOCK_DURATION = 0.96
BLOCK_SIZE = 15360
LOWCUT = 100 Hz
HIGHCUT = 8000 Hz
SIREN_KEYWORDS = ["siren", "police car (siren)", "ambulance (siren)", 
                  "fire engine, fire truck (siren)", "emergency vehicle"]
SIREN_SCORE_THRESHOLD = 0.05
```

#### Video Configuration
```python
BRIGHTNESS_THRESHOLD = 200
MIN_CONTOUR_AREA = 120
MAX_CONTOUR_AREA = 4000
BLINK_HISTORY = 18
BLINK_MIN_RATIO = 0.25
BLINK_MAX_RATIO = 0.75
MODEL_PATH = "bestAllVehicle.pt"
FRAME_SKIP = 4
OCR_INTERVAL = 10
INFERENCE_SIZE = (320, 320)
MAX_FPS = 30
```

#### Camera Configuration
```python
FRONT_CAMERA_INDEX = 1
TOP_CAMERA_INDEX = 2
```

#### Process Control Flags
```python
PROCESS_FLAGS = {
    "front": True,
    "top": True,
    "upload_front": False,
    "upload_top": False
}
```

#### Shared State Structure
```python
latest_data = {
    "audio": {
        "status": str,
        "confidence": float,
        "label": str,
        "top_class": str,
        "category": str,
        "dominant_freq": int,
        "wavelength": float
    },
    "video": {
        "front": {
            "vehicle_type": str,
            "siren_light": str,
            "ocr_text": [],
            "is_emergency": bool,
            "running": bool
        },
        "top": { ... },
        "upload_front": { ... },
        "upload_top": { ... },
        "is_emergency": bool
    },
    "system": {
        "last_update": str (ISO format),
        "search_mode": bool,
        "search_reason": str
    }
}
```

#### Environment Variables Required
```
MONGO_URI: MongoDB connection string
DB_NAME: Database name
COLLECTION_NAME: Collection name
SMS_API_KEY: SMS API key from smsapi.lk
LOCATION: System location (fetched from IP geolocation)
```

#### Dynamic Location Detection
- Fetches location from ipinfo.io API
- Format: "City, Region"
- Fallback: "Unknown Location"

---

### 6. **main.py**

#### Purpose
Central application orchestrator that:
- Starts all processing threads
- Runs Flask API server
- Implements emergency decision logic
- Coordinates between all modules

#### Threads Started
1. **Audio Thread**: `audio_handler.audio_processing_loop()`
2. **Front Video Thread**: `video_handler.video_processing_loop(camera_index=1, view="front")`
3. **Top Video Thread**: `video_handler.video_processing_loop(camera_index=2, view="top")`
4. **API Thread**: `run_flask()` - Flask server on port 5000
5. **Decision Thread**: `decision_logic_loop()`

#### Decision Logic
Monitors for emergency conditions and executes:
1. Determines emergency vehicle type using priority logic:
   - **Priority Order**: Ambulance > Fire Truck > Police/VIP
2. Saves final decision to MongoDB
3. Records SUMO injection data
4. Saves complete emergency info JSON
5. **Triggers SMS alerts** to relevant staff

#### Upload Folder
```
uploads/
- Stores uploaded video files
- Allowed formats: mp4, avi, mov, mkv
- Maximum file size: Depends on Flask config (default 16MB)
```

#### Test Cases
- [ ] Verify all threads start successfully
- [ ] Test Flask API availability
- [ ] Test emergency detection triggering
- [ ] Verify priority logic for vehicle type selection
- [ ] Test SMS triggering on emergency detection
- [ ] Verify database logging occurs
- [ ] Check performance with all threads running

---

## API Endpoints

### Base URL
```
http://localhost:5000
```

### Status & Data Endpoints

#### 1. Get System Status
```
GET /api/status
```
Returns: Current state of all sensors (audio, video, system)

**Response:**
```json
{
  "audio": {
    "status": "SIREN DETECTED",
    "confidence": 0.75,
    "label": "police car (siren)",
    "category": "SIREN",
    "dominant_freq": 450.5,
    "wavelength": 0.7622
  },
  "video": {
    "front": {
      "vehicle_type": "police",
      "siren_light": "red blinking",
      "ocr_text": ["POLICE", "119"],
      "is_emergency": true,
      "running": true
    },
    "top": { ... },
    "is_emergency": true
  },
  "system": {
    "last_update": "2026-04-28T14:30:45.123456",
    "search_mode": true,
    "search_reason": "Audio Siren"
  }
}
```

---

#### 2. Get Analytics
```
GET /api/analytics?date=YYYY-MM-DD
```
Query Parameters:
- `date` (optional): Filter by specific date

Returns: Statistics for detections on specified date

**Response:**
```json
{
  "total_detections": 15,
  "emergency_vehicles": 12,
  "false_alarms": 3,
  "detection_types": {
    "ambulance": 5,
    "police": 4,
    "firetruck": 3
  }
}
```

---

#### 3. Get Recent Alerts
```
GET /api/alerts
```
Returns: List of recent emergency alerts (last 24 hours)

**Response:**
```json
[
  {
    "_id": "ObjectId",
    "timestamp": "2026-04-28T14:30:45.123456",
    "vehicle_type": "Ambulance",
    "location": "Colombo, Western",
    "status": "active" | "resolved"
  }
]
```

---

#### 4. Get Latest Detection
```
GET /api/latest_detection
```
Returns: Most recent detection event with full details

**Response:**
```json
{
  "_id": "ObjectId",
  "timestamp": "2026-04-28T14:30:45.123456",
  "camera_view": "front",
  "vehicle_type": "ambulance",
  "siren_light": "red blinking",
  "ocr_text": ["AMBULANCE", "1990"],
  "is_emergency": true,
  "audio_status": "SIREN DETECTED"
}
```

---

### Staff Management Endpoints

#### 5. Get All Staff
```
GET /api/staff
```
Returns: List of all on-duty staff members

**Response:**
```json
[
  {
    "Name": "Officer John",
    "Phone": "94xxxxxxxxxx",
    "Location": "Colombo"
  },
  {
    "Name": "Officer Jane",
    "Phone": "94xxxxxxxxxx",
    "Location": "Colombo"
  }
]
```

---

#### 6. Add Staff Member
```
POST /api/staff
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "Officer John",
  "phone": "94xxxxxxxxxx",
  "location": "Colombo"
}
```

**Response (Success - 201):**
```json
{
  "status": "success"
}
```

**Response (Error - 400):**
```json
{
  "status": "error",
  "message": "Missing fields"
}
```

---

### Video Processing Endpoints

#### 7. Upload Video
```
POST /api/upload_video
Content-Type: multipart/form-data
```

**Parameters:**
- `video` (file, required): Video file (mp4, avi, mov, mkv)
- `view` (string, optional): Camera view - "front" or "top" (default: "front")

**Response (Success - 200):**
```json
{
  "status": "success",
  "message": "Video uploaded for front analysis",
  "filename": "sample_video.mp4",
  "view": "front"
}
```

**Response (Error - 400):**
```json
{
  "status": "error",
  "message": "File type not allowed"
}
```

Allowed Extensions: `.mp4`, `.avi`, `.mov`, `.mkv`

---

#### 8. Video Control
```
POST /api/video/control
Content-Type: application/json
```

**Request Body:**
```json
{
  "view": "front",
  "action": "start" | "stop"
}
```

**Parameters:**
- `view`: "front", "top", "upload_front", or "upload_top"
- `action`: "start" to resume processing, "stop" to pause

**Response (Success - 200):**
```json
{
  "status": "success",
  "message": "front started"
}
```

**Response (Error - 400):**
```json
{
  "status": "error",
  "message": "Invalid view"
}
```

---

### Video Feed Streaming Endpoints

#### 9. Front Camera Feed
```
GET /video_feed_front
```
Returns: MJPEG stream of front camera with annotations

**Content-Type:** `multipart/x-mixed-replace; boundary=frame`

---

#### 10. Top Camera Feed
```
GET /video_feed_top
```
Returns: MJPEG stream of top camera with annotations

**Content-Type:** `multipart/x-mixed-replace; boundary=frame`

---

#### 11. Upload Front Video Feed
```
GET /video_feed_upload_front
```
Returns: MJPEG stream of uploaded front video with annotations

**Content-Type:** `multipart/x-mixed-replace; boundary=frame`

---

#### 12. Upload Top Video Feed
```
GET /video_feed_upload_top
```
Returns: MJPEG stream of uploaded top video with annotations

**Content-Type:** `multipart/x-mixed-replace; boundary=frame`

---

### Alert Management Endpoints

#### 13. Delete Alert
```
DELETE /api/alerts/<alert_id>
```

**Response (Success - 200):**
```json
{
  "status": "success",
  "message": "Alert deleted"
}
```

**Response (Error - 400):**
```json
{
  "status": "error",
  "message": "Failed to delete alert"
}
```

---

## Testing Guidelines

### Unit Testing Strategy

#### 1. Audio Handler Tests
```bash
# Test microphone input
python -c "from audio_handler import *; audio_processing_loop()"

# Test with mock audio
import numpy as np
test_siren_audio = np.random.randn(16000).astype(np.float32)
scores, _, _ = yamnet(test_siren_audio)
```

#### 2. Video Handler Tests
- Test with sample video files in `uploads/` folder
- Test with live camera feeds (verify camera indices correct)
- Test YOLO model loading
- Test OCR accuracy

#### 3. Database Tests
```python
from db_handler import *

# Test connection
client.server_info()

# Test save operation
save_detection("front", "ambulance", "red", ["AMBULANCE"], True, "SIREN DETECTED")

# Retrieve saved data
db.Traffic_Signals_IOT.find_one()
```

#### 4. API Tests
```bash
# Test status endpoint
curl http://localhost:5000/api/status

# Test video upload
curl -X POST http://localhost:5000/api/upload_video \
  -F "video=@sample.mp4" \
  -F "view=front"

# Test staff management
curl -X POST http://localhost:5000/api/staff \
  -H "Content-Type: application/json" \
  -d '{"name":"Officer","phone":"94xxxxxxxxxx","location":"Colombo"}'
```

#### 5. Integration Tests
- Start main.py with all threads
- Simulate emergency scenario (play siren audio + video)
- Verify detection across all modules
- Verify database logging
- Verify SMS alerts triggered
- Check video feeds streaming

### Performance Testing
- Monitor CPU usage with all threads
- Check FPS on video streams
- Monitor memory usage
- Database query response time
- API response latency

### Stress Testing
- Multiple simultaneous video uploads
- Rapid siren detections
- High-frequency API calls
- Continuous 24-hour operation

---

## Error Handling

### Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| YAMNet fails to load | TensorFlow Hub cache corrupted | Clear cache in TEMP/tfhub_modules |
| Camera not found | Wrong camera index | Update FRONT_CAMERA_INDEX / TOP_CAMERA_INDEX |
| MongoDB connection fails | Invalid connection string | Verify MONGO_URI in .env |
| SMS not sending | Mock mode or invalid API key | Configure real SMS_API_KEY in .env |
| Video upload fails | File size too large | Increase Flask max_content_length |
| Low FPS on video | Inference too slow | Increase FRAME_SKIP or reduce INFERENCE_SIZE |

---

## System Requirements

- Python 3.8+
- MongoDB instance
- 2+ webcams (or video files for upload)
- Microphone for audio input
- Internet connection (for geolocation, YAMNet model, SMS API)
- GPU recommended (NVIDIA with CUDA for YOLO acceleration)

---

## Dependencies

Key Python packages:
- `tensorflow` & `tensorflow-hub` (for YAMNet)
- `torch` & `ultralytics` (for YOLO)
- `easyocr` (for OCR)
- `opencv-python` (for video processing)
- `sounddevice` (for audio capture)
- `pymongo` (for database)
- `flask` & `flask-cors` (for API)
- `numpy`, `scipy`, `pandas` (utilities)

---

---

## VM Deployment Steps

### Phase 1: Azure VM Creation

#### Pre-Deployment Setup
1. **Create Azure Account**
   - Create account at [Azure Portal](https://portal.azure.com)
   - Set up active subscription

2. **Install Azure CLI (Optional)**
   ```bash
   # For automated VM creation via command line
   az login
   az group create --name emergency-detection-rg --location eastus
   ```

3. **Clean Up Project Locally**
   ```bash
   # Remove test files
   rm test_*.py
   
   # Remove cache
   rm -rf __pycache__ .pytest_cache
   
   # Verify .env has real MongoDB credentials
   # Verify requirements.txt is up to date
   ```

#### Create Azure VM

**Via Azure Portal:**
1. Go to [Azure Portal](https://portal.azure.com)
2. Click **Create a resource** → Search for **Virtual Machine**
3. Configure VM:
   - **Image**: Ubuntu 22.04 LTS (or Ubuntu 24.04)
   - **Size**: Standard_B2s or Standard_D2s v3 (2 vCPUs, 4-8GB RAM)
   - **Region**: Choose closest to your location
   - **Authentication**: Generate SSH keys (save locally)
   - **Public IP**: Create new
   - **Inbound Rules**: SSH (22), HTTP (80), HTTPS (443), Custom (5000)

**Via Azure CLI:**
```bash
az vm create \
  --resource-group emergency-detection-rg \
  --name emergency-vehicle-vm \
  --image UbuntuLTS \
  --size Standard_B2s \
  --admin-username azureuser \
  --generate-ssh-keys \
  --public-ip-sku Standard
```

#### Record VM Details
- [ ] Public IP: `________________`
- [ ] Username: `azureuser`
- [ ] SSH Key Location: `C:\Users\<username>\.ssh\id_rsa`
- [ ] Region: `________________`

---

### Phase 2: SSH Connection & System Setup

#### Step 1: Connect to VM
```powershell
# From Windows PowerShell
ssh -i "C:\Users\sange\.ssh\id_rsa" azureuser@<VM_PUBLIC_IP>

# Expected output: azureuser@emergency-vm:~$
```

#### Step 2: Update System
```bash
sudo apt update && sudo apt upgrade -y
```
Estimated time: 2-3 minutes

#### Step 3: Install Dependencies
```bash
sudo apt install -y python3.10 python3.10-venv python3-pip git libsm6 libxext6 libxrender-dev ffmpeg portaudio19-dev
```
Estimated time: 3-5 minutes

Required packages:
- `python3.10`: Python runtime
- `python3.10-venv`: Virtual environment
- `python3-pip`: Package manager
- `git`: Version control
- `libsm6`, `libxext6`, `libxrender-dev`: OpenCV dependencies
- `ffmpeg`: Video processing
- `portaudio19-dev`: Audio library

#### Step 4: Create Application Directory
```bash
mkdir -p ~/emergency-detection
cd ~/emergency-detection
```

---

### Phase 3: Upload Project Files

#### Option A: Using SCP (Recommended)
```powershell
# From NEW PowerShell window on local machine
cd C:\Users\sange\Desktop\Intergration

# Upload all files
scp -i "C:\Users\sange\.ssh\id_rsa" -r * azureuser@<VM_PUBLIC_IP>:~/emergency-detection/

# Verify upload (in VM terminal)
ls -la ~/emergency-detection/
```

#### Option B: Using Git
```bash
# On VM terminal
cd ~/emergency-detection
git clone <your-repo-url> .
```

#### Verify Upload
```bash
# Check key files are present
ls -la ~/emergency-detection/main.py
ls -la ~/emergency-detection/requirements.txt
ls -la ~/emergency-detection/config.py
ls -la ~/emergency-detection/bestAllVehicle.pt
```

---

### Phase 4: Python Environment Setup

#### Step 1: Create Virtual Environment
```bash
cd ~/emergency-detection
python3.10 -m venv venv
```

#### Step 2: Activate Virtual Environment
```bash
source venv/bin/activate
```
**Expected:** Terminal prompt starts with `(venv)`

#### Step 3: Upgrade Pip
```bash
pip install --upgrade pip setuptools wheel
```

#### Step 4: Install Dependencies
```bash
pip install -r requirements.txt
```
Estimated time: 10-15 minutes (first time)

#### Step 5: Verify Installation
```bash
# Check key packages
pip list | grep flask
pip list | grep tensorflow
pip list | grep opencv-python
pip list | grep pymongo
```

---

### Phase 5: Configuration

#### Step 1: Create .env File
```bash
nano .env
```

#### Step 2: Add Configuration
```
# Environment
ENVIRONMENT=AZURE
FLASK_ENV=production

# MongoDB Configuration
MONGO_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/emergency_detection?retryWrites=true&w=majority
DB_NAME=EmergencyDetection
COLLECTION_NAME=detections

# Flask Configuration
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# SMS Configuration (if using SMS alerts)
SMS_API_KEY=<your-sms-api-key>
SMS_SENDER_ID=<your-sender-id>

# Location (optional - fetched from IP if not set)
LOCATION=Colombo, Western
```

#### Step 3: Save File
- Press `Ctrl+O` then `Enter` to save
- Press `Ctrl+X` to exit nano

---

### Phase 6: Disable Cameras (IMPORTANT for Azure)

#### Edit config.py
```bash
nano config.py
```

#### Find and Modify PROCESS_FLAGS
```python
# BEFORE (with live cameras)
PROCESS_FLAGS = {
    "front": True,
    "top": True,
    "upload_front": False,
    "upload_top": False
}

# AFTER (for video upload only)
PROCESS_FLAGS = {
    "front": False,
    "top": False,
    "upload_front": False,
    "upload_top": False
}
```

#### Camera Configuration (Optional)
If you want to test with dummy cameras (won't capture anything):
```python
# Set invalid indices to prevent camera access errors
FRONT_CAMERA_INDEX = 999
TOP_CAMERA_INDEX = 999
```

---

### Phase 7: Run Application

#### Step 1: Activate Virtual Environment (if not already)
```bash
cd ~/emergency-detection
source venv/bin/activate
```

#### Step 2: Start Application
```bash
python main.py
```

#### Expected Output
```
[INFO] Connected to MongoDB successfully.
[INFO] Loading YOLO model...
[INFO] Loading OCR model...
[INFO] Starting audio stream...
[INFO] Integrated Emergency System Started.
[INFO] API available at http://localhost:5000/api/status
[INFO] Front View: http://localhost:5000/video_feed_front
[INFO] Top View: http://localhost:5000/video_feed_top
```

#### Step 3: Test API (from another terminal)
```bash
# From local machine or another VM terminal
curl http://<VM_PUBLIC_IP>:5000/api/status

# Expected: JSON response with system status
```

---

### Phase 8: Run as Background Service (Optional)

#### Option A: Using tmux or screen
```bash
# Install tmux
sudo apt install -y tmux

# Start in background
tmux new-session -d -s emergency python main.py

# Attach to session
tmux attach -t emergency

# Detach (in tmux): Ctrl+B then D
```

#### Option B: Using systemd (Recommended for production)
```bash
# Create systemd service file
sudo nano /etc/systemd/system/emergency-detection.service
```

Add content:
```ini
[Unit]
Description=Emergency Vehicle Detection System
After=network.target

[Service]
Type=simple
User=azureuser
WorkingDirectory=/home/azureuser/emergency-detection
Environment="PATH=/home/azureuser/emergency-detection/venv/bin"
ExecStart=/home/azureuser/emergency-detection/venv/bin/python main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable emergency-detection
sudo systemctl start emergency-detection
sudo systemctl status emergency-detection
```

Monitor logs:
```bash
sudo journalctl -u emergency-detection -f
```

---

### Phase 9: Setup Nginx Reverse Proxy (Optional, for Production)

#### Step 1: Install Nginx
```bash
sudo apt install -y nginx
```

#### Step 2: Create Nginx Config
```bash
sudo nano /etc/nginx/sites-available/emergency-detection
```

Add configuration:
```nginx
server {
    listen 80;
    server_name <your-domain-or-ip>;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Streaming support
        proxy_buffering off;
        proxy_request_buffering off;
    }
}
```

#### Step 3: Enable Configuration
```bash
sudo ln -s /etc/nginx/sites-available/emergency-detection /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl restart nginx
```

---

### Phase 10: Access Application

#### API Endpoints (Publicly Available)
```
http://<VM_PUBLIC_IP>:5000/api/status
http://<VM_PUBLIC_IP>:5000/api/analytics
http://<VM_PUBLIC_IP>:5000/api/staff
http://<VM_PUBLIC_IP>:5000/api/alerts
```

#### Video Feeds
```
http://<VM_PUBLIC_IP>:5000/video_feed_front
http://<VM_PUBLIC_IP>:5000/video_feed_top
http://<VM_PUBLIC_IP>:5000/video_feed_upload_front
http://<VM_PUBLIC_IP>:5000/video_feed_upload_top
```

#### Upload Video
```bash
curl -X POST http://<VM_PUBLIC_IP>:5000/api/upload_video \
  -F "video=@video.mp4" \
  -F "view=front"
```

---

### Troubleshooting Common Issues

| Issue | Solution |
|-------|----------|
| SSH Key Permission Denied | `chmod 600 ~/.ssh/id_rsa` |
| Package Installation Fails | `sudo apt update` then retry `pip install` |
| YOLO Model Download Timeout | Model loads on first run; check internet connection |
| MongoDB Connection Error | Verify MONGO_URI in .env with correct credentials |
| Port 5000 Already in Use | Change Flask port in config.py or .env |
| Camera Access Error | Set FRONT_CAMERA_INDEX and TOP_CAMERA_INDEX to 999 or disable cameras |
| Video Upload Fails | Check file size and format (mp4, avi, mov, mkv) |
| Low Memory | Kill unnecessary processes: `sudo killall python3` |

---

### Monitoring & Maintenance

#### Check System Status
```bash
# Check running processes
ps aux | grep python

# Check memory usage
free -h

# Check disk usage
df -h

# Check logs
tail -100 /var/log/syslog
```

#### Restart Application
```bash
# If running in tmux
tmux kill-session -t emergency

# Or if running as service
sudo systemctl restart emergency-detection
```

#### Update Application
```bash
cd ~/emergency-detection
git pull origin main  # If using Git

# Or upload new files via SCP
scp -r /path/to/new/files azureuser@<IP>:~/emergency-detection/

# Restart application
sudo systemctl restart emergency-detection
```

---

## Summary of Deployment Process

**Total Time: 30-45 minutes**

| Phase | Time | Steps |
|-------|------|-------|
| VM Creation | 5 min | Azure Portal or CLI |
| SSH Connection | 2 min | Connect via SSH |
| System Setup | 5 min | Update & install packages |
| Upload Files | 3 min | SCP transfer |
| Python Setup | 5 min | venv & pip install |
| Configuration | 3 min | .env & config.py |
| Run Application | 2 min | python main.py |
| Testing | 10 min | Test endpoints |

---

**End of Report**
