# Telemetry Configuration

## Purpose

This document defines the telemetry routing configuration used within the UAS Systems Lab environment.

The environment uses:
- ArduPilot SITL
- MAVProxy
- QGroundControl
- Python MAVLink scripts

Telemetry is distributed locally over UDP using MAVProxy outputs.

---

# Telemetry Architecture

ArduPilot SITL
        ↓
    MAVProxy
   ↙        ↘
UDP 14550   UDP 14551
   ↓             ↓
QGroundControl   Python MAVLink Scripts

---

# MAVProxy Output Configuration

## QGroundControl Output

```bash
output add 127.0.0.1:14550
```

Purpose:
- Sends MAVLink telemetry to QGroundControl
- Supports HUD, map, mission planning, and operator visualization

---

## Python MAVLink Output

```bash
output add 127.0.0.1:14551
```

Purpose:
- Sends MAVLink telemetry to Python scripts
- Used for automation, telemetry parsing, and mission scripting

---

# Network Details

## Loopback Address

```text
127.0.0.1
```

Purpose:
- Refers to the local machine
- Allows inter-process communication without external networking

---

# UDP Transport

UDP is used for telemetry distribution because:
- low latency
- lightweight transport
- real-time telemetry updates
- acceptable packet loss characteristics for streaming telemetry

---

# Validation Steps

Verify MAVProxy outputs:

```bash
output list
```

Expected outputs:
- 127.0.0.1:14550
- 127.0.0.1:14551

---

# Lessons Learned

- MAVProxy acts as telemetry middleware/router
- Multiple clients can consume telemetry simultaneously
- Proper port management is critical for distributed systems communication
- Telemetry flow can be validated through heartbeat monitoring and connection testing
