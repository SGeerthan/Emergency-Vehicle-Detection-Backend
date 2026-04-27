import csv
import os
import requests
import config

def init_staff_file():
    """Initializes the staff CSV file if it doesn't exist."""
    if not os.path.exists(config.STAFF_FILE_PATH):
        with open(config.STAFF_FILE_PATH, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Name", "Phone", "Location"])
        print(f"[INFO] Created staff file: {config.STAFF_FILE_PATH}")

def add_staff(name, phone, location):
    """Adds a new staff member to the records."""
    init_staff_file()
    try:
        with open(config.STAFF_FILE_PATH, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([name, phone, location])
        return True
    except Exception as e:
        print(f"[ERROR] Failed to add staff: {e}")
        return False

def get_all_staff():
    """Returns all staff members as a list of dictionaries."""
    init_staff_file()
    staff_list = []
    try:
        with open(config.STAFF_FILE_PATH, mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                staff_list.append(row)
    except Exception as e:
        print(f"[ERROR] Failed to read staff file: {e}")
    return staff_list

def get_staff_by_location(location):
    """Returns phone numbers for staff registered at a specific location."""
    all_staff = get_all_staff()
    # Normalize location for better matching (case-insensitive, partial match)
    location = location.lower().strip()
    
    matches = []
    for s in all_staff:
        if location in s["Location"].lower():
            matches.append(s["Phone"])
    return matches

def send_sms_alert(phone_number, vehicle_type, location):
    """Sends an SMS alert via smsapi.lk gateway."""
    if config.SMS_API_KEY == "YOUR_API_KEY_HERE":
        print(f"[MOCK SMS] To: {phone_number} | Message: EMERGENCY! {vehicle_type} detected at {location}. Please clear traffic.")
        return True

    message = f"EMERGENCY! {vehicle_type} detected at {location}. Please clear traffic immediately."
    
    params = {
        "api_key": config.SMS_API_KEY,
        "sender": config.SMS_SENDER_ID,
        "number": phone_number,
        "type": "plain",
        "message": message
    }
    
    try:
        response = requests.post(config.SMS_GATEWAY_URL, data=params, timeout=10)
        res_json = response.json()
        if res_json.get("status") == "success":
            print(f"[INFO] SMS Sent to {phone_number} successfully.")
            return True
        else:
            print(f"[ERROR] SMS Gateway error: {res_json}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to send SMS: {e}")
        return False

def trigger_location_alerts(vehicle_type, location):
    """Triggers SMS for all staff at a specific location."""
    phone_numbers = get_staff_by_location(location)
    if not phone_numbers:
        print(f"[INFO] No staff on duty found for location: {location}")
        return

    print(f"[INFO] Triggering {len(phone_numbers)} alerts for {location}")
    for phone in phone_numbers:
        send_sms_alert(phone, vehicle_type, location)
