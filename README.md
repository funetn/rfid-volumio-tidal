# RFID Whole-House Audio System
### Physical album browsing for Volumio + Tidal — powered by Raspberry Pi

> *"Pay it and Play it Forward"* 🎵

![System Overview](images/setup.png)

A maker project that brings the tactile experience of browsing and playing physical records back to streaming music. Place a custom RFID-tagged mini album card on a stand — music starts. Remove it — music stops. One special "Magic 8-Ball" card picks random albums and chains them continuously, one after another, all day long.

Built on **Volumio** (with Tidal integration) and two Raspberry Pi nodes communicating over UDP. No fragile community plugins. No complex middleware. Just reliable, direct Tidal → Volumio → whole-house audio.

Note: I am not a software engineer or programmer - just a guy using multiple Ai resources to make something I never could have on my own and pushing back on AI when I didn't like the responses and landed here finally.

---

## ✨ Features

- **Physical album browsing** — Unlimited "album" cards with RFID tags, browsed like a record store crate (I made mine with cd-mailers, custom sized artwork and RFID tag placed on the back).
- **Instant play** — place an album card on the stand, music starts within 1 second
- **Instant stop** — remove the card, music stops immediately via hardware interrupt
- **Magic 8-Ball mode** — one special tag picks random albums continuously, avoiding repeats for 60 days
- **Whole-house audio** — Volumio RPI via DAC output drives a 6-zone amplifier covering your zones (or amp of your choice)
- **Hardware IRQ** — light sensor state changes handled by GPIO interrupt, not polling — low CPU, no race conditions
- **Socket.IO watchdog** — keeps Volumio connection alive through multi-hour listening sessions
- **PeppyMeters VU display** — animated VU meters on a remote Waveshare 11.9" monitor on the PeppyMeters RPI (driven by VolumioRFID) GROUP casting feature

---

## 🎯 The Concept

Inspired by the [Phoniebox](https://github.com/MiczFlor/RPi-Jukebox-RFID) project but re-architected for stability. Rather than relying on community-maintained Mopidy/Tidal plugins, this system uses **Volumio's native commercial Tidal integration** directly — goal is to have fewer dependencies, fewer breaking changes and more reliable long-term operation.

**Trade-off:** Requires a [Volumio Prima](https://volumio.com/en/get-started/) subscription for Tidal support. If you're already paying for Tidal and want rock-solid streaming, this is a worthwhile project to consider checking out.

---

## 🖥️ Architecture

Two Raspberry Pi nodes communicate over UDP on your local network:

```
┌─────────────────────────────────┐         UDP :5005        ┌─────────────────────────────────┐
│     PeppyMeters (Reader)        │ ───────────────────────► │    VolumioRFID (Receiver)        │
│     192.168.1.206               │                          │    192.168.1.204                 │
│                                 │ ◄─────────────────────── │                                  │
│  • USB HID RFID Reader          │     Socket.IO pushState  │  • Volumio OS + Tidal plugin     │
│  • Light sensor (GPIO17 IRQ)    │                          │  • Monoprice 6-zone amp          │
│  • LED indicator (GPIO14)       │                          │  • REST API + Socket.IO server   │
│  • PeppyMeters VU display       │                          │  • Wired Ethernet                │
│  • rfidreader.py                │                          │  • VolumioRFID.py                │
└─────────────────────────────────┘                          └─────────────────────────────────┘
```

**Why two Pis?**
- Clean separation of concerns — physical interface vs audio playback
- Volumio runs best dedicated; PeppyMeters + GPIO adds negligible load to the reader Pi
- Independent failure domains — a GPIO issue doesn't affect audio playback
- Wired Ethernet on the audio-critical Volumio node; WiFi fine for the reader node
- PeppyMeters RPI also allows for remote PeppyMeters away from the main VolumioRFIP RPI via the Peppy-Basic-Meter plugin enabled and playing from VolumioRFID --> PeppyMeters RPI via Volumio's Group feature

---

## 🛠️ Hardware

### Reader Node (PeppyMeters Pi)
| Component | Details |
|-----------|---------|
| Raspberry Pi 4B | Any Pi with GPIO header and USB host port — running Volumio OS V4.x |
| USB HID RFID Reader | Waveshare-compatible, presents as keyboard (ARM CM0) |
| Light Sensor Module | KY-018 or similar; installed **inside** the RFID reader enclosure |
| LED Indicator | Any LED on GPIO14 via resistor |
| Album Cards | CD mailer sized cards with RFID tags on reverse |

### Receiver Node (VolumioRFID Pi)
| Component | Details |
|-----------|---------|
| Raspberry Pi 4B | Running Volumio OS V4.x |
| Volumio Prima subscription | Required for Tidal integration |
| Amplifier | Monoprice 6-zone whole-house amp (or any amp/receiver) |
| Network | **Wired Ethernet strongly recommended** for audio reliability |

### GPIO Pin Reference (Reader Node)
| BCM Pin | Direction | Component | Behaviour |
|---------|-----------|-----------|-----------|
| GPIO 14 | OUTPUT | LED indicator | HIGH = ON; LOW = OFF |
| GPIO 17 | INPUT | Light sensor module | LOW = dark (album present/play); HIGH = light (album removed/stop) |

---

## 💡 Light Sensor Integration — Inside the RFID Reader

A key hardware innovation in this build: the light sensor module is installed **inside** the USB RFID reader enclosure rather than as a separate external component.

**Why this works perfectly:**
- The album card must be centered over the RFID coil for a reliable tag read
- Centering the card also maximally blocks the light sensor
- The two functions are physically coupled — you can't trigger one without the other
- One clean enclosure, one USB cable and three thin sensor wires
- A light source needs to be facing opposite of the light sensor but with enough room for the mini-album to break the light beam to the light sensor

**How to open the fused enclosure:**
1. Start on the opposite side from the USB jack — this edge has the most flex
2. Work the two corners apart first using a utility knife with shallow passes
3. Slide the blade along the seam toward the USB jack with multiple shallow passes
4. Do not force it — multiple passes beats single hard pressure
5. The bond is strong but will release with patience

**Inside the enclosure:**
- The RFID copper coil is in the center on a foam pad — avoid this area
- Opposite of the USB jack, outside the looping PCB provides the perfect space for the light sensor placement
- Drill 2 holes in the top cover: sensor eye, trim pot access based on module placement and positon of sendor eye and trim pot
- Knotch out side of case to allow 3 jumper wires to exit the case and remove any additional internal case plastic as needed
- If the sensor isn't facing perpendicular of the PCB carefully bend the sensor leads 90° so the sensor faces up through the top cover
- Secure with double-sided foam tape
- Route 3 wires (VCC, GND, Signal) out of the case to your PeppyMeters RPI (5V, GND and GPIO17)

![RFID Reader with integrated light sensor](images/rfid_reader_sensor.png)

---

## 📁 Repository Structure

```
rfid-volumio-tidal/
├── README.md                    ← You are here
├── rfidreader.py                ← Reader node service (PeppyMeters Pi)
├── VolumioRFID.py               ← Receiver node service (VolumioRFID Pi)
├── gpio_cleanup.sh              ← Pre-start GPIO cleanup (called by systemd)
├── rfid_lookup_local.csv        ← Sample tag-to-URI lookup table
├── systemd/
│   ├── rfidreader.service       ← systemd unit for reader node
│   └── VolumioRFID.service      ← systemd unit for receiver node
├── docs/
│   └── System_Design_Rev2.0.pdf ← Full technical reference document
└── images/
    ├── setup.png                ← Full system photo
    ├── rfid_reader_sensor.png   ← Sensor integration photo
    ├── album_cards.png          ← Custom album cards
    └── stand.png                ← Album stand with light sensor
```

---

## ⚙️ Installation

### Prerequisites
- Two Raspberry Pi boards (any model with GPIO)
- Volumio OS V4.x on the receiver Pi with Tidal configured and authenticated
- Volumio OS V4.x on the reader Pi
- Python 3 on both nodes

### Reader Node (PeppyMeters Pi)

**1. Install Python dependencies:**
```bash
pip3 install python-socketio evdev RPi.GPIO gpiozero
```

**2. Create the data directory:**
```bash
sudo mkdir -p /data/rfidreader
sudo chown volumio:volumio /data/rfidreader
```

**3. Copy files:**
```bash
sudo cp rfidreader.py /data/rfidreader/
sudo cp rfid_lookup_local.csv /data/rfidreader/
sudo cp gpio_cleanup.sh /data/rfidreader/
sudo chmod +x /data/rfidreader/gpio_cleanup.sh
```

**4. Edit configuration in rfidreader.py:**
```python
MAIN_PI_IP  = '192.168.1.204'   # IP of your VolumioRFID Pi
MAGIC_TAG   = "289378361"        # Tag ID of your Magic 8-Ball card
EXCLUDE_DAYS = 60                # Days before Magic 8-Ball repeats an album
```

**5. Install systemd service:**
```bash
sudo cp systemd/rfidreader.service /lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rfidreader.service
sudo systemctl start rfidreader.service
```

### Receiver Node (VolumioRFID Pi)

**1. Install Python dependencies:**
```bash
pip3 install requests
```

**2. Create directory and copy files:**
```bash
mkdir -p /home/VolumioRFID
cp VolumioRFID.py /home/VolumioRFID/
```

**3. Install systemd service:**
```bash
sudo cp systemd/VolumioRFID.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable VolumioRFID.service
sudo systemctl start VolumioRFID.service
```

---

## 📋 CSV Lookup Table

The `rfid_lookup_local.csv` file maps RFID tag IDs to Tidal album URIs or local stored music:

```csv
tag,location,service,artist,album
239478361,tidal://album/4084137,tidal,Magic 8-Ball,Magic 8-Ball
4215180854,tidal://album/82704482,tidal,Def Leppard,Pyromania
1366328633,tidal://album/4623872,tidal,Paul McCartney & Wings,Band on the Run
561721881,mnt/USB/Music/Jimmy Page & Robert Plant/No Quarter,mpd,Jimmy Page & Robert Plant,No Quarter
```

| Column | Required | Description |
|--------|----------|-------------|
| tag | Yes | Raw decimal tag ID as emitted by USB HID reader |
| location | Yes | Tidal URI (tidal://album/XXXXXXX) |
| service | No | Volumio service name — defaults to 'tidal' |
| artist | No | Human readable — appears in logs only |
| album | No | Human readable — appears in logs only |

Note: local music can also be played - see example above table (Jimmy Page & Robert Plant)

**Finding your Tidal URI:**
1. Open the Tidal app and find your album
2. Share the album and copy the link: `https://tidal.com/album/4084137`
3. Remove the "u" at the end (usually)
4. Convert to Volumio format: `tidal://album/4084137`

**⚠️ Important:** Tidal occasionally changes album IDs when albums are remastered or re-released. If Magic 8-Ball silently stops chaining, check the log for the last queued URI and validate it against the Tidal app.

---

## 🎱 Magic 8-Ball Feature

One reserved tag ID activates continuous random album play mode:

- Picks a random album from your entire library
- Avoids albums played in the last 60 days (configurable via `EXCLUDE_DAYS`)
- Automatically chains the next random album when one finishes
- Continues indefinitely until the Magic 8-Ball card is removed
- LED flashes 5 times to confirm activation (vs 2 times for normal tags) (LED is connected via GPIO14 or a relay as your needs require)

Set your Magic 8-Ball tag ID in `rfidreader.py`:
```python
MAGIC_TAG = "289378361"   # Replace with your actual tag ID
```

---

## 🔌 How It Works — End to End

### Normal Album Play
1. Album card placed on stand → light sensor goes LOW → **hardware IRQ fires instantly**
2. Main thread wakes, reads RFID tag via USB HID reader (3 second timeout)
3. Tag ID looked up in CSV → Tidal URI resolved
4. UDP datagram sent to VolumioRFID: `{"uri": "tidal://album/XXXX", "service": "tidal"}`
5. VolumioRFID calls Volumio's `replaceAndPlay` API → music starts
6. LED flashes 2 times to confirm
7. Album card removed → IRQ fires → stop UDP sent → music stops instantly

### Magic 8-Ball Continuous Play
1. Magic 8-Ball card placed → tag read → `magic_active = True`
2. Random album selected (avoiding recent 60 days) → UDP sent → music starts
3. LED flashes 5 times
4. When album finishes → Volumio emits `pushState: status=stop` via Socket.IO
5. `on_push_state` handler picks next random album → UDP sent → music continues
6. Repeats indefinitely until Magic 8-Ball card is removed

---

## 🔧 Adding a New RFID Tag

1. Run the reader service and tail the log:
```bash
tail -f /data/rfidreader/rfidreader.log
```

2. Scan your new tag — look for:
```
Unknown tag: XXXXXXXXX. No action taken.
```

3. Find your Tidal album URI (see CSV section above)

4. Add a row to the CSV:
```
XXXXXXXXX,tidal://album/4084137,tidal,Artist Name,Album Name
```

5. Restart the service to reload the CSV:
```bash
sudo systemctl restart rfidreader.service
```

6. Scan the tag again — confirm the log shows:
```
Playing: Artist Name — Album Name
```

---

## 🩺 Troubleshooting

### Diagnostic Log Signatures

| Symptom | Log Signature | Likely Cause |
|---------|---------------|--------------|
| Magic chain stops, no next album | `pushState stop` received but no UDP sent | Stale Tidal URI — validate CSV against Tidal app |
| Magic chain stops silently | Log silent after album queued | Socket.IO dropped — watchdog reconnects within 30s |
| Album doesn't start | UDP sent, replaceAndPlay success, no `status=play` | Tidal API hiccup — remove and replace card |
| Music won't stop on removal | No IRQ HIGH logged | Light sensor wiring or gpiozero issue |

### Useful Commands

**Reader Node (PeppyMeters):**
```bash
sudo systemctl status rfidreader.service
sudo systemctl restart rfidreader.service
tail -f /data/rfidreader/rfidreader.log
sudo journalctl -u rfidreader.service -f
```

**Receiver Node (VolumioRFID):**
```bash
sudo systemctl status VolumioRFID.service
sudo systemctl restart VolumioRFID.service
sudo journalctl -u VolumioRFID.service -f
```

### Socket.IO Watchdog
The reader maintains a 30-second watchdog on the Socket.IO connection to Volumio. If the connection drops silently (which would break Magic 8-Ball chaining), the watchdog reconnects automatically. You'll see this in the log:
```
Socket.IO watchdog: connection lost — reconnecting...
Socket.IO watchdog: reconnected successfully.
```

---

## 🏗️ Key Design Decisions

### Hardware IRQ vs Polling
GPIO17 (light sensor) is monitored via `gpiozero` hardware interrupts (`when_activated` / `when_deactivated`) rather than software polling. Benefits:
- Near-zero CPU overhead — the Pi does nothing until the sensor changes state
- Microsecond response time vs up to 1 second polling lag
- No race conditions between the polling loop and Socket.IO event handling

### Why `read_loop()` as the Main Loop Backbone
Early versions used `stand_event.wait()` as the main loop, which blocked the main thread and caused silent Socket.IO disconnections during long albums. The current architecture restores `read_loop()` as the continuous main loop backbone — keeping Socket.IO's background thread well-serviced — while the IRQ callback simply sets a flag that `read_loop()` checks.

### Why Volumio + Tidal over Phoniebox + Mopidy
Phoniebox/Mopidy/Tidal relies on community-maintained plugins that can break with Tidal API changes. Volumio has a commercial relationship with Tidal — the integration is a core product feature with financial incentive to maintain it. Requires a Volumio Prima subscription but delivers significantly more reliable long-term operation.

---

## 📦 Python Dependencies

| Module | Node | Purpose |
|--------|------|---------|
| evdev | Reader | Raw keypress events from USB HID RFID device |
| gpiozero | Reader | Hardware IRQ via DigitalInputDevice |
| RPi.GPIO | Reader | LED control on GPIO14; startup cleanup |
| python-socketio | Reader | Socket.IO client for Volumio pushState events |
| threading | Reader | threading.Event for IRQ → main thread signalling |
| socket | Both | UDP datagram send/receive |
| struct | Reader | Byte-swap USB tag ID to PN532 little-endian |
| fcntl | Reader | Non-blocking RFID device file descriptor |
| csv | Reader | Tag lookup table parsing |
| json | Both | UDP payload encoding/decoding |
| requests | Receiver | Volumio REST API HTTP calls |
| logging | Both | Timestamped log output |
| random | Reader | Magic 8-Ball random URI selection |
| datetime | Reader | EXCLUDE_DAYS cutoff calculation |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

Free to use, modify, and distribute. If you build something cool with this, consider sharing it back with the maker community! 🎸



---

## 🙏 Inspiration & Credits

- [Phoniebox](https://github.com/MiczFlor/RPi-Jukebox-RFID) — the original inspiration for RFID-triggered music on Raspberry Pi
- [Volumio](https://volumio.com) — the audio platform powering playback
- [PeppyMeters](https://github.com/project-owner/PeppyMeters) — VU meter display
- The maker community — for sharing knowledge so others can build on it

---
## Disclamers
- I make no guarantees about the completeness, reliability, or accuracy of the information. Any action you take based on this content is strictly at your own risk.
- Code examples are provided as-is, without warranty of any kind. Always test in a safe environment before running on production systems.
- Not responsible for any damage to you or hardware.  Use your best judgement - I did, you can too.  Be smart.
---

*Built by [@funetn](https://github.com/funetn) — a bunch of "what-if's we do this" turned into a fully working whole-house audio system.* 🎵
