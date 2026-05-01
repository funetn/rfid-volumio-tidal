#!/usr/bin/env python3
"""
volumio_watchdog.py — Monitors Volumio playback state
Sends "stopped" callback to rfidreader AND controls display on PeppyMeters.
"""

import requests
import socket
import json
import time
import logging

# ========================= CONFIG =========================
RFID_PI_IP     = '192.168.1.223'
CALLBACK_PORT  = 5006
PEPPY_IP       = '192.168.1.206'
DISPLAY_PORT   = 5007
VOLUMIO_URL    = "http://localhost:3000/api/v1/getState"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('/var/log/volumio_watchdog.log')]
)
log = logging.info

# ========================= UDP HELPERS =========================
def send_stopped_to_rfidreader():
    try:
        payload = {"command": "stopped"}
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(json.dumps(payload).encode(), (RFID_PI_IP, CALLBACK_PORT))
        log("✅ Sent 'stopped' callback to rfidreader")
    except Exception as e:
        log(f"Failed to send stopped callback to rfidreader: {e}")

def send_to_peppy(command):
    try:
        payload = {"command": command}
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(json.dumps(payload).encode(), (PEPPY_IP, DISPLAY_PORT))
        log(f"Sent to PeppyMeters: {command}")
    except Exception as e:
        log(f"Failed to send to PeppyMeters: {e}")

# ========================= MAIN =========================
def main():
    log("Volumio Watchdog started - monitoring playback state...")

    last_status = None
    last_was_playing = False

    while True:
        try:
            state = requests.get(VOLUMIO_URL, timeout=5).json()
            current_status = state.get('status', 'unknown')

            # Only log and act when status actually changes
            if current_status != last_status:
                log(f"Volumio status changed: {current_status}")
                
                if current_status == "play":
                    send_to_peppy("display_on")
                elif current_status in ('stop', 'idle'):
                    send_stopped_to_rfidreader()
                    send_to_peppy("display_off")        # Start 30s grace period on PeppyMeters

                last_status = current_status

            # Update playing state for natural end detection
            last_was_playing = (current_status == 'play')

        except Exception as e:
            if "Connection" in str(e) or "Timeout" in str(e):
                log("Warning: Could not connect to Volumio API")
            else:
                log(f"Watchdog error: {e}")

        time.sleep(3)   # Poll every 3 seconds

if __name__ == "__main__":
    main()
