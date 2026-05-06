# Telemetry Architecture

## Purpose

This document explains telemetry flow and communication architecture within the UAS Systems Lab.

---

# Core Components

## ArduPilot SITL

Software-In-The-Loop simulation environment.

Purpose:
- Simulates vehicle flight controller
- Generates MAVLink telemetry
- Simulates sensors and vehicle state

Acts As:
- simulated autopilot
- flight controller
- telemetry source

---

## MAVProxy

Command-line MAVLink relay and control utility.

Purpose:
- routes telemetry
- forwards MAVLink packets
- allows command/control interaction
- distributes telemetry to multiple endpoints

Acts As:
- telemetry router
- command interface
- MAVLink relay

---

## QGroundControl

Ground control station application.

Purpose:
- visualizes telemetry
- displays vehicle state
- uploads missions
- monitors flight operations

Acts As:
- operator interface
- mission planning station
- telemetry display

---

## Python MAVLink Scripts

Custom automation and telemetry scripts.

Purpose:
- monitor telemetry
- automate actions
- test MAVLink communication
- build autonomous behaviors

Acts As:
- automation layer
- telemetry consumer
- future autonomy interface

---

# Telemetry Flow

```text
ArduPilot SITL
    |
    | MAVLink packets
    v
MAVProxy
    |
    +------> QGroundControl (UDP 14550)
    |
    +------> Python Scripts (UDP 14551)
```

---

# MAVLink Overview

MAVLink is a lightweight messaging protocol used by unmanned systems.

Functions:
- telemetry transmission
- command/control
- GPS data
- attitude information
- mission updates
- vehicle health status

Examples:
- heartbeat
- GPS coordinates
- altitude
- battery status
- flight mode

---

# UDP Port Usage

| Port | Purpose |
|---|---|
| 14550 | QGroundControl telemetry |
| 14551 | Python MAVLink scripts |

---

# Key Networking Concepts

## Localhost

`127.0.0.1`

Represents local machine communication.

Purpose:
- allows software on same computer to communicate internally.

---

## UDP

User Datagram Protocol.

Characteristics:
- lightweight
- low latency
- connectionless
- common in telemetry systems

Advantages:
- fast telemetry updates
- minimal overhead

Disadvantages:
- packets may be lost
- no delivery guarantee

---

# Troubleshooting Concepts

## Verify Listening Ports

```bash
ss -tulnp
```

Purpose:
- identify active listeners
- verify services bound to expected ports

---

## Verify Packet Traffic

```bash
tcpdump -i any port 14550
```

Purpose:
- inspect telemetry traffic
- confirm packets flowing

---

## Verify MAVProxy Outputs

Within MAVProxy:

```bash
output
```

Purpose:
- display active telemetry routes

---

# Lessons Learned

- telemetry routing is dependent on startup order
- UDP telemetry requires correct output configuration
- MAVLink traffic can be distributed to multiple consumers
- networking visibility is critical for troubleshooting
