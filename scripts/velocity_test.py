"""
Velocity command test for ArduPilot SITL.
Purpose:
- Connect to MAVLink telemetry
- Set GUIDED mode with confirmation
- Arm the vehicle
- Take off and verify altitude reached
- Send velocity commands using SET_POSITION_TARGET_LOCAL_NED at 10Hz
- Log actual vs commanded velocity via LOCAL_POSITION_NED
- Test forward, lateral, vertical, and diagonal movement
- Stop movement
- Return to launch location and land
Environment:
- ArduPilot SITL running
- MAVProxy routing telemetry to UDP port 14551
- Python virtual environment active
"""

from pymavlink import mavutil
import time

CONNECTION_STRING = "udpin:127.0.0.1:14551"
TAKEOFF_ALT = 10
TAKEOFF_TIMEOUT = 20
MODE_TIMEOUT = 5
ACK_TIMEOUT = 5
ALT_TOLERANCE = 1.0
COMMAND_RATE_HZ = 10
RTL_TIMEOUT = 30


def connect_vehicle():
    print(f"Connecting to MAVLink stream on {CONNECTION_STRING}")
    master = mavutil.mavlink_connection(CONNECTION_STRING)
    print("Waiting for heartbeat...")
    master.wait_heartbeat()
    print(f"Heartbeat received — System ID: {master.target_system}, Component ID: {master.target_component}")
    return master


def wait_for_ack(master, command, timeout=ACK_TIMEOUT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = master.recv_match(type="COMMAND_ACK", blocking=False)
        if msg and msg.command == command:
            if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                print(f"ACK received: command {command} ACCEPTED")
                return True
            else:
                print(f"ACK received: command {command} REJECTED (result={msg.result})")
                return False
        time.sleep(0.05)
    print(f"ACK timeout: no response for command {command} within {timeout}s")
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
    print(f"Mode command sent: {mode}, waiting for confirmation...")

    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = master.recv_match(type="HEARTBEAT", blocking=False)
        if msg:
            current_mode = mavutil.mode_string_v10(msg)
            if current_mode == mode:
                print(f"Mode confirmed: {mode}")
                return True
        time.sleep(0.1)

    print(f"Mode change to {mode} not confirmed within {timeout}s")
    return False


def arm(master):
    print("Arming vehicle...")
    master.arducopter_arm()
    master.motors_armed_wait()
    print("Vehicle armed")
    time.sleep(1)


def takeoff(master, altitude, timeout=TAKEOFF_TIMEOUT):
    print(f"Sending takeoff command to {altitude}m...")
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0, 0, 0, 0, 0, 0, 0,
        altitude,
    )

    if not wait_for_ack(master, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF):
        print("Takeoff command rejected — aborting")
        return False

    print(f"Climbing to {altitude}m, waiting...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = master.recv_match(type="GLOBAL_POSITION_INT", blocking=False)
        if msg:
            current_alt = msg.relative_alt / 1000.0
            print(f"  Altitude: {current_alt:.1f}m", end="\r")
            if abs(current_alt - altitude) <= ALT_TOLERANCE:
                print(f"\nTarget altitude reached: {current_alt:.1f}m")
                return True
        time.sleep(0.2)

    print(f"\nTakeoff timeout — altitude not reached within {timeout}s")
    return False


def get_local_velocity(master):
    msg = master.recv_match(type="LOCAL_POSITION_NED", blocking=False)
    if msg:
        return msg.vx, msg.vy, msg.vz
    return None


def send_velocity(master, vx, vy, vz, duration, label=""):
    tag = f"[{label}] " if label else ""
    print(f"{tag}Commanding velocity: vx={vx}, vy={vy}, vz={vz} m/s for {duration}s")

    interval = 1.0 / COMMAND_RATE_HZ
    start = time.time()

    while time.time() - start < duration:
        master.mav.set_position_target_local_ned_send(
            0,
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            0b0000111111000111,
            0, 0, 0,
            vx, vy, vz,
            0, 0, 0,
            0, 0,
        )

        actual = get_local_velocity(master)
        if actual:
            ax, ay, az = actual
            print(
                f"  CMD: ({vx:+.1f}, {vy:+.1f}, {vz:+.1f}) | "
                f"ACT: ({ax:+.1f}, {ay:+.1f}, {az:+.1f}) m/s"
            )

        time.sleep(interval)


def stop_vehicle(master, duration=3):
    print("Stopping vehicle...")
    send_velocity(master, 0, 0, 0, duration, label="STOP")


def return_to_launch(master, timeout=RTL_TIMEOUT):
    print("Returning to launch...")
    if not set_mode(master, "RTL"):
        print("Failed to set RTL mode — aborting RTL")
        return False

    print("RTL mode set, waiting for vehicle to descend and land...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = master.recv_match(type="GLOBAL_POSITION_INT", blocking=False)
        if msg:
            current_alt = msg.relative_alt / 1000.0
            print(f"  Altitude: {current_alt:.1f}m", end="\r")
            if current_alt <= 0.5:
                print(f"\nVehicle returned and landed")
                return True
        time.sleep(0.2)

    print(f"\nRTL timeout — vehicle may still be descending")
    return False


def main():
    master = connect_vehicle()

    if not set_mode(master, "GUIDED"):
        print("Failed to set GUIDED mode — aborting")
        return

    arm(master)

    if not takeoff(master, TAKEOFF_ALT):
        print("Takeoff failed — aborting")
        return

    # Cardinal axes
    send_velocity(master, vx=2,  vy=0,  vz=0,  duration=5, label="NORTH")
    stop_vehicle(master)

    send_velocity(master, vx=0,  vy=2,  vz=0,  duration=5, label="EAST")
    stop_vehicle(master)

    send_velocity(master, vx=-2, vy=0,  vz=0,  duration=5, label="SOUTH")
    stop_vehicle(master)

    send_velocity(master, vx=0,  vy=-2, vz=0,  duration=5, label="WEST")
    stop_vehicle(master)

    # Vertical
    send_velocity(master, vx=0,  vy=0,  vz=-1, duration=4, label="UP")
    stop_vehicle(master)

    send_velocity(master, vx=0,  vy=0,  vz=1,  duration=4, label="DOWN")
    stop_vehicle(master)

    # Diagonal
    send_velocity(master, vx=2,  vy=2,  vz=0,  duration=5, label="NE DIAGONAL")
    stop_vehicle(master)

    # Full 3D
    send_velocity(master, vx=2,  vy=1,  vz=-0.5, duration=5, label="3D COMBINED")
    stop_vehicle(master)

    return_to_launch(master)
    print("\nVelocity test complete")


if __name__ == "__main__":
    main()
