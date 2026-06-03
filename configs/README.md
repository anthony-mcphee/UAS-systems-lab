# Configs

YAML configuration files for mission parameters and connection settings. All tunable values live here — no hardcoded parameters in mission scripts.

## config.yaml

Primary configuration file. Pass it to any script with `--config configs/config.yaml`.

### Sections

| Section | Key Parameters | Purpose |
|---|---|---|
| `connection` | `uri` | MAVLink connection string — switch between SITL and hardware without touching script code |
| `home` | `lat`, `lon` | Home/launch coordinates — used as the simulated beacon orbit center |
| `altitudes` | `takeoff`, `follow`, `descend_high`, `descend_low` | Altitude thresholds that drive state transitions in the beacon follower |
| `follow` | `radius_m`, `update_rate_sec` | Beacon tracking behavior — arrival radius and main loop interval |
| `beacon` | `source` | Selects the active beacon input: `simulate`, `udp`, or `serial` |
| `beacon.udp` | `host`, `port` | Address for incoming UDP beacon datagrams |
| `beacon.serial` | `port`, `baudrate` | Serial port and baud rate for NMEA GPS receiver |
| `logging` | `log_dir`, `level` | Output directory for log files and verbosity level |

### Switching to Hardware

Change `connection.uri` to connect to a physical flight controller over serial or telemetry radio:

```yaml
connection:
  uri: "serial:///dev/ttyUSB0:57600"
```

### Switching Beacon Source

```yaml
beacon:
  source: "udp"
  udp:
    host: "0.0.0.0"
    port: 5005
```

Send test datagrams with:
```bash
echo "-35.363,149.165" | nc -u 127.0.0.1 5005
```

### Optional Sections

Scripts with additional config support will read these blocks if present, falling back to hardcoded defaults if absent. Add them to `config.yaml` as needed:

```yaml
# Used by pre_flight_check.py
preflight:
  min_battery_voltage_v: 10.5
  min_battery_remaining_pct: 20
  min_gps_fix_type: 3          # 3 = 3D fix minimum

# Used by health_monitor.py
health:
  battery_warn_voltage_v: 11.0
  battery_critical_voltage_v: 10.5
  battery_warn_remaining_pct: 30
  battery_critical_remaining_pct: 15
  min_gps_fix_type: 3
  min_satellites: 6
  rssi_warn_dbm: -90
  poll_rate_sec: 2
```
