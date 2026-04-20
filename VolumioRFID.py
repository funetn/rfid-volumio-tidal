import socket
import json
import requests
import time

UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('', UDP_PORT))

VOLUMIO_API = 'http://localhost:3000/api/v1'

print(f"UDP listener started on port {UDP_PORT}...")

while True:
    try:
        data, addr = sock.recvfrom(1024)
        payload = json.loads(data.decode().strip())

        print(f"Received from {addr}: {payload}")

        if payload.get('command') == 'stop':
            print("Stopping playback and clearing queue")
            requests.post(f'{VOLUMIO_API}/replaceAndPlay', json={"uri": "", "service": ""})
            continue

        if 'uri' in payload:
            uri = payload['uri']
            service = payload.get('service', 'tidal')

            print(f"Playing {uri} ({service})")
            # Clear first to avoid race
            requests.post(f'{VOLUMIO_API}/replaceAndPlay', json={"uri": "", "service": ""})
            time.sleep(0.3)

            r = requests.post(f'{VOLUMIO_API}/replaceAndPlay', json={"uri": uri, "service": service})
            print(f"replaceAndPlay response: {r.text}")

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(1)
