#!/usr/bin/env python3
"""
VolumioRFID.py — Truly Dumb Player

Only receives and executes play/stop commands.
Sends NOTHING back. The watchdog handles all notifications.
"""

import socket
import json
import requests
import time
import logging

UDP_PORT    = 5005
VOLUMIO_API = 'http://127.0.0.1:3000/api/v1'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('/var/log/volumiorfid.log')]
)
log = logging.info

def play_uri(uri, service="tidal"):
    try:
        # Clear current queue
        requests.post(f'{VOLUMIO_API}/replaceAndPlay', json={"uri": "", "service": ""})
        time.sleep(0.5)
        
        # Play new track
        requests.post(f'{VOLUMIO_API}/replaceAndPlay', json={"uri": uri, "service": service})
        log(f"Started playback: {uri}")
    except Exception as e:
        log(f"Play error: {e}")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('', UDP_PORT))
log(f"VolumioRFID (dumb player) started on port {UDP_PORT}...")

while True:
    try:
        data, addr = sock.recvfrom(1024)
        payload = json.loads(data.decode().strip())

        if payload.get('command') == 'stop':
            log("Stop command received - clearing queue")
            requests.post(f'{VOLUMIO_API}/replaceAndPlay', json={"uri": "", "service": ""})

        elif 'uri' in payload:
            uri = payload['uri']
            service = payload.get('service', 'tidal')
            log(f"Playing {uri}")
            play_uri(uri, service)

    except Exception as e:
        log(f"Error: {e}")
        time.sleep(1)
