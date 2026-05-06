# Lab Environment

## Host System

- Device: Microsoft Surface Pro
- Operating System: Windows with Ubuntu WSL
- Ubuntu Version: Ubuntu 24.04 LTS

## Python Environment

Virtual environment used for ArduPilot and MAVLink experimentation:

```bash
source ~/venv-ardupilot/bin/activate
```

## Core Components

### ArduPilot SITL

Used for simulated quadcopter flight operations and MAVLink telemetry generation.

### MAVProxy

Used as MAVLink relay, command interface, and telemetry router.

### QGroundControl

Used as primary ground control station interface.

### Python MAVLink Scripts

Used for telemetry monitoring and future automation scripting.

## Telemetry Ports

| Service | Port | Protocol |
|---|---|---|
| QGroundControl | 14550 | UDP |
| Python MAVLink Script | 14551 | UDP |

## Current Capabilities

- SITL startup
- MAVProxy routing
- QGroundControl connection
- Autonomous waypoint missions
- MAVLink telemetry monitoring
- Linux troubleshooting practice

## Known Issues Encountered

- Connection refused during startup sequencing
- MAVProxy output configuration confusion
- Python package dependency conflicts
- Port binding/order-of-operations troubleshooting

## Lessons Learned

- Startup order matters
- MAVLink telemetry routing must be verified
- UDP listeners require correct bind targets
- Linux logs and networking tools are critical for troubleshooting
