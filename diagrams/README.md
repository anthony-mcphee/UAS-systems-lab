# Diagrams

System architecture and data flow diagrams for the UAS Systems Lab.

## system_flow.txt

ASCII block diagram of the MAVLink telemetry routing architecture:

```
ArduPilot SITL → MAVProxy → QGroundControl (14550)
                          → Python scripts  (14551)
```

The key architectural point: MAVProxy acts as a telemetry multiplexer, allowing
both the GCS (QGroundControl) and the automation layer (Python scripts) to consume
the same MAVLink stream simultaneously on separate ports — without either client
interfering with the other.

This mirrors the separation between a crew chief's monitoring station and the
pilot's instruments in a manned aircraft: same data source, independent consumers,
no contention.
