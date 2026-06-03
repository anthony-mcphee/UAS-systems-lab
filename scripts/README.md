# Scripts

Python MAVLink scripts for autonomous mission execution, telemetry monitoring, and vehicle health management. All scripts connect to the vehicle via MAVProxy on UDP port 14551 by default.

## Setup

Activate the project virtual environment before running any script:

```bash
cd ~/drone-control
source venv/bin/activate
```

## Script Reference

### Connection and Telemetry

| Script | Purpose |
|---|---|
| `heartbeat_test.py` | Verifies MAVLink connection — prints system and component IDs. Run this first to confirm the telemetry path is working. |
| `telemetry_monitor.py` | Streams live lat/lon/altitude from `GLOBAL_POSITION_INT`. Useful for watching a mission in a separate terminal. |

### Missions

| Script | Purpose |
|---|---|
| `mission.py` | V1 basic mission — fly to a single waypoint and return. Learning artifact, superseded by `guided_waypoint_mission.py`. |
| `guided_waypoint_mission.py` | 10-waypoint expanding box search pattern. Includes haversine arrival detection, per-waypoint loiter, ACK checking, and live groundspeed telemetry. |
| `velocity_test.py` | Validates velocity commands in all axes using `SET_POSITION_TARGET_LOCAL_NED`. Logs commanded vs. actual velocity at 10 Hz to confirm autopilot response. |

### Autonomy

| Script | Purpose |
|---|---|
| `beacon_follower.py` | Beacon-follow state machine with operator keyboard override. Supports simulated, UDP, and serial/NMEA beacon sources. Primary mission script — see `configs/config.yaml` for all parameters. |

### Operations

| Script | Purpose |
|---|---|
| `pre_flight_check.py` | Pre-flight go/no-go checklist. Checks sensor health, GPS fix quality, EKF status, battery voltage, armed state, and home position. Exits with code 0 (GO) or 1 (NO-GO). |
| `health_monitor.py` | Real-time telemetry health monitor. Runs alongside an active mission, watching battery, GPS, EKF, and radio link quality. Logs alerts when values cross configured thresholds. |

## Common Usage

```bash
# 1. Verify connection
python scripts/heartbeat_test.py

# 2. Run pre-flight check before any mission
python scripts/pre_flight_check.py --config configs/config.yaml

# 3. Run beacon follower (in one terminal)
python scripts/beacon_follower.py --config configs/config.yaml

# 4. Run health monitor alongside it (in a second terminal)
python scripts/health_monitor.py --config configs/config.yaml

# 5. Replay a previous telemetry log
python scripts/beacon_follower.py --replay logs/telem_20260510_142301.csv
```

## Port Layout

```
MAVProxy → 14550 → QGroundControl
MAVProxy → 14551 → Python scripts  ← all scripts connect here
```

Never run QGroundControl and Python scripts on the same port — they will conflict.
