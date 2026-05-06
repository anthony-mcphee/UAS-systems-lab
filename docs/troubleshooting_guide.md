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

# Troubleshooting Philosophy

Use a structured fault-isolation method:

```text
Symptom → Possible Causes → Isolation Steps → Findings → Corrective Action → Verification
```

This mirrors aircraft maintenance troubleshooting but applies it to software-enabled UAS systems.
