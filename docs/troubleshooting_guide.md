# Troubleshooting Guide

## Purpose

This document captures common faults, likely causes, isolation steps, and corrective actions for the UAS Systems Lab.

---

# Fault 1: QGroundControl Does Not Connect

## Symptoms

- QGroundControl opens but does not detect vehicle
- No HUD telemetry
- No vehicle location on map

## Possible Causes

- SITL not running
- MAVProxy not fully initialized
- UDP output to port 14550 not configured
- QGroundControl started before telemetry stream was available

## Isolation Steps

1. Verify SITL is running.
2. Verify MAVProxy console is active.
3. In MAVProxy, check output routing:

```bash
output
```

4. Add QGroundControl output if missing:

```bash
output add 127.0.0.1:14550
```

5. Restart QGroundControl.

## Corrective Action

Re-establish MAVProxy telemetry output to UDP port 14550 and restart QGroundControl.

---

# Fault 2: Python Script Does Not Receive Heartbeat

## Symptoms

- Script hangs at `wait_heartbeat()`
- No heartbeat received
- Connection refused messages

## Possible Causes

- UDP output to port 14551 not configured
- Wrong port used in script
- SITL not initialized
- MAVProxy not routing telemetry

## Isolation Steps

1. Verify Python script uses:

```python
master = mavutil.mavlink_connection("udpin:127.0.0.1:14551")
```

2. In MAVProxy, add output:

```bash
output add 127.0.0.1:14551
```

3. Confirm MAVProxy output list:

```bash
output
```

4. Re-run Python script.

## Corrective Action

Configure MAVProxy to forward MAVLink telemetry to UDP port 14551.

---

# Fault 3: Connection Refused During Startup

## Symptoms

- Terminal shows repeated connection refused messages
- MAVProxy or script attempts reconnect
- No link established

## Possible Causes

- Component started before SITL finished initializing
- Wrong port
- No listener available
- MAVProxy output not configured

## Isolation Steps

1. Allow SITL to fully initialize.
2. Confirm MAVProxy is active.
3. Verify outputs.
4. Restart the affected component after telemetry is available.

## Corrective Action

Follow standardized startup order and verify telemetry outputs before launching dependent tools.

---

# Fault 4: Port Conflict

## Symptoms

- Service cannot bind to port
- Telemetry does not flow correctly
- Unexpected process already using port

## Isolation Steps

Check active UDP/TCP ports:

```bash
ss -tulnp | grep 14550
ss -tulnp | grep 14551
```

Identify conflicting process and stop it if required.

## Corrective Action

Free the required port or configure a different telemetry output port.

---

# Fault 5: Unknown Telemetry Issue

## General Isolation Flow

1. Confirm SITL is running.
2. Confirm MAVProxy is running.
3. Confirm MAVProxy output ports.
4. Confirm QGroundControl or script uses correct port.
5. Confirm traffic flow with:

```bash
tcpdump -i any port 14550
tcpdump -i any port 14551
```

6. Review terminal output for errors.
7. Restart components in proper sequence.

---

# Fault 6: SiK Ground Radio Not Recognized on Windows

## Symptoms

- Windows does not assign a COM port to the SiK ground radio
- Device Manager shows unknown or unrecognized device
- QGroundControl cannot connect over radio link

## Possible Causes

- Silicon Labs CP210x USB driver not installed on Windows

## Isolation Steps

1. Open **Device Manager** on Windows.
2. Look for an unknown device under **Other Devices** or **Ports (COM & LPT)**.
3. Check if a COM port is assigned — if not, driver is missing.

## Corrective Action

1. Download and install the **Silicon Labs CP210x Universal Windows Driver** from the Silicon Labs website.
2. Reconnect the SiK ground radio.
3. Verify a COM port appears in Device Manager.
4. Air and ground units will pair automatically once the driver is installed — no manual pairing required.

---

# Fault 7: SiK Radio Link Not Establishing

## Symptoms

- Both radios powered but QGC shows no vehicle
- LEDs on radios not solid green

## Possible Causes

- Radios not matched (different firmware or NET ID configuration)
- Air unit not powered (Pixhawk not powered)
- COM port not selected in QGC

## Isolation Steps

1. Confirm the Pixhawk is powered (wall charger or USB).
2. Confirm the ground radio COM port is correct in QGC connection settings.
3. Check LED status on both radios — solid green indicates linked.
4. If LEDs are blinking rapidly, radios are searching for a link — verify NET IDs match.

## Corrective Action

If NET IDs are mismatched, reconfigure both radios using SiK Radio firmware tools to use the same NET ID. Factory-matched pairs from the same kit link automatically without reconfiguration.

---

# Troubleshooting Philosophy

Use a structured fault-isolation method:

```text
Symptom → Possible Causes → Isolation Steps → Findings → Corrective Action → Verification
```

This mirrors aircraft maintenance troubleshooting but applies it to software-enabled UAS systems.
