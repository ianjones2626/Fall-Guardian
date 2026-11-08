# Fall Guardian Dashboard

A lightweight caregiver dashboard prototype built with Python's standard library and static HTML, CSS, and JavaScript. No packages need to be installed.

## Run locally

1. Open a terminal in the Fall-Guardian repository.
2. Start the dashboard:

   ```powershell
   python .\dashboard\server.py
   ```

   If `python` is not available on your PATH, try `py .\dashboard\server.py`.
3. Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in a browser.
4. Click **Simulate fall** to display a red fall alert.
5. Click **Acknowledge alert** to acknowledge it. The alert remains visible as acknowledged, and the event stays in the incident history.
6. Press **Ctrl+C** in the terminal to stop the server.

The initial status and incident history are sample data and are labeled **DEMO DATA**. Simulated events are individually marked **DEMO**. This prototype does not contact emergency services or send notifications.

## Fall detector integration

The server exposes a same-origin JSON endpoint for a Python detector running on the same machine:

```python
import json
from urllib.request import Request, urlopen

payload = json.dumps({
    "event_type": "fall_detected",
    "source": "fall_detector",
}).encode("utf-8")
request = Request(
    "http://127.0.0.1:8000/api/events",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urlopen(request, timeout=3) as response:
    print(response.status, response.read().decode("utf-8"))
```

`POST /api/events` accepts:

| Field | Required | Description |
|---|---|---|
| `event_type` | Yes | Currently `fall_detected` |
| `source` | No | Source label; defaults to `fall_detector`. Use `demo` for simulated events. |
| `timestamp` | No | ISO 8601 event time; defaults to the server's current time. |

Successful events return `201` with the incident and updated dashboard state. Non-demo events switch the header from **DEMO DATA** to **DETECTOR EVENT**; demo entries remain individually labeled. `GET /api/state` returns current camera/monitoring/safety statuses, the active alert, and recent incidents. `POST /api/alerts/acknowledge` acknowledges an active alert and returns the updated state (or `409` if there is no active alert).

The camera and monitoring statuses are placeholders in this prototype; wire them to the relevant system components when integrating the detector. State is held in memory and resets when the server restarts. The server binds to `127.0.0.1` and is intended for local demos, not network deployment.
