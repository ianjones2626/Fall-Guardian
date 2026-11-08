"""Local Fall Guardian caregiver dashboard server."""

from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit
import uuid


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "static"
MAX_BODY_SIZE = 4096
MAX_INCIDENTS = 50
STATE_LOCK = threading.Lock()


def current_time() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def make_incident(
    event_type: str,
    occurred_at: datetime,
    source: str,
    demo: bool,
    status: str = "logged",
) -> dict[str, object]:
    return {
        "id": uuid.uuid4().hex,
        "event_type": event_type,
        "timestamp": isoformat(occurred_at),
        "source": source,
        "demo": demo,
        "status": status,
        "acknowledged_at": None,
    }


started_at = current_time()
INCIDENTS: list[dict[str, object]] = [
    make_incident("System check", started_at - timedelta(minutes=18), "demo", True),
    make_incident(
        "Fall detected",
        started_at - timedelta(hours=2, minutes=14),
        "demo",
        True,
        "acknowledged",
    ),
    make_incident("Monitoring started", started_at - timedelta(hours=6), "demo", True),
]
ACTIVE_ALERT: dict[str, object] | None = None
DEMO_MODE = True


def dashboard_state() -> dict[str, object]:
    with STATE_LOCK:
        alert = dict(ACTIVE_ALERT) if ACTIVE_ALERT else None
        return {
            "camera_status": "online",
            "monitoring_status": "active",
            "active_alert": alert,
            "safety_status": (
                "alert"
                if alert and alert["status"] == "active"
                else "acknowledged"
                if alert
                else "safe"
            ),
            "demo_mode": DEMO_MODE,
            "incidents": [dict(incident) for incident in INCIDENTS],
            "server_time": isoformat(current_time()),
        }


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "FallGuardianDashboard/1.0"

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/state":
            self._send_json(200, dashboard_state())
            return

        relative_path = "index.html" if path == "/" else path.lstrip("/")
        requested_file = (WEB_ROOT / relative_path).resolve()
        if WEB_ROOT.resolve() not in requested_file.parents:
            self.send_error(404)
            return
        if not requested_file.is_file():
            self.send_error(404)
            return

        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
        }.get(requested_file.suffix, "application/octet-stream")
        content = requested_file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/events":
            self._handle_event()
        elif path == "/api/alerts/acknowledge":
            self._handle_acknowledgement()
        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def _read_json(self) -> dict[str, object] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "Invalid Content-Length"})
            return None
        if length < 1 or length > MAX_BODY_SIZE:
            self._send_json(400, {"error": "Request body must be between 1 and 4096 bytes"})
            return None
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "Request body must be valid JSON"})
            return None
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "Request body must be a JSON object"})
            return None
        return payload

    def _handle_event(self) -> None:
        global ACTIVE_ALERT, DEMO_MODE
        payload = self._read_json()
        if payload is None:
            return
        if payload.get("event_type") != "fall_detected":
            self._send_json(400, {"error": "event_type must be 'fall_detected'"})
            return

        source = payload.get("source", "fall_detector")
        if not isinstance(source, str) or not source.strip() or len(source) > 80:
            self._send_json(400, {"error": "source must be a non-empty string of at most 80 characters"})
            return

        occurred_at = current_time()
        supplied_timestamp = payload.get("timestamp")
        if supplied_timestamp is not None:
            if not isinstance(supplied_timestamp, str):
                self._send_json(400, {"error": "timestamp must be an ISO 8601 string"})
                return
            try:
                occurred_at = datetime.fromisoformat(supplied_timestamp.replace("Z", "+00:00"))
                if occurred_at.tzinfo is None:
                    occurred_at = occurred_at.replace(tzinfo=timezone.utc)
            except ValueError:
                self._send_json(400, {"error": "timestamp must be a valid ISO 8601 datetime"})
                return

        is_demo = source.strip().lower() == "demo"
        incident = make_incident("Fall detected", occurred_at, source.strip(), is_demo, "active")
        with STATE_LOCK:
            INCIDENTS.insert(0, incident)
            del INCIDENTS[MAX_INCIDENTS:]
            ACTIVE_ALERT = dict(incident)
            if not is_demo:
                DEMO_MODE = False

        self._send_json(201, {"incident": incident, "state": dashboard_state()})

    def _handle_acknowledgement(self) -> None:
        global ACTIVE_ALERT
        with STATE_LOCK:
            if ACTIVE_ALERT is None or ACTIVE_ALERT["status"] != "active":
                self._send_json(409, {"error": "There is no active alert to acknowledge"})
                return
            acknowledged_at = isoformat(current_time())
            ACTIVE_ALERT["status"] = "acknowledged"
            ACTIVE_ALERT["acknowledged_at"] = acknowledged_at
            for incident in INCIDENTS:
                if incident["id"] == ACTIVE_ALERT["id"]:
                    incident["status"] = "acknowledged"
                    incident["acknowledged_at"] = acknowledged_at
                    break
        self._send_json(200, {"state": dashboard_state()})

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


def main() -> None:
    host = "127.0.0.1"
    port = 8000
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Fall Guardian dashboard: http://{host}:{port}")
    print("Demo data is active. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
