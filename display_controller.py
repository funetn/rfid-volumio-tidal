#!/usr/bin/env python3
"""
display_controller.py — Runs on PeppyMeters Pi

Now handles 30-second grace period for display off.
Receives commands from volumio_watchdog.
"""

import socket
import json
import subprocess
import threading
import logging
from datetime import datetime

DISPLAY_LISTEN_PORT = 5007
GRACE_PERIOD_SEC = 30

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/var/log/display_controller.log')
    ]
)
log = logging.info

# Global timer for pending display off
pending_off_timer = None

def control_display(state: str):
    """state must be exactly 'on' or 'off'"""
    if state not in ('on', 'off'):
        log(f"Invalid state requested: {state}")
        return

    service = f"display-{state}.service"
    log(f"Received request to turn display {state.upper()} → starting {service}")

    try:
        result = subprocess.run(
            ['sudo', 'systemctl', 'start', service],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            log(f"✅ Display {state.upper()} executed successfully")
        else:
            log(f"❌ Display {state.upper()} failed: {result.stderr.strip()}")
    except Exception as e:
        log(f"💥 Failed to control display {state}: {e}")

def display_on():
    global pending_off_timer
    # Cancel any pending off timer
    if pending_off_timer is not None:
        pending_off_timer.cancel()
        pending_off_timer = None
        log("Cancelled pending display off timer")

    control_display("on")

def schedule_display_off():
    """Start 30-second timer to turn display off"""
    global pending_off_timer

    def turn_off():
        log(f"Grace period ({GRACE_PERIOD_SEC}s) expired - turning display OFF")
        control_display("off")

    # Cancel any existing timer
    if pending_off_timer is not None:
        pending_off_timer.cancel()

    pending_off_timer = threading.Timer(GRACE_PERIOD_SEC, turn_off)
    pending_off_timer.start()
    log(f"Started {GRACE_PERIOD_SEC}s grace period timer for display off")

# ========================= UDP Listener =========================
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('', DISPLAY_LISTEN_PORT))
log(f"Display controller listening on UDP port {DISPLAY_LISTEN_PORT}")

while True:
    try:
        data, addr = sock.recvfrom(1024)
        payload = json.loads(data.decode().strip())
        log(f"Received from {addr}: {payload}")

        cmd = payload.get('command')

        if cmd == 'display_on':
            display_on()
        elif cmd == 'display_off':
            schedule_display_off()
        else:
            log(f"Unknown command: {cmd}")

    except json.JSONDecodeError:
        log("Invalid JSON received")
    except Exception as e:
        log(f"Error in display controller: {e}")
