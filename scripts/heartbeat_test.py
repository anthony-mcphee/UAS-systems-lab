import argparse

import yaml
from pymavlink import mavutil


def load_uri(config_path: str) -> str:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)["connection"]["uri"]


def connect_vehicle(uri: str):
    print(f"Connecting to {uri}...")
    master = mavutil.mavlink_connection(uri)

    print("Waiting for heartbeat...")
    master.wait_heartbeat()

    print("Heartbeat received")
    print(f"System ID: {master.target_system}")
    print(f"Component ID: {master.target_component}")

    return master


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MAVLink heartbeat test")
    parser.add_argument("--config", default="configs/config.yaml", help="Path to config YAML")
    args = parser.parse_args()

    uri = load_uri(args.config)
    connect_vehicle(uri)
