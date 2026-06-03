"""
beacon_follower.py
==================
ArduPilot MAVLink beacon-follow state machine.

Features
--------
- Config file (config.yaml) for all tunable parameters
- Structured logging to file + console (logs/ directory)
- Swappable beacon source: simulated | UDP | serial/NMEA
- Mission replay via --replay <logfile>
- Clean shutdown on Ctrl-C

Usage
-----
  python beacon_follower.py                        # uses config.yaml
  python beacon_follower.py --config my.yaml       # custom config
  python beacon_follower.py --replay logs/foo.csv  # replay a log
"""

import argparse
import csv
import logging
import math
import os
import select
import socket
import sys
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import yaml
from pymavlink import mavutil

# ============================================================
# Logging setup
# ============================================================

def setup_logging(log_dir: str, level_str: str) -> logging.Logger:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(log_dir) / f"beacon_{timestamp}.log"

    level = getattr(logging, level_str.upper(), logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )

    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    logger = logging.getLogger("beacon_follower")
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info(f"Logging to {log_path}")
    return logger


# ============================================================
# Config loading
# ============================================================

def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


# ============================================================
# Beacon sources  (Strategy pattern — swap without touching core)
# ============================================================

class BeaconSource(ABC):
    """All beacon sources must implement get() → (lat, lon) or None."""

    @abstractmethod
    def get(self) -> tuple[float, float] | None:
        ...

    def close(self):
        pass


class SimulatedBeacon(BeaconSource):
    """Circular motion around home — mirrors original behaviour."""

    def __init__(self, home_lat: float, home_lon: float):
        self._home_lat = home_lat
        self._home_lon = home_lon
        self._start = time.time()

    def get(self) -> tuple[float, float]:
        t = time.time() - self._start
        lat = self._home_lat + 0.00025 * math.sin(t / 20)
        lon = self._home_lon + 0.00025 * math.cos(t / 20)
        return lat, lon


class UDPBeacon(BeaconSource):
    """
    Listens on UDP for newline-delimited "lat,lon" strings.
    e.g.  echo "-35.363,149.165" | nc -u 127.0.0.1 5005
    Thread-safe: background thread updates latest fix.
    """

    def __init__(self, host: str, port: int, logger: logging.Logger):
        self._logger = logger
        self._latest: tuple[float, float] | None = None
        self._lock = threading.Lock()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((host, port))
        self._sock.settimeout(1.0)
        self._running = True
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()
        logger.info(f"UDP beacon listening on {host}:{port}")

    def _recv_loop(self):
        while self._running:
            try:
                data, _ = self._sock.recvfrom(256)
                lat_s, lon_s = data.decode().strip().split(",")
                fix = float(lat_s), float(lon_s)
                with self._lock:
                    self._latest = fix
            except (socket.timeout, ValueError):
                pass
            except Exception as e:
                self._logger.warning(f"UDP recv error: {e}")

    def get(self) -> tuple[float, float] | None:
        with self._lock:
            return self._latest

    def close(self):
        self._running = False
        self._sock.close()


class SerialNMEABeacon(BeaconSource):
    """
    Reads NMEA GGA/RMC sentences from a serial port.
    Requires: pip install pyserial
    Thread-safe: background thread updates latest fix.
    """

    def __init__(self, port: str, baudrate: int, logger: logging.Logger):
        import serial  # lazy import — only needed for this source
        self._logger = logger
        self._latest: tuple[float, float] | None = None
        self._lock = threading.Lock()
        self._ser = serial.Serial(port, baudrate, timeout=1)
        self._running = True
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()
        logger.info(f"Serial beacon on {port} @ {baudrate} baud")

    def _nmea_to_decimal(self, raw: str, direction: str) -> float:
        """Convert NMEA ddmm.mmmm + N/S/E/W to signed decimal degrees."""
        dot = raw.index(".")
        degrees = float(raw[:dot - 2])
        minutes = float(raw[dot - 2:])
        decimal = degrees + minutes / 60.0
        if direction in ("S", "W"):
            decimal = -decimal
        return decimal

    def _recv_loop(self):
        while self._running:
            try:
                line = self._ser.readline().decode("ascii", errors="ignore").strip()
                if not line.startswith(("$GPGGA", "$GPRMC", "$GNGGA", "$GNRMC")):
                    continue
                parts = line.split(",")
                # GGA: lat=2, lat_dir=3, lon=4, lon_dir=5
                # RMC: lat=3, lat_dir=4, lon=5, lon_dir=6
                if "GGA" in parts[0]:
                    lat = self._nmea_to_decimal(parts[2], parts[3])
                    lon = self._nmea_to_decimal(parts[4], parts[5])
                else:  # RMC
                    if parts[2] != "A":  # status must be Active
                        continue
                    lat = self._nmea_to_decimal(parts[3], parts[4])
                    lon = self._nmea_to_decimal(parts[5], parts[6])
                with self._lock:
                    self._latest = (lat, lon)
            except Exception as e:
                self._logger.debug(f"Serial parse error: {e}")

    def get(self) -> tuple[float, float] | None:
        with self._lock:
            return self._latest

    def close(self):
        self._running = False
        self._ser.close()


class ReplayBeacon(BeaconSource):
    """
    Replays beacon positions from a previously recorded CSV log.
    CSV columns expected: timestamp, beacon_lat, beacon_lon, ...
    Plays back in real-time based on elapsed timestamps.
    """

    def __init__(self, csv_path: str, logger: logging.Logger):
        self._logger = logger
        self._frames: list[tuple[float, float, float]] = []  # (t, lat, lon)
        self._idx = 0
        self._start = time.time()

        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            t0 = None
            for row in reader:
                t = float(row["elapsed_sec"])
                if t0 is None:
                    t0 = t
                self._frames.append((t - t0, float(row["beacon_lat"]), float(row["beacon_lon"])))

        logger.info(f"Replay loaded: {len(self._frames)} frames from {csv_path}")

    def get(self) -> tuple[float, float] | None:
        elapsed = time.time() - self._start
        # Advance frame pointer to the last frame whose timestamp ≤ elapsed
        while self._idx + 1 < len(self._frames) and self._frames[self._idx + 1][0] <= elapsed:
            self._idx += 1
        if self._frames:
            _, lat, lon = self._frames[self._idx]
            return lat, lon
        return None


def build_beacon_source(cfg: dict, logger: logging.Logger, replay_path: str | None) -> BeaconSource:
    if replay_path:
        return ReplayBeacon(replay_path, logger)

    source = cfg["beacon"]["source"]
    home_lat = cfg["home"]["lat"]
    home_lon = cfg["home"]["lon"]

    if source == "simulate":
        logger.info("Beacon source: simulated")
        return SimulatedBeacon(home_lat, home_lon)
    elif source == "udp":
        udp = cfg["beacon"]["udp"]
        return UDPBeacon(udp["host"], udp["port"], logger)
    elif source == "serial":
        ser = cfg["beacon"]["serial"]
        return SerialNMEABeacon(ser["port"], ser["baudrate"], logger)
    else:
        raise ValueError(f"Unknown beacon source: {source!r}")


# ============================================================
# Telemetry CSV logger
# ============================================================

class TelemetryLogger:
    """Appends one CSV row per loop iteration for replay and analysis."""

    FIELDS = [
        "elapsed_sec", "state",
        "drone_lat", "drone_lon", "drone_alt",
        "beacon_lat", "beacon_lon",
        "dist_to_beacon_m"
    ]

    def __init__(self, log_dir: str):
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._path = Path(log_dir) / f"telem_{timestamp}.csv"
        self._f = open(self._path, "w", newline="")
        self._writer = csv.DictWriter(self._f, fieldnames=self.FIELDS)
        self._writer.writeheader()

    def write(self, row: dict):
        self._writer.writerow(row)
        self._f.flush()

    def close(self):
        self._f.close()

    @property
    def path(self):
        return self._path


# ============================================================
# MAVLink vehicle wrapper
# ============================================================

class Vehicle:
    def __init__(self, uri: str, logger: logging.Logger):
        self._log = logger
        self._log.info(f"Connecting: {uri}")
        self.master = mavutil.mavlink_connection(uri)
        self._log.info("Waiting for heartbeat...")
        self.master.wait_heartbeat()
        self._log.info(
            f"Connected — system {self.master.target_system}, "
            f"component {self.master.target_component}"
        )

    def set_mode(self, mode: str):
        mode_id = self.master.mode_mapping()[mode]
        self.master.mav.set_mode_send(
            self.master.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id
        )
        self._log.info(f"Mode set: {mode}")
        time.sleep(2)

    def arm(self):
        self._log.info("Arming...")
        self.master.arducopter_arm()
        self.master.motors_armed_wait()
        self._log.info("Armed")

    def takeoff(self, alt: float):
        self._log.info(f"Takeoff to {alt} m")
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0, 0, 0, 0, 0, 0, 0, alt
        )
        time.sleep(15)

    def goto_gps(self, lat: float, lon: float, alt: float):
        self.master.mav.set_position_target_global_int_send(
            0,
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            int(0b110111111000),
            int(lat * 1e7),
            int(lon * 1e7),
            alt,
            0, 0, 0,
            0, 0, 0,
            0, 0
        )

    def get_position(self) -> tuple[float, float, float] | None:
        msg = self.master.recv_match(
            type="GLOBAL_POSITION_INT", blocking=True, timeout=1
        )
        if msg is None:
            return None
        return msg.lat / 1e7, msg.lon / 1e7, msg.relative_alt / 1000.0

    def land(self):
        self._log.info("Landing...")
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0, 0, 0, 0, 0, 0, 0, 0
        )

    def rtl(self):
        self._log.info("RTL commanded")
        self.set_mode("RTL")


# ============================================================
# Geometry
# ============================================================

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ============================================================
# Keyboard input (non-blocking)
# ============================================================

def keyboard_command() -> str | None:
    if select.select([sys.stdin], [], [], 0)[0]:
        return sys.stdin.readline().strip().lower()
    return None


COMMAND_HELP = """
Commands
--------
  f  — follow beacon
  h  — hold current position
  d  — descend on beacon (staged)
  r  — return to launch
  l  — land now
  q  — quit script (no new command sent)
"""


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Beacon follower state machine")
    parser.add_argument("--config", default="config.yaml", help="Path to config YAML")
    parser.add_argument("--replay", default=None, help="Path to telemetry CSV to replay")
    args = parser.parse_args()

    cfg = load_config(args.config)

    log_dir = cfg["logging"]["log_dir"]
    log_level = cfg["logging"]["level"]
    logger = setup_logging(log_dir, log_level)

    beacon = build_beacon_source(cfg, logger, args.replay)
    telem_log = TelemetryLogger(log_dir)
    logger.info(f"Telemetry CSV: {telem_log.path}")

    vehicle = Vehicle(cfg["connection"]["uri"], logger)

    # Unpack config
    follow_alt       = cfg["altitudes"]["follow"]
    descend_alt_high = cfg["altitudes"]["descend_high"]
    descend_alt_low  = cfg["altitudes"]["descend_low"]
    takeoff_alt      = cfg["altitudes"]["takeoff"]
    follow_radius    = cfg["follow"]["radius_m"]
    update_rate      = cfg["follow"]["update_rate_sec"]

    print(COMMAND_HELP)

    vehicle.set_mode("GUIDED")
    vehicle.arm()
    vehicle.takeoff(takeoff_alt)

    state = "FOLLOW_BEACON"
    hold_position: tuple[float, float, float] | None = None
    start_time = time.time()

    try:
        while True:
            elapsed = time.time() - start_time

            # --- keyboard input ---
            cmd = keyboard_command()
            if cmd == "f":
                state = "FOLLOW_BEACON"
                logger.info("State → FOLLOW_BEACON")
            elif cmd == "h":
                pos = vehicle.get_position()
                if pos:
                    hold_position = pos
                    state = "HOLD_POSITION"
                    logger.info(f"State → HOLD_POSITION @ {pos}")
                else:
                    logger.warning("Hold requested but no position fix.")
            elif cmd == "d":
                state = "DESCEND_ON_BEACON"
                logger.info("State → DESCEND_ON_BEACON")
            elif cmd == "r":
                state = "RETURN_TO_LAUNCH"
                logger.info("State → RETURN_TO_LAUNCH")
            elif cmd == "l":
                state = "LAND"
                logger.info("State → LAND")
            elif cmd == "q":
                logger.info("Quit requested by operator.")
                break

            # --- beacon fix ---
            beacon_fix = beacon.get()
            if beacon_fix is None:
                logger.warning("No beacon fix — holding last command.")
                time.sleep(update_rate)
                continue
            beacon_lat, beacon_lon = beacon_fix

            # --- vehicle position ---
            current = vehicle.get_position()
            if current is None:
                logger.warning("No vehicle position update.")
                time.sleep(update_rate)
                continue
            current_lat, current_lon, current_alt = current

            dist = haversine(current_lat, current_lon, beacon_lat, beacon_lon)

            logger.info(
                f"state={state} | beacon=({beacon_lat:.7f},{beacon_lon:.7f}) | "
                f"alt={current_alt:.1f}m | dist={dist:.1f}m"
            )

            # --- telemetry CSV row ---
            telem_log.write({
                "elapsed_sec":    round(elapsed, 2),
                "state":          state,
                "drone_lat":      round(current_lat, 7),
                "drone_lon":      round(current_lon, 7),
                "drone_alt":      round(current_alt, 2),
                "beacon_lat":     round(beacon_lat, 7),
                "beacon_lon":     round(beacon_lon, 7),
                "dist_to_beacon_m": round(dist, 2),
            })

            # --- state machine ---
            if state == "FOLLOW_BEACON":
                vehicle.goto_gps(beacon_lat, beacon_lon, follow_alt)

            elif state == "HOLD_POSITION":
                if hold_position:
                    vehicle.goto_gps(*hold_position)

            elif state == "DESCEND_ON_BEACON":
                if dist > follow_radius:
                    vehicle.goto_gps(beacon_lat, beacon_lon, follow_alt)
                elif current_alt > descend_alt_high:
                    logger.info("Over beacon — descending to high waypoint.")
                    vehicle.goto_gps(beacon_lat, beacon_lon, descend_alt_high)
                elif current_alt > descend_alt_low:
                    logger.info("Descending to low waypoint.")
                    vehicle.goto_gps(beacon_lat, beacon_lon, descend_alt_low)
                else:
                    logger.info("Low alt reached — landing.")
                    vehicle.land()
                    break

            elif state == "RETURN_TO_LAUNCH":
                vehicle.rtl()
                break

            elif state == "LAND":
                vehicle.land()
                break

            time.sleep(update_rate)

    except KeyboardInterrupt:
        logger.warning("Keyboard interrupt — commanding RTL as safety fallback.")
        vehicle.rtl()

    finally:
        beacon.close()
        telem_log.close()
        logger.info("State machine stopped.")


if __name__ == "__main__":
    main()
