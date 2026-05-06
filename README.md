# UAS Systems Lab

This repository documents my UAS systems integration and autonomy lab. The lab is focused on ArduPilot SITL, MAVProxy, QGroundControl, MAVLink telemetry, Linux troubleshooting, networking, and autonomous flight experimentation.

## Purpose

The purpose of this project is to build practical experience with unmanned aircraft systems, autonomy workflows, telemetry paths, and field-level troubleshooting of software-enabled aviation systems.

## Current Capabilities

- Ubuntu/WSL lab environment
- ArduPilot SITL using ArduCopter
- MAVProxy command interface
- QGroundControl ground control station connection
- MAVLink telemetry flow over UDP
- Python-based MAVLink connection testing
- Autonomous waypoint mission execution in simulation
- Basic Linux service, log, and network troubleshooting practice

## Lab Architecture

Initial lab architecture:

```text
ArduPilot SITL
    |
    | MAVLink telemetry
    v
MAVProxy
    |
    | UDP outputs
    v
QGroundControl / Python MAVLink scripts
