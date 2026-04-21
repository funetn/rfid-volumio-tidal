# Waveshare 11.9" DSI Display — PeppyMeters Setup Guide
## Volumio 4.x + PeppyMeter Basic on Raspberry Pi 4B

> **Recovery reference** — If your SD card fails, follow this guide exactly to restore
> the display to working condition. Take an SD card image backup immediately after
> completing this setup!

---

## Overview

This guide documents the exact steps required to get the Waveshare 11.9" DSI display
working with PeppyMeter Basic on a Volumio 4.x (Bookworm-based) Raspberry Pi 4B.
The setup is non-trivial because Volumio manages its own display pipeline and fights
against standard DSI configuration approaches.

**What makes this tricky:**
- Volumio injects its own HDMI video settings into the boot process
- The framebuffer defaults to HDMI even when DSI is connected
- PeppyMeter Basic requires X11 which requires the Touch Display plugin
- PeppyMeter Basic's video driver defaults to `dummy` — must be changed to `x11`
- The 1480x320 meter templates live in a different location than the plugin expects

---

## Hardware

| Component | Details |
|-----------|---------|
| Raspberry Pi 4B | GPIO header mounted directly onto Waveshare board via POGO pins |
| Waveshare 11.9" DSI | Connected via 15-pin FPC ribbon cable to Pi DSI port |
| DSI Port | Outer DSI port on Pi (away from USB ports, toward board edge) |
| Ribbon orientation | Gold contacts facing DOWN toward Waveshare PCB on both ends |
| Power/I2C | Provided via GPIO POGO pin connection — no separate cable needed |

**Important:** The POGO pin GPIO connection provides both 5V power AND I2C
communication (SDA/SCL on GPIO2/GPIO3). No separate 4-pin I2C cable is required
when the Pi is mounted directly on the Waveshare board.

---

## Step 1 — Verify Hardware is Working (Clean Pi OS Test)

Before configuring Volumio, validate the hardware on a clean Raspberry Pi OS image:

1. Flash Raspberry Pi OS Bookworm (32-bit) to a spare SD card
2. Boot and enable I2C via `sudo raspi-config` → Interface Options → I2C → Enable
3. Run `sudo i2cdetect -y 1` — you should see device at address `0x45`
4. If `0x45` appears the hardware connection is good ✅
5. Add to `/boot/firmware/config.txt`:
```
dtoverlay=vc4-kms-dsi-waveshare-panel,11_9_inch,rotation=90
```
6. Reboot — display should initialize and show content

> **Note:** Landscape rotation on clean Pi OS GUI requires `xrandr --output DSI-1 --rotate left`
> but for Volumio/PeppyMeters the rotation is handled differently (see Step 3).

---

## Step 2 — Volumio Boot Configuration

Volumio manages `/boot/cmdline.txt` and `/boot/userconfig.txt`. Edit these carefully.

### /boot/userconfig.txt

```
# Waveshare 11.9" DSI - Volumio/PeppyMeters
dtoverlay=vc4-kms-dsi-waveshare-panel,11_9_inch,rotation=90
max_framebuffers=2
max_framebuffer_height=1480
max_framebuffer_width=1480
#### Touch Display rotation setting below: do not alter ####
# (Leave the lines below blank or commented out with #)
```

**Critical notes:**
- `rotation=90` in the overlay is correct for landscape orientation
- Do NOT add HDMI timing lines (`hdmi_group`, `hdmi_mode`, `hdmi_timings`) — these
  fight the DSI configuration
- Do NOT add `display_auto_detect=1` — this overrides manual overlay settings
- Do NOT add `disable_fw_kms_setup=1` — this interferes with rotation

### /boot/cmdline.txt

Add the following to the **END** of the existing Volumio cmdline line (keep all
existing Volumio parameters, just append these):

```
video=HDMI-A-1:d video=DSI-1:1480x320@60,rotate=90
```

- `video=HDMI-A-1:d` — disables HDMI output
- `video=DSI-1:1480x320@60,rotate=90` — forces DSI as active display in landscape

**The winning combination:**
- `userconfig.txt`: `rotation=90`
- `cmdline.txt`: `video=DSI-1:1480x320@60,rotate=90`

> **Warning:** Volumio may regenerate cmdline.txt on system updates. Check after
> every Volumio update and re-add the video parameters if they disappear.

---

## Step 3 — Verify DSI is Active After Reboot

After rebooting with the above config, verify DSI is the active display:

```bash
sudo kmsprint
```

Expected output — HDMI disconnected, DSI active:
```
Connector 0 (33) HDMI-A-1 (disconnected)
Connector 1 (42) HDMI-A-2 (disconnected)
Connector 2 (47) DSI-1 (connected)
  Crtc 2 (91) 320x1480@60.24
    FB 722 320x1480 RG16
```

Also verify framebuffer resolution:
```bash
sudo fbset -s
```

Expected:
```
mode "320x1480"
    geometry 320 1480 320 1480 16
```

If HDMI still shows as connected or active, double-check cmdline.txt has both
`video=HDMI-A-1:d` and `video=DSI-1:1480x320@60,rotate=90` appended correctly.

---

## Step 4 — Install Touch Display Plugin (Required for X11)

PeppyMeter Basic uses pygame which requires X11. Volumio's Touch Display plugin
installs and manages the X server. **It must be installed even if you don't use
touch functionality.**

1. Go to Volumio UI → Plugins → User Interface → Touch Display
2. Install the plugin
3. Enable the plugin (required for initial X11 setup)
4. Reboot

Verify X11/Xorg is now installed:
```bash
which Xorg
```
Expected: `/usr/bin/Xorg`

Verify X server is running:
```bash
ps aux | grep -i Xorg
```

You should see something like:
```
/usr/lib/xorg/Xorg :0 -nocursor -auth /tmp/serverauth.XXXXXXX
```

> **Note:** Touch Display can be disabled after installation if not needed for
> touch input. Xorg remains installed and available for PeppyMeters to use.

---

## Step 5 — Install PeppyMeter Basic Plugin

1. Go to Volumio UI → Plugins → User Interface → PeppyMeter Basic
2. Install the plugin
3. Enable the plugin

### Upload 1480x320 Meter Templates

The 1480x320 meter templates must be uploaded via the plugin UI:

1. Go to PeppyMeter Basic plugin settings in Volumio UI
2. Use the zip file upload feature to install 1480x320 meter packs
3. Templates are stored at: `/data/INTERNAL/PeppyMeterBasic/Templates/`

Verify templates are present:
```bash
ls /data/INTERNAL/PeppyMeterBasic/Templates/ | grep 1480
```

Expected output includes entries like:
```
1480x320-Gelo-A
1480x320-Gelo-B
1480x320-Gelo-C
1480x320-Gelo-D
1480x320-Gelo-E
1480x320-Gelo5-BASIC_521
```

### Configure Screen Size

In PeppyMeter Basic plugin settings:
- Set screen size to `1480x320`
- Select your preferred meter template

---

## Step 6 — Fix PeppyMeter Basic Video Driver (Critical!)

This is the final and most important fix. PeppyMeter Basic defaults to
`video.driver = dummy` which renders to nothing. It must be changed to `x11`.

```bash
sudo nano /data/plugins/user_interface/peppymeterbasic/config.txt.tmpl
```

Find the `[sdl.env]` section and change:
```
video.driver = dummy
```
To:
```
video.driver = x11
```

The full `[sdl.env]` section should look like:
```
[sdl.env]
framebuffer.device = /dev/fb0
mouse.device = /dev/input/event0
mouse.driver = TSLIB
mouse.enabled = False
video.driver = x11
video.display = :0
double.buffer = True
no.frame = True
```

> **Warning:** The Volumio PeppyMeter Basic plugin may overwrite config.txt when
> settings are changed via the UI. If meters disappear after changing plugin settings,
> re-check `video.driver` — it may have been reset to `dummy`.

---

## Step 7 — Configure PeppyMeter Basic systemd Service

The PeppyMeter Basic service needs environment variables to find the X11 display:

```bash
sudo nano /etc/systemd/system/peppymeterbasic.service
```

Ensure the `[Service]` section includes:
```
Environment=XDG_RUNTIME_DIR=/run/user/1000
Environment=SDL_VIDEODRIVER=x11
```

Full service file:
```
[Unit]
Description=peppymeterbasic Daemon
After=syslog.target

[Service]
Type=simple
WorkingDirectory=/data/plugins/user_interface/peppymeterbasic
ExecStart=/data/plugins/user_interface/peppymeterbasic/startpeppymeterbasic.sh
Restart=no
SyslogIdentifier=volumio
User=volumio
Group=volumio
TimeoutSec=1
Environment=XDG_RUNTIME_DIR=/run/user/1000

[Install]
WantedBy=multi-user.target
```

Apply and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart peppymeterbasic
sudo systemctl status peppymeterbasic
```

---

## Step 8 — Verify Everything is Working

```bash
# Check DSI display is active
sudo kmsprint

# Check framebuffer resolution
sudo fbset -s

# Check X11 is running
ps aux | grep Xorg

# Check PeppyMeters service
sudo systemctl status peppymeterbasic

# Check PeppyMeters log
sudo journalctl -u peppymeterbasic -n 20 --no-pager
```

VU meters should now be visible on the Waveshare 11.9" DSI display in landscape
orientation. 🎉

---

## Troubleshooting

### Flashing green light on monitor, no display
- DSI panel is powered but not receiving signal
- Check ribbon cable is fully seated on both ends (gold contacts facing DOWN)
- Verify `dtoverlay=vc4-kms-dsi-waveshare-panel,11_9_inch,rotation=90` is in userconfig.txt
- Run `sudo i2cdetect -y 1` — should show `0x45`

### Display shows content but in portrait mode
- Verify `video=DSI-1:1480x320@60,rotate=90` is in cmdline.txt
- Verify `rotation=90` (not 270) in userconfig.txt overlay line
- Both values must match for correct landscape orientation

### HDMI still active instead of DSI
- Verify `video=HDMI-A-1:d` is in cmdline.txt
- Remove any HDMI timing lines from userconfig.txt
- Check `sudo kmsprint` — HDMI-A-1 should show `(disconnected)`

### PeppyMeters crashes with `fbcon not available`
- SDL is trying to use legacy framebuffer console driver
- Remove `SDL_VIDEODRIVER=fbcon` from service environment
- Use `SDL_VIDEODRIVER=x11` instead (or remove entirely)

### PeppyMeters crashes with `kmsdrm not available`
- SDL KMS/DRM driver not available in this pygame build
- Use `video.driver = x11` in config.txt instead
- Requires X11/Xorg to be running (Touch Display plugin installed)

### PeppyMeters runs but renders to nothing (offscreen)
- `video.driver = dummy` in config.txt — change to `x11`
- This is the default and must be manually changed after every plugin reinstall

### NoOptionError: No option 'meter.type' in section '1480x320-XXXX'
- 1480x320 meter templates not installed
- Upload meter zip files via PeppyMeter Basic plugin UI
- Verify templates exist at `/data/INTERNAL/PeppyMeterBasic/Templates/`

### Meters disappear after changing PeppyMeter Basic settings in UI
- Plugin UI resets `video.driver` to `dummy` when saving settings
- Re-edit config.txt and change back to `video.driver = x11`
- Restart service: `sudo systemctl restart peppymeterbasic`

---

## Key File Locations

| File | Purpose |
|------|---------|
| `/boot/userconfig.txt` | DSI overlay and framebuffer config |
| `/boot/cmdline.txt` | Kernel video parameters — disable HDMI, enable DSI |
| `/data/plugins/user_interface/peppymeterbasic/BasicPeppyMeter/config.txt` | PeppyMeters config — **video.driver must be x11** |
| `/etc/systemd/system/peppymeterbasic.service` | PeppyMeters systemd service |
| `/etc/X11/xorg.conf.d/95-touch_display-plugin.conf` | X11 display config (managed by Touch Display plugin) |
| `/data/INTERNAL/PeppyMeterBasic/Templates/` | Meter template storage location |

---

## Possible Gotchas
Keep a backup of that modified /etc/systemd/system/peppymeterbasic.service file. Whenever the PeppyMeter plugin gets an update, it will likely overwrite your Environment edits and the config.txt.tmpl changes, which will "break" the meters until you re-apply those specific lines.

---

## Useful Commands Reference

```bash
# Display status
sudo kmsprint                              # Show all display connectors and modes
sudo fbset -s                             # Show framebuffer resolution
cat /sys/class/drm/card1-DSI-1/status    # DSI connection status
sudo dmesg | grep -i "dsi\|waveshare"    # DSI kernel messages

# PeppyMeters
sudo systemctl status peppymeterbasic     # Service status
sudo systemctl restart peppymeterbasic    # Restart service
sudo journalctl -u peppymeterbasic -f     # Live log
cat /data/plugins/user_interface/peppymeterbasic/BasicPeppyMeter/config.txt

# X11
ps aux | grep Xorg                        # Verify X server running
which Xorg                                # Verify Xorg installed

# Touch Display
sudo systemctl status touch_display       # Touch display service status
```

---

## Important Notes for Recovery

1. **SD Card Image** — Take a full SD card image immediately after setup is working.
   This is your fastest recovery path.

2. **video.driver = x11** — This is the most commonly lost setting. Every time
   PeppyMeter Basic plugin settings are saved via the Volumio UI, check this value.

3. **cmdline.txt video parameters** — Volumio may regenerate cmdline.txt on updates.
   Keep a note of the exact parameters to re-add.

4. **Touch Display plugin** — Must remain installed (can be disabled) for Xorg to
   be available. If uninstalled, Xorg is removed and PeppyMeters stops working.

5. **Meter templates** — Stored in `/data/INTERNAL/` which survives plugin reinstalls.
   Only lost if data partition is wiped.

---

*Document generated April 2026 — Waveshare 11.9" DSI + Volumio 4.x + PeppyMeter Basic*
*Part of the RFID Whole-House Audio System project by @funetn*
