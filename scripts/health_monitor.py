"""
health_monitor.py
=================
Real-time telemetry health monitor for an ArduPilot MAVLink vehicle.

Intended to run in a second terminal alongside an active mission, watching
key telemetry streams and emitting structured alerts when values cross
configured thresholds. All alerts are written to a timestamped log file.

Aviation analogy: this is the crew chief watching engine health gauges
while the aircraft is airborne — not flying it, but watching for conditions
that should trigger operator intervention.

Usage
-----
  python scripts/health_monitor.py                         # uses configs/config.yaml
  python scripts/health_monitor.py --config my.yaml        # custom config

Monitored streams
-----------------
  - Battery voltage and remaining capacity   (SYS_STATUS)
  - GPS fix quality and satellite count      (GPS_RAW_INT)
  - EKF navigation filter health flags       (EKF_STATUS_REPORT)
  - Radio link RSSI                          (RADIO_STATUS, if present)
  - Flight mode transitions                  (HEARTBEAT)

Alert levels
------------
  WARNING  — degraded condition, operator should be aware
  CRITICAL — condition requires immediate attention

Ctrl-C exits cleanly and prints a session summary.

Config additions (optional, falls back to defaults if absent)
-------------------------------------------------------------
  health:
    battery_warn_voltage_v: 11.0
    battery_critical_voltage_v: 10.5
    battery_warn_remaining_pct: 30
    battery_critical_remaining_pct: 15
    min_gps_fix_type: 3
    min_satellites: 6
    rssi_warn_dbm: -90
    poll_rate_sec: 2
"""

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path

import yaml
from pymavlink import mavutil


# ============================================================
# Logging setup — same pattern as beacon_follower.py
# ============================================================

def setup_logging(log_dir: str, level_str: str) -> logging.Logger:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(log_dir) / f"health_{timestamp}.log"

    level = getattr(logging, level_str.upper(), logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(fmt)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    logger = logging.getLogger("health_monitor")
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.info(f"Health monitor logging to {log_path}")
    return logger


# ============================================================
# Config
# ============================================================

def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_thresholds(cfg: dict) -> dict:
    """
    Extract health thresholds from config, using safe defaults for any
    missing keys. This means the monitor works out of the box with just
    the existing config.yaml, and you can tune thresholds by adding a
    'health' block without touching the script.
    """
    h = cfg.get("health", {})
    return {
        "battery_warn_v":       h.get("battery_warn_voltage_v",          11.0),
        "battery_critical_v":   h.get("battery_critical_voltage_v",      10.5),
        "battery_warn_pct":     h.get("battery_warn_remaining_pct",        30),
        "battery_critical_pct": h.get("battery_critical_remaining_pct",    15),
        "min_gps_fix":          h.get("min_gps_fix_type",                   3),
        "min_satellites":       h.get("min_satellites",                      6),
        "rssi_warn_dbm":        h.get("rssi_warn_dbm",                    -90),
        "poll_rate":            h.get("poll_rate_sec",                       2),
    }


# ============================================================
# MAVLink connection
# ============================================================

def connect(uri: str, logger: logging.Logger) -> mavutil.mavfile:
    logger.info(f"Connecting to {uri}")
    master = mavutil.mavlink_connection(uri)
    master.wait_heartbeat()
    logger.info(f"Connected — SYS:{master.target_system} COMP:{master.target_component}")
    return master


# ============================================================
# Message collection
# ============================================================

def drain_messages(master: mavutil.mavfile, wanted: set, window_sec: float) -> dict:
    """
    Read the incoming MAVLink buffer for up to window_sec seconds,
    collecting the most recent message of each requested type.

    Using a time-windowed drain rather than separate blocking recv_match
    calls ensures we catch messages that arrive close together in the
    stream without blocking on any single message type.
    """
    latest: dict = {}
    deadline = time.time() + window_sec
    while time.time() < deadline:
        msg = master.recv_match(blocking=False)
        if msg is None:
            # No message available right now — yield briefly so we don't
            # burn CPU in a tight busy-loop
            time.sleep(0.01)
            continue
        msg_type = msg.get_type()
        if msg_type in wanted:
            latest[msg_type] = msg   # overwrite with fresher reading
    return latest


# ============================================================
# Alert tracker
#
# Prevents the log from flooding with repeated alerts for the same
# sustained condition. An alert fires once when a condition starts and
# once when it clears — not on every poll cycle.
# ============================================================

class AlertTracker:
    def __init__(self):
        self._active: dict[str, str] = {}   # condition_key → current severity

    def check(self, key: str, severity: str | None) -> bool:
        """
        Returns True if this is a new alert or severity escalation.
        severity=None means the condition has cleared.
        """
        previous = self._active.get(key)

        if severity is None:
            if previous is not None:
                self._active.pop(key)
                return True   # cleared — log it once
            return False      # was already clear, nothing to report

        if severity != previous:
            self._active[key] = severity
            return True       # new alert or escalation

        return False          # same severity as before, suppress

    def active_count(self) -> int:
        return len(self._active)


# ============================================================
# Individual health checks
#
# Each function receives the latest message for its type (may be None if
# the stream hasn't delivered one yet), the thresholds dict, the alert
# tracker, and the logger.
#
# Returns a short status token string used in the summary log line.
# ============================================================

def check_battery(msg, thresholds: dict, tracker: AlertTracker, logger: logging.Logger) -> str:
    """
    Monitor battery voltage and remaining capacity from SYS_STATUS.

    voltage_battery is in millivolts; battery_remaining is 0–100% or -1.
    Critical threshold takes priority over warning threshold.
    """
    if msg is None:
        return "batt=n/a"

    voltage_v = msg.voltage_battery / 1000.0
    remaining = msg.battery_remaining

    if (voltage_v < thresholds["battery_critical_v"] or
            (remaining != -1 and remaining < thresholds["battery_critical_pct"])):
        severity = "CRITICAL"
    elif (voltage_v < thresholds["battery_warn_v"] or
            (remaining != -1 and remaining < thresholds["battery_warn_pct"])):
        severity = "WARNING"
    else:
        severity = None

    pct_str = f"{remaining}%" if remaining != -1 else "n/a"

    if tracker.check("battery", severity):
        if severity is None:
            logger.info("Battery: condition cleared")
        else:
            logger.warning(f"Battery {severity}: {voltage_v:.2f}V remaining={pct_str}")

    return f"batt={voltage_v:.2f}V({pct_str})"


def check_gps(msg, thresholds: dict, tracker: AlertTracker, logger: logging.Logger) -> str:
    """
    Monitor GPS fix type and satellite count from GPS_RAW_INT.

    A degraded fix type in GUIDED mode causes position drift — the EKF
    will degrade gracefully but the vehicle may not track waypoints accurately.
    Low satellite count is a leading indicator before fix type degrades.
    """
    if msg is None:
        return "gps=n/a"

    FIX_NAMES = {0: "NO_GPS", 1: "NO_FIX", 2: "2D", 3: "3D", 4: "DGPS", 5: "RTK_F", 6: "RTK_FIXED"}
    fix_name = FIX_NAMES.get(msg.fix_type, f"UNK({msg.fix_type})")
    sats = msg.satellites_visible

    if msg.fix_type < thresholds["min_gps_fix"]:
        severity = "CRITICAL"
    elif sats < thresholds["min_satellites"]:
        severity = "WARNING"
    else:
        severity = None

    if tracker.check("gps", severity):
        if severity is None:
            logger.info("GPS: condition cleared")
        else:
            logger.warning(f"GPS {severity}: fix={fix_name} sats={sats}")

    return f"gps={fix_name}(sats={sats})"


def check_ekf(msg, tracker: AlertTracker, logger: logging.Logger) -> str:
    """
    Monitor EKF navigation filter health from EKF_STATUS_REPORT.

    If EKF flags are missing, GUIDED mode cannot navigate reliably.
    EKF_STATUS_REPORT is not streamed at high rate — we catch it
    opportunistically and use the most recent reading.

    Flag bits:
      0x01 attitude | 0x02 vel_horiz | 0x04 vel_vert | 0x08 pos_horiz | 0x10 pos_vert
    """
    if msg is None:
        return "ekf=n/a"

    REQUIRED = 0x01 | 0x02 | 0x04 | 0x08 | 0x10
    flags = msg.flags
    missing = REQUIRED & ~flags

    if missing:
        FLAG_NAMES = {0x01: "ATT", 0x02: "VEL_H", 0x04: "VEL_V", 0x08: "POS_H", 0x10: "POS_V"}
        missing_names = [name for bit, name in FLAG_NAMES.items() if missing & bit]
        if tracker.check("ekf", "CRITICAL"):
            logger.warning(f"EKF CRITICAL: missing flags {missing_names}")
    else:
        if tracker.check("ekf", None):
            logger.info("EKF: condition cleared")

    return f"ekf=0x{flags:02X}"


def check_radio(msg, thresholds: dict, tracker: AlertTracker, logger: logging.Logger) -> str:
    """
    Monitor radio telemetry link quality from RADIO_STATUS.

    Only present when using a SiK/RFD900 or similar telemetry radio.
    If this message never appears, it means the setup uses direct UDP
    (SITL/companion computer) — not a fault.

    SiK RSSI: 0–255 raw value. Approximate dBm: rssi/1.9 - 127.
    This conversion is specific to SiK radio firmware — hardware may vary.
    rxerrors is a cumulative packet error counter.
    """
    if msg is None:
        return "radio=n/a"

    rssi = msg.rssi
    rssi_dbm = (rssi / 1.9) - 127 if rssi > 0 else -127.0

    if rssi_dbm < thresholds["rssi_warn_dbm"]:
        if tracker.check("radio", "WARNING"):
            logger.warning(
                f"Radio WARNING: RSSI={rssi} (~{rssi_dbm:.0f} dBm) "
                f"rxerrors={msg.rxerrors}"
            )
    else:
        if tracker.check("radio", None):
            logger.info("Radio link: condition cleared")

    return f"radio={rssi}({rssi_dbm:.0f}dBm)"


def check_mode(msg, state: dict, logger: logging.Logger) -> None:
    """
    Log every flight mode transition.

    `state` is a dict that persists across calls to track the previous mode.
    Passing state in rather than using a global keeps this function testable
    and avoids module-level side effects.
    """
    if msg is None:
        return
    current_mode = mavutil.mode_string_v10(msg)
    if current_mode != state.get("last_mode"):
        if state.get("last_mode") is not None:
            logger.info(f"Mode change: {state['last_mode']} → {current_mode}")
        state["last_mode"] = current_mode


# ============================================================
# Session summary
# ============================================================

def print_summary(start_time: float, total_alert_events: int, logger: logging.Logger) -> None:
    elapsed = time.time() - start_time
    minutes, seconds = divmod(int(elapsed), 60)
    logger.info(
        f"Monitor stopped | duration={minutes}m{seconds}s | "
        f"total alert events={total_alert_events}"
    )


# ============================================================
# Main monitoring loop
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Real-time telemetry health monitor")
    parser.add_argument("--config", default="configs/config.yaml", help="Path to config YAML")
    args = parser.parse_args()

    cfg = load_config(args.config)
    logger = setup_logging(cfg["logging"]["log_dir"], cfg["logging"]["level"])
    thresholds = get_thresholds(cfg)

    master = connect(cfg["connection"]["uri"], logger)

    tracker = AlertTracker()
    mode_state: dict = {}    # persistent dict for mode change tracking
    start_time = time.time()
    poll_rate = thresholds["poll_rate"]
    total_alert_events = 0

    # Messages we want to collect each poll cycle
    WANTED = {"SYS_STATUS", "GPS_RAW_INT", "EKF_STATUS_REPORT", "RADIO_STATUS", "HEARTBEAT"}

    logger.info(
        f"Monitoring started | poll_rate={poll_rate}s | "
        f"batt_warn={thresholds['battery_warn_v']}V | "
        f"min_gps_fix={thresholds['min_gps_fix']}"
    )
    logger.info("Press Ctrl-C to stop.")

    try:
        while True:
            loop_start = time.time()

            # Collect all available messages for this poll window.
            # The window is half the poll rate so we have time left
            # for processing and logging before the next cycle.
            messages = drain_messages(master, WANTED, window_sec=poll_rate / 2)

            # Run each check — each returns a short status token
            batt_status  = check_battery(messages.get("SYS_STATUS"),       thresholds, tracker, logger)
            gps_status   = check_gps(messages.get("GPS_RAW_INT"),           thresholds, tracker, logger)
            ekf_status   = check_ekf(messages.get("EKF_STATUS_REPORT"),     tracker, logger)
            radio_status = check_radio(messages.get("RADIO_STATUS"),        thresholds, tracker, logger)
            check_mode(messages.get("HEARTBEAT"), mode_state, logger)

            # Count alert events fired this cycle (tracker fires once per transition)
            # We approximate by tracking changes — simpler than wiring a return value
            # through every check function
            current_active = tracker.active_count()
            if current_active > 0:
                total_alert_events += 1

            # One-line telemetry summary per poll cycle
            summary = " | ".join([batt_status, gps_status, ekf_status, radio_status])
            alert_flag = f" *** {current_active} ACTIVE ALERT(S)" if current_active else ""
            logger.info(f"{summary}{alert_flag}")

            # Sleep for the remainder of the poll interval
            elapsed = time.time() - loop_start
            remaining = max(0.0, poll_rate - elapsed)
            time.sleep(remaining)

    except KeyboardInterrupt:
        logger.info("Ctrl-C received — stopping.")

    finally:
        print_summary(start_time, total_alert_events, logger)


if __name__ == "__main__":
    main()
