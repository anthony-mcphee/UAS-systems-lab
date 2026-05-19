from pymavlink import mavutil

master = mavutil.mavlink_connection("udpin:127.0.0.1:14551")

print("Waiting for heartbeat...")
master.wait_heartbeat()
print("Connected")

while True:
    msg = master.recv_match(type='GLOBAL_POSITION_INT', blocking=True)

    if msg:
        lat = msg.lat / 1e7
        lon = msg.lon / 1e7
        alt = msg.relative_alt / 1000

        print(f"Lat: {lat}")
        print(f"Lon: {lon}")
        print(f"Altitude: {alt} m")
        print("-----")
