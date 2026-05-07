import threading
import time
import cv2
from flask import Flask, jsonify, Response, request
import config
import audio_handler
import video_handler
import db_handler
import staff_handler



# =====================================================
# FLASK API
# =====================================================

from flask_cors import CORS

import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

@app.route("/")
def health_check():
    return jsonify({"status": "ok", "service": "Emergency Vehicle Detection API"}), 200

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

fallback_thread = None

@app.route("/api/upload_video", methods=["POST"])
def upload_video():
    if 'video' not in request.files:
        return jsonify({"status": "error", "message": "No video part"}), 400
    file = request.files['video']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        view = request.form.get('view', 'front') # 'front' or 'top'
        slot_name = f"upload_{view}"
        
        # Stop existing thread for this slot if any
        config.PROCESS_FLAGS[slot_name] = False
        time.sleep(0.5) # Give it a moment to stop
        
        # Clear old frame
        if view == "front": config.upload_front_processed_frame = None
        else: config.upload_top_processed_frame = None

        # Start processing thread for this video
        config.PROCESS_FLAGS[slot_name] = True
        thread = threading.Thread(
            target=video_handler.video_processing_loop,
            args=(filepath, slot_name),
            daemon=True
        )
        thread.start()
        
        return jsonify({"status": "success", "message": f"Video uploaded for {view} analysis", "filename": filename, "view": view}), 200
    return jsonify({"status": "error", "message": "File type not allowed"}), 400

@app.route("/api/video/control", methods=["POST"])
def video_control():
    data = request.json
    view = data.get("view") # 'front', 'top', 'upload_front', 'upload_top'
    action = data.get("action") # 'start', 'stop'
    
    if view not in config.PROCESS_FLAGS:
        return jsonify({"status": "error", "message": "Invalid view"}), 400
    
    if action == "start":
        if not config.PROCESS_FLAGS[view]:
            config.PROCESS_FLAGS[view] = True
            # For live feeds, we need to restart the thread if it was stopped.
            # However, in this architecture, the main.py usually starts front/top threads once.
            # If they exit due to PROCESS_FLAGS=False, they need to be restarted.
            if view == "front":
                threading.Thread(target=video_handler.video_processing_loop, args=(config.FRONT_CAMERA_INDEX, "front"), daemon=True).start()
            elif view == "top":
                threading.Thread(target=video_handler.video_processing_loop, args=(config.TOP_CAMERA_INDEX, "top"), daemon=True).start()
            # For uploads, starting without a file doesn't make sense here, usually triggered by upload.
            
        return jsonify({"status": "success", "message": f"{view} started"}), 200
    elif action == "stop":
        config.PROCESS_FLAGS[view] = False
        return jsonify({"status": "success", "message": f"{view} stopped"}), 200
    
    return jsonify({"status": "error", "message": "Invalid action"}), 400

@app.route("/api/status")
def get_status():
    return jsonify(config.latest_data)

@app.route("/api/analytics")
def get_analytics():
    date_str = request.args.get("date")
    return jsonify(db_handler.get_analytics_data(date_str))

@app.route("/api/staff", methods=["GET", "POST"])
def manage_staff():
    if request.method == "POST":
        data = request.json
        name = data.get("name")
        phone = data.get("phone")
        location = data.get("location")
        if name and phone and location:
            success = staff_handler.add_staff(name, phone, location)
            return jsonify({"status": "success" if success else "error"}), 201
        return jsonify({"status": "error", "message": "Missing fields"}), 400
    
    return jsonify(staff_handler.get_all_staff())

@app.route("/api/alerts")
def get_alerts():
    return jsonify(db_handler.get_recent_alerts())

@app.route("/api/latest_detection")
def get_latest_detection():
    return jsonify(db_handler.get_latest_detection())

@app.route("/api/alerts/<alert_id>", methods=["DELETE"])
def delete_alert_route(alert_id):
    success = db_handler.delete_alert(alert_id)
    if success:
        return jsonify({"status": "success", "message": "Alert deleted"}), 200
    else:
        return jsonify({"status": "error", "message": "Failed to delete alert"}), 400

def gen_frames(camera_type):
    while True:
        if camera_type == "front":
            frame_source = config.front_processed_frame
        elif camera_type == "top":
            frame_source = config.top_processed_frame
        elif camera_type == "upload_front":
            frame_source = config.upload_front_processed_frame
        elif camera_type == "upload_top":
            frame_source = config.upload_top_processed_frame
        else:
            frame_source = None

        if frame_source is not None:
            ret, buffer = cv2.imencode('.jpg', frame_source, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            time.sleep(0.1)

@app.route("/video_feed_front")
def video_feed_front():
    return Response(gen_frames("front"), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/video_feed_top")
def video_feed_top():
    return Response(gen_frames("top"), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/video_feed_upload_front")
def video_feed_upload_front():
    return Response(gen_frames("upload_front"), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/video_feed_upload_top")
def video_feed_upload_top():
    return Response(gen_frames("upload_top"), mimetype='multipart/x-mixed-replace; boundary=frame')

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def decision_logic_loop():
    """
    Centralized decision loop that monitors sensors and logs results exactly once per event.
    """
    emergency_ongoing = False
    detected_type = "Unknown"
    
    print("[INFO] Decision Logic Loop Started.")
    
    while True:
        # Check if any sensor detects an emergency
        current_emergency = config.latest_data["video"]["is_emergency"]
        
        if current_emergency and not emergency_ongoing:
            # Start of a new emergency event
            emergency_ongoing = True
            
            # Try to determine the best vehicle type from both cameras
            front_type = config.latest_data["video"]["front"]["vehicle_type"].lower()
            top_type = config.latest_data["video"]["top"]["vehicle_type"].lower()
            u_front_type = config.latest_data["video"]["upload_front"]["vehicle_type"].lower()
            u_top_type = config.latest_data["video"]["upload_top"]["vehicle_type"].lower()
            
            # --- PRIORITY LOGIC ---
            # Priority: ambulance > fire engine > vip/police
            detected_types = []
            if front_type and front_type != "none": detected_types.append(front_type)
            if top_type and top_type != "none": detected_types.append(top_type)
            if u_front_type and u_front_type != "none": detected_types.append(u_front_type)
            if u_top_type and u_top_type != "none": detected_types.append(u_top_type)
            
            # Define priority order
            priority_order = ["ambulance", "fire", "engine", "police", "vip"]
            
            detected_type = "Emergency Vehicle" # Default
            
            # Find highest priority detected vehicle
            found_priority = False
            for p in priority_order:
                for d in detected_types:
                    if p in d:
                        detected_type = d.capitalize()
                        found_priority = True
                        break
                if found_priority:
                    break
            
            if not found_priority and detected_types:
                detected_type = detected_types[0].capitalize()

            # Prepare details for logging
            details = {
                "audio_status": config.latest_data["audio"]["status"],
                "front_light": config.latest_data["video"]["front"]["siren_light"],
                "top_light": config.latest_data["video"]["top"]["siren_light"],
                "u_front_light": config.latest_data["video"]["upload_front"]["siren_light"],
                "u_top_light": config.latest_data["video"]["upload_top"]["siren_light"],
                "ocr_texts": list(set(
                    config.latest_data["video"]["front"]["ocr_text"] + 
                    config.latest_data["video"]["top"]["ocr_text"] +
                    config.latest_data["video"]["upload_front"]["ocr_text"] +
                    config.latest_data["video"]["upload_top"]["ocr_text"]
                ))
            }
            
            # Log final decision to MongoDB
            db_handler.save_final_decision(
                confirmed_type=detected_type,
                location=config.LOCATION,
                details=details
            )
            
            # Record for SUMO Injection
            db_handler.save_sumo_injection(
                vehicle_type=detected_type,
                entry_point="-E4" # Default entry point for SUMO
            )
            
            # Save complete emergency information JSON
            db_handler.save_emergency_info(config.latest_data)

            # --- SMS TRIGGER ---
            print(f"[INFO] Emergency Triggered! Sending SMS to staff in {config.LOCATION}")
            staff_handler.trigger_location_alerts(detected_type, config.LOCATION)
            # -------------------
            
        elif not current_emergency and emergency_ongoing:
            # End of the emergency event
            emergency_ongoing = False
            print(f"[INFO] Emergency encounter ended: {detected_type}")
            
        time.sleep(1) # Check every second

# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":
    # Start threads
    audio_thread = threading.Thread(target=audio_handler.audio_processing_loop, daemon=True)
    
    # Dual Video Threads
    front_video_thread = threading.Thread(
        target=video_handler.video_processing_loop, 
        args=(config.FRONT_CAMERA_INDEX, "front"), 
        daemon=True
    )
    top_video_thread = threading.Thread(
        target=video_handler.video_processing_loop, 
        args=(config.TOP_CAMERA_INDEX, "top"), 
        daemon=True
    )
    
    api_thread = threading.Thread(target=run_flask, daemon=True)
    decision_thread = threading.Thread(target=decision_logic_loop, daemon=True)

    
    audio_thread.start()
    front_video_thread.start()
    top_video_thread.start()
    api_thread.start()
    decision_thread.start()

    
    print("[INFO] Integrated Emergency System Started.")
    print("[INFO] API available at http://localhost:5000/api/status")
    print("[INFO] Front View: http://localhost:5000/video_feed_front")
    print("[INFO] Top View: http://localhost:5000/video_feed_top")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[INFO] Shutting down...")
