"""
mission.py — V1 learning artifact. Superseded by guided_waypoint_mission.py.

Differences from the current version:
- Uses angular distance (distance_degrees) instead of haversine — inaccurate at scale
- Takeoff waits on a fixed sleep rather than confirming altitude reached
- Single waypoint, no multi-leg pattern, no ACK checking

Kept for progression reference. Do not use for new missions.
---
Guided waypoint mission test for ArduPilot SITL.

Mission sequence:
1. Connect to MAVLink telemetry stream
2. Set GUIDED mode
3. Arm vehicle
4. Take off
5. Fly to target waypoint
6. Hold position
7. Fly back to return waypoint
8. Land

Environment:
- ArduPilot SITL running
- MAVProxy routing telemetry to UDP port 14551
- Python virtual environment active
"""

from pymavlink import mavutil
import time
import math


CONNECTION_STRING = "udpin:127.0.0.1:14551"

TAKEOFF_ALT = 10

TARGET_LAT = -35.362500
TARGET_LON = 149.166500
TARGET_ALT = 20

RETURN_LAT = -35.363262
RETURN_LON = 149.165237
RETURN_ALT = 10

HOLD_TIME = 10


def connect_vehicle():
    print(f"Connecting to MAVLink stream on {CONNECTION_STRING}")
    master = mavutil.mavlink_connection(CONNECTION_STRING)

    print("Waiting for heartbeat...")
    master.wait_heartbeat()

    print("Heartbeat received")
    print(f"System ID: {master.target_system}")
    print(f"Component ID: {master.target_component}")

    return master


def set_mode(master, mode):
    modes = master.mode_mapping()

    if mode not in modes:
        print(f"Unknown mode: {mode}")
        print(f"Available modes: {list(modes.keys())}")
        return False

    master.mav.set_mode_send(
        master.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        modes[mode],
    )

    print(f"Mode command sent: {mode}")
    time.sleep(2)
    return True


def arm(master):
    print("Arming vehicle...")

    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        1,
        0,
        0,
        0,
        0,
        0,
        0,
    )

    master.motors_armed_wait()
    print("Vehicle armed")


def takeoff(master, altitude):
    print(f"Taking off to {altitude} meters...")

    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        altitude,
    )

    time.sleep(5)


def send_waypoint(master, lat, lon, alt):
    print(f"Sending waypoint: lat={lat}, lon={lon}, alt={alt}m")

    master.mav.set_position_target_global_int_send(
        0,
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        0b0000111111111000,
        int(lat * 1e7),
        int(lon * 1e7),
        alt,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    )


def send_waypoint_repeated(master, lat, lon, alt, seconds=10):
    print(f"Commanding waypoint for {seconds} seconds...")

    start_time = time.time()

    while time.time() - start_time < seconds:
        send_waypoint(master, lat, lon, alt)
        time.sleep(1)


def get_position(master):
    msg = master.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=5)

    if msg is None:
        return None

    lat = msg.lat / 1e7
    lon = msg.lon / 1e7
    alt = msg.relative_alt / 1000.0

    return lat, lon, alt


def distance_degrees(lat1, lon1, lat2, lon2):
    return math.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2)


def wait_until_arrival(master, target_lat, target_lon, threshold=0.00005, timeout=90):
    print("Monitoring vehicle position...")

    start_time = time.time()

    while True:
        position = get_position(master)

        if position is None:
            print("No position message received")
            continue

        lat, lon, alt = position
        distance = distance_degrees(lat, lon, target_lat, target_lon)

        print(
            f"Current: {lat:.7f}, {lon:.7f}, alt={alt:.1f}m "
            f"| Distance: {distance:.7f}"
        )

        if distance < threshold:
            print("Reached target")
            return True

        if time.time() - start_time > timeout:
            print("Timed out before reaching target")
            return False

        time.sleep(1)


def land(master):
    print("Landing...")

    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_LAND,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    )


def main():
    master = connect_vehicle()

    print("Starting mission...")

    if not set_mode(master, "GUIDED"):
        return

    arm(master)
    takeoff(master, TAKEOFF_ALT)

    send_waypoint_repeated(master, TARGET_LAT, TARGET_LON, TARGET_ALT, seconds=10)
    reached_target = wait_until_arrival(master, TARGET_LAT, TARGET_LON)

    if reached_target:
        print(f"Holding position for {HOLD_TIME} seconds...")
        time.sleep(HOLD_TIME)

    send_waypoint_repeated(master, RETURN_LAT, RETURN_LON, RETURN_ALT, seconds=10)
    wait_until_arrival(master, RETURN_LAT, RETURN_LON)

    land(master)

    print("Mission complete")


if __name__ == "__main__":
    main()
