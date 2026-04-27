import datetime
import requests
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

def get_current_location():
    try:
        response = requests.get("https://ipinfo.io/json", timeout=5)
        data = response.json()
        city = data.get("city", "Unknown City")
        region = data.get("region", "Unknown Region")
        country = data.get("country", "Unknown Country")
        loc = data.get("loc", "Unknown Coordinates")
        print(f"[INFO] Current Location: {city}, {region}, {country} ({loc})")
        return f"{city}, {region}"
    except Exception as e:
        print(f"[ERROR] Could not fetch location: {e}")
        return "Unknown Location"

# =====================================================
# CONFIGURATION
# =====================================================

LOCATION = get_current_location()

# Audio Config
SAMPLE_RATE = 16000
BLOCK_DURATION = 0.96
BLOCK_SIZE = int(SAMPLE_RATE * BLOCK_DURATION)
LOWCUT = 100          # Widened further to cover broader range
HIGHCUT = 8000        # Widened further to catch very high harmonics
CONF_THRESHOLD_AUDIO = 0.05
TEMPORAL_FRAMES = 1  # Detect on first positive frame — instant response
ENERGY_THRESHOLD = 0.001

# Exact YAMNet display_name strings for siren classes
SIREN_KEYWORDS = [
    "siren",
    "police car (siren)",
    "ambulance (siren)",
    "fire engine, fire truck (siren)",
    "emergency vehicle"
]

# Aggregate siren-score threshold (used by classify_siren)
SIREN_SCORE_THRESHOLD = 0.05  # Lower = more sensitive; raise if false positives occur

# Video Config
BRIGHTNESS_THRESHOLD = 200
MIN_CONTOUR_AREA = 120
MAX_CONTOUR_AREA = 4000
BLINK_HISTORY = 18
BLINK_MIN_RATIO = 0.25
BLINK_MAX_RATIO = 0.75
MODEL_PATH = "bestAllVehicle.pt"
FRAME_SKIP = 2 # Run YOLO every Nth frame
OCR_INTERVAL = 10 # Run OCR every Nth frame if vehicle detected
INFERENCE_SIZE = (640, 480) # Resize for faster inference

# Camera Indices
FRONT_CAMERA_INDEX = 1
TOP_CAMERA_INDEX = 2

# OCR Keywords
OCR_KEYWORDS = [
    "ambulance", "emergency", "hospital", "medical",
    "suwasariya", "1990", "first aid",
    "police", "traffic", "119", "fire", "rescue",
    "vip", "municipal council" 
]

# Video Performance and Control
PROCESS_FLAGS = {
    "front": True,
    "top": True,
    "upload_front": False,
    "upload_top": False
}
ENABLE_OCR = True # Enable OCR to detect emergency vehicle text
ENABLE_DETECTION = True
MAX_FPS = 30 # Increased for smoother feeds
FRAME_SKIP = 4 # Run YOLO less often to save CPU
INFERENCE_SIZE = (320, 320) # Smaller size for much faster inference

# Shared State
latest_data = {
    "audio": {
        "status": "Listening...",
        "confidence": 0.0,
        "label": "None",
        "top_class": "Listening...",
        "category": "NORMAL TRAFFIC",
        "dominant_freq": 0,
        "wavelength": 0
    },
    "video": {
        "front": {
            "vehicle_type": "None",
            "siren_light": "None",
            "ocr_text": [],
            "is_emergency": False,
            "running": True
        },
        "top": {
            "vehicle_type": "None",
            "siren_light": "None",
            "ocr_text": [],
            "is_emergency": False,
            "running": True
        },
        "upload_front": {
            "vehicle_type": "None",
            "siren_light": "None",
            "ocr_text": [],
            "is_emergency": False,
            "running": False
        },
        "upload_top": {
            "vehicle_type": "None",
            "siren_light": "None",
            "ocr_text": [],
            "is_emergency": False,
            "running": False
        },
        "is_emergency": False
    },
    "system": {
        "last_update": "",
        "search_mode": False,
        "search_reason": "None"
    }
}

# Live Feed Frames
front_processed_frame = None
top_processed_frame = None
upload_front_processed_frame = None
upload_top_processed_frame = None

# MongoDB Config
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

# SMS API Config (Get your API Key from https://dashboard.smsapi.lk/)
SMS_API_KEY = os.getenv("SMS_API_KEY", "370|bwsnjGSnYYRO1KwABpyX1yqrpWxzSsHlUnGdUAXU")
# SENDER_ID is the "From" name that appears on the phone (e.g., 'SmsPlus')
SMS_SENDER_ID = os.getenv("SMS_SENDER_ID", "TRAFFIXION")
SMS_GATEWAY_URL = "https://dashboard.smsapi.lk/api/v3/sms/send"

# Staff Config
STAFF_FILE_PATH = os.path.join(os.path.dirname(__file__), "policemen_duty.csv")

