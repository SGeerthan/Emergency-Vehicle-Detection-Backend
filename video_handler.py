import cv2
import numpy as np
from collections import deque
from ultralytics import YOLO
import easyocr
import config
import datetime
import db_handler
import time

# Initialization
import os
# Guard YOLO model load
yolo_model = None
if os.path.exists(config.MODEL_PATH):
    print("[INFO] Loading YOLO model...")
    yolo_model = YOLO(config.MODEL_PATH)
    print("[INFO] YOLO model loaded.")
else:
    print(f"[WARNING] YOLO model not found at {config.MODEL_PATH}. Detection disabled.")

# Guard EasyOCR load
ocr_reader = None
try:
    print("[INFO] Loading OCR model...")
    ocr_reader = easyocr.Reader(['en'])
    print("[INFO] OCR model loaded.")
except Exception as e:
    print(f"[WARNING] OCR disabled: {e}")

# Emergency Vehicle Classes from bestAllVehicle.pt
EMERGENCY_VEHICLE_CLASSES = ['ambulance', 'firetruck', 'police']

blink_red = deque(maxlen=config.BLINK_HISTORY)
blink_blue = deque(maxlen=config.BLINK_HISTORY)
blink_amber = deque(maxlen=config.BLINK_HISTORY)

def blinking(buffer):
    if len(buffer) < config.BLINK_HISTORY: return False
    ratio = sum(buffer) / config.BLINK_HISTORY
    return config.BLINK_MIN_RATIO < ratio < config.BLINK_MAX_RATIO

def get_color_mask(hsv, bright_mask):
    red_mask = cv2.bitwise_or(
        cv2.inRange(hsv, np.array([0, 120, 180]), np.array([10, 255, 255])),
        cv2.inRange(hsv, np.array([170, 120, 180]), np.array([180, 255, 255]))
    )
    blue_mask = cv2.inRange(hsv, np.array([90, 120, 180]), np.array([130, 255, 255]))
    amber_mask = cv2.inRange(hsv, np.array([10, 120, 180]), np.array([28, 255, 255]))
    
    red_mask = cv2.bitwise_and(red_mask, bright_mask)
    blue_mask = cv2.bitwise_and(blue_mask, bright_mask)
    amber_mask = cv2.bitwise_and(amber_mask, bright_mask)
    
    return red_mask, blue_mask, amber_mask

def run_ocr(crop):
    if ocr_reader is None:
        return []
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    results = ocr_reader.readtext(gray)
    found = []
    for _, text, _ in results:
        clean = text.lower()
        if any(word in clean for word in config.OCR_KEYWORDS):
            found.append(text)
    return found

def video_processing_loop(source, view_name):
    """
    # Guard YOLO model loading
    if yolo_model is None:
        print(f"[WARNING] Skipping {view_name} — no YOLO model loaded.")
        return
    source can be a camera index (int) or a file path (string).
    """
    cap = cv2.VideoCapture(source)
    
    # Initialize separate blink histories for this camera/thread
    local_blink_red = deque(maxlen=config.BLINK_HISTORY)
    local_blink_blue = deque(maxlen=config.BLINK_HISTORY)
    local_blink_amber = deque(maxlen=config.BLINK_HISTORY)
    
    is_file = isinstance(source, str)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    delay = int(1000 / fps) if is_file else 1
    
    frame_count = 0

    results = None
    best_vehicle_type = "None"
    best_ocr_found = []
    best_is_emergency = False
    last_boxes = [] # Store scaled boxes to redraw on skipped frames
    last_frame_time = time.time()
    
    while cap.isOpened():
        # Check if the process should still be running
        if not config.PROCESS_FLAGS.get(view_name, False):
            print(f"[INFO] Stopping process for {view_name}")
            config.latest_data["video"][view_name]["running"] = False
            break

        # FPS Limiting to save CPU
        elapsed = time.time() - last_frame_time
        wait_time = (1.0 / config.MAX_FPS) - elapsed
        if wait_time > 0:
            time.sleep(wait_time)
        last_frame_time = time.time()
        ret, frame = cap.read()
        if not ret: 
            if is_file:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            else:
                break
        
        config.latest_data["video"][view_name]["running"] = True
        
        config.latest_data["system"]["last_update"] = datetime.datetime.now().isoformat()
        
        # Only run YOLO every FRAME_SKIP frames and if detection is enabled
        if config.ENABLE_DETECTION and (frame_count % config.FRAME_SKIP == 0):
            # Resize for inference to speed up processing
            if hasattr(config, 'INFERENCE_SIZE') and config.INFERENCE_SIZE:
                inf_frame = cv2.resize(frame, config.INFERENCE_SIZE)
                results = yolo_model(inf_frame, conf=0.4, verbose=False, stream=False)[0]
                # Scale boxes back if we resized
                h, w = frame.shape[:2]
                ih, iw = config.INFERENCE_SIZE
                scale_x, scale_y = w / iw, h / ih
            else:
                results = yolo_model(frame, conf=0.4, verbose=False)[0]
        
        # Frame-level color flags
        frame_has_red = False
        frame_has_blue = False
        frame_has_amber = False
        
        if config.ENABLE_DETECTION and (frame_count % config.FRAME_SKIP == 0):
            best_vehicle_type = "None"
            best_ocr_found = []
            best_is_emergency = False
            last_boxes = []

            if results:
                for box in results.boxes:
                    # If we resized, we need to rescale the box coordinates
                    if hasattr(config, 'INFERENCE_SIZE') and config.INFERENCE_SIZE:
                        x1, y1, x2, y2 = box.xyxy[0]
                        x1, x2 = int(x1 * scale_x), int(x2 * scale_x)
                        y1, y2 = int(y1 * scale_y), int(y2 * scale_y)
                    else:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                    
                    cls = int(box.cls[0])
                    v_type = yolo_model.names[cls]
                    
                    is_emergency_type = any(k in v_type.lower() for k in config.OCR_KEYWORDS)
                    
                    crop = frame[y1:y2, x1:x2]
                    if crop.size == 0: continue
                    
                    # Run OCR every OCR_INTERVAL frames if vehicle is potentially an emergency and OCR is enabled
                    is_ocr_emergency = False
                    if config.ENABLE_OCR and (frame_count % config.OCR_INTERVAL == 0):
                        found_words = run_ocr(crop)
                        is_ocr_emergency = len(found_words) > 0
                        if found_words:
                            best_ocr_found.extend(found_words)
                    
                    # Update best detection for this frame
                    if is_emergency_type or is_ocr_emergency:
                        best_is_emergency = True
                        best_vehicle_type = v_type
                    elif best_vehicle_type == "None":
                        best_vehicle_type = v_type

                    # Store box for redrawing on skipped frames
                    is_emergency_candidate = (v_type in EMERGENCY_VEHICLE_CLASSES) or is_ocr_emergency
                    last_boxes.append(((x1, y1, x2, y2), v_type, is_emergency_candidate))

                    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    _, bright = cv2.threshold(gray, config.BRIGHTNESS_THRESHOLD, 255, cv2.THRESH_BINARY)
                    
                    rm, bm, am = get_color_mask(hsv, bright)
                    
                    if cv2.countNonZero(rm) > 15: frame_has_red = True
                    if cv2.countNonZero(bm) > 15: frame_has_blue = True
                    if cv2.countNonZero(am) > 15: frame_has_amber = True
        
        # Redraw last known boxes on every frame (including skipped ones)
        for (x1, y1, x2, y2), v_type, is_emergency_candidate in last_boxes:
            color = (0, 0, 255) if is_emergency_candidate else (0, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, v_type, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Update blink history ONCE per frame
        local_blink_red.append(1 if frame_has_red else 0)
        local_blink_blue.append(1 if frame_has_blue else 0)
        local_blink_amber.append(1 if frame_has_amber else 0)
        
        # Determine light status based on blink history
        light_status = "None"
        is_blink_red = blinking(local_blink_red)
        is_blink_blue = blinking(local_blink_blue)
        is_blink_amber = blinking(local_blink_amber)

        if is_blink_red and is_blink_blue:
            light_status = "VIP (RED+BLUE)"
        elif is_blink_blue:
            light_status = "POLICE (BLUE)"
        elif is_blink_red and is_blink_amber:
            light_status = "FIRE/AMBULANCE (RED+AMBER)"
        elif is_blink_red:
            light_status = "FIRE/AMBULANCE (RED)"
        elif is_blink_amber:
            light_status = "VIP/ESCORT (AMBER)"

        # STRICTOR EMERGENCY LOGIC:
        # 1. Vehicle must be an emergency type (from YOLO or OCR)
        # 2. Siren light must be active (light_status is not "None")
        # 3. Siren sound must be detected (from audio_handler)
        
        siren_sound_detected = (config.latest_data["audio"]["status"] == "SIREN DETECTED")
        light_detected = (light_status != "None")
        
        # For live feeds, we previously required audio and light.
        # Now, we will trigger based solely on vehicle detection for reliable MongoDB storage.
        if view_name.startswith("upload"):
            final_is_emergency = best_is_emergency # and light_detected
        else:
            final_is_emergency = best_is_emergency # and light_detected and siren_sound_detected

        frame_count += 1

        config.latest_data["video"][view_name] = {
            "vehicle_type": best_vehicle_type,
            "siren_light": light_status,
            "ocr_text": best_ocr_found,
            "is_emergency": final_is_emergency,
            "running": True
        }

        # Overall global emergency status
        any_emergency = config.latest_data["video"]["front"]["is_emergency"] or \
                        config.latest_data["video"]["top"]["is_emergency"] or \
                        config.latest_data["video"]["upload_front"]["is_emergency"] or \
                        config.latest_data["video"]["upload_top"]["is_emergency"]
        
        config.latest_data["video"]["is_emergency"] = any_emergency

        # Reset search mode if emergency is cleared
        if not any_emergency:
            config.latest_data["system"]["search_mode"] = False
            config.latest_data["system"]["search_reason"] = "None"

        if light_detected:
            # print(f"[INFO] {view_name.upper()} Light Detected: {light_status}")
            pass

        if frame_count % 10 == 0 and best_vehicle_type != "None":
            db_handler.save_generic_detection(best_vehicle_type, best_is_emergency, light_status)

        cv2.putText(frame, f"AUDIO: {config.latest_data['audio']['status']}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"VIEW: {view_name.upper()}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Display Light Status on Frame
        light_color = (0, 255, 0) if light_detected else (255, 255, 255)
        cv2.putText(frame, f"LIGHTS: {light_status}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, light_color, 2)

        if config.latest_data["system"]["search_mode"] and not any_emergency:
             reason = config.latest_data["system"]["search_reason"]
             cv2.putText(frame, f"SEARCHING: {reason}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
             cv2.putText(frame, "VEHICLE MAY BE HIDDEN", (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        # Store for Streaming
        if view_name == "front":
            config.front_processed_frame = frame.copy()
        elif view_name == "top":
            config.top_processed_frame = frame.copy()
        elif view_name == "upload_front":
            config.upload_front_processed_frame = frame.copy()
        elif view_name == "upload_top":
            config.upload_top_processed_frame = frame.copy()
        
        if not is_file:
            time.sleep(0.001)  # non‑blocking yield
        else:
            time.sleep(delay / 1000.0)  # maintain original delay
        
    cap.release()
    # cv2.destroyAllWindows()
    config.latest_data["video"][view_name]["running"] = False
    
    # Clear frames when stopped to show offline/stopped state
    if view_name == "front": config.front_processed_frame = None
    elif view_name == "top": config.top_processed_frame = None
    elif view_name == "upload_front": config.upload_front_processed_frame = None
    elif view_name == "upload_top": config.upload_top_processed_frame = None
