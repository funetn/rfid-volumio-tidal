# RFID Whole-House Audio System: Volumio + Tidal

A distributed microservices architecture for RFID-controlled Tidal music playback across multiple zones using Volumio. Play albums by scanning NFC/RFID tags, or use an iPhone shortcut for Magic 8-Ball continuous playlist shuffling.  3 RPI's used - 1) RFID Tag reader/controller; 2) Volumio V4.x; 3) Volumio V4.x w/PeppyMeterBasic & Touch Display plugins installed on.

**Version:** 3.1 | **Status:** Production Stable

---

## 🎵 Overview

This project transforms physical RFID tags into a music controller for Tidal streaming. Scan a tag to instantly play an album across your entire home audio system. Tap an iPhone shortcut to enter Magic 8-Ball mode and shuffle through a randomized playlist. Built on three independent Raspberry Pis communicating via UDP, with automatic display management.

### Key Features

- **RFID Tag Scanning:** NFC/RFID reader with PN532 HAT instantly triggers album playback
- **Tidal Integration:** Direct album URI support via Volumio's Tidal plugin
- **Magic 8-Ball Mode:** Continuous shuffle through your library with random album selection
- **iPhone Shortcut:** Remote trigger for Magic 8-Ball mode from your phone
- **Multi-Zone Audio:** Coordinated playback across all Volumio zones simultaneously
- **Smart Display Control:** Automatic screen on/off with grace periods and daily schedules
- **Light Deduplication:** Prevents duplicate rapid plays and command stuttering
- **Play History Tracking:** Maintains 60-day exclusion history for Magic 8-Ball fairness
- **PeppyMeterBasic:** Music signal data transportation is handled via VolmuioRFID RPI's Group/Cast feature.

---

## 🏗️ Architecture

### Three Microservices on Separate Raspberry Pis

```
┌─────────────────────────────────────────────────────────────┐
│                      Home Network (192.168.1.x)             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐   ┌──────────────────┐                │
│  │  RFID Reader Pi  │   │  VolumioRFID Pi  │  Volumio API   │
│  │  (192.168.1.223) │   │  (192.168.1.204) │  :3000         │
│  │                  │   │                  │                │
│  │  • rfidreader.py │   │ • VolumioRFID.py │  ┌────────┐    │
│  │  • CSV lookup    │   │ • watchdog.py    │  │ Tidal  │    │
│  │  • HTTP server   │   │                  │  │Plugin  │    │
│  │    :8080         │   │                  │  └────────┘    │
│  │  • UDP 5005/5006 │   │  UDP 5005        │                │
│  └──────────────────┘   │  (receive)       │                │
│    UDP 5005                                │                │
│    UDP 5006 ◄─────────────────────────────►│  UDP 5007      │
│             (callbacks)                    │                │
│                                            └────────────────┘
│                                                    ▲
│                                                    │ UDP 5007
│                                                    │
│                                         ┌──────────────────┐
│                                         │ PeppyMeters Pi   │
│                                         │(192.168.1.206)   │
│                                         │                  │
│                                         │• display_ctrl.py │
│                                         │• systemd timers  │
│                                         │• DSI backlight   │
│                                         └──────────────────┘
│                                                             
└─────────────────────────────────────────────────────────────┘
```

### Service Communication Flow

| Service | Port | Protocol | Role |
|---------|------|----------|------|
| **rfidreader** | 5005 (send) | UDP | RFID reader → VolumioRFID commands |
| | 5006 (listen) | UDP | Callback listener (watchdog stops) |
| | 8080 (HTTP) | HTTP | iPhone Magic 8-Ball endpoint |
| **VolumioRFID** | 5005 (listen) | UDP | Play/stop commands from RFID reader |
| | 3000 (REST) | HTTP | Volumio API calls |
| **volumio_watchdog** | 5006 (send) | UDP | Playback state callbacks to RFID reader |
| | 3000 (REST) | HTTP | Volumio state polling |
| **display_controller** | 5007 (listen) | UDP | Display on/off commands |

---

## 📋 Requirements

### Hardware

- **3× Raspberry Pi 4/3B+** (or compatible SBC running Raspberry Pi OS Bookworm)
- **1× Waveshare PN532 NFC/RFID HAT** (SPI interface, 40-pin GPIO)
- **1× LED & resistor** (GPIO 14, for visual feedback)
- **1× Waveshare 11.9" DSI touch/LCD display** (for PeppyMeters, optional but recommended)
- **Network:** Wired Ethernet or stable 2.4GHz WiFi (all Pis)
- **Audio:** Volumio Premium subsscription level with multi-zone setup with Tidal subscription

### Software

- **OS:** Raspberry Pi OS Bookworm (Lite or Desktop)
- **Python:** 3.10+
- **Volumio:** 3.x with Tidal plugin installed
- **systemd:** For service management (included in RPi OS)

### Python Dependencies

```
pn532           # RFID reader SPI communication
RPi.GPIO        # GPIO control (LED feedback)
requests        # HTTP API calls to Volumio
python-socketio # (Optional) for Socket.IO listeners
```

### Network Requirements

- All three Pis must be on the same subnet
- Static IP addresses recommended (or DHCP reservations)
- UDP ports 5005–5007 must be open between Pis
- HTTP port 8080 (rfidreader) accessible from iPhone for Magic 8-Ball

---

## 🚀 Installation

### 1. Prepare Raspberry Pi OS

On each Pi:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-dev git
sudo apt install -y librpi-gpio-python python3-rpi.gpio
```

### 2. Install Python Dependencies

```bash
pip install requests
pip install pn532  # for rfidreader only
```

### 3. Deploy rfidreader Pi (192.168.1.223)

```bash
# Create directory structure
sudo mkdir -p /data/rfidreader
sudo chown pi:pi /data/rfidreader

# Copy service file
sudo cp rfidreader.py /data/rfidreader/
sudo cp rfid_lookup_local.csv /data/rfidreader/

# Create systemd service
sudo tee /etc/systemd/system/rfidreader.service > /dev/null <<EOF
[Unit]
Description=RFID Reader Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/data/rfidreader
ExecStart=/usr/bin/python3 /data/rfidreader/rfidreader.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable rfidreader
sudo systemctl start rfidreader
```

**GPIO Configuration for PN532 HAT:**
- CS (chip select): GPIO 4
- MOSI: GPIO 10
- MISO: GPIO 9
- CLK: GPIO 11
- RST (reset): GPIO 20
- LED indicator: GPIO 14

### 4. Deploy VolumioRFID Pi (192.168.1.204)

```bash
# Create directory structure
mkdir -p /home/volumio/VolumioRFID

# Copy service files
cp VolumioRFID.py /home/volumio/VolumioRFID/
cp volumio_watchdog.py /home/volumio/VolumioRFID/

# Create systemd services
sudo tee /etc/systemd/system/VolumioRFID.service > /dev/null <<EOF
[Unit]
Description=Volumio RFID Player Service
After=network.target

[Service]
Type=simple
User=volumio
WorkingDirectory=/home/volumio/VolumioRFID
ExecStart=/usr/bin/python3 /home/volumio/VolumioRFID/VolumioRFID.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/volumio_watchdog.service > /dev/null <<EOF
[Unit]
Description=Volumio Playback Watchdog
After=network.target

[Service]
Type=simple
User=volumio
WorkingDirectory=/home/volumio/VolumioRFID
ExecStart=/usr/bin/python3 /home/volumio/VolumioRFID/volumio_watchdog.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable VolumioRFID volumio_watchdog
sudo systemctl start VolumioRFID volumio_watchdog
```

### 5. Deploy display_controller Pi (192.168.1.206)

```bash
# Create directory structure
sudo mkdir -p /data/display_controller
sudo chown pi:pi /data/display_controller

# Copy service
sudo cp display_controller.py /data/display_controller/

# Create systemd service
sudo tee /etc/systemd/system/display_controller.service > /dev/null <<EOF
[Unit]
Description=Display Controller Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/data/display_controller
ExecStart=/usr/bin/python3 /data/display_controller/display_controller.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create display on/off oneshot services
sudo tee /etc/systemd/system/display-on.service > /dev/null <<EOF
[Unit]
Description=Turn Display On

[Service]
Type=oneshot
ExecStart=/usr/bin/vcgencmd display_power 1
EOF

sudo tee /etc/systemd/system/display-off.service > /dev/null <<EOF
[Unit]
Description=Turn Display Off

[Service]
Type=oneshot
ExecStart=/usr/bin/vcgencmd display_power 0
EOF

# Create daily timers (7am on, 11:30pm off)
sudo tee /etc/systemd/system/display-on.timer > /dev/null <<EOF
[Unit]
Description=Daily Display On Timer

[Timer]
OnCalendar=*-*-* 07:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo tee /etc/systemd/system/display-off.timer > /dev/null <<EOF
[Unit]
Description=Daily Display Off Timer

[Timer]
OnCalendar=*-*-* 23:30:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable display_controller display-on.timer display-off.timer
sudo systemctl start display_controller display-on.timer display-off.timer
```

---

## 🏷️ Setting Up RFID Tags

### Adding a New Tag

1. **Scan the Unknown Tag**

   With rfidreader running:
   ```bash
   tail -f /data/rfidreader/rfidreader.log
   ```

   Look for:
   ```
   Unknown tag: 289378361
   ```

2. **Find the Tidal URI**

   In the Tidal app:
   - Navigate to the album
   - Share → Copy Link
   - Extract the ID: `https://tidal.com/album/4084137` → `tidal://album/4084137`

3. **Update the CSV**

   Append to `/data/rfidreader/rfid_lookup_local.csv`:
   ```csv
   289378361,tidal://album/4084137,tidal,Artist Name,Album Name
   ```

4. **Reload the Service**

   ```bash
   sudo systemctl restart rfidreader
   ```

5. **Verify**

   Scan the tag again and confirm the log shows:
   ```
   Playing normal tag: Artist Name — Album Name
   ```

### CSV Format

```csv
tag,location,service,artist,album
289378361,tidal://album/4084137,tidal,Pink Floyd,The Dark Side of the Moon
289378362,tidal://album/9876543,tidal,David Bowie,Ziggy Stardust
561421881,mnt/USB/Music/Jimmy Page & Robert Plant/No Quarter,mpd,Jimmy Page & Robert Plant,No Quarter
```

**Notes:**
- **tag:** RFID reader output (scan to get this)
- **location:** Tidal URI or any Volumio-compatible URI
- **service:** `tidal`, `spotify`, `local`, etc.
- **artist/album:** Human-readable metadata (for logging)

### Magic 8-Ball Tag

Set the MAGIC_TAG constant in `rfidreader.py`:

```python
MAGIC_TAG = "289378361"
```

Scanning this tag triggers continuous random album playback. The system excludes recently-played albums from the last 60 days.

---

## 📱 iPhone Magic 8-Ball Shortcut

To enable remote triggering from iPhone:

1. **Install Shortcut App** on your iPhone

2. **Create a New Shortcut** with one action:
   ```
   GET http://192.168.1.223:8080/magic
   ```

3. **Add to Home Screen** (optional, for quick access)

4. **Usage:**
   - Tap the shortcut to start Magic 8-Ball
   - Returns JSON: `{"status": "ok"}`

---

## 🎮 Usage

### Normal Play (Single Album)

1. Scan tag with rfidreader running
2. Album plays immediately across all Volumio zones
3. LED flashes 2× for visual confirmation
4. Display turns on (if enabled)
5. Album ends → display blanks after 30s grace period

### Magic 8-Ball (Continuous Shuffle)

1. **Via RFID Tag:** Scan the MAGIC_TAG
2. **Via iPhone:** Tap the Magic 8-Ball shortcut
3. Random album loads from exclusion-filtered library
4. After album ends, next random album auto-plays
5. LED flashes 5× on initial trigger indicating Magic 8-Ball mode
6. Remove tag or use iPhone shortcut again to stop

### Manual Control

```bash
# Turn display on
sudo systemctl start display-on.service

# Turn display off
sudo systemctl start display-off.service

# Check current status
rfidreader RPI - sudo systemctl status rfidreader
VolumioRFID RPI - sudo systemctl status VolumioRFID
VolumioRFID - sudo systemctl status volumio_watchdog
PeppyMeters RPI -sudo systemctl status display_controller
PeppyMeters RPI - echo $(date) $(cat /sys/class/backlight/10-0045/device/backlight/10-0045/bl_power) $(printf "(0=on, 1=off)")
```

---

## 🔧 Configuration

All configuration is hardcoded in the service files. Customize via environment variables or edit the Python files directly:

### rfidreader.py

```python
VOLUMIO_PI_IP      = '192.168.1.204'  # Change if using different IP
UDP_SEND_PORT      = 5005             # Play/stop commands
UDP_LISTEN_PORT    = 5006             # Callbacks from watchdog
HTTP_PORT          = 8080             # iPhone Magic 8-Ball
LED_GPIO           = 14               # GPIO pin for LED
MAGIC_TAG          = "289378361"      # Change to your tag ID
REMOVAL_TIMEOUT    = 3.0              # Seconds before tag removal confirmed
EXCLUDE_DAYS       = 60               # Magic 8-Ball history exclusion
MAX_HISTORY        = 2000             # Max entries in magic_history.json
```

### volumio_watchdog.py

```python
RFID_PI_IP         = '192.168.1.223'  # RFID reader Pi
PEPPY_IP           = '192.168.1.206'  # PeppyMeters Pi
VOLUMIO_URL        = "http://localhost:3000/api/v1/getState"
# Poll interval: hardcoded to 3 seconds (line: time.sleep(3))
```

### display_controller.py

```python
GRACE_PERIOD_SEC   = 30    # Seconds before display blanks
# Listen port: hardcoded to 5007
```

---

## 📊 System Communication

### Normal Tag Play Flow

| Step | Service | Action | Message |
|------|---------|--------|---------|
| 1 | rfidreader | Tag detected | Display ON request → PeppyMeters |
| 2 | rfidreader | CSV lookup | Play URI → VolumioRFID (UDP 5005) |
| 3 | VolumioRFID | API call | `replaceAndPlay` → Volumio |
| 4 | Volumio | Loading | Album queues and plays |
| 5 | volumio_watchdog | Poll | Detects `status=play` → logs |
| 6 | Volumio | Playing | Audio streams to zones |
| 7 | Volumio | End-of-track | Status changes to `stop` |
| 8 | volumio_watchdog | Poll | Detects `status=stop` → callback |
| 9 | rfidreader | Callback | Receives "stopped" → schedules OFF |
| 10 | display_controller | Timer | 30s grace period → turns display off |

### Magic 8-Ball Flow

| Step | Service | Action |
|------|---------|--------|
| 1 | User | Scans MAGIC_TAG or taps iPhone shortcut |
| 2 | rfidreader | `trigger_magic_8ball()` → random URI |
| 3 | rfidreader | UDP play → VolumioRFID |
| 4 | rfidreader | Record URI in `magic_history.json` |
| 5 | rfidreader | LED flashes 5× |
| 6 | VolumioRFID | `replaceAndPlay` → Volumio |
| 7 | Volumio | Album plays |
| 8 | volumio_watchdog | End-of-album → "stopped" callback |
| 9 | rfidreader | Detects `magic_active=True` → next random |
| 10 | *Loop* | Repeat steps 3–9 indefinitely |

---

## 📝 Logs

Each service writes timestamped logs for debugging:

```bash
# RFID Reader
tail -f /data/rfidreader/rfidreader.log

# VolumioRFID
tail -f /var/log/volumiorfid.log

# Watchdog
tail -f /var/log/volumio_watchdog.log

# Display Controller
tail -f /var/log/display_controller.log
```

### Log Example

```
2026-04-15 19:23:01 - Received from ('192.168.1.223', 12345): {'command': 'display_on'}
2026-04-15 19:23:01 - ✅ Display ON executed successfully
2026-04-15 19:24:32 - Received UDP: {'uri': 'tidal://album/4084137', 'service': 'tidal'}
2026-04-15 19:24:32 - Started playback: tidal://album/4084137
2026-04-15 19:34:15 - Received stopped callback
2026-04-15 19:34:45 - Grace period expired - turning display OFF
```

---

## ⚙️ Troubleshooting

### Magic 8-Ball Stops Chaining

**Problem:** Music stops after first album, doesn't auto-play next.

**Cause:** `magic_active=False` when 'stopped' callback arrives (tag was removed during play).

**Fix:**
- Replace tag on reader, or
- Use iPhone shortcut to re-trigger

### Music Stop Playing

**Problem:** Music stops randomly, between tracks or albums, doesn't auto-play next.

**Cause:** `Possible Volumio/Tidal API hiccup.

**Fix:**
- Replace tag on reader, or
- Use iPhone shortcut to re-trigger (this will pick a new random album)

### Display Won't Turn On

**Problem:** Display stays blank even after tag scan.

**Cause:** `display_on` command not reaching display_controller.

**Check:**
```bash
# Verify watchdog sees play state
tail -f /var/log/volumio_watchdog.log

# Check display controller is listening
sudo systemctl status display_controller

# Manual test
echo '{"command": "display_on"}' | nc -u -w0 192.168.1.206 5007
```

### Same Album Plays Twice Rapidly

**Problem:** One tag scan results in the same album playing twice.

**Cause:** PN532 detects/loses tag at boundary; deduplication window (2s) too short.

**Fix:**
- Increase deduplication window in `rfidreader.py`:
  ```python
  if uri and uri == last_sent_uri and (now - last_sent_time) < 5.0:  # 5s window
      return
  ```
- Reposition tag on reader for cleaner detection

### No Music on Tag Placement

**Problem:** Tag scans but no playback.  Also same for Magic 8-Ball if lights flashes 5x but no music plays.

**Cause:** Stale Tidal URI in CSV (album ID changed on Tidal).

**Fix:**
1. Open Tidal app and find the album
2. Share → copy current link
3. Compare ID against CSV entry (remove trailing "u")
4. Update CSV if different:
   ```bash
   nano /data/rfidreader/rfid_lookup_local.csv
   sudo systemctl restart rfidreader
   ```

### Watchdog Sends 'Stopped' Immediately

**Problem:** Album starts but 'stopped' callback arrives within 1–2 seconds.

**Cause:** Volumio briefly stops during album loading; watchdog catches it.

**Fix:** This is usually self-correcting. The 4s poll interval + natural debounce prevents spurious triggers. If persistent, check Volumio logs:

```bash
# On VolumioRFID Pi
docker logs -f volumio
```

### magic_history.json Permission Denied

**Problem:** Service logs show file lock error.

**Cause:** File owned by root instead of pi:pi (e.g., after manual restore).

**Fix:**
```bash
sudo chown pi:pi /data/rfidreader/magic_history.json
sudo systemctl restart rfidreader
```

---

## 🔌 Network & Connectivity

### Static IP Setup (Recommended)

Edit `/etc/dhcpcd.conf` on each Pi:

```bash
interface wlan0
static ip_address=192.168.1.223/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 8.8.4.4
```

Then restart networking:
```bash
sudo systemctl restart dhcpcd
```

### Testing UDP Connectivity

From rfidreader Pi to VolumioRFID Pi:

```bash
# Send a test packet
echo '{"command": "test"}' | nc -u -w0 192.168.1.204 5005

# Listen for incoming packets
nc -u -l 5006
```

### iPhone Magic 8-Ball Remote Access

The shortcut works **only on home WiFi**. For remote access, set up Tailscale VPN:

1. Install Tailscale on all Pis: `sudo apt install tailscale`
2. Get Tailscale IPs: `tailscale ip -4`
3. Update shortcut to use Tailscale IP instead of home IP

---

## 🛠️ Maintenance

### Reload CSV Without Restarting Service

The CSV is loaded once at startup. To add new tags, restart the service:

```bash
sudo systemctl restart rfidreader
```

Possible Future enhancement: Add inotify file watcher for hot-reload.

### Validate Tidal URIs Periodically

Albums on Tidal occasionally change IDs (remastering, rights changes):

```bash
# Check CSV against Tidal app
# If album link differs, update CSV and restart
grep "ARTIST_NAME" /data/rfidreader/rfid_lookup_local.csv

```
This is a manual process and just easiest done at time of playback failure.

### Clean Magic 8-Ball History

If the 60-day exclusion list grows too large:

```bash
# Manually trim magic_history.json
# Keep only recent 1000 entries, sort by date
jq 'sort_by(.timestamp) | .[-1000:]' /data/rfidreader/magic_history.json > /tmp/trimmed.json
sudo mv /tmp/trimmed.json /data/rfidreader/magic_history.json
sudo chown pi:pi /data/rfidreader/magic_history.json
```

---

## ⚠️ Known Limitations

- **UDP is fire-and-forget:** Lost packets on the local LAN silently drop commands. Rare but theoretically possible.
- **Watchdog poll interval (3s):** A very short album could theoretically end and restart within the poll window. Unlikely in practice.
- **magic_active lost on restart:** Restarting rfidreader mid-Magic 8-Ball resets state. Use iPhone shortcut to re-trigger.
- **CSV loaded once at startup:** Adding tags requires service restart.
- **Tidal URI stability:** Album IDs change occasionally. Periodic CSV validation against Tidal app recommended.
- **WiFi on rfidreader & PeppyMeters:** Recommended to use 2.4GHz for stability. Powerline adapters available as fallback.
- **iPhone shortcut WiFi-only:** Works on home network only.

---

## 📁 File Structure

```
rfidreader/ (192.168.1.223)
├── rfidreader.py
├── rfid_lookup_local.csv
├── magic_history.json
└── rfidreader.log

VolumioRFID/ (192.168.1.204)
├── VolumioRFID.py
├── volumio_watchdog.py
├── volumiorfid.log
└── volumio_watchdog.log

PeppyMeters/ (192.168.1.206)
├── display_controller.py
├── display_controller.log
└── systemd unit files for display-on/off timers
```

---

## 🔐 Security Considerations

This system is designed for **private home networks only**. Hardcoded IPs and no authentication mean it should not be exposed to untrusted networks.

If internet access is needed:
- Use Tailscale VPN for remote access
- Do not port-forward UDP 5005–5007 to the internet
- Restrict HTTP port 8080 to home network

---

## 📚 Dependencies Reference

| Module | Service | Purpose |
|--------|---------|---------|
| `pn532` | rfidreader | PN532 HAT SPI communication and tag reading |
| `RPi.GPIO` | rfidreader | LED control on GPIO 14 |
| `fcntl` | rfidreader | File locking for magic_history.json |
| `http.server` | rfidreader | iPhone Magic 8-Ball HTTP endpoint |
| `threading` | rfidreader | Background threads for UDP listener & HTTP server |
| `socket` | All | UDP datagram send/receive |
| `requests` | VolumioRFID, watchdog | Volumio REST API HTTP calls |
| `json` | All | UDP payload encoding/decoding |
| `csv` | rfidreader | Tag lookup table parsing |
| `subprocess` | display_controller | Calling systemd services |
| `logging` | All | Timestamped structured logging |
| `random` | rfidreader | Magic 8-Ball random URI selection |
| `datetime` | rfidreader | EXCLUDE_DAYS cutoff calculation |

---

## 🚀 Areas for Possible Future Enhancements

- [ ] Hot-reload CSV on file change (inotify watcher)
- [ ] Persistent magic_active state (store in JSON on shutdown)
- [ ] Display brightness control via PWM
- [ ] Spotify/Apple Music URI support
- [ ] Zone-specific playback control
- [ ] Web dashboard for tag management
- [ ] TCP fallback for UDP reliability
- [ ] Mobile app for tag scanning and Magic 8-Ball trigger

---

## 📜 License

This project is provided as-is for personal use. Pay it and play it forward.

---

## 🤝 Contributing

Found a bug? Have an improvement? Open an issue or submit a pull request.

---

## 📖 Documentation

See the complete system design document ([VolumioTidal_RFID_System_Design_Rev_3_0.pdf](./VolumioTidal_RFID_System_Design_Rev_3_0.pdf)) for detailed architecture, electrical schematics, and advanced troubleshooting.

---

**Last Updated:** April 2026 | **Revision:** 3.0  
Repository: [github.com/funetn/rfid-volumio-tidal](https://github.com/funetn/rfid-volumio-tidal)
