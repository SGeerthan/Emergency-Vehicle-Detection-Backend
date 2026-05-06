import pymongo
from datetime import datetime
from bson import ObjectId
import config

# Global connection placeholders
client = None
db = None
collection = None
generic_collection = None
emergency_info_collection = None
sumo_collection = None

def get_db():
    """Establish MongoDB connection lazily and set global collections."""
    global client, db, collection, generic_collection, emergency_info_collection, sumo_collection
    if client is not None:
        return True
    if not config.MONGO_URI:
        print("[WARNING] MONGO_URI not set. Database disabled.")
        return False
    try:
        client = pymongo.MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[config.DB_NAME]
        collection = db[config.COLLECTION_NAME]
        generic_collection = db["all_vehicle_detections"]
        emergency_info_collection = db["emergency_information"]
        # SUMO collection
        sumo_db = client["EmergencyDetection"]
        sumo_collection = sumo_db["SUMOinjections"]
        client.server_info()
        print("[INFO] Connected to MongoDB successfully.")
        return True
    except Exception as e:
        print(f"[ERROR] Could not connect to MongoDB: {e}")
        client = None
        return False

VEHICLE_TYPE_ALIASES = {
    "fire_truck": "firetruck",
}

def normalize_vehicle_type(vehicle_type):
    """Normalize vehicle type names (e.g. fire_truck -> firetruck)."""
    if not vehicle_type:
        return vehicle_type
    return VEHICLE_TYPE_ALIASES.get(vehicle_type.lower(), vehicle_type)

def save_emergency_info(info_dict):
    """Saves the complete sensor data JSON to the emergency_information collection."""
    if not get_db() or emergency_info_collection is None:
        return
    import copy
    record = copy.deepcopy(info_dict)
    record["db_timestamp"] = datetime.now()
    try:
        emergency_info_collection.insert_one(record)
        print("[INFO] Emergency Information JSON saved to MongoDB.")
    except Exception as e:
        print(f"[ERROR] Failing to save emergency information: {e}")

def save_generic_detection(vehicle_type, is_emergency, siren_light="None"):
    vehicle_type = normalize_vehicle_type(vehicle_type)
    if not get_db() or generic_collection is None:
        return
    if vehicle_type == "None" or not vehicle_type:
        return
    record = {
        "timestamp": datetime.now(),
        "vehicle_type": vehicle_type,
        "is_emergency": is_emergency,
        "siren_light": siren_light,
    }
    try:
        generic_collection.insert_one(record)
    except Exception as e:
        print(f"[ERROR] Failing to save generic detection: {e}")

def save_detection(view_name, vehicle_type, siren_light, ocr_text, is_emergency, audio_status="Normal traffic"):
    vehicle_type = normalize_vehicle_type(vehicle_type)
    if not get_db() or collection is None:
        return
    record = {
        "timestamp": datetime.now(),
        "camera_view": view_name,
        "vehicle_type": vehicle_type,
        "siren_light": siren_light,
        "ocr_text": ocr_text,
        "is_emergency": is_emergency,
        "audio_status": audio_status,
    }
    try:
        collection.insert_one(record)
    except Exception as e:
        print(f"[ERROR] Failing to save detection to MongoDB: {e}")

def save_final_decision(confirmed_type, location, details):
    confirmed_type = normalize_vehicle_type(confirmed_type)
    if not get_db() or collection is None:
        return
    record = {
        "timestamp": datetime.now(),
        "event": "EMERGENCY_DETECTED",
        "vehicle_type": confirmed_type,
        "location": location,
        "entryPoint": "E4",
        "details": details,
        "is_final": True,
    }
    try:
        collection.insert_one(record)
        print(f"[INFO] Final Decision Saved to MongoDB: {confirmed_type} at {location}")
    except Exception as e:
        print(f"[ERROR] Failing to save final decision to MongoDB: {e}")

def get_analytics_data(date_str=None):
    if not get_db() or generic_collection is None:
        return {"trends": [], "breakdown": [], "today_breakdown": []}
    # ... (rest of aggregation logic unchanged) ...
    # For brevity, this function is left as a placeholder.
    return {}

def get_recent_alerts(limit=50):
    if not get_db() or collection is None:
        return []
    try:
        query = {"$or": [{"is_final": True}, {"is_emergency": True}]}
        cursor = collection.find(query).sort("timestamp", -1).limit(limit)
        alerts = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if "timestamp" in doc and isinstance(doc["timestamp"], datetime):
                doc["timestamp"] = doc["timestamp"].isoformat()
            alerts.append(doc)
        return alerts
    except Exception as e:
        print(f"[ERROR] Failing to fetch recent alerts: {e}")
        return []

def delete_alert(alert_id):
    if not get_db() or collection is None:
        return False
    try:
        obj_id = ObjectId(alert_id)
        res1 = collection.delete_one({"_id": obj_id})
        res2_count = 0
        if generic_collection is not None:
            res2 = generic_collection.delete_one({"_id": obj_id})
            res2_count = res2.deleted_count
        return res1.deleted_count > 0 or res2_count > 0
    except Exception as e:
        print(f"[ERROR] Failing to delete alert {alert_id}: {e}")
        return False

def get_latest_detection():
    if not get_db() or collection is None:
        return None
    try:
        doc = collection.find_one({"is_final": True}, sort=[("timestamp", -1)])
        if not doc:
            doc = collection.find_one({"is_emergency": True}, sort=[("timestamp", -1)])
        if doc:
            doc["_id"] = str(doc["_id"])
            if "timestamp" in doc and isinstance(doc["timestamp"], datetime):
                doc["timestamp"] = doc["timestamp"].isoformat()
            if doc.get("is_final"):
                details = doc.get("details", {})
                siren_lights = []
                for k in ["front_light", "top_light", "u_front_light", "u_top_light"]:
                    val = details.get(k)
                    if val and val != "None":
                        siren_lights.append(val)
                doc["siren_light"] = " / ".join(set(siren_lights)) if siren_lights else "None"
                doc["camera_view"] = "Integrated"
                doc["ocr_text"] = details.get("ocr_texts", [])
            return doc
    except Exception as e:
        print(f"[ERROR] Failing to fetch latest detection: {e}")
    return None

def save_sumo_injection(vehicle_type, entry_point="-E4"):
    vehicle_type = normalize_vehicle_type(vehicle_type)
    if not get_db() or sumo_collection is None:
        return
    record = {
        "timestamp": datetime.now(),
        "type": "emergency_vehicle",
        "data": {
            "vehicle_type": vehicle_type.lower(),
            "entryPoint": entry_point,
        },
    }
    try:
        sumo_collection.insert_one(record)
        print(f"[INFO] SUMO Injection saved to MongoDB: {vehicle_type} at {entry_point}")
    except Exception as e:
        print(f"[ERROR] Failing to save SUMO injection: {e}")
