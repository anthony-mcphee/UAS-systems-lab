cat > ~/drone-control/README.md << 'EOF'
# UAS Systems Lab Startup Workflow

## Purpose

This document standardizes startup and operational procedures for the UAS Systems Lab environment using:

- Ubuntu WSL
- ArduPilot SITL
- MAVProxy
- QGroundControl
- Python MAVLink control scripts

---

# System Architecture

\`\`\`text
ArduPilot SITL
        ↓
    MAVProxy
     ↙     ↘
QGroundControl   Python Script
   14550             14551
\`\`\`

---

# Startup Sequence

## 1. Open Ubuntu WSL

Launch Ubuntu terminal environment.

Verify no virtual environment is active.

---

## 2. Start ArduPilot SITL

Open **Terminal 1**:

\`\`\`bash
cd ~/ardupilot/ArduCopter
../Tools/autotest/sim_vehicle.py -v ArduCopter -f quad --no-mavproxy
\`\`\`

Expected Result:
- ArduCopter SITL starts
- TCP port 5760 opens
- Vehicle initializes successfully

Example Output:

\`\`\`text
SERIAL0 on TCP port 5760
Home: -35.363262 149.165237
\`\`\`

Leave this terminal running.

---

## 3. Start MAVProxy

Open **Terminal 2**:

\`\`\`bash
mavproxy.py --master=tcp:127.0.0.1:5760 --out=127.0.0.1:14550 --out=127.0.0.1:14551
\`\`\`

Purpose:
- Connect MAVProxy to SITL
- Route MAVLink telemetry

Port Usage:
- \`14550\` → QGroundControl
- \`14551\` → Python MAVLink scripts

Expected Result:

\`\`\`text
Detected vehicle 1:1
online system 1
MAV>
\`\`\`

Leave this terminal running.

---

## 4. Launch QGroundControl

Open **Terminal 3**:

If \`(venv)\` or \`(venv-ardupilot)\` appears:

\`\`\`bash
deactivate
\`\`\`

\`\`\`bash
cd ~
LIBGL_ALWAYS_SOFTWARE=1 ./QGroundControl-x86_64.AppImage
\`\`\`

Expected Result:
- Vehicle automatically connects
- Telemetry visible
- Vehicle displayed on map
- No communication errors

---

## 5. Verify MAVLink Telemetry

Confirm:
- heartbeat present
- GPS lock established
- telemetry values updating
- battery telemetry visible
- no disconnects

---

## 6. Activate Python Mission Environment

Open **Terminal 4**:

\`\`\`bash
cd ~/drone-control
source venv/bin/activate
\`\`\`

Expected Result:

\`\`\`bash
(venv)
\`\`\`

---

## 7. Verify Python MAVLink Connection

Run the heartbeat test script:

\`\`\`bash
python heartbeat_test.py
\`\`\`

Expected Result:
- Script connects successfully
- Heartbeat received
- QGroundControl remains connected

---

## 8. Execute Mission

Example mission sequence:
- set GUIDED mode
- arm vehicle
- takeoff
- waypoint navigation
- loiter
- return
- land

---

# Shutdown Procedure

Shutdown order:

## Terminal 4 (Python)

\`\`\`bash
Ctrl + C
deactivate
\`\`\`

---

## Terminal 3 (QGroundControl)

Close window normally.

If needed:

\`\`\`bash
pkill -f QGroundControl
\`\`\`

---

## Terminal 2 (MAVProxy)

\`\`\`bash
Ctrl + C
\`\`\`

---

## Terminal 1 (SITL)

\`\`\`bash
Ctrl + C
\`\`\`

---

# Common Failure Points

## Connection Refused

Possible Causes:
- SITL not started
- MAVProxy launched before SITL fully initialized
- TCP port 5760 unavailable

Verify:

\`\`\`bash
ss -tlnp | grep 5760
\`\`\`

---

## QGroundControl "Communication Lost"

Possible Causes:
- Python script using port 14550
- MAVProxy outputs misconfigured

Correct Configuration:

\`\`\`text
14550 → QGroundControl
14551 → Python script
\`\`\`

---

## MAVProxy Missing Modules

Install missing dependencies:

\`\`\`bash
python3 -m pip install --user MAVProxy future --break-system-packages
\`\`\`

---

## Wrong Virtual Environment

Rules:
- SITL → no venv
- MAVProxy → no venv
- QGroundControl → no venv
- Python scripts → project venv only

---

# Lessons Learned

- Separate MAVLink outputs prevent connection conflicts
- QGroundControl and Python scripts should never share the same UDP port
- Running all components inside Ubuntu WSL simplifies networking
- MAVProxy is more stable when launched manually
- Startup order matters:
  1. SITL
  2. MAVProxy
  3. QGroundControl
  4. Python scripts
EOF
