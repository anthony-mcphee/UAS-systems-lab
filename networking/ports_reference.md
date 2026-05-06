# Port Reference

## Purpose

This document tracks telemetry ports and networking assignments used within the UAS Systems Lab.

---

# Current Port Assignments

| Port | Protocol | Purpose |
|---|---|---|
| 14550 | UDP | QGroundControl telemetry |
| 14551 | UDP | Python MAVLink scripts |

---

# Commands

## View Listening Ports

```bash
ss -tulnp
```

---

## Filter Specific Port

```bash
ss -tulnp | grep 14550
```

---

## Inspect Packet Traffic

```bash
tcpdump -i any port 14550
```

---

# Key Concepts

## Listener

A process waiting for incoming network traffic.

Examples:
- QGroundControl
- MAVProxy
- Python MAVLink scripts

---

## UDP

User Datagram Protocol.

Characteristics:
- fast
- lightweight
- no delivery guarantees
- commonly used for telemetry systems

---

## Localhost

```text
127.0.0.1
```

Represents communication occurring within the same machine.

---

# Lessons Learned

- telemetry systems depend heavily on correct port routing
- startup order affects listener availability
- port conflicts can interrupt telemetry flow
- packet visibility tools are important for troubleshooting
