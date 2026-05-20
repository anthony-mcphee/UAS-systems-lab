"""
Guided waypoint mission test for ArduPilot SITL.

Mission sequence:
1. Connect to MAVLink telemetry stream
2. Set GUIDED mode with heartbeat confirmation
3. Arm vehicle
4. Take off and verify altitude
5. Fly a multi-waypoint search pattern
6. Hold at each waypoint briefly
7. Return to launch and land

Environment:
- ArduPilot SITL running
- MAVProxy routing telemetry to UDP port 14551
- Python virtual environment active
"""

from pymavlink import mavutil
import time
import math

# --- Connection ---
CONNECTION_STRING = "udpin:127.0.0.1:14551"

# --- Flight parameters ---
TAKEOFF_ALT      = 10      # meters
CRUISE_ALT       = 20      # meters for waypoint legs
TAKEOFF_TIMEOUT  = 20      # seconds
MODE_TIMEOUT     = 5
ACK_TIMEOUT      = 5
ALT_TOLERANCE    = 1.0     # meters
ARRIVAL_RADIUS   = 3.0     # meters
WAYPOINT_TIMEOUT = 90      # seconds per leg
HOLD_TIME        = 8       # seconds to loiter at each waypoint
WAYPOINT_HZ      = 2       # setpoint refresh rate during transit

# --- Home / launch point (SITL default) ---
HOME_LAT =  -35.363262
HOME_LON =  149.165237

# --- Search pattern waypoints ---
# Expanding box pattern around home — good for area familiarization / search
WAYPOINTS = [
    {"label": "WP1 - North",       "lat": -35.362262, "lon": 149.165237, "alt": CRUISE_ALT},
    {"label": "WP2 - Northeast",   "lat": -35.362262, "lon": 149.166237, "alt": CRUISE_ALT},
    {"label": "WP3 - East",        "lat": -35.363262, "lon": 149.166237, "alt": CRUISE_ALT},
    {"label": "WP4 - Southeast",   "lat": -35.364262, "lon": 149.166237, "alt": CRUISE_ALT},
    {"label": "WP5 - South",       "lat": -35.364262, "lon": 149.165237, "alt": CRUISE_ALT},
    {"label": "WP6 - Southwest",   "lat": -35.364262, "lon": 149.164237, "alt": CRUISE_ALT},
    {"label": "WP7 - West",        "lat": -35.363262, "lon": 149.164237, "alt": CRUISE_ALT},
    {"label": "WP8 - Northwest",   "lat": -35.362262, "lon": 149.164237, "alt": CRUISE_ALT},
    {"label": "WP9 - High Pass",   "lat": -35.362262, "lon": 149.165237, "alt": 40},
    {"label": "WP10 - Low Pass",   "lat": -35.364262, "lon": 149.166237, "alt": 8},
]


# -------------------------
# MAVLink helpers
# -------------------------

def connect_vehicle():
    print(f"Connecting to {CONNECTION_STRING}...")
    master = mavutil.mavlink_connection(CONNECTION_STRING)
    print("Waiting for heartbeat...")
    master.wait_heartbeat()
    print(f"Heartbeat received — SYS:{master.target_system} COMP:{master.target_component}")
    return master


def wait_for_ack(master, command, timeout=ACK_TIMEOUT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = master.recv_match(type="COMMAND_ACK", blocking=False)
        if msg and msg.command == command:
            if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                print(f"  ACK: command {command} ACCEPTED")
                return True
            else:
                print(f"  ACK: command {command} REJECTED (result={msg.result})")
                return False
        time.sleep(0.05)
    print(f"  ACK timeout: no response for command {command}")
    return False


def set_mode(master, mode, timeout=MODE_TIMEOUT):
    modes = master.mode_mapping()
    if mode not in modes:
        print(f"Unknown mode: {mode}. Available: {list(modes.keys())}")
        return False

    master.mav.set_mode_send(
        master.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        modes[mode],
    )
    print(f"Mode command sent: {mode}")

    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = master.recv_match(type="HEARTBEAT", blocking=False)
        if msg and mavutil.mode_string_v10(msg) == mode:
            print(f"Mode confirmed: {mode}")
            return True
        time.sleep(0.1)

    print(f"Mode change to {mode} not confirmed within {timeout}s")
    return False


def arm(master, timeout=15):
    print("Arming vehicle...")
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 1, 0, 0, 0, 0, 0, 0,
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        master.motors_armed_wait()
        print("Vehicle armed")
        return True
    print("Arming timed out")
    return False


def takeoff(master, altitude, timeout=TAKEOFF_TIMEOUT):
    print(f"Taking off to {altitude}m...")
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0, 0, 0, 0, 0, 0, 0,
        altitude,
    )

    if not wait_for_ack(master, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF):
        print("Takeoff rejected — aborting")
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = master.recv_match(type="GLOBAL_POSITION_INT", blocking=False)
        if msg:
            alt = msg.relative_alt / 1000.0
            print(f"  Altitude: {alt:.1f}m", end="\r")
            if abs(alt - altitude) <= ALT_TOLERANCE:
                print(f"\nTarget altitude reached: {alt:.1f}m")
                return True
        time.sleep(0.2)

    print(f"\nTakeoff timeout after {timeout}s")
    return False


# -------------------------
# Navigation helpers
# -------------------------

def haversine(lat1, lon1, lat2, lon2):
    """Returns distance in meters between two lat/lon points."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_position(master):
    msg = master.recv_match(type="GLOBAL_POSITION_INT", blocking=False)
    if msg:
        return msg.lat / 1e7, msg.lon / 1e7, msg.relative_alt / 1000.0
    return None


def get_groundspeed(master):
    msg = master.recv_match(type="VFR_HUD", blocking=False)
    if msg:
        return msg.groundspeed
    return None


def send_waypoint(master, lat, lon, alt):
    master.mav.set_position_target_global_int_send(
        0,
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        0b0000111111111000,
        int(lat * 1e7),
        int(lon * 1e7),
        alt,
        0, 0, 0,
        0, 0, 0,
        0, 0,
    )


def fly_to(master, lat, lon, alt, label="waypoint",
           timeout=WAYPOINT_TIMEOUT, radius=ARRIVAL_RADIUS):
    """
    Send repeated waypoint setpoints until arrival or timeout.
    Prints live position, distance, and groundspeed each cycle.
    """
    print(f"\n--- Flying to {label} | lat={lat}, lon={lon}, alt={alt}m ---")
    interval = 1.0 / WAYPOINT_HZ
    deadline = time.time() + timeout

    while time.time() < deadline:
        send_waypoint(master, lat, lon, alt)

        pos = get_position(master)
        spd = get_groundspeed(master)

        if pos:
            clat, clon, calt = pos
            dist = haversine(clat, clon, lat, lon)
            spd_str = f"{spd:.1f} m/s" if spd is not None else "n/a"
            print(
                f"  Pos: ({clat:.6f}, {clon:.6f}) Alt: {calt:.1f}m "
                f"| Dist: {dist:.1f}m | GS: {spd_str}"
            )
            if dist < radius:
                print(f"  Arrived at {label}")
                return True

        time.sleep(interval)

    print(f"  Timeout reaching {label}")
    return False


def hold_position(master, lat, lon, alt, label="position", duration=HOLD_TIME):
    """Loiter at current position by continuing to send the same setpoint."""
    print(f"  Holding at {label} for {duration}s...")
    start = time.time()
    interval = 1.0 / WAYPOINT_HZ
    while time.time() - start < duration:
        send_waypoint(master, lat, lon, alt)
        time.sleep(interval)

def return_to_launch(master, timeout=60):
    print("\n--- Returning to launch ---")
    if not set_mode(master, "RTL"):
        print("Failed to set RTL — aborting")
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = master.recv_match(type="GLOBAL_POSITION_INT", blocking=False)
        if msg:
            alt = msg.relative_alt / 1000.0
            print(f"  Altitude: {alt:.1f}m", end="\r")
            if alt <= 0.5:
                print("\nVehicle landed at home")
                return True
        time.sleep(0.2)

    print("\nRTL timeout — vehicle may still be descending")
    return False


# -------------------------
# Mission
# -------------------------

def main():
    master = connect_vehicle()

    if not set_mode(master, "GUIDED"):
        print("Failed to set GUIDED — aborting")
        return

    if not arm(master):
        print("Arming failed — aborting")
        return

    if not takeoff(master, TAKEOFF_ALT):
        print("Takeoff failed — aborting")
        return

    print(f"\n=== Beginning search pattern: {len(WAYPOINTS)} waypoints ===")
    completed = 0

    for i, wp in enumerate(WAYPOINTS):
        label = wp["label"]
        lat, lon, alt = wp["lat"], wp["lon"], wp["alt"]

        arrived = fly_to(master, lat, lon, alt, label=label)

        if arrived:
            completed += 1
            hold_position(master, lat, lon, alt, duration=HOLD_TIME)
        else:
            print(f"  Skipping hold at {label} — did not arrive in time")

    print(f"\n=== Pattern complete: {completed}/{len(WAYPOINTS)} waypoints reached ===")

    return_to_launch(master)
    print("\nMission complete")


if __name__ == "__main__":
    main()
