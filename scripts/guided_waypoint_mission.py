"""
Mission execution script for ArduPilot SITL.

Purpose:
- Connects to the MAVLink telemetry stream
- Sets GUIDED mode
- Arms the simulated vehicle
- Commands takeoff
- Sends waypoint commands
- Monitors position until arrival
- Commands return waypoint
- Lands vehicle

Environment:
- ArduPilot SITL running
- MAVProxy connected to tcp:127.0.0.1:5760
- MAVProxy output configured for UDP 14551
- Python virtual environment active
"""
from pymavlink import mavutil
import time
import math

# -------------------------
# Connection
# -------------------------

master = mavutil.mavlink_connection("udpin:127.0.0.1:14551")

print("Waiting for heartbeat...")
master.wait_heartbeat()
print(f"Connected to system {master.target_system}, component {master.target_component}")

print("Waiting 5 seconds for vehicle systems to stabilize...")
time.sleep(5)

# -------------------------
# Mission settings
# -------------------------

TARGET_LAT = -35.362500
TARGET_LON = 149.166500
TARGET_ALT = 20

RETURN_LAT = -35.363262
RETURN_LON = 149.165237
RETURN_ALT = 10

TAKEOFF_ALT = 10
HOLD_TIME = 10

# -------------------------
# Functions
# -------------------------

def set_mode(mode):
    print(f"Setting mode to {mode}...")
    mode_id = master.mode_mapping()[mode]
    master.mav.set_mode_send(
        master.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_id
    )
    time.sleep(3)

def arm():
    print("Arming...")
    master.arducopter_arm()
    master.motors_armed_wait()
    print("Armed")
    time.sleep(3)

def takeoff(alt):
    print(f"Taking off to {alt} meters...")
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0,
        0, 0, 0, 0,
        0, 0, alt
    )
    time.sleep(15)

def goto_location(lat, lon, alt):
    master.mav.set_position_target_global_int_send(
        0,
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        int(0b110111111000),
        int(lat * 1e7),
        int(lon * 1e7),
        alt,
        0, 0, 0,
        0, 0, 0,
        0, 0
    )

def get_position():
    msg = master.recv_match(type="GLOBAL_POSITION_INT", blocking=True)
    lat = msg.lat / 1e7
    lon = msg.lon / 1e7
    alt = msg.relative_alt / 1000.0
    return lat, lon, alt

def distance(lat1, lon1, lat2, lon2):
    return math.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2)

def send_waypoint_repeated(lat, lon, alt, seconds=10):
    print(f"Sending waypoint: lat={lat}, lon={lon}, alt={alt}m")
    for _ in range(seconds):
        goto_location(lat, lon, alt)
        time.sleep(1)

def wait_until_arrival(target_lat, target_lon, threshold=0.00002, timeout=90):
    print("Waiting to reach target...")
    start_time = time.time()

    while True:
        lat, lon, alt = get_position()
        dist = distance(lat, lon, target_lat, target_lon)

        print(f"Current: {lat:.7f}, {lon:.7f}, alt={alt:.1f}m | Distance: {dist:.7f}")

        if dist < threshold:
            print("Reached target")
            return True

        if time.time() - start_time > timeout:
            print("Timed out before reaching target")
            return False

        time.sleep(1)

def land():
    print("Landing...")
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_LAND,
        0,
        0, 0, 0, 0,
        0, 0, 0
    )

# -------------------------
# Mission execution
# -------------------------

print("Starting mission...")

set_mode("GUIDED")
arm()
takeoff(TAKEOFF_ALT)

send_waypoint_repeated(TARGET_LAT, TARGET_LON, TARGET_ALT, seconds=10)
reached_target = wait_until_arrival(TARGET_LAT, TARGET_LON)

if reached_target:
    print(f"Holding position for {HOLD_TIME} seconds...")
    time.sleep(HOLD_TIME)

send_waypoint_repeated(RETURN_LAT, RETURN_LON, RETURN_ALT, seconds=10)
wait_until_arrival(RETURN_LAT, RETURN_LON)

land()

print("Mission complete")
