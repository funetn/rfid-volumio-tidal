#!/usr/bin/env python3
"""
rfidreader.py — Dedicated RFID Pi (RPi 3B + PN532 HAT)

Stable version with light sender-side deduplication.
Rev 3.1 — Added state_lock to protect shared globals accessed from
           main loop, UDP listener thread, and HTTP server thread.
"""

import socket
import time
import threading
import RPi.GPIO as GPIO
from pn532 import PN532_SPI
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import csv
import random
import json
import os
import logging
import fcntl

# ========================= CONFIG =========================
VOLUMIO_PI_IP      = '192.168.1.204'
UDP_SEND_PORT      = 5005
UDP_LISTEN_PORT    = 5006
HTTP_PORT          = 8080
LED_GPIO           = 14

LOCAL_CSV          = '/data/rfidreader/rfid_lookup_local.csv'
MAGIC_HISTORY_JSON = '/data/rfidreader/magic_history.json'
MAGIC_TAG          = "289378361"

REMOVAL_TIMEOUT    = 3.0
MAX_HISTORY        = 2000
EXCLUDE_DAYS       = 60

# ========================= GLOBAL STATE =========================
previous_tag_id    = None
magic_active       = False
last_send_time     = 0.0
last_tag_time      = 0.0
last_sent_uri      = None
last_sent_time     = 0.0

# Protects magic_active, last_sent_uri, last_sent_time —
# written from main loop, UDP listener thread, and HTTP server thread.
state_lock = threading.Lock()

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

# ========================= HARDWARE =========================
GPIO.setwarnings(False)
GPIO.cleanup()
time.sleep(0.2)
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_GPIO, GPIO.OUT, initial=GPIO.LOW)

def flash_led(times=3):
    for _ in range(times):
        GPIO.output(LED_GPIO, GPIO.HIGH)
        time.sleep(0.2)
        GPIO.output(LED_GPIO, GPIO.LOW)
        time.sleep(0.2)

# ========================= UDP =========================
def send_udp(payload, ip, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(json.dumps(payload).encode(), (ip, port))
            log(f"Sent UDP to {ip}:{port}: {payload}")
    except Exception as e:
        log(f"UDP send error: {e}")

def send_volumio(payload):
    global last_sent_uri, last_sent_time
    uri = payload.get('uri')
    now = time.time()

    with state_lock:
        # Light deduplication: don't send the same URI again within 2 seconds
        if uri and uri == last_sent_uri and (now - last_sent_time) < 2.0:
            return
        if uri:
            last_sent_uri = uri
            last_sent_time = now

    send_udp(payload, VOLUMIO_PI_IP, UDP_SEND_PORT)

# ========================= CSV & MAGIC =========================
def load_lookup(csv_file):
    lookup_table, uris = {}, []
    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                tag = row.get('tag', '').strip().lower()
                location = row.get('location', '').strip()
                service = row.get('service', 'tidal').lower()
                if tag and location:
                    lookup_table[tag] = {
                        'location': location,
                        'service': service,
                        'artist': row.get('artist', ''),
                        'album': row.get('album', '')
                    }
                    uris.append(location)
        log(f"Loaded {len(lookup_table)} entries from CSV.")
        return lookup_table, uris
    except Exception as e:
        log(f"CSV load error: {e}")
        return {}, []

lookup, all_uris = load_lookup(LOCAL_CSV)

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
    entry = {"timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "uri": uri}
    try:
        with open(MAGIC_HISTORY_JSON, 'a+') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.seek(0)
            try:
                history = json.loads(f.read() or '[]')
            except:
                history = []
            history = history[-(MAX_HISTORY - 1):] + [entry]
            f.seek(0)
            f.truncate()
            json.dump(history, f, indent=2)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        log(f"Failed to record magic play: {e}")

def trigger_magic_8ball():
    global magic_active, last_send_time
    loc = choose_non_recent_uri()
    if not loc:
        log("No URIs available for Magic 8-Ball")
        return

    with state_lock:
        magic_active = True
        last_send_time = time.time()

    send_volumio({"uri": loc, "service": "tidal", "magic": True})
    record_magic_play(loc)
    flash_led(5)
    log(f"Magic 8-Ball triggered: {loc}")

# ========================= UDP LISTENER =========================
def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', UDP_LISTEN_PORT))
    log(f"UDP listener started on port {UDP_LISTEN_PORT}")

    while True:
        try:
            data, addr = sock.recvfrom(1024)
            payload = json.loads(data.decode().strip())
            log(f"Callback from {addr}: {payload}")

            if payload.get('command') == 'stopped':
                with state_lock:
                    is_magic = magic_active
                if is_magic:
                    log("Received 'stopped' callback for Magic 8-Ball — queuing next album")
                    trigger_magic_8ball()
                else:
                    log("Received 'stopped' callback for single album — do nothing (wait for tag removal)")

        except Exception as e:
            log(f"UDP listener error: {e}")

# ========================= HTTP SERVER =========================
class MagicHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/magic':
            log("Magic 8-Ball triggered via iPhone shortcut")
            trigger_magic_8ball()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

def start_http_server():
    try:
        server = HTTPServer(('', HTTP_PORT), MagicHandler)
        log(f"HTTP server started on port {HTTP_PORT}")
        server.serve_forever()
    except Exception as e:
        log(f"HTTP server error: {e}")

# ========================= PN532 =========================
pn532 = None
for attempt in range(3):
    try:
        pn532 = PN532_SPI(debug=False, reset=20, cs=4)
        pn532.SAM_configuration()
        log("PN532 initialized successfully")
        break
    except Exception as e:
        log(f"PN532 init attempt {attempt+1} failed: {e}")
        time.sleep(2)

if pn532 is None:
    log("CRITICAL: PN532 failed to initialize")
    exit(1)

# ========================= STARTUP =========================
log("=== RFID Reader Started (PN532 HAT + 3-Pi Architecture) ===")

threading.Thread(target=udp_listener, daemon=True).start()
threading.Thread(target=start_http_server, daemon=True).start()

# ========================= MAIN LOOP =========================
previous_tag_id = None
last_tag_time = time.time()

try:
    while True:
        uid = pn532.read_passive_target(timeout=0.5)
        now = time.time()

        if uid is None:
            # No tag detected — check for physical removal
            if previous_tag_id is not None and (now - last_tag_time) > REMOVAL_TIMEOUT:
                log(f"Tag {previous_tag_id} removal confirmed (timeout)")
                send_volumio({"command": "stop"})
                previous_tag_id = None      # Fully clear the previous tag
                with state_lock:
                    magic_active = False
                last_tag_time = now         # Use now rather than 0 — guard is on previous_tag_id anyway
        else:
            tag_id = str(int.from_bytes(uid, byteorder='big'))
            last_tag_time = now

            # Only process if this is a new tag (or first tag)
            if tag_id != previous_tag_id:
                previous_tag_id = tag_id
                if tag_id == MAGIC_TAG:
                    trigger_magic_8ball()
                elif tag_id in lookup:
                    with state_lock:
                        magic_active = False
                    ent = lookup[tag_id]
                    send_volumio({"uri": ent['location'], "service": ent['service'], "magic": False})
                    flash_led(2)
                    log(f"Playing normal tag: {ent.get('artist')} - {ent.get('album')}")
                else:
                    log(f"Unknown tag: {tag_id}")

except KeyboardInterrupt:
    log("Shutdown requested.")
except Exception as e:
    log(f"Fatal error: {e}")
finally:
    GPIO.cleanup()
    log("GPIO cleaned up.")
