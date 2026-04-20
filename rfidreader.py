#!/usr/bin/env python3
import socket
import time
from datetime import datetime, timedelta
import csv
import random
import json
import os
import logging
import threading
import socketio
import evdev
import struct
import fcntl
import RPi.GPIO as GPIO
from gpiozero import DigitalInputDevice

# Full GPIO cleanup at startup
GPIO.setwarnings(False)
GPIO.cleanup()
time.sleep(0.2)

# ========================= CONFIG =========================
MAIN_PI_IP         = '192.168.1.204'
UDP_PORT           = 5005
LED_GPIO           = 14
SWITCH_GPIO        = 17
LOCAL_CSV          = '/data/rfidreader/rfid_lookup_local.csv'
MAGIC_HISTORY_JSON = '/data/rfidreader/magic_history.json'
MAGIC_TAG          = "289378361"

STOP_COOLDOWN_SEC  = 8
MAX_HISTORY        = 2000
EXCLUDE_DAYS       = 60
WATCHDOG_INTERVAL  = 30   # seconds — how often to check Socket.IO connection

# ========================= GLOBAL STATE =========================
magic_active      = False
last_trigger_time = 0.0
last_send_time    = 0.0
stand_event       = threading.Event()
stand_occupied    = False

# ========================= LOGGING =========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/data/rfidreader/rfidreader.log')
    ]
)
log = logging.info
logging.getLogger('socketio').setLevel(logging.WARNING)
logging.getLogger('engineio').setLevel(logging.WARNING)

# ========================= SOCKET.IO =========================
sio = socketio.Client(reconnection=True, reconnection_attempts=0, reconnection_delay=5)

@sio.event
def connect():
    log("Socket.IO connected to Volumio.")

@sio.event
def disconnect():
    log("Socket.IO disconnected from Volumio.")

# ========================= HARDWARE =========================
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_GPIO, GPIO.OUT, initial=GPIO.LOW)

light_sensor = DigitalInputDevice(SWITCH_GPIO, pull_up=True, bounce_time=0.3)

# ========================= HELPERS =========================
def flash_led(times=3):
    for _ in range(times):
        GPIO.output(LED_GPIO, GPIO.HIGH)
        time.sleep(0.2)
        GPIO.output(LED_GPIO, GPIO.LOW)
        time.sleep(0.2)

def send_udp(payload):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(json.dumps(payload).encode(), (MAIN_PI_IP, UDP_PORT))
        sock.close()
        log(f"Sent UDP: {payload}")
    except Exception as e:
        log(f"UDP Error: {e}")

def stop_playback():
    global magic_active
    send_udp({"command": "stop"})
    magic_active = False
    log("Playback stopped — album removed from stand.")

def find_rfid_device(name_substring="ARM CM0"):
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
            if name_substring.lower() in dev.name.lower():
                log(f"Auto-detected reader: {dev.name} at {path}")
                return dev
        except:
            continue
    return None

def convert_usb_to_pn532(usb_tag_str):
    try:
        val = int(usb_tag_str)
        swapped_val = struct.unpack("<I", struct.pack(">I", val))[0]
        return str(swapped_val)
    except Exception as e:
        log(f"Conversion error: {e}")
        return usb_tag_str

# ========================= CSV LOADER =========================
def load_lookup(csv_file):
    lookup_table, uris = {}, []
    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                tag      = row.get('tag', '').strip().lower()
                location = row.get('location', '').strip()
                service  = row.get('service', 'tidal').lower()
                if tag and location:
                    lookup_table[tag] = {
                        'location': location,
                        'service':  service,
                        'artist':   row.get('artist', ''),
                        'album':    row.get('album', '')
                    }
                    uris.append(location)
        log(f"Loaded {len(lookup_table)} valid entries.")
        return lookup_table, uris
    except Exception as e:
        log(f"CSV Error: {e}")
        return {}, []

lookup, all_uris = load_lookup(LOCAL_CSV)

# ========================= MAGIC 8-BALL =========================
def choose_non_recent_uri():
    cutoff = datetime.now() - timedelta(days=EXCLUDE_DAYS)
    recent = set()
    if os.path.exists(MAGIC_HISTORY_JSON):
        try:
            with open(MAGIC_HISTORY_JSON, 'r') as f:
                for e in json.load(f):
                    if datetime.strptime(e['timestamp'], '%Y-%m-%d %H:%M:%S') >= cutoff:
                        recent.add(e['uri'])
        except:
            pass
    available = [u for u in all_uris if u not in recent] or all_uris
    return random.choice(available)

def record_magic_play(uri):
    entry   = {"timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "uri": uri}
    history = []
    if os.path.exists(MAGIC_HISTORY_JSON):
        try:
            with open(MAGIC_HISTORY_JSON, 'r') as f:
                history = json.load(f)
        except:
            pass
    history = history[-(MAX_HISTORY - 1):] + [entry]
    with open(MAGIC_HISTORY_JSON, 'w') as f:
        json.dump(history, f, indent=2)

# ========================= SOCKET.IO RECONNECT =========================
def ensure_sio_connected():
    """Checks Socket.IO connection and reconnects if dropped."""
    if not sio.connected:
        log("Socket.IO watchdog: connection lost — reconnecting...")
        try:
            sio.connect(f'ws://{MAIN_PI_IP}:3000', transports=['websocket'])
            log("Socket.IO watchdog: reconnected successfully.")
        except Exception as e:
            log(f"Socket.IO watchdog: reconnect failed: {e}")

# ========================= VOLUMIO PUSHSTATE =========================
@sio.on('pushState')
def on_push_state(data):
    """
    Receives Volumio state updates.
    Chains next random album in Magic 8-Ball mode when playback stops,
    but only while the album is still on the stand (GPIO17 LOW).
    """
    global magic_active, last_trigger_time, last_send_time

    status  = data.get('status', 'unknown').lower()
    service = data.get('service', '')
    now     = time.time()

    # Log every pushState so we can confirm they're arriving
    log(f"pushState: status={status} service={service} magic={magic_active} "
        f"stand={stand_occupied} since_trigger={now - last_trigger_time:.1f}s "
        f"since_send={now - last_send_time:.1f}s")

    if data.get('volatile', False) or service in ['tidalconnect', 'airplay', 'volspotconnect2']:
        return

    if (magic_active
            and status == 'stop'
            and stand_occupied
            and now - last_trigger_time > STOP_COOLDOWN_SEC + 2
            and now - last_send_time > 5):
        location = choose_non_recent_uri()
        send_udp({"uri": location, "service": "tidal"})
        last_trigger_time = now
        last_send_time    = now
        record_magic_play(location)
        log(f"Magic 8-Ball: queued next album {location}")

# ========================= IRQ CALLBACK =========================
def on_switch_change():
    """
    Fires instantly on any GPIO17 edge via gpiozero.
    Minimal work — just captures state and wakes main thread.
    """
    global stand_occupied
    new_state = (light_sensor.value == 0)   # LOW = album present
    if new_state != stand_occupied:
        stand_occupied = new_state
        direction = "LOW (album placed / Dark Mode)" if new_state else "HIGH (album removed / Light Mode)"
        log(f"IRQ: GPIO17 → {direction}")
        stand_event.set()

light_sensor.when_activated   = on_switch_change   # LOW  → album placed
light_sensor.when_deactivated = on_switch_change   # HIGH → album removed

# ========================= STARTUP =========================
log("Starting RFID reader (hardware IRQ mode with gpiozero)...")

rfid_dev = find_rfid_device("ARM CM0") or find_rfid_device("Keyboard")
if not rfid_dev:
    log("CRITICAL: No RFID reader detected.")
    exit(1)

flags = fcntl.fcntl(rfid_dev.fd, fcntl.F_GETFL)
fcntl.fcntl(rfid_dev.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

try:
    sio.connect(f'ws://{MAIN_PI_IP}:3000', transports=['websocket'])
except Exception as e:
    log(f"Socket.IO initial connect failed: {e}")

# Capture initial stand state — fire event if album already present at startup
stand_occupied = (light_sensor.value == 0)
log(f"Initial stand state: {'album present (LOW/Dark)' if stand_occupied else 'empty (HIGH/Light)'}")
if stand_occupied:
    stand_event.set()

# ========================= MAIN LOOP =========================
# stand_event.wait(timeout=WATCHDOG_INTERVAL) wakes on either:
#   a) IRQ firing (stand state changed), or
#   b) Watchdog timeout every 30s to check Socket.IO is still alive
try:
    while True:
        triggered = stand_event.wait(timeout=WATCHDOG_INTERVAL)

        if not triggered:
            # Watchdog tick — no IRQ fired, just check Socket.IO health
            ensure_sio_connected()
            continue

        stand_event.clear()

        if stand_occupied:
            # ── Album PLACED (GPIO17 went LOW) ──────────────────────────────
            log("Album placed on stand — reading RFID tag...")
            time.sleep(0.08)  # brief settle time
            tag_id = None
            current_tag_buffer = ""
            scancodes = {2:"1", 3:"2", 4:"3", 5:"4", 6:"5",
                         7:"6", 8:"7", 9:"8", 10:"9", 11:"0"}

            try:
                start_time = time.time()
                for event in rfid_dev.read_loop():
                    if time.time() - start_time > 3.0:
                        break
                    if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                        key = evdev.categorize(event)
                        if key.scancode in scancodes:
                            current_tag_buffer += scancodes[key.scancode]
                        elif key.scancode == 28:  # Enter — end of tag
                            if current_tag_buffer:
                                tag_id = convert_usb_to_pn532(current_tag_buffer.strip())
                                current_tag_buffer = ""
                            break
            except Exception as e:
                log(f"RFID read error: {e}")

            if tag_id is None:
                log("No tag read (timeout or error). Returning to wait.")
                continue

            log(f"Tag read: {tag_id}")
            last_send_time = time.time()

            if tag_id == MAGIC_TAG:
                # Magic 8-Ball: play random albums continuously
                magic_active      = True
                last_trigger_time = time.time()
                loc = choose_non_recent_uri()
                send_udp({"uri": loc, "service": "tidal"})
                record_magic_play(loc)
                flash_led(5)
                log("Magic 8-Ball activated — continuous play until album removed.")

            elif tag_id in lookup:
                # Normal tag: play the associated album once
                magic_active = False
                ent = lookup[tag_id]
                send_udp({"uri": ent['location'], "service": ent['service']})
                flash_led(2)
                log(f"Playing: {ent.get('artist', '')} — {ent.get('album', '')}")

            else:
                log(f"Unknown tag: {tag_id}. No action taken.")

        else:
            # ── Album REMOVED (GPIO17 went HIGH) ────────────────────────────
            stop_playback()

except KeyboardInterrupt:
    log("Shutdown requested.")
finally:
    GPIO.cleanup()
    log("GPIO cleaned up.")
