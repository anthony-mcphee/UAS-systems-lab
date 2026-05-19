from pymavlink import mavutil

CONNECTION_STRING = "udpin:127.0.0.1:14551"

def connect_vehicle():
    print(f"Connecting to MAVLink stream on {CONNECTION_STRING}")

    master = mavutil.mavlink_connection(CONNECTION_STRING)

    print("Waiting for heartbeat...")
    master.wait_heartbeat()

    print("Heartbeat received")
    print(f"System ID: {master.target_system}")
    print(f"Component ID: {master.target_component}")

    return master

if __name__ == "__main__":
    connect_vehicle()
