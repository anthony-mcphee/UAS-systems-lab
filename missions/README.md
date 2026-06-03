# Missions

QGroundControl mission plan files for pre-planned waypoint missions.

## File Formats

QGroundControl exports missions in two formats:

| Format | Extension | Notes |
|---|---|---|
| Plan format | `.plan` | JSON — includes waypoints, geofence, and rally points in one file |
| Waypoints format | `.waypoints` | Plain text — MAVLink waypoint list, compatible with MAVProxy upload |

Export from QGroundControl: **Plan view → File → Save Mission As**

## Upload via MAVProxy

```bash
wp load missions/your_mission.waypoints
wp list   # verify upload
```

## Planned Additions

- Expanding box search pattern matching the waypoints in `guided_waypoint_mission.py`
- Beacon approach corridor with staged descent waypoints
