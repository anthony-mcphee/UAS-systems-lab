# Startup Workflow

## Purpose

This document standardizes startup and operational procedures for the UAS Systems Lab environment.

---

# Startup Sequence

## 1. Open Ubuntu WSL

Launch Ubuntu terminal environment.

---

## 2. Activate Python Virtual Environment

```bash
source ~/venv-ardupilot/bin/activate
```

Expected Result:
- `(venv-ardupilot)` appears in terminal prompt.

---

## 3. Navigate to ArduPilot Directory

```bash
cd ~/ardupilot
```

---

## 4. Start ArduPilot SITL

```bash
python Tools/autotest/sim_vehicle.py -v ArduCopter --console --map
```

Expected Result:
- ArduCopter simulation launches
- Map window appears
- MAVProxy console opens
- Vehicle initializes

---

## 5. Verify MAVProxy Output Ports

Within MAVProxy console:

```bash
output add 127.0.0.1:14550
output add 127.0.0.1:14551
```

Purpose:
- Port 14550 used by QGroundControl
- Port 14551 used by Python MAVLink scripts

---

## 6. Launch QGroundControl

Start QGroundControl AppImage.

Expected Result:
- Vehicle automatically connects
- HUD displays telemetry
- Vehicle location visible on map

---

## 7. Verify MAVLink Telemetry

Confirm:
- heartbeat present
- GPS lock established
- telemetry values updating
- no connection errors

---

## 8. Start Python MAVLink Script

Example:

```python
from pymavlink import mavutil

master = mavutil.mavlink_connection("udpin:127.0.0.1:14551")
master.wait_heartbeat()

print("Heartbeat received")
```

Expected Result:
- Script connects successfully
- Heartbeat received

---

## 9. Execute Mission

Example operations:
- arm vehicle
- takeoff
- waypoint navigation
- return-to-launch

---

## 10. Shutdown Procedure

Close in order:
1. Python scripts
2. QGroundControl
3. MAVProxy
4. SITL terminal

---

# Common Failure Points

## Connection Refused

Possible Causes:
- SITL not fully initialized
- MAVProxy outputs not configured
- incorrect UDP port
- startup sequence incorrect

---

## No QGroundControl Connection

Verify:
- MAVProxy outputs active
- UDP port 14550 configured
- firewall not blocking traffic

---

## Python Script Cannot Connect

Verify:
- correct UDP port
- telemetry output exists
- script waiting for heartbeat

---

# Lessons Learned

- Startup order matters
- MAVLink routing must be verified
- UDP telemetry flow is critical
- Logs and terminal output provide troubleshooting clues
