# Lab Environment

## Host System

- Device: Microsoft Surface Pro
- Operating System: Windows with Ubuntu WSL
- Ubuntu Version: Ubuntu 24.04 LTS

---

## Physical Hardware

### Flight Controller

- **Pixhawk 6C Mini**
- Firmware: ArduPilot 1.16.0
- Connection: USB-C → Windows COM3

### GPS Module

- **Holybro M10 GPS**
- Port: GPS1 on Pixhawk
- External compass set as primary
- Confirmed: 3D lock, 27 satellites, 0.5 HDOP

### Telemetry Radios

- **SiK Telemetry Radio V3** (air + ground units)
- Air unit: TELEM1 port on Pixhawk
- Ground unit: USB-C adapter → Windows COM4
- Link: auto-paired, wireless MAVLink to QGroundControl

### COM Port Reference

| Device           | COM Port | Interface     |
|------------------|----------|---------------|
| Pixhawk 6C Mini  | COM3     | USB-C direct  |
| SiK Ground Radio | COM4     | USB-C adapter |

---

## Simulation Stack (SITL)

### Python Environment

Virtual environment used for ArduPilot and MAVLink experimentation:

```bash
cd ~/drone-control
source venv/bin/activate
```

### ArduPilot SITL

Used for simulated quadcopter flight operations and MAVLink telemetry generation.

### MAVProxy

Used as MAVLink relay, command interface, and telemetry router.

### QGroundControl

Used as primary ground control station interface.

### Python MAVLink Scripts

Used for telemetry monitoring and future automation scripting.

### Telemetry Ports (SITL)

| Service | Port | Protocol |
|---|---|---|
| QGroundControl | 14550 | UDP |
| Python MAVLink Script | 14551 | UDP |

---

## Current Capabilities

**Hardware:**
- Pixhawk 6C Mini bench integration with full sensor calibration
- M10 GPS 3D lock with external compass as primary
- SiK radio wireless telemetry link — QGC Ready To Fly over COM4

**Simulation (SITL):**
- SITL startup and MAVProxy routing
- QGroundControl connection
- Autonomous waypoint missions
- MAVLink telemetry monitoring
- Linux troubleshooting practice

---

## Known Issues Encountered

- Connection refused during startup sequencing (SITL)
- MAVProxy output configuration confusion
- Python package dependency conflicts
- Port binding/order-of-operations troubleshooting
- COM port driver missing for SiK ground radio on Windows (Silicon Labs CP210x)

## Lessons Learned

- Startup order matters for SITL stack
- MAVLink telemetry routing must be verified
- UDP listeners require correct bind targets
- Linux logs and networking tools are critical for troubleshooting
- SiK radios pair automatically once drivers are installed — no manual pairing required
- Compass calibration must be rerun after adding external GPS; external must be set as primary
