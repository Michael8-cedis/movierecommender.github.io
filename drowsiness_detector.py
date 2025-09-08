# f4ebaa37-898b-4c54-9eb6-65c9a973954d.py
# (Full SafeRide drowsiness detector with reset-request handling added)
import os
import sys
import json
import time
import datetime
import configparser
import threading
import queue
import uuid
import csv
import socket
import platform
import random
import string
import re
from collections import deque

import cv2
import numpy as np
import mediapipe as mp

# audio
import pygame
import pyttsx3

# firebase admin
import firebase_admin
from firebase_admin import credentials, firestore, storage

# ---------------- CONFIG & DEFAULTS ----------------
CONFIG_FILE = "config.ini"
config = configparser.ConfigParser()
if os.path.exists(CONFIG_FILE):
    config.read(CONFIG_FILE)

# FIREBASE service account path
SERVICE_ACCOUNT = config.get('FIREBASE', 'service_account', fallback="drowsy-detection-5adb9-firebase-adminsdk-fbsvc-78407f31e9.json")

# ---------------- AUTOMATIC ID GENERATION ----------------
DEVICE_ID_FILE = config.get('SYSTEM', 'device_id_file', fallback='device_id.json')

def _random_tail(n=6):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(random.choice(alphabet) for _ in range(n))

def _get_mac_like():
    try:
        import uuid as _uuid
        mac = _uuid.getnode()
        return f"{mac:012x}"
    except Exception:
        return None

def _hostname_snippet():
    try:
        host = socket.gethostname()
        return ''.join(ch for ch in host if ch.isalnum())[:8].upper()
    except Exception:
        return "HOST"

DEFAULT_DEVICE_TYPE = config.get('VEHICLE', 'device_type', fallback='Laptop/Camera')

# Fallback old static values (only used if device_id.json & env absent)
_CFG_VEHICLE_NAME = config.get('VEHICLE', 'name', fallback="LAPTOP-MICHAEL-001")
_CFG_DRIVER_ID = config.get('VEHICLE', 'driver_id', fallback=_CFG_VEHICLE_NAME)
_CFG_DRIVER_NAME = config.get('VEHICLE', 'driver_name', fallback="Driver")

# ENV overrides (optional)
ENV_VEHICLE_ID = os.environ.get('SAFERIDE_VEHICLE_ID')
ENV_DRIVER_ID = os.environ.get('SAFERIDE_DRIVER_ID')
ENV_DRIVER_NAME = os.environ.get('SAFERIDE_DRIVER_NAME')


def load_or_create_device_ids():
    """Return (vehicle_id, driver_id, driver_name)."""
    # 1) Persisted file
    if os.path.exists(DEVICE_ID_FILE):
        try:
            with open(DEVICE_ID_FILE, 'r') as f:
                data = json.load(f)
            v = data.get('vehicleId')
            d = data.get('driverId') or v
            n = data.get('driverName') or 'Driver'
            if v:
                return v, d, n
        except Exception:
            pass

    # 2) ENV
    if ENV_VEHICLE_ID or ENV_DRIVER_ID or ENV_DRIVER_NAME:
        vehicle_id = ENV_VEHICLE_ID or ENV_DRIVER_ID or _hostname_snippet() + "-" + _random_tail(4)
        driver_id = ENV_DRIVER_ID or vehicle_id
        driver_name = ENV_DRIVER_NAME or 'Driver'
        _persist_device_ids(vehicle_id, driver_id, driver_name)
        return vehicle_id, driver_id, driver_name

    # 3) Auto-generate
    mac = _get_mac_like() or _hostname_snippet()
    tail = _random_tail(5)
    vehicle_id = f"SR-{mac[-6:].upper()}-{tail}"
    driver_id = vehicle_id
    driver_name = 'Driver'
    _persist_device_ids(vehicle_id, driver_id, driver_name)
    return vehicle_id, driver_id, driver_name


def _persist_device_ids(vehicle_id, driver_id, driver_name):
    try:
        with open(DEVICE_ID_FILE, 'w') as f:
            json.dump({
                'vehicleId': vehicle_id,
                'driverId': driver_id,
                'driverName': driver_name,
                'createdAt': datetime.datetime.utcnow().isoformat()
            }, f, indent=2)
        print(f"[INFO] Persisted device IDs to {DEVICE_ID_FILE}: {vehicle_id}")
    except Exception as e:
        print("[WARN] Could not persist IDs:", e)


# initial load (module-level)
VEHICLE_NAME, DRIVER_ID, DRIVER_NAME = load_or_create_device_ids()

# Thresholds (defaults safe values)
EYE_AR_THRESH = float(config.get('Thresholds', 'eye_aspect_ratio', fallback="0.25"))
EYE_CLOSED_FRAMES = int(config.get('Thresholds', 'consecutive_frames', fallback="20"))
MOUTH_AR_THRESH = float(config.get('Thresholds', 'mouth_aspect_ratio', fallback="0.75"))
YAWN_FRAMES = int(config.get('Thresholds', 'yawn_frames', fallback="15"))

# Head pose tolerance
MAX_YAW_ANGLE = float(config.get('Thresholds', 'max_yaw_angle', fallback="15.0"))
MAX_PITCH_ANGLE = float(config.get('Thresholds', 'max_pitch_angle', fallback="10.0"))

# ======== ESCALATION WINDOWS (CHANGED TO 3s STEPS) ========
# We collapse escalation into 3-second steps after unsafe is detected.
HIGH_AFTER = 3    # seconds to go from Normal -> High
SEVERE_AFTER = 6  # High -> Severe
CRITICAL_AFTER = 9  # Severe -> Critical

# Start counting immediately on unsafe
GAZE_HOLD_SECONDS = 0.0  # CHANGED to 0.0 so timer starts right away

# Performance / camera
CAM_INDEX = int(config.get('SYSTEM', 'camera_index', fallback="0"))
FRAME_SKIP = int(config.get('SYSTEM', 'frame_skip', fallback="1"))  # 1 = process every frame

# audio files
ALARM_FILE = config.get('SYSTEM', 'alarm_file', fallback="alarm.wav")

# CSV fallback
LOCAL_CSV = config.get('SYSTEM', 'local_csv', fallback="saferide_local_log.csv")
if not os.path.exists(LOCAL_CSV):
    try:
        with open(LOCAL_CSV, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp","driverId","vehicleId","eventType","level","startedAt","endedAt","durationSec","ear","mar","pitch","yaw","yawning","gaze"])
    except Exception:
        pass

# TTS volumes / behavior
VOL_LOW = float(config.get('SYSTEM', 'vol_low', fallback="0.2"))
VOL_HIGH = float(config.get('SYSTEM', 'vol_high', fallback="0.45"))
VOL_SEVERE = float(config.get('SYSTEM', 'vol_severe', fallback="0.75"))
VOL_CRITICAL = float(config.get('SYSTEM', 'vol_critical', fallback="1.0"))

# Auto emergency: 0 disables (seconds sustained Critical before auto-create emergency record)
EMERGENCY_AUTO_AFTER = int(config.get('SYSTEM', 'emergency_auto_after', fallback="0"))

# Snapshot path prefix in storage
SNAPSHOT_PREFIX = config.get('SYSTEM', 'snapshot_prefix', fallback="snapshots")

# Collection names
COL_DRIVER_STATUS = config.get('FIRESTORE', 'driver_status', fallback="driver_status")
COL_EVENTS = config.get('FIRESTORE', 'drowsiness_events', fallback="drowsiness_events")
COL_EMERGENCY = config.get('FIRESTORE', 'emergency_calls', fallback="emergency_calls")
COL_REGISTERED = config.get('FIRESTORE', 'registered_vehicles', fallback="registeredVehicles")
COL_DRIVER_MESSAGES = config.get('FIRESTORE', 'driver_messages', fallback="driver_messages")
COL_RECENT_ALERTS = config.get('FIRESTORE', 'recent_alerts', fallback="recent_alerts")
COL_DASH_STATS = config.get('FIRESTORE', 'dashboard_stats', fallback="dashboard_stats")
COL_DRIVER_RESPONSES = config.get('FIRESTORE', 'driver_responses', fallback="driver_responses")

# ---------------- FIREBASE SETUP ----------------
db = None
fb_bucket = None
try:
    cred = credentials.Certificate(SERVICE_ACCOUNT)
    default_bucket = os.environ.get("FIREBASE_STORAGE_BUCKET", None)
    if default_bucket:
        firebase_admin.initialize_app(cred, {"storageBucket": default_bucket})
    else:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    try:
        fb_bucket = storage.bucket()
    except Exception:
        fb_bucket = None
    print("[INFO] Firebase initialized.")
except Exception as e:
    print("[WARN] Firebase init failed:", e)
    db = None
    fb_bucket = None

# ---------------- Registration bootstrap helpers ----------------
REGISTRATION_CACHE = {
    'exists': False,
    'complete': False,
    'contacts': {},
}

REG_WATCH_STOP = None

def _merge_contact_fields(d):
    out = {}
    if not isinstance(d, dict):
        return out
    for key in (
        'emergencyContact1Name','emergencyContact1Phone',
        'emergencyContact2Name','emergencyContact2Phone',
        'emergencyService1Name','emergencyService1Phone',
        'emergencyService2Name','emergencyService2Phone'):
        if key in d and d[key]:
            out[key] = d[key]
    return out


def ensure_registered_vehicle():
    if db is None:
        return
    try:
        ref = db.collection(COL_REGISTERED).document(VEHICLE_NAME)
        snap = ref.get()
        now = firestore.SERVER_TIMESTAMP
        device_info = {
            "vehicleId": VEHICLE_NAME,
            "driverId": DRIVER_ID,
            "driverName": DRIVER_NAME,
            "deviceType": DEFAULT_DEVICE_TYPE,
            "active": True,
            "lastSeen": now,
        }
        if not snap.exists:
            doc = {
                **device_info,
                "registrationComplete": False,
                "createdAt": now,
                "licensePlate": None,
                "vehicleMake": None,
                "vehicleModel": None,
                "emergencyContact1Name": None,
                "emergencyContact1Phone": None,
                "emergencyContact2Name": None,
                "emergencyContact2Phone": None,
                "emergencyService1Name": None,
                "emergencyService1Phone": None,
                "emergencyService2Name": None,
                "emergencyService2Phone": None,
            }
            ref.set(doc, merge=True)
            REGISTRATION_CACHE['exists'] = True
            REGISTRATION_CACHE['complete'] = False
            REGISTRATION_CACHE['contacts'] = {}
            print("[INFO] registeredVehicles created (placeholder).")
        else:
            current = snap.to_dict() or {}
            REGISTRATION_CACHE['exists'] = True
            REGISTRATION_CACHE['complete'] = bool(current.get('registrationComplete', False))
            REGISTRATION_CACHE['contacts'] = _merge_contact_fields(current)
            ref.set({"lastSeen": now, **device_info}, merge=True)
            print(f"[INFO] registeredVehicles exists. registrationComplete={REGISTRATION_CACHE['complete']}")
    except Exception as e:
        print("[WARN] ensure_registered_vehicle:", e)


def _registration_listener(doc_snapshot, changes, read_time):
    for doc in doc_snapshot:
        if not doc.exists:
            continue
        d = doc.to_dict() or {}
        REGISTRATION_CACHE['exists'] = True
        REGISTRATION_CACHE['complete'] = bool(d.get('registrationComplete', False))
        REGISTRATION_CACHE['contacts'] = _merge_contact_fields(d)
        if db:
            try:
                db.collection(COL_DRIVER_STATUS).document(DRIVER_ID).set({
                    "driverId": DRIVER_ID,
                    "driverName": DRIVER_NAME,
                    "vehicleId": VEHICLE_NAME,
                    "status": "Awaiting Registration" if not REGISTRATION_CACHE['complete'] else "Normal",
                    "needsRegistration": not REGISTRATION_CACHE['complete'],
                    "lastUpdated": firestore.SERVER_TIMESTAMP,
                }, merge=True)
            except Exception:
                pass

# prime registration and start a live listener
if db:
    ensure_registered_vehicle()
    try:
        REG_WATCH_STOP = db.collection(COL_REGISTERED).document(VEHICLE_NAME).on_snapshot(_registration_listener)
    except Exception:
        REG_WATCH_STOP = None

# ---------------- RESET REQUESTS LISTENER ----------------
last_processed_reset = None
RESET_WATCH_STOP = None

def _process_approved_reset(reset_doc_snapshot):
    global last_processed_reset, VEHICLE_NAME, DRIVER_ID, DRIVER_NAME, REG_WATCH_STOP
    try:
        doc_id = reset_doc_snapshot.id
        data = reset_doc_snapshot.to_dict() or {}
        status = data.get("status")
        if status != "approved":
            return
        if last_processed_reset == doc_id:
            return

        print(f"[INFO] Approved reset detected for driver {data.get('driver_id')}, id={doc_id}")

        try:
            if os.path.exists(DEVICE_ID_FILE):
                os.remove(DEVICE_ID_FILE)
                print(f"[INFO] Deleted local device id file: {DEVICE_ID_FILE}")
        except Exception as e:
            print("[WARN] Could not delete device_id.json:", e)

        new_vehicle, new_driver, new_name = load_or_create_device_ids()
        VEHICLE_NAME = new_vehicle
        DRIVER_ID = new_driver
        DRIVER_NAME = new_name
        print(f"[INFO] New IDs generated: vehicle={VEHICLE_NAME}, driver={DRIVER_ID}")

        try:
            ref = db.collection(COL_REGISTERED).document(VEHICLE_NAME)
            now = firestore.SERVER_TIMESTAMP
            doc_payload = {
                "vehicleId": VEHICLE_NAME,
                "driverId": DRIVER_ID,
                "driverName": DRIVER_NAME,
                "deviceType": DEFAULT_DEVICE_TYPE,
                "registrationComplete": False,
                "active": True,
                "lastSeen": now,
                "createdAt": now
            }
            ref.set(doc_payload, merge=True)
            print(f"[INFO] registeredVehicles placeholder created for {VEHICLE_NAME}")
        except Exception as e:
            print("[WARN] Could not create registeredVehicles placeholder:", e)

        try:
            db.collection(COL_DRIVER_STATUS).document(DRIVER_ID).set({
                "driverId": DRIVER_ID,
                "driverName": DRIVER_NAME,
                "vehicleId": VEHICLE_NAME,
                "status": "Awaiting Registration",
                "needsRegistration": True,
                "lastUpdated": firestore.SERVER_TIMESTAMP
            }, merge=True)
            print(f"[INFO] driver_status updated for new driver {DRIVER_ID}")
        except Exception as e:
            print("[WARN] Could not update driver_status:", e)

        try:
            db.collection("reset_requests").document(doc_id).update({
                "status": "done",
                "note": f"{VEHICLE_NAME}",
                "resolvedAt": firestore.SERVER_TIMESTAMP
            })
            print(f"[INFO] reset_requests/{doc_id} updated to done with new vehicle id note.")
        except Exception as e:
            print("[WARN] Could not update reset_requests doc:", e)

        try:
            if REG_WATCH_STOP:
                try:
                    REG_WATCH_STOP()
                except Exception:
                    pass
            try:
                REG_WATCH_STOP = db.collection(COL_REGISTERED).document(VEHICLE_NAME).on_snapshot(_registration_listener)
            except Exception:
                REG_WATCH_STOP = None
        except Exception:
            pass

        last_processed_reset = doc_id

    except Exception as e:
        print("[WARN] _process_approved_reset error:", e)


def _reset_requests_listener(doc_snapshot, changes, read_time):
    try:
        for ds in doc_snapshot:
            if not ds.exists:
                continue
            d = ds.to_dict() or {}
            if d.get("status") == "approved":
                _process_approved_reset(ds)
                break
    except Exception as e:
        print("[WARN] reset_requests listener error:", e)


if db:
    try:
        RESET_WATCH_STOP = db.collection("reset_requests").where("driver_id", "==", DRIVER_ID).on_snapshot(_reset_requests_listener)
        print("[INFO] Listening for reset_requests for this driver.")
    except Exception as e:
        print("[WARN] Could not start reset_requests listener:", e)
        RESET_WATCH_STOP = None

# ---------------- AUDIO (pygame + pyttsx3) ----------------
pygame.mixer.init()
ALARM_SOUND_OBJ = None
if os.path.exists(ALARM_FILE):
    try:
        ALARM_SOUND_OBJ = pygame.mixer.Sound(ALARM_FILE)
    except Exception as e:
        print("[WARN] Could not load alarm file:", e)

def play_alarm(loop=True, volume=0.5):
    try:
        if ALARM_SOUND_OBJ:
            ALARM_SOUND_OBJ.set_volume(volume)
            if loop:
                ALARM_SOUND_OBJ.play(loops=-1)
            else:
                ALARM_SOUND_OBJ.play()
    except Exception:
        pass

def stop_alarm():
    try:
        if ALARM_SOUND_OBJ:
            ALARM_SOUND_OBJ.stop()
    except Exception:
        pass

# TTS queue + worker
tts_q = queue.Queue()
tts_engine = None

def init_tts():
    global tts_engine
    try:
        tts_engine = pyttsx3.init()
        voices = tts_engine.getProperty('voices')
        chosen = None
        for v in voices:
            nm = (v.name or "").lower()
            if "female" in nm or "zira" in nm or "victoria" in nm or "samantha" in nm or "susan" in nm:
                chosen = v.id
                break
        if not chosen and len(voices) > 1:
            chosen = voices[1].id
        if chosen:
            tts_engine.setProperty('voice', chosen)
        tts_engine.setProperty('rate', 150)
    except Exception as e:
        print("[WARN] pyttsx3 TTS init failed:", e)
        tts_engine = None

def tts_worker():
    while True:
        msg = tts_q.get()
        if msg is None:
            break
        try:
            if tts_engine:
                tts_engine.say(msg)
                tts_engine.runAndWait()
        except Exception:
            pass

def speak_short(msg):
    try:
        tts_q.put(msg)
    except Exception:
        pass

init_tts()
threading.Thread(target=tts_worker, daemon=True).start()

# ---------------- MEDIAPIPE SETUP ----------------
mp_face = mp.solutions.face_mesh
face_mesh = mp_face.FaceMesh(max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.5, min_tracking_confidence=0.5)

# landmark idx sets used (MediaPipe indices)
LEFT_EYE_IDX = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]
MOUTH_UP = [13, 14]
MOUTH_LOW = [78, 308]

def to_px(lm, shape):
    h, w = shape[:2]
    return np.array([lm.x * w, lm.y * h], dtype=np.float32)

def eye_aspect_ratio(eye_pts):
    A = np.linalg.norm(eye_pts[1] - eye_pts[5])
    B = np.linalg.norm(eye_pts[2] - eye_pts[4])
    C = np.linalg.norm(eye_pts[0] - eye_pts[3])
    return (A + B) / (2.0 * C) if C > 1e-6 else 0.0

def mouth_aspect_ratio(upper, lower):
    upper_c = np.mean(upper, axis=0)
    lower_c = np.mean(lower, axis=0)
    vert = np.linalg.norm(upper_c - lower_c)
    hor = np.linalg.norm(lower[0] - lower[1]) + 1e-6
    return vert / hor

# ---------------- WRITER QUEUE (async Firestore writes with CSV fallback) ----------------
write_q = queue.Queue()

def writer_loop():
    while True:
        task = write_q.get()
        if task is None:
            break
        func, args = task
        try:
            func(*args)
        except Exception as e:
            try:
                if func.__name__ == "_write_event":
                    payload = args[0]
                    row = [
                        datetime.datetime.utcnow().isoformat(),
                        payload.get("driverId", DRIVER_ID),
                        payload.get("vehicleId", VEHICLE_NAME),
                        payload.get("eventType", ""),
                        payload.get("level", ""),
                        payload.get("startedAt", ""),
                        payload.get("endedAt", ""),
                        payload.get("durationSec", ""),
                        payload.get("metrics", {}).get("ear", ""),
                        payload.get("metrics", {}).get("mar", ""),
                        payload.get("metrics", {}).get("pitch", ""),
                        payload.get("metrics", {}).get("yaw", ""),
                        payload.get("metrics", {}).get("yawning", False),
                        payload.get("metrics", {}).get("gaze", "")
                    ]
                    with open(LOCAL_CSV, "a", newline="") as f:
                        csv.writer(f).writerow(row)
            except Exception:
                pass

writer_thread = threading.Thread(target=writer_loop, daemon=True)
writer_thread.start()

def enqueue_write(func, *args):
    write_q.put((func, args))

# Firestore write functions (used by writer thread)
def _write_status(doc):
    if db is None: return
    db.collection(COL_DRIVER_STATUS).document(DRIVER_ID).set(doc, merge=True)

def _write_event(payload):
    if db is None: return
    db.collection(COL_EVENTS).add(payload)

def _write_emergency(payload):
    if db is None: return
    db.collection(COL_EMERGENCY).add(payload)

def _write_driver_message(payload):
    if db is None: return
    db.collection(COL_DRIVER_MESSAGES).add(payload)

def _write_dashboard_stats(doc):
    if db is None: return
    db.collection(COL_DASH_STATS).document("global").set(doc, merge=True)

def _write_recent_alert(doc):
    if db is None: return
    db.collection(COL_RECENT_ALERTS).document(DRIVER_ID).set(doc, merge=True)

def _write_snapshot(bytes_data, path):
    if fb_bucket is None: return
    blob = fb_bucket.blob(path)
    blob.upload_from_string(bytes_data, content_type="image/jpeg")

def write_status_async(doc): enqueue_write(_write_status, doc)
def write_event_async(payload): enqueue_write(_write_event, payload)
def write_emergency_async(payload): enqueue_write(_write_emergency, payload)
def write_driver_message_async(payload): enqueue_write(_write_driver_message, payload)
def write_dashboard_stats_async(doc): enqueue_write(_write_dashboard_stats, doc)
def write_recent_alert_async(doc): enqueue_write(_write_recent_alert, doc)
def write_snapshot_async(b, path): enqueue_write(_write_snapshot, b, path)

# ---------------- STATE TRACKING ----------------
EAR_BUF = deque(maxlen=5)
MAR_BUF = deque(maxlen=5)
PITCH_BUF = deque(maxlen=5)
YAW_BUF = deque(maxlen=5)

inattentive_since = None
active_event = None
last_status_write = 0
alarm_playing = False
emergency_triggered = False

def seconds_to_level(s):
    if s >= CRITICAL_AFTER: return "Critical"
    if s >= SEVERE_AFTER: return "Severe"
    if s >= HIGH_AFTER: return "High"
    return "Normal"

def escalate_on_yawn(level):
    order = ["Normal","High","Severe","Critical"]
    try:
        i = order.index(level)
        return order[min(i+1, len(order)-1)]
    except:
        return level

def frame_to_jpeg_bytes(frame):
    ret, buf = cv2.imencode(".jpg", frame)
    return buf.tobytes() if ret else None

def update_alarm_for_level(level):
    global alarm_playing
    try:
        if level == "Normal":
            stop_alarm()
            alarm_playing = False
            return
        vol = VOL_LOW
        loop = False
        if level == "High":
            vol = VOL_HIGH; loop = False
        elif level == "Severe":
            vol = VOL_SEVERE; loop = True
        elif level == "Critical":
            vol = VOL_CRITICAL; loop = True
        if ALARM_SOUND_OBJ:
            stop_alarm()
            play_alarm(loop=loop, volume=vol)
            alarm_playing = True
    except Exception:
        pass

# TTS frequency control and repetition
last_tts_time = 0
last_tts_level = None

def tts_for_level(level, now_ts, high_persist_duration=0):
    global last_tts_time, last_tts_level
    if level == "Normal": return
    if level in ("High","Severe"):
        interval = 10 if level == "High" else 5
        if level == "High" and high_persist_duration >= 10:
            interval = max(2, interval // 2)
        msg = "Warning. Please focus on the road."
    else:
        interval = 2
        msg = "Critical alert. Please stop the vehicle and seek help."
    if now_ts - last_tts_time >= interval or last_tts_level != level:
        speak_short(msg)
        last_tts_time = now_ts
        last_tts_level = level

# ---------------- SETTINGS LISTENERS ----------------
settings_lock = threading.Lock()
reverse_flag = False

def thresholds_listener(doc_snapshot, changes, read_time):
    global EYE_AR_THRESH, MOUTH_AR_THRESH, MAX_PITCH_ANGLE, MAX_YAW_ANGLE, HIGH_AFTER, SEVERE_AFTER, CRITICAL_AFTER
    for doc in doc_snapshot:
        if not doc.exists: continue
        d = doc.to_dict()
        with settings_lock:
            EYE_AR_THRESH = float(d.get("eye_aspect_ratio_threshold", EYE_AR_THRESH))
            MOUTH_AR_THRESH = float(d.get("mouth_aspect_ratio_threshold", MOUTH_AR_THRESH))
            MAX_PITCH_ANGLE = float(d.get("pitch_threshold", MAX_PITCH_ANGLE))
            MAX_YAW_ANGLE = float(d.get("yaw_threshold", MAX_YAW_ANGLE))
            # Preserve our 3s steps unless console overrides:
            HIGH_AFTER = int(d.get("high_seconds", HIGH_AFTER))
            SEVERE_AFTER = int(d.get("severe_seconds", SEVERE_AFTER))
            CRITICAL_AFTER = int(d.get("critical_seconds", CRITICAL_AFTER))
    print("[INFO] thresholds updated from Firestore")

def vehicle_state_listener(doc_snapshot, changes, read_time):
    global reverse_flag
    for doc in doc_snapshot:
        if not doc.exists: continue
        with settings_lock:
            reverse_flag = bool(doc.to_dict().get('reverse', False))

if db:
    try:
        db.collection("settings").document("alert_thresholds").on_snapshot(thresholds_listener)
    except Exception:
        pass
    try:
        db.collection("settings").document("vehicle_state").on_snapshot(vehicle_state_listener)
    except Exception:
        pass


# ---------------- Emergency plumbing ----------------
TWILIO_ACCOUNT_SID = (
    os.environ.get("TWILIO_ACCOUNT_SID") or
    os.environ.get("REACT_APP_TWILIO_ACCOUNT_SID") or
    config.get("TWILIO", "account_sid")
)
TWILIO_AUTH_TOKEN = (
    os.environ.get("TWILIO_AUTH_TOKEN") or
    os.environ.get("REACT_APP_TWILIO_AUTH_TOKEN") or
    config.get("TWILIO", "auth_token")
)
TWILIO_PHONE_NUMBER = (
    os.environ.get("TWILIO_PHONE_NUMBER") or
    os.environ.get("REACT_APP_TWILIO_PHONE_NUMBER") or
    config.get("TWILIO", "phone_number")
)
DEFAULT_COUNTRY_CODE = config.get(
    "TWILIO", "default_country_code",
    fallback=os.environ.get("DEFAULT_COUNTRY_CODE", "+1")
)

_twilio_client = None
try:
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        from twilio.rest import Client
        _twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        print("[INFO] Twilio client initialized.")
    else:
        print("[WARN] Twilio credentials not found; Twilio disabled.")
except Exception as e:
    print("[WARN] Twilio init failed:", e)
    _twilio_client = None

# ------------------ Phone Normalization ------------------
def _normalize_phone(raw_phone: str):
    if not raw_phone:
        return None
    s = str(raw_phone).strip()
    s = re.sub(r"[\s\-\(\)]+", "", s)
    s = re.sub(r"[^0-9+]", "", s)
    if s.startswith("+") and len(s) > 6:
        return s
    if s.startswith("00"):
        return "+" + s[2:]
    if s.startswith("0"):
        s = s.lstrip("0")
        return DEFAULT_COUNTRY_CODE + s
    if len(s) <= 10:
        return DEFAULT_COUNTRY_CODE + s
    return "+" + s

# ------------------ Twilio Send Functions ------------------
def _send_sms(to, body):
    if _twilio_client is None:
        print("[WARN] Twilio client not initialized; skipping SMS to", to)
        return None
    try:
        to_e164 = _normalize_phone(to)
        msg = _twilio_client.messages.create(
            from_=TWILIO_PHONE_NUMBER,
            to=to_e164,
            body=body
        )
        print(f"[INFO] SMS queued to {to_e164} sid={msg.sid}")
        return msg.sid
    except Exception as e:
        print("[WARN] send_sms failed:", e)
        return None

def _make_call(to, say_text):
    if _twilio_client is None:
        print("[WARN] Twilio client not initialized; skipping call to", to)
        return None
    try:
        to_e164 = _normalize_phone(to)
        twiml = f'<Response><Say voice="alice">{say_text}</Say></Response>'
        call = _twilio_client.calls.create(
            from_=TWILIO_PHONE_NUMBER,
            to=to_e164,
            twiml=twiml
        )
        print(f"[INFO] Call started to {to_e164} sid={call.sid}")
        return call.sid
    except Exception as e:
        print("[WARN] make_call failed:", e)
        return None

# ------------------ Fetch Emergency Contacts ------------------
def _fetch_registered_contacts(driver_id):
    contacts = []
    try:
        ref = db.collection(COL_REGISTERED).document(driver_id)
        snap = ref.get()
        if not snap.exists:
            return contacts
        d = snap.to_dict() or {}
        for kname, kphone in (
            ('emergencyContact1Name', 'emergencyContact1Phone'),
            ('emergencyContact2Name', 'emergencyContact2Phone'),
            ('emergencyService1Name', 'emergencyService1Phone'),
            ('emergencyService2Name', 'emergencyService2Phone'),
        ):
            name = d.get(kname)
            phone = d.get(kphone)
            if phone:
                contacts.append({"name": name or kname, "phone": str(phone).strip()})
    except Exception as e:
        print("[WARN] _fetch_registered_contacts failed:", e)
    return contacts

def resolve_emergency_targets_from_cache():
    contacts = REGISTRATION_CACHE.get('contacts', {})
    targets = []
    for kname, kphone in (
        ('emergencyContact1Name', 'emergencyContact1Phone'),
        ('emergencyContact2Name', 'emergencyContact2Phone'),
        ('emergencyService1Name', 'emergencyService1Phone'),
        ('emergencyService2Name', 'emergencyService2Phone'),
    ):
        name = contacts.get(kname)
        phone = contacts.get(kphone)
        if phone:
            targets.append({"name": name or kname, "phone": str(phone)})
    return targets

# ------------------ Emergency Guards ------------------
_emergency_in_progress = False
_emergency_targets_contacted = set()

# ------------------ Handle Emergency Doc ------------------
def _handle_emergency_doc(doc_id, data):
    global _emergency_in_progress, _emergency_targets_contacted
    try:
        if not data or data.get('handled') or data.get('processing'):
            print(f"[INFO] emergency doc {doc_id} already handled/processing.")
            return

        if _emergency_in_progress:
            print(f"[INFO] Emergency already in progress, skipping doc {doc_id}.")
            return

        _emergency_in_progress = True
        _emergency_targets_contacted.clear()

        try:
            db.collection(COL_EMERGENCY).document(doc_id).set({'processing': True}, merge=True)
        except Exception: pass

        driver_id = data.get('driverId') or data.get('driver_id') or DRIVER_ID
        vehicle_id = data.get('vehicleId') or data.get('vehicle_id') or VEHICLE_NAME
        reason = data.get('reason') or data.get('trigger') or data.get('emergencyReason') or 'unknown'

        status_snapshot = {}
        try:
            sref = db.collection(COL_DRIVER_STATUS).document(driver_id)
            ssnap = sref.get()
            status_snapshot = ssnap.to_dict() if ssnap.exists else {}
        except Exception:
            status_snapshot = {}

        targets = resolve_emergency_targets_from_cache() or _fetch_registered_contacts(driver_id)
        if not targets:
            print(f"[WARN] No emergency targets found for driver {driver_id} — aborting.")
            try: db.collection(COL_EMERGENCY).document(doc_id).delete()
            except Exception: pass
            _emergency_in_progress = False
            return

        driver_name = status_snapshot.get('driverName') or DRIVER_NAME or ''
        status_text = status_snapshot.get('status') or 'Unknown'
        vehicle_text = vehicle_id or VEHICLE_NAME or ''

        sms_body = (
            f" DRIVER ALERT\nDriver: {driver_name}\nVehicle: {vehicle_text}\n"
            f"Status: {status_text}\nReason: {reason}\nPlease attend to the driver immediately."
        )
        call_text = (
            f"SafeRide Emergency. Driver {driver_name}, vehicle {vehicle_text}, "
            f"requires immediate assistance. Reason: {reason}."
        )

        sms_sids, call_sids = [], []
        for t in targets:
            phone = t.get('phone')
            if not phone or phone in _emergency_targets_contacted:
                continue
            try:
                csid = _make_call(phone, call_text)
                if csid:
                    call_sids.append({'phone': phone, 'sid': csid})
            except Exception as e:
                print("[WARN] call error for", phone, e)
            try:
                msid = _send_sms(phone, sms_body)
                if msid:
                    sms_sids.append({'phone': phone, 'sid': msid})
            except Exception as e:
                print("[WARN] sms error for", phone, e)
            _emergency_targets_contacted.add(phone)

        try:
            db.collection('emergency_call_history').add({
                'driverId': driver_id,
                'driverName': driver_name,
                'vehicleId': vehicle_text,
                'reason': reason,
                'targets': targets,
                'callSids': call_sids,
                'smsSids': sms_sids,
                'handledAt': firestore.SERVER_TIMESTAMP
            })
        except Exception as e:
            print("[WARN] failed to write emergency_call_history:", e)

        try:
            db.collection(COL_EMERGENCY).document(doc_id).delete()
            print(f"[INFO] emergency request {doc_id} handled and deleted.")
        except Exception as e:
            print("[WARN] failed to delete emergency request doc:", e)

    except Exception as e:
        print("[WARN] _handle_emergency_doc general error:", e)
    finally:
        _emergency_in_progress = False
        _emergency_targets_contacted.clear()


# ------------------ Emergency Snapshot Listener ------------------
def _emergency_on_snapshot(col_snapshot, changes, read_time):
    for change in changes:
        try:
            if change.type.name != 'ADDED': continue
            doc = change.document
            data = doc.to_dict() or {}
            if data.get('handled'): continue
            resp = (data.get('response') or '').lower() if data.get('response') else ''
            if resp == 'yes':
                try: db.collection(COL_EMERGENCY).document(doc.id).delete()
                except Exception: pass
                continue
            threading.Thread(target=_handle_emergency_doc, args=(doc.id, data), daemon=True).start()
        except Exception as e:
            print('[WARN] emergency snapshot handler error:', e)

try:
    if db:
        _EMERGENCY_WATCH_STOP = db.collection(COL_EMERGENCY).on_snapshot(_emergency_on_snapshot)
        print('[INFO] Twilio emergency listener attached to collection:', COL_EMERGENCY)
except Exception as e:
    print('[WARN] Could not attach emergency_calls listener:', e)

# ------------------ Driver Status Watch (Updated for Single Emergency Trigger) ------------------
# ------------------ Driver Status Watch ------------------
def _driver_status_watch(doc_snapshot, changes, read_time):
    global _emergency_in_progress  # Local flag to avoid duplicate calls
    global _last_logged_status     # Track last status to avoid spam
    for doc in doc_snapshot:
        try:
            if not doc.exists:
                continue
            d = doc.to_dict() or {}
            status = (d.get('status') or '').lower()
            emergency_called = d.get('emergencyCalled', False)

            suppress = False
            driver_response = None
            try:
                resp_snap = db.collection(COL_DRIVER_RESPONSES).document(DRIVER_ID).get()
                if resp_snap.exists:
                    driver_response = (resp_snap.to_dict() or {}).get('response', '').lower()
                    if driver_response == 'yes':
                        suppress = True
            except Exception:
                pass

            # --- Case 1: Driver pressed "NO" → immediate call (but not if NORMAL) ---
            if (
                driver_response == 'no'
                and status != 'normal'
                and not _emergency_in_progress
            ):
                print('[INFO] Driver pressed NO, triggering immediate emergency call.')
                _emergency_in_progress = True
                try:
                    trigger_emergency_notification('driver_pressed_no')
                except Exception as e:
                    print('[WARN] trigger_emergency_notification failed (NO case):', e)

            # --- Case 2: Status escalates to Critical without "YES" suppression → auto call ---
            elif (
                status == 'critical'
                and not suppress
                and not emergency_called
                and not _emergency_in_progress
            ):
                print('[INFO] driver_status Critical detected, auto-creating emergency request.')
                _emergency_in_progress = True
                try:
                    trigger_emergency_notification('auto_status_critical')
                except Exception as e:
                    print('[WARN] trigger_emergency_notification failed (CRITICAL case):', e)

            # --- Case 3: Status returns to Normal → reset everything ---
            if status == 'normal':
                if _last_logged_status != 'normal':  # Avoid repeating log spam
                    print('[INFO] Driver back to NORMAL — reset suppression and emergency flag.')
                _emergency_in_progress = False
                try:
                    db.collection(COL_DRIVER_RESPONSES).document(DRIVER_ID).delete()
                except Exception:
                    pass
                try:
                    db.collection(COL_DRIVER_STATUS).document(DRIVER_ID).update(
                        {'emergencyCalled': False}
                    )
                except Exception:
                    pass

            # Update last logged status
            _last_logged_status = status

        except Exception as e:
            print('[WARN] driver_status_watch error:', e)


# Attach watcher
try:
    if db:
        _last_logged_status = None  # initialize tracker
        db.collection(COL_DRIVER_STATUS).document(DRIVER_ID).on_snapshot(_driver_status_watch)
        print('[INFO] Attached driver_status watcher for', DRIVER_ID)
except Exception as e:
    print('[WARN] Could not attach driver_status watcher:', e)


# ------------------ Trigger Emergency ------------------
def trigger_emergency_notification(reason, snapshot_path=None):
    try:
        targets = resolve_emergency_targets_from_cache()
        payload = {
            "driverId": DRIVER_ID,
            "driverName": DRIVER_NAME,
            "vehicleId": VEHICLE_NAME,
            "reason": reason,
            "targets": targets,
            "snapshotPath": snapshot_path,
            "createdAt": firestore.SERVER_TIMESTAMP if db else datetime.datetime.utcnow().isoformat(),
            "handled": False,
        }
        write_emergency_async(payload)
        write_status_async({
            "driverId": DRIVER_ID,
            "vehicleId": VEHICLE_NAME,
            "status": "Critical",
            "emergencyCalled": True,
            "emergencyReason": reason,
            "lastUpdated": firestore.SERVER_TIMESTAMP if db else datetime.datetime.utcnow().isoformat(),
        })
        print("[INFO] Emergency notification queued:", reason, "targets=", len(targets))
    except Exception as e:
        print("[WARN] trigger_emergency_notification:", e)





# ---------------- MAIN LOOP ----------------
def main():
    global inattentive_since, active_event, last_status_write, emergency_triggered

    ensure_registered_vehicle()

    if db and not REGISTRATION_CACHE.get('complete', False):
        try:
            write_status_async({
                "driverId": DRIVER_ID,
                "driverName": DRIVER_NAME,
                "vehicleId": VEHICLE_NAME,
                "status": "Awaiting Registration",
                "needsRegistration": True,
                "lastUpdated": firestore.SERVER_TIMESTAMP,
            })
            speak_short("SafeRide setup: please complete registration on screen.")
        except Exception:
            pass

    cap = cv2.VideoCapture(CAM_INDEX)
    cap.set(3, 640)
    cap.set(4, 480)
    frame_idx = 0
    print("[INFO] drowsiness_detector starting. Press 'q' to quit.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.03)
                continue

            # Flip the frame horizontally to correct mirror effect
            frame = cv2.flip(frame, 1)

            frame_idx += 1
            if FRAME_SKIP > 1 and (frame_idx % FRAME_SKIP) != 0:
                cv2.imshow("SafeRide Monitor", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(img)

            ear = 0.0
            mar = 0.0
            pitch = 0.0
            yaw = 0.0
            yawning = False
            eyes_closed = False
            gaze = "on_road"
            confidence_ok = True

            if results.multi_face_landmarks:
                lm = results.multi_face_landmarks[0].landmark
                # compute eyes EAR
                left_eye = np.array([to_px(lm[i], frame.shape) for i in LEFT_EYE_IDX])
                right_eye = np.array([to_px(lm[i], frame.shape) for i in RIGHT_EYE_IDX])
                left_ear = eye_aspect_ratio(left_eye)
                right_ear = eye_aspect_ratio(right_eye)
                ear = (left_ear + right_ear) / 2.0
                EAR_BUF.append(ear)

                # mouth (yawn)
                upper = np.array([to_px(lm[i], frame.shape) for i in MOUTH_UP])
                lower = np.array([to_px(lm[i], frame.shape) for i in MOUTH_LOW])
                mar = mouth_aspect_ratio(upper, lower)
                MAR_BUF.append(mar)

                # crude head pose proxies
                yaw_proxy = (right_eye[0][0] - left_eye[0][0]) * 0.05
                pitch_proxy = (left_eye[1][1] - right_eye[1][1]) * 0.05
                yaw = float(yaw_proxy)
                pitch = float(pitch_proxy)
                YAW_BUF.append(yaw)
                PITCH_BUF.append(pitch)

                deg_yaw = yaw
                deg_pitch = pitch

                if abs(deg_yaw) > MAX_YAW_ANGLE:
                    gaze = "looking_away"
                if abs(deg_pitch) > MAX_PITCH_ANGLE:
                    gaze = "head_down" if gaze == "on_road" else "mixed"

                eyes_closed = ear < EYE_AR_THRESH
                yawning = mar > MOUTH_AR_THRESH

                confidence_ok = True
            else:
                # No face -> treat as unsafe (possible driver not visible)
                gaze = "no_face"
                eyes_closed = True
                confidence_ok = False

            with settings_lock:
                in_reverse = reverse_flag

            # Do not consider unsafe if vehicle in reverse
            unsafe_condition = (not in_reverse) and (eyes_closed or yawning or gaze in ("looking_away", "head_down", "mixed", "no_face"))

            now_ts = time.time()

            # START/END of inattentive window
            if unsafe_condition:
                if inattentive_since is None:
                    inattentive_since = now_ts
            else:
                if inattentive_since is not None and active_event is not None:
                    ended_at = firestore.SERVER_TIMESTAMP if db else datetime.datetime.utcnow().isoformat()
                    duration = now_ts - active_event["started"]
                    metrics = {"ear": round(ear, 3), "mar": round(mar, 3), "pitch": round(pitch, 3), "yaw": round(yaw, 3), "yawning": bool(yawning), "gazeState": gaze}
                    payload = {
                        "driverId": DRIVER_ID,
                        "driverName": DRIVER_NAME,
                        "vehicleId": VEHICLE_NAME,
                        "eventType": active_event.get("type", "inattentive"),
                        "level": active_event.get("level", ""),
                        "status": "Resolved",
                        "startedAt": active_event.get("startedFirestore", active_event.get("started")),
                        "endedAt": ended_at,
                        "durationSec": float(duration),
                        "metrics": metrics
                    }
                    write_event_async(payload)
                    status_doc = {
                        "driverId": DRIVER_ID,
                        "driverName": DRIVER_NAME,
                        "vehicleId": VEHICLE_NAME,
                        "status": "Normal",
                        "lastUpdated": firestore.SERVER_TIMESTAMP if db else datetime.datetime.utcnow().isoformat(),
                        "activeAlerts": 0,
                        "ear": round(ear, 3),
                        "mar": round(mar, 3),
                        "pitch": round(pitch, 3),
                        "yaw": round(yaw, 3),
                        "yawning": bool(yawning),
                        "gazeState": str(gaze) if gaze is not None else "unknown"
                    }
                    write_status_async(status_doc)
                    write_dashboard_stats_async({"lastEvent": payload.get("eventType", ""), "lastLevel": payload.get("level", ""), "lastDuration": payload.get("durationSec", 0)})
                    recent_doc = {
                        "driverId": DRIVER_ID,
                        "driverName": DRIVER_NAME,
                        "vehicleId": VEHICLE_NAME,
                        "level": active_event.get("level", ""),
                        "status": "Resolved",
                        "timestamp": ended_at
                    }
                    write_recent_alert_async(recent_doc)
                    active_event = None
                inattentive_since = None

            # Compute level using 3s steps
            elapsed = 0.0
            level = "Normal"
            if inattentive_since:
                hold_elapsed = now_ts - inattentive_since
                if hold_elapsed >= GAZE_HOLD_SECONDS:
                    elapsed = hold_elapsed - GAZE_HOLD_SECONDS
                    level = seconds_to_level(elapsed)
                else:
                    level = "Normal"

            # escalate on yawn if applicable
            if yawning and (level != "Critical"):
                level = escalate_on_yawn(level)

            # Create or update active event
            if unsafe_condition and level != "Normal":
                if active_event is None:
                    event_type = "yawn" if (yawning and not eyes_closed) else ("eyes_closed" if eyes_closed else gaze)
                    active_event = {
                        "id": str(uuid.uuid4()),
                        "started": now_ts,
                        "startedFirestore": firestore.SERVER_TIMESTAMP if db else datetime.datetime.utcnow().isoformat(),
                        "type": event_type,
                        "level": level,
                        "snapshot_taken": False
                    }
                    metrics = {"ear": round(ear, 3), "mar": round(mar, 3), "pitch": round(pitch, 3), "yaw": round(yaw, 3), "yawning": bool(yawning), "gazeState": gaze}
                    payload = {
                        "driverId": DRIVER_ID,
                        "driverName": DRIVER_NAME,
                        "vehicleId": VEHICLE_NAME,
                        "eventType": event_type,
                        "level": level,
                        "status": "Active",
                        "startedAt": active_event["startedFirestore"],
                        "durationSec": 0.0,
                        "metrics": metrics
                    }
                    write_event_async(payload)
                    status_doc = {
                        "driverId": DRIVER_ID,
                        "driverName": DRIVER_NAME,
                        "vehicleId": VEHICLE_NAME,
                        "status": level,
                        "statusSince": active_event["startedFirestore"],
                        "lastUpdated": firestore.SERVER_TIMESTAMP if db else datetime.datetime.utcnow().isoformat(),
                        "activeAlerts": 1,
                        "ear": metrics["ear"],
                        "mar": metrics["mar"],
                        "pitch": metrics["pitch"],
                        "yaw": metrics["yaw"],
                        "yawning": metrics["yawning"],
                        "gazeState": metrics["gazeState"]
                    }
                    write_status_async(status_doc)
                    recent_doc = {
                        "driverId": DRIVER_ID,
                        "driverName": DRIVER_NAME,
                        "vehicleId": VEHICLE_NAME,
                        "level": level,
                        "status": "Active",
                        "timestamp": firestore.SERVER_TIMESTAMP if db else datetime.datetime.utcnow().isoformat(),
                        "metrics": metrics
                    }
                    write_recent_alert_async(recent_doc)
                else:
                    # update level if escalated
                    if level != active_event.get("level"):
                        active_event["level"] = level
                        metrics = {"ear": round(ear, 3), "mar": round(mar, 3), "pitch": round(pitch, 3), "yaw": round(yaw, 3), "yawning": bool(yawning), "gazeState": gaze}
                        payload = {
                            "driverId": DRIVER_ID,
                            "driverName": DRIVER_NAME,
                            "vehicleId": VEHICLE_NAME,
                            "eventType": active_event.get("type"),
                            "level": level,
                            "status": "Active",
                            "startedAt": active_event.get("startedFirestore"),
                            "durationSec": float(now_ts - active_event.get("started")),
                            "metrics": metrics
                        }
                        write_event_async(payload)
                        status_doc = {
                            "driverId": DRIVER_ID,
                            "driverName": DRIVER_NAME,
                            "vehicleId": VEHICLE_NAME,
                            "status": level,
                            "lastUpdated": firestore.SERVER_TIMESTAMP if db else datetime.datetime.utcnow().isoformat(),
                            "activeAlerts": 1,
                            "ear": metrics["ear"],
                            "mar": metrics["mar"]
                        }
                        write_status_async(status_doc)

            # -------- periodic driver_status refresh (ALWAYS RUNS) --------
            if db and (time.time() - last_status_write > 1.0):
                try:
                    status_doc = {
                        "driverId": DRIVER_ID,
                        "driverName": DRIVER_NAME,
                        "vehicleId": VEHICLE_NAME,
                        "status": level if REGISTRATION_CACHE.get('complete', True) else "Awaiting Registration",
                        "needsRegistration": not REGISTRATION_CACHE.get('complete', True),
                        "lastUpdated": firestore.SERVER_TIMESTAMP,
                        "activeAlerts": 1 if level in ("High", "Severe", "Critical") else 0,
                        "ear": float(ear) if ear is not None else 0.0,
                        "mar": float(mar) if mar is not None else 0.0,
                        "pitch": float(pitch) if pitch is not None else 0.0,
                        "yaw": float(yaw) if yaw is not None else 0.0,
                        "yawning": bool(yawning),
                        "gazeState": gaze if gaze is not None else "no_face"
                    }
                    write_status_async(status_doc)
                    last_status_write = time.time()
                except Exception as e:
                    print(f"❌ Firestore write failed: {e}")

            # alarms and TTS
            high_persist_duration = 0
            if inattentive_since:
                hold_elapsed = now_ts - inattentive_since
                if hold_elapsed >= GAZE_HOLD_SECONDS:
                    high_persist_duration = hold_elapsed - GAZE_HOLD_SECONDS
            update_alarm_for_level(level)
            tts_for_level(level, time.time(), high_persist_duration)

            # snapshot for Critical once
            snapshot_path = None
            if active_event and active_event.get("level") == "Critical" and not active_event.get("snapshot_taken"):
                jpeg = frame_to_jpeg_bytes(frame)
                if jpeg and fb_bucket:
                    path = f"{SNAPSHOT_PREFIX}/{VEHICLE_NAME}/{int(time.time())}.jpg"
                    write_snapshot_async(jpeg, path)
                    snapshot_path = path
                active_event["snapshot_taken"] = True

            # auto emergency if configured
            if active_event and active_event.get("level") == "Critical" and EMERGENCY_AUTO_AFTER > 0 and not emergency_triggered:
                if time.time() - active_event["started"] >= EMERGENCY_AUTO_AFTER:
                    trigger_emergency_notification("Auto-emergency: sustained critical", snapshot_path)
                    speak_short("Emergency services notified")
                    emergency_triggered = True

            # -------- overlay debug info (adds visible timer) --------
            cv2.putText(frame, f"Vehicle: {VEHICLE_NAME}", (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.putText(frame, f"Level: {level}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0) if level == "Normal" else (0, 0, 255), 2)
            cv2.putText(frame, f"EAR:{round(ear,3)} MAR:{round(mar,3)} P:{round(pitch,2)} Y:{round(yaw,2)}", (10, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            if inattentive_since:
                elapsed_txt = f"Unsafe for: {int(now_ts - inattentive_since)}s  (High@3s, Severe@6s, Critical@9s)"
                cv2.putText(frame, elapsed_txt, (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 200), 1)

            cv2.imshow("SafeRide Monitor", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print("[INFO] Interrupted by user.")
    finally:
        try:
            write_q.put(None)
        except:
            pass
        try:
            cap.release()
            cv2.destroyAllWindows()
        except:
            pass
        print("[INFO] Shutdown complete.")


if __name__ == "__main__":
    main()
