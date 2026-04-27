# import time
# import os
# import pymongo
# from dotenv import load_dotenv

# try:
#     from pyfirmata import ArduinoMega, util
#     FIRMATA_AVAILABLE = True
# except ImportError:
#     FIRMATA_AVAILABLE = False
#     print("[WARNING] pyfirmata is not installed. Run 'pip install pyfirmata'")

# load_dotenv()

# # =====================================================
# # CONFIGURATION
# # =====================================================
# MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
# DB_NAME = os.getenv("DB_NAME", "EmergencyDetection")
# COLLECTION_NAME = "Traffic_Signals_IOT"

# # Arduino Configuration
# # Change 'COM3' to your Arduino Mega's serial port (e.g., '/dev/ttyACM0' on Linux/Mac)
# ARDUINO_PORT = 'COM11'

# # Mapping junction lights to Arduino pins
# # Map specific edge IDs (e.g., '-E3', 'E0', 'J4_c0') to their color LED pins.
# # Assigning 3 pins (red, yellow, green) for all 9 vehicular signals and 2 pins (red, green) for the 2 pedestrian signals.
# PIN_MAP = {
#     "J1": {
#         "-E3": {"red": 2, "yellow": 3, "green": 4},
#         "-E2": {"red": 5, "yellow": 6, "green": 7},
#         "E00": {"red": 8, "yellow": 9, "green": 10},
#         "buzzer": 11
#     },
#     "J8": {
#         "-E5": {"red": 12, "yellow": 13, "green": 14},
#         "-E4": {"red": 15, "yellow": 16, "green": 17},
#         "-E8": {"red": 18, "yellow": 19, "green": 22}, # Skipping 20, 21 as they are I2C
#         "E3": {"red": 23, "yellow": 24, "green": 25},
#     },
#     "J4": {
#         "E0": {"red": 26, "yellow": 27, "green": 28},
#         "-E0": {"red": 29, "yellow": 30, "green": 31},
#         "J4_c0": {"red": 32, "green": 33},  # Pedestrian 1
#         "J4_c1": {"red": 34, "green": 35},  # Pedestrian 2
#         "buzzer": 36
#     }
# }

# # =====================================================
# # SETUP FUNCTIONS
# # =====================================================
# def setup_arduino():
#     if not FIRMATA_AVAILABLE:
#         return None
        
#     try:
#         print(f"[INFO] Connecting to Arduino Mega on {ARDUINO_PORT}...")
#         # Note: You must upload 'StandardFirmata' to your Arduino Mega from the Arduino IDE Examples.
#         board = ArduinoMega(ARDUINO_PORT)
        
#         # Start an iterator thread to avoid serial buffer overflow (essential for pyfirmata)
#         it = util.Iterator(board)
#         it.start()
#         print("[INFO] Successfully connected to Arduino Mega via pyFirmata.")
#         return board
#     except Exception as e:
#         print(f"[ERROR] Failed to connect to Arduino: {e}")
#         print("[TIP] Check if the Arduino is plugged in, the port is correct, and StandardFirmata is uploaded.")
#         return None

# def setup_mongo():
#     try:
#         print("[INFO] Connecting to MongoDB...")
#         client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
#         db = client[DB_NAME]
#         collection = db[COLLECTION_NAME]
#         client.server_info() # Test connection
#         print("[INFO] Connected to MongoDB successfully.")
#         return collection
#     except Exception as e:
#         print(f"[ERROR] Could not connect to MongoDB: {e}")
#         return None

# # =====================================================
# # CONTROL LOGIC
# # =====================================================
# def update_signals(board, data):
#     """
#     Update Arduino pins based on the MongoDB data document.
#     """
#     junction_data = data.get("junction", {})
    
#     for junction_id, signals_state in junction_data.items():
#         if junction_id not in PIN_MAP:
#             print(f"[WARNING] Unknown junction ID: {junction_id}")
#             continue
            
#         pins = PIN_MAP[junction_id]
        
#         for signal_name, color in signals_state.items():
#             if signal_name in pins:
#                 signal_pins = pins[signal_name]
                
#                 if isinstance(signal_pins, dict):
#                     # Turn off all lights for this signal first
#                     if "red" in signal_pins:
#                         board.digital[signal_pins["red"]].write(0)
#                     if "yellow" in signal_pins:
#                         board.digital[signal_pins["yellow"]].write(0)
#                     if "green" in signal_pins:
#                         board.digital[signal_pins["green"]].write(0)
                    
#                     # Turn on the mandated color
#                     if color in signal_pins:
#                         board.digital[signal_pins[color]].write(1)
            
#         # Update Buzzer (optional if available in data)
#         buzzer_pin = pins.get("buzzer")
#         if buzzer_pin:
#             buzzer_active = data.get("buzzer_active", False)
#             board.digital[buzzer_pin].write(1 if buzzer_active else 0)

#         print(f"[INFO] Applied physical hardware state for {junction_id}.")

# # =====================================================
# # MAIN LOOP
# # =====================================================
# def main():
#     print("="*50)
#     print(" Smart Traffic Control - IoT Arduino Bridge")
#     print("="*50)
    
#     collection = setup_mongo()
#     board = setup_arduino()
    
#     if collection is None:
#         print("[ERROR] Database initialization failed. Exiting.")
#         return
        
#     if not board:
#         print("[WARNING] Running in Simulation/Debug Mode (No Arduino connected).")
    
#     print("[INFO] Starting IoT synchronization loop...")
#     last_id = None
    
#     while True:
#         try:
#             # Fetch the most recent document inserted
#             # Assuming you insert documents from the MARL/SUMO engine with a timestamp
#             latest_doc = collection.find_one(sort=[("timestamp", pymongo.DESCENDING)])
            
#             if latest_doc and latest_doc.get("_id") != last_id:
#                 last_id = latest_doc.get("_id")
#                 ts = latest_doc.get('timestamp')
#                 print(f"\n[INFO] New traffic optimization decision received at {ts}")
                
#                 if board:
#                     update_signals(board, latest_doc)
#                 else:
#                     print(f"[DEBUG] Simulated Update: {latest_doc}")
            
#             time.sleep(0.5) # Poll twice a second to reduce latency
            
#         except pymongo.errors.ConnectionFailure as e:
#             print(f"[ERROR] MongoDB Connection lost: {e}")
#             time.sleep(5)
#         except Exception as e:
#             print(f"[ERROR] Unexpected error in main loop: {e}")
#             time.sleep(2)

# if __name__ == "__main__":
#     main()
