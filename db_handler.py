import pymongo
from datetime import datetime
from bson import ObjectId
import config

# Initialize MongoDB client
try:
    client = pymongo.MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[config.DB_NAME]
    collection = db[config.COLLECTION_NAME]
    # Check connection
    client.server_info()
    print("[INFO] Connected to MongoDB successfully.")
except Exception as e:
    print(f"[ERROR] Could not connect to MongoDB: {e}")
    collection = None

VEHICLE_TYPE_ALIASES = {
    "fire_truck": "firetruck",
}

def normalize_vehicle_type(vehicle_type):
    """Normalize vehicle type names (e.g. fire_truck -> firetruck)."""
    if not vehicle_type:
        return vehicle_type
    return VEHICLE_TYPE_ALIASES.get(vehicle_type.lower(), vehicle_type)

GENERIC_COLLECTION_NAME = "all_vehicle_detections"
generic_collection = db[GENERIC_COLLECTION_NAME] if collection is not None else None

EMERGENCY_INFO_COLLECTION = "emergency_information"
emergency_info_collection = db[EMERGENCY_INFO_COLLECTION] if collection is not None else None

# SUMO Injection Collection
SUMO_DB_NAME = "EmergencyDetection"
SUMO_COLLECTION_NAME = "SUMOinjections"
try:
    sumo_db = client[SUMO_DB_NAME]
    sumo_collection = sumo_db[SUMO_COLLECTION_NAME]
except Exception as e:
    print(f"[ERROR] Could not connect to SUMO collection: {e}")
    sumo_collection = None

def save_emergency_info(info_dict):
    """Saves the complete sensor data JSON to the emergency_information collection."""
    if emergency_info_collection is None:
        return
    
    # We create a deep copy or just structure it as-is? 
    # Usually it's better to store a copy to avoid side effects if the original dict is modified.
    import copy
    record = copy.deepcopy(info_dict)
    record["db_timestamp"] = datetime.now()
    
    try:
        emergency_info_collection.insert_one(record)
        print(f"[INFO] Emergency Information JSON saved to MongoDB.")
    except Exception as e:
        print(f"[ERROR] Failing to save emergency information: {e}")

def save_generic_detection(vehicle_type, is_emergency, siren_light="None"):
    vehicle_type = normalize_vehicle_type(vehicle_type)
    """Saves a generic vehicle detection to a separate collection for analytics."""
    if generic_collection is None:
        return
    
    # We only save if vehicle_type is valid
    if vehicle_type == "None" or not vehicle_type:
        return

    record = {
        "timestamp": datetime.now(),
        "vehicle_type": vehicle_type,
        "is_emergency": is_emergency,
        "siren_light": siren_light
    }
    
    try:
        generic_collection.insert_one(record)
    except Exception as e:
        print(f"[ERROR] Failing to save generic detection: {e}")

def save_detection(view_name, vehicle_type, siren_light, ocr_text, is_emergency, audio_status="Normal traffic"):
    vehicle_type = normalize_vehicle_type(vehicle_type)
    """Saves a detection event to MongoDB."""
    if collection is None:
        return

    record = {
        "timestamp": datetime.now(),
        "camera_view": view_name,
        "vehicle_type": vehicle_type,
        "siren_light": siren_light,
        "ocr_text": ocr_text,
        "is_emergency": is_emergency,
        "audio_status": audio_status
    }
    
    try:
        collection.insert_one(record)
    except Exception as e:
        print(f"[ERROR] Failing to save detection to MongoDB: {e}")

def save_final_decision(confirmed_type, location, details):
    confirmed_type = normalize_vehicle_type(confirmed_type)
    """Saves a finalized integrated detection event to MongoDB."""
    if collection is None:
        return

    record = {
        "timestamp": datetime.now(),
        "event": "EMERGENCY_DETECTED",
        "vehicle_type": confirmed_type,
        "location": location,
        "entryPoint": "E4",
        "details": details,
        "is_final": True
    }
    
    try:
        collection.insert_one(record)
        print(f"[INFO] Final Decision Saved to MongoDB: {confirmed_type} at {location}")
    except Exception as e:
        print(f"[ERROR] Failing to save final decision to MongoDB: {e}")

def get_analytics_data(date_str=None):
    """Retrieves aggregated data for the analytics dashboard (Emergency Vehicles Only)."""
    if collection is None or generic_collection is None:
        return {
            "trends": [],
            "breakdown": [],
            "today_breakdown": []
        }

    # Determine the date range
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            target_date = datetime.now()
    else:
        target_date = datetime.now()
        
    start_of_day = datetime(target_date.year, target_date.month, target_date.day)
    end_of_day = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)

    # Breakdown by emergency vehicle types (Pie Chart - for the selected day)
    pipeline_breakdown = [
        {"$match": {"is_emergency": True, "timestamp": {"$gte": start_of_day, "$lte": end_of_day}}},
        {"$group": {"_id": "$vehicle_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    
    breakdown = list(generic_collection.aggregate(pipeline_breakdown))
    formatted_breakdown = [{"name": b["_id"].capitalize(), "value": b["count"]} for b in breakdown if b["_id"] != "None"]

    # Today's Breakdown (Start of today, specifically for dashboard stat cards if needed)
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)
    pipeline_today = [
        {"$match": {"is_emergency": True, "timestamp": {"$gte": today_start}}},
        {"$group": {"_id": "$vehicle_type", "count": {"$sum": 1}}}
    ]
    today_raw = list(generic_collection.aggregate(pipeline_today))
    today_breakdown = [{"name": b["_id"].capitalize(), "value": b["count"]} for b in today_raw if b["_id"] != "None"]

    # Trends: Emergency Vehicle Types per Hour (Line Chart / Bar Chart)
    # Filter by the selected day
    pipeline_trends = [
        {"$match": {"is_emergency": True, "timestamp": {"$gte": start_of_day, "$lte": end_of_day}}},
        {"$project": {
            "hour": {"$hour": "$timestamp"},
            "vehicle_type": 1
        }},
        {"$group": {
            "_id": {"hour": "$hour", "type": "$vehicle_type"},
            "count": {"$sum": 1}
        }}
    ]
    
    trends_raw = list(generic_collection.aggregate(pipeline_trends))
    
    # Initialize all 24 hours with zeros
    hourly_data_map = {}
    for h in range(24):
        hour_label = f"{h:02d}:00"
        hourly_data_map[hour_label] = {
            "hour": hour_label,
            "Ambulance": 0,
            "Police": 0,
            "Fire": 0,
            "VIP": 0,
            "Total": 0
        }

    for entry in trends_raw:
        hour_val = entry["_id"]["hour"]
        hour_label = f"{hour_val:02d}:00"
        vtype = entry["_id"]["type"].lower()
        
        category = "Other"
        if "ambulance" in vtype: category = "Ambulance"
        elif "police" in vtype: category = "Police"
        elif "fire" in vtype or "engine" in vtype: category = "Fire"
        elif "vip" in vtype or "minister" in vtype: category = "VIP"

        if category in hourly_data_map[hour_label]:
            hourly_data_map[hour_label][category] += entry["count"]
            hourly_data_map[hour_label]["Total"] += entry["count"]

    return {
        "trends": sorted(list(hourly_data_map.values()), key=lambda x: x["hour"]),
        "breakdown": formatted_breakdown,
        "today_breakdown": today_breakdown
    }

def get_recent_alerts(limit=50):
    """Retrieves the most recent emergency alerts."""
    if collection is None:
        return []

    try:
        # Fetch records that are either final decisions or marked as emergency
        query = {"$or": [{"is_final": True}, {"is_emergency": True}]}
        cursor = collection.find(query).sort("timestamp", -1).limit(limit)
        
        alerts = []
        for doc in cursor:
            # Convert ObjectId and datetime to string for JSON serialization
            doc["_id"] = str(doc["_id"])
            if "timestamp" in doc and isinstance(doc["timestamp"], datetime):
                doc["timestamp"] = doc["timestamp"].isoformat()
            alerts.append(doc)
            
        return alerts
    except Exception as e:
        print(f"[ERROR] Failing to fetch recent alerts: {e}")
        return []

def delete_alert(alert_id):
    """Deletes an alert from both collections by its ID."""
    if collection is None:
        return False
    
    try:
        obj_id = ObjectId(alert_id)
        # Try deleting from primary collection
        res1 = collection.delete_one({"_id": obj_id})
        
        # Also try generic collection if it exists
        res2_count = 0
        if generic_collection is not None:
             res2 = generic_collection.delete_one({"_id": obj_id})
             res2_count = res2.deleted_count
             
        return res1.deleted_count > 0 or res2_count > 0
    except Exception as e:
        print(f"[ERROR] Failing to delete alert {alert_id}: {e}")
        return False

def get_latest_detection():
    """Retrieves the most recent emergency detection from MongoDB."""
    if collection is None:
        return None
    try:
        # Search for the latest record marked as a final decision, falling back to older is_emergency records
        doc = collection.find_one({"is_final": True}, sort=[("timestamp", -1)])
        if not doc:
            doc = collection.find_one({"is_emergency": True}, sort=[("timestamp", -1)])
            
        if doc:
            doc["_id"] = str(doc["_id"])
            if "timestamp" in doc and isinstance(doc["timestamp"], datetime):
                doc["timestamp"] = doc["timestamp"].isoformat()
            
            # Map integrated 'details' back to generic keys expected by the frontend
            if doc.get("is_final"):
                details = doc.get("details", {})
                
                # Consolidate siren lights from all views
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
    """Saves emergency vehicle info to SUMOinjections collection."""
    if sumo_collection is None:
        return
    
    record = {
        "timestamp": datetime.now(),
        "type": "emergency_vehicle",
        "data": {
            "vehicle_type": vehicle_type.lower(),
            "entryPoint": entry_point
        }
    }
    
    try:
        sumo_collection.insert_one(record)
        print(f"[INFO] SUMO Injection saved to MongoDB: {vehicle_type} at {entry_point}")
    except Exception as e:
        print(f"[ERROR] Failing to save SUMO injection: {e}")
