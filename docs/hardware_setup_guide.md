# UAS Systems Lab Hardware Setup Guide

## Purpose

This document covers the physical bench integration process for the UAS Systems Lab hardware stack:

- Pixhawk 6C Mini flight controller (ArduPilot)
- Holybro M10 GPS module
- SiK Telemetry Radio V3 (air + ground units)
- QGroundControl on Windows

---

# Hardware Overview

```text
[Wall Charger]
      |
[Pixhawk 6C Mini]
   |         |
[GPS1]    [TELEM1]
   |         |
[M10 GPS] [SiK Air Radio]
               |
           (wireless)
               |
          [SiK Ground Radio]
               |
           [Windows PC / COM4]
               |
          [QGroundControl]
```

---

# Phase 1 — Pixhawk Initial Connection

## 1. Install QGroundControl

Download and install QGroundControl from the official site.

Expected Result:
- QGC launches with no vehicle connected
- No errors on startup

---

## 2. Connect Pixhawk via USB-C

Connect the Pixhawk 6C Mini to the Windows PC using a USB-C cable.

Expected Result:
- Windows recognizes device as **USB Serial Device on COM3**
- QGC detects vehicle automatically
- QGC Summary screen displays vehicle status

---

## 3. Confirm Firmware

In QGC, navigate to **Vehicle Setup → Summary**.

Verify:
- Firmware: ArduPilot
- Version: 1.16.0 (or current installed version)
- All sensor indicators visible

Reference Screenshot: `pixhawk_qgc_connected_firmware_confirmed.png`

---

# Phase 2 — Sensor Calibration

## 4. Calibrate Accelerometer

In QGC, navigate to **Vehicle Setup → Sensors → Accelerometer**.

Follow the on-screen orientation prompts (6 positions).

Expected Result:
- Accelerometer calibration indicator turns green

---

## 5. Calibrate Gyroscope

In QGC, navigate to **Vehicle Setup → Sensors → Gyroscope**.

Hold the vehicle still during calibration.

Expected Result:
- Gyroscope calibration indicator turns green

---

## 6. Calibrate Compass (Initial — Internal Only)

In QGC, navigate to **Vehicle Setup → Sensors → Compass**.

Rotate the vehicle through all axes as prompted.

Expected Result:
- Compass calibration indicator turns green

---

## 7. Connect M10 GPS and Recalibrate Compass

Connect the Holybro M10 GPS module to the **GPS1** port on the Pixhawk.

Rerun compass calibration with the external GPS compass included:

- Set the external compass as **primary**
- Complete full rotation sequence

Expected Result:
- All sensor indicators green
- External compass set as primary in compass settings

Reference Screenshot: `sensors_calibration_complete.png`

---

# Phase 3 — GPS Lock Verification

## 8. Confirm 3D GPS Lock

With the M10 GPS connected, allow time for satellite acquisition.

Verify in QGC:
- GPS fix type: **3D Lock**
- Satellite count: 20+ recommended (27 confirmed in lab setup)
- HDOP: below 1.0 (0.5 confirmed in lab setup)

Expected Result:
- QGC GPS indicator shows 3D lock
- Vehicle position visible on map

Reference Screenshot: `gps_3d_lock_27_satellites.png`

---

# Phase 4 — SiK Radio Wireless Link

## 9. Connect SiK Air Radio to Pixhawk

Connect the SiK Telemetry Radio V3 air unit to the **TELEM1** port on the Pixhawk using the included cable.

---

## 10. Connect SiK Ground Radio to PC

Connect the SiK ground unit to the Windows PC via USB-C adapter.

Expected Result:
- Windows assigns ground radio a COM port (COM4 confirmed in lab setup)

---

## 11. Resolve COM Port Driver Issues (if needed)

If the ground radio is not recognized:

1. Open **Device Manager**
2. Locate the unrecognized device
3. Update or install the Silicon Labs CP210x USB driver

Expected Result:
- Ground radio appears as a COM port in Device Manager
- Air and ground units pair and link automatically (indicated by solid green LEDs on both radios)

---

## 12. Confirm Wireless Telemetry Link in QGC

Disconnect the USB-C tether from the Pixhawk. Switch Pixhawk power to a wall charger.

In QGC, verify:
- Vehicle reconnects automatically over SiK radio
- Live RSSI visible in QGC telemetry toolbar
- **"Ready To Fly"** status displayed
- Vehicle position visible on map with no USB connection

Expected Result:
- Full QGC functionality over wireless SiK link only
- Pixhawk operating on wall power

Reference Screenshot: `sik_radio_wireless_link_ready_to_fly.png`

---

# COM Port Reference

| Device              | COM Port | Interface     |
|---------------------|----------|---------------|
| Pixhawk 6C Mini     | COM3     | USB-C direct  |
| SiK Ground Radio    | COM4     | USB-C adapter |

---

# Lessons Learned

- Compass calibration should be rerun after adding the external GPS — the external compass must be explicitly set as primary
- SiK radios pair automatically once both are powered and COM port drivers are installed; no manual pairing required
- Switching from USB power to wall charger before final wireless validation confirms the radio link is fully independent
- HDOP below 1.0 is the target threshold for reliable GPS-assisted flight modes
