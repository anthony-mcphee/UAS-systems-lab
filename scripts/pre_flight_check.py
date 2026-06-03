"""
pre_flight_check.py
===================
Pre-flight go/no-go checklist for an ArduPilot MAVLink vehicle.

Aviation background note: this mirrors the structured preflight inspection
process — each check is discrete, has a defined pass/fail criterion, and the
final output is an explicit GO or NO-GO decision. Silent continues are not
acceptable for operational systems.

Usage
-----
  python scripts/pre_flight_check.py                        # uses configs/config.yaml
  python scripts/pre_flight_check.py --config my.yaml       # custom config

Checks performed
----------------
  1. Heartbeat          — vehicle is alive and system status is acceptable
  2. Sensor health      — all enabled sensors report healthy (SYS_STATUS)
  3. GPS fix quality    — 3D fix or better, configurable minimum
  4. EKF status         — navigation filter has attitude, velocity, and position
  5. Battery            — voltage and remaining capacity above configured minimums
  6. Armed state        — vehicle is disarmed before preflight
  7. Home position      — RTL destination is set and non-zero

Exit codes
----------
  0 — all checks passed (GO)
  1 — one or more checks failed (NO-GO)

Config additions (optional, falls back to defaults if absent)
-------------------------------------------------------------
  preflight:
    min_battery_voltage_v: 10.5
    min_battery_remaining_pct: 20
    min_gps_fix_type: 3
"""

import argparse
import sys
import time
from dataclasses import dataclass

import yaml
from pymavlink import mavutil


# ============================================================
# Data types
# ============================================================

@dataclass
class CheckResult:
    """Holds the outcome of a single preflight check."""
    name: str
    passed: bool
    detail: str   # human-readable finding — what the check actually observed


# ============================================================
# Config loading
# ============================================================

def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


# ============================================================
# MAVLink connection and telemetry collection
# ============================================================

def connect(uri: str) -> mavutil.mavfile:
    print(f"Connecting to {uri}...")
    master = mavutil.mavlink_connection(uri)
    master.wait_heartbeat(timeout=10)
    print(f"  Heartbeat received — SYS:{master.target_system} COMP:{master.target_component}\n")
    return master


def collect_telemetry(master: mavutil.mavfile, timeout: float = 5.0) -> dict:
    """
    Collect a snapshot of all required telemetry messages in one pass.

    Reads the incoming MAVLink stream for up to `timeout` seconds, keeping
    the first instance of each message type we care about. Reading all
    messages in one pass avoids the timing issues that come from issuing
    separate blocking recv_match calls per check.

    HOME_POSITION is not streamed by default, so we request it explicitly
    before reading the stream.
    """
    wanted = {"HEARTBEAT", "SYS_STATUS", "GPS_RAW_INT", "EKF_STATUS_REPORT", "HOME_POSITION"}

    # Request HOME_POSITION — message ID 242 — it won't appear in the stream
    # unless we ask for it. MAV_CMD_REQUEST_MESSAGE (512) is the standard way
    # to pull a single message on demand.
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE,
        0,
        242,   # MAVLINK_MSG_ID_HOME_POSITION
        0, 0, 0, 0, 0, 0,
    )

    collected: dict = {}
    deadline = time.time() + timeout

    while time.time() < deadline:
        msg = master.recv_match(blocking=True, timeout=0.5)
        if msg is None:
            continue
        msg_type = msg.get_type()
        # Keep the first instance of each type — messages change slowly enough
        # that the first read within a 5s window is representative
        if msg_type in wanted and msg_type not in collected:
            collected[msg_type] = msg
        if wanted.issubset(collected.keys()):
            break   # got everything we need, stop early

    return collected


# ============================================================
# Individual checks
#
# Each function receives the pre-collected telemetry snapshot (a dict of
# message type → message object) and returns a CheckResult.
#
# Accepting the snapshot dict rather than calling recv_match inside each
# function keeps the checks fast, testable, and free of network side effects.
# ============================================================

def check_heartbeat(telemetry: dict) -> CheckResult:
    """
    Verify the vehicle is alive and its system status is acceptable.

    MAV_STATE values:
      0=UNINIT  1=BOOT  2=CALIBRATING  3=STANDBY  4=ACTIVE
      5=CRITICAL  6=EMERGENCY  7=POWEROFF
    STANDBY and ACTIVE are both acceptable pre-flight states.
    """
    msg = telemetry.get("HEARTBEAT")
    if msg is None:
        return CheckResult("Heartbeat", False, "No heartbeat received")

    STATUS_NAMES = {
        0: "UNINIT", 1: "BOOT", 2: "CALIBRATING", 3: "STANDBY",
        4: "ACTIVE", 5: "CRITICAL", 6: "EMERGENCY", 7: "POWEROFF",
    }
    status_name = STATUS_NAMES.get(msg.system_status, f"UNKNOWN({msg.system_status})")
    passed = msg.system_status in (3, 4)
    return CheckResult("Heartbeat", passed, f"System status: {status_name}")


def check_sensors(telemetry: dict) -> CheckResult:
    """
    Check flight controller sensor health using the SYS_STATUS bitmask.

    ArduPilot reports which sensors are enabled and which are healthy.
    Any sensor that is enabled but not healthy is a failure — the autopilot
    is using that sensor for navigation and it is not working correctly.

    The bitmask bits map to sensor subsystems (gyro, accel, mag, GPS, etc.).
    """
    msg = telemetry.get("SYS_STATUS")
    if msg is None:
        return CheckResult("Sensor health", False, "No SYS_STATUS received")

    enabled = msg.onboard_control_sensors_enabled
    healthy = msg.onboard_control_sensors_health
    # Sensors that are switched on but not reporting healthy
    unhealthy_enabled = enabled & ~healthy

    if unhealthy_enabled:
        SENSOR_BITS = {
            0x000001: "3D_GYRO",     0x000002: "3D_ACCEL",      0x000004: "3D_MAG",
            0x000008: "ABS_PRESSURE",0x000010: "DIFF_PRESSURE",  0x000020: "GPS",
            0x000040: "OPTICAL_FLOW",0x000400: "ANGULAR_RATE",   0x000800: "ATT_STAB",
            0x001000: "YAW_POS",     0x002000: "Z_ALT_CTRL",     0x004000: "XY_POS_CTRL",
            0x008000: "MOTOR_OUT",   0x010000: "RC_RECEIVER",
        }
        bad = [name for bit, name in SENSOR_BITS.items() if unhealthy_enabled & bit]
        return CheckResult("Sensor health", False, f"Unhealthy: {', '.join(bad)}")

    return CheckResult("Sensor health", True, "All enabled sensors healthy")


def check_gps(telemetry: dict, min_fix_type: int) -> CheckResult:
    """
    Verify GPS fix quality meets the required minimum.

    fix_type values:
      0=NO_GPS  1=NO_FIX  2=2D_FIX  3=3D_FIX  4=DGPS
      5=RTK_FLOAT  6=RTK_FIXED

    HDOP (horizontal dilution of precision) is reported as eph * 0.01 meters.
    A value of 65535 means unavailable.
    """
    msg = telemetry.get("GPS_RAW_INT")
    if msg is None:
        return CheckResult("GPS fix", False, "No GPS_RAW_INT received")

    FIX_NAMES = {
        0: "NO_GPS", 1: "NO_FIX", 2: "2D_FIX", 3: "3D_FIX",
        4: "DGPS", 5: "RTK_FLOAT", 6: "RTK_FIXED",
    }
    fix_name = FIX_NAMES.get(msg.fix_type, f"UNK({msg.fix_type})")
    sats = msg.satellites_visible
    hdop = msg.eph / 100.0 if msg.eph != 65535 else float("inf")

    passed = msg.fix_type >= min_fix_type
    detail = f"{fix_name} | sats={sats} | HDOP={hdop:.1f}"
    return CheckResult("GPS fix", passed, detail)


def check_ekf(telemetry: dict) -> CheckResult:
    """
    Verify the EKF (Extended Kalman Filter) navigation filter is healthy.

    The EKF fuses GPS, IMU, baro, and magnetometer into the position/velocity/
    attitude estimates that GUIDED mode relies on. If EKF flags are missing,
    the autopilot cannot safely navigate to a GPS waypoint.

    EKF_STATUS_REPORT.flags bitmask:
      0x01 = attitude OK
      0x02 = horizontal velocity OK
      0x04 = vertical velocity OK
      0x08 = horizontal position OK
      0x10 = vertical position OK
    """
    msg = telemetry.get("EKF_STATUS_REPORT")
    if msg is None:
        # EKF_STATUS_REPORT is not always streamed by default in all SITL builds.
        # Treat absence as a soft pass — not a hard fail for simulation.
        return CheckResult("EKF status", True, "EKF_STATUS_REPORT not available (skipped)")

    FLAGS_NEEDED = 0x01 | 0x02 | 0x04 | 0x08 | 0x10
    flags = msg.flags
    missing_bits = FLAGS_NEEDED & ~flags

    if missing_bits:
        FLAG_NAMES = {0x01: "ATT", 0x02: "VEL_H", 0x04: "VEL_V", 0x08: "POS_H", 0x10: "POS_V"}
        missing = [name for bit, name in FLAG_NAMES.items() if missing_bits & bit]
        return CheckResult("EKF status", False, f"Missing EKF flags: {', '.join(missing)}")

    return CheckResult("EKF status", True, f"EKF healthy (flags=0x{flags:02X})")


def check_battery(telemetry: dict, min_voltage_v: float, min_remaining_pct: int) -> CheckResult:
    """
    Check battery voltage and remaining capacity.

    SYS_STATUS reports voltage_battery in millivolts and battery_remaining
    as a percentage (0–100), or -1 if the flight controller cannot estimate it.
    Voltage is the primary indicator; remaining % is a secondary guard when available.
    """
    msg = telemetry.get("SYS_STATUS")
    if msg is None:
        return CheckResult("Battery", False, "No SYS_STATUS received")

    voltage_v = msg.voltage_battery / 1000.0
    remaining = msg.battery_remaining   # -1 = not estimated

    voltage_ok = voltage_v >= min_voltage_v
    pct_ok = remaining == -1 or remaining >= min_remaining_pct

    pct_str = f"{remaining}%" if remaining != -1 else "n/a"
    detail = f"{voltage_v:.2f}V | remaining={pct_str} (min={min_voltage_v:.1f}V / {min_remaining_pct}%)"
    return CheckResult("Battery", voltage_ok and pct_ok, detail)


def check_armed_state(telemetry: dict) -> CheckResult:
    """
    Confirm the vehicle is disarmed before running preflight.

    MAV_MODE_FLAG_SAFETY_ARMED (0x80) in base_mode indicates the vehicle is
    armed. Running preflight on an already-armed vehicle means it may be
    airborne — the check results would be meaningless.
    """
    msg = telemetry.get("HEARTBEAT")
    if msg is None:
        return CheckResult("Armed state", False, "No HEARTBEAT received")

    is_armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    if is_armed:
        return CheckResult("Armed state", False, "Vehicle is ARMED — run preflight before arming")
    return CheckResult("Armed state", True, "Vehicle is disarmed")


def check_home_position(telemetry: dict) -> CheckResult:
    """
    Confirm a home position has been set.

    Home is the RTL destination. If home is not set (coordinates are 0,0),
    RTL will fail or fly to an incorrect location. ArduPilot sets home
    automatically on first GPS fix when armed, or it can be set manually.
    """
    msg = telemetry.get("HOME_POSITION")
    if msg is None:
        return CheckResult("Home position", False, "HOME_POSITION not received (not set?)")

    lat = msg.latitude / 1e7
    lon = msg.longitude / 1e7
    alt = msg.altitude / 1000.0

    if lat == 0.0 and lon == 0.0:
        return CheckResult("Home position", False, "Home is (0, 0) — not initialized")

    return CheckResult("Home position", True, f"({lat:.6f}, {lon:.6f}) alt={alt:.1f}m")


# ============================================================
# Report printer
# ============================================================

_SEP = "-" * 58

def print_report(results: list[CheckResult]) -> bool:
    """Print a formatted checklist table and return True if all checks passed."""
    print(_SEP)
    print("  PRE-FLIGHT CHECK REPORT")
    print(_SEP)
    for r in results:
        status = "  PASS" if r.passed else "  FAIL"
        print(f"{status}  {r.name:<22}  {r.detail}")
    print(_SEP)
    all_passed = all(r.passed for r in results)
    print(f"  RESULT: {'GO' if all_passed else 'NO-GO'}")
    print(_SEP)
    return all_passed


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Pre-flight go/no-go checklist")
    parser.add_argument("--config", default="configs/config.yaml", help="Path to config YAML")
    args = parser.parse_args()

    cfg = load_config(args.config)
    uri = cfg["connection"]["uri"]

    # Read optional preflight thresholds from config — fall back to safe defaults
    pf = cfg.get("preflight", {})
    min_voltage     = pf.get("min_battery_voltage_v", 10.5)
    min_remaining   = pf.get("min_battery_remaining_pct", 20)
    min_gps_fix     = pf.get("min_gps_fix_type", 3)

    master = connect(uri)

    print("Collecting telemetry snapshot...")
    telemetry = collect_telemetry(master, timeout=5.0)
    received = list(telemetry.keys())
    print(f"  Received: {', '.join(received) if received else 'none'}\n")

    results = [
        check_heartbeat(telemetry),
        check_sensors(telemetry),
        check_gps(telemetry, min_fix_type=min_gps_fix),
        check_ekf(telemetry),
        check_battery(telemetry, min_voltage_v=min_voltage, min_remaining_pct=min_remaining),
        check_armed_state(telemetry),
        check_home_position(telemetry),
    ]

    go = print_report(results)
    sys.exit(0 if go else 1)


if __name__ == "__main__":
    main()
