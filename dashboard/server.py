"""Local-only, prototype Fall Guardian caregiver dashboard. No emergency calling."""

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit
import uuid

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "static"
MAX_BODY_SIZE = 4096
MAX_INCIDENTS = 50
HEARTBEAT_TIMEOUT = 12.0
STATE_LOCK = threading.Lock()
INCIDENTS = []
LAST_HEARTBEAT = None
HEARTBEAT = {"camera_online": False, "monitoring_active": False, "people_visible": 0}
LIVE_INPUT_SEEN = False


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def find_incident(event_id):
    return next((item for item in INCIDENTS if item["event_id"] == event_id), None)


def dashboard_state():
    with STATE_LOCK:
        fresh = LAST_HEARTBEAT is not None and time.monotonic() - LAST_HEARTBEAT < HEARTBEAT_TIMEOUT
        camera_online = fresh and HEARTBEAT["camera_online"]
        monitoring = camera_online and HEARTBEAT["monitoring_active"]
        alert = next((dict(item) for item in INCIDENTS if item["status"] in ("active", "escalated", "acknowledged")), None)
        return {
            "camera_status": "online" if camera_online else "offline",
            "monitoring_status": "active" if monitoring else "paused",
            "people_visible": HEARTBEAT["people_visible"] if fresh else None,
            "active_alert": alert,
            "safety_status": "alert" if alert and alert["status"] in ("active", "escalated") else "acknowledged" if alert else "safe" if monitoring else "unknown",
            "demo_mode": not LIVE_INPUT_SEEN,
            "incidents": [dict(item) for item in INCIDENTS],
            "server_time": now_iso(),
        }


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "FallGuardianPrototype/2.0"

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/state":
            return self._send_json(200, dashboard_state())
        relative = "index.html" if path == "/" else path.lstrip("/")
        target = (WEB_ROOT / relative).resolve()
        if WEB_ROOT.resolve() not in target.parents or not target.is_file():
            return self.send_error(404)
        content = target.read_bytes()
        content_type = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8"}.get(target.suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        path = urlsplit(self.path).path
        if path == "/api/events":
            return self._handle_event()
        if path == "/api/heartbeat":
            return self._handle_heartbeat()
        if path == "/api/alerts/acknowledge":
            return self._handle_acknowledgement()
        self._send_json(404, {"error": "Unknown endpoint"})

    def _read_json(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "Invalid Content-Length"})
            return None
        if not 1 <= size <= MAX_BODY_SIZE:
            self._send_json(400, {"error": "Invalid body size"})
            return None
        try:
            payload = json.loads(self.rfile.read(size))
        except (ValueError, UnicodeDecodeError):
            self._send_json(400, {"error": "Invalid JSON"})
            return None
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "Expected JSON object"})
            return None
        return payload

    def _handle_heartbeat(self):
        global LAST_HEARTBEAT, LIVE_INPUT_SEEN
        payload = self._read_json()
        if payload is None:
            return
        if not isinstance(payload.get("camera_online"), bool) or not isinstance(payload.get("monitoring_active"), bool):
            return self._send_json(400, {"error": "camera_online and monitoring_active must be booleans"})
        count = payload.get("people_visible", 0)
        if type(count) is not int or not 0 <= count <= 20:
            return self._send_json(400, {"error": "people_visible must be an integer between 0 and 20"})
        with STATE_LOCK:
            LAST_HEARTBEAT = time.monotonic()
            HEARTBEAT.update({"camera_online": payload["camera_online"], "monitoring_active": payload["monitoring_active"], "people_visible": count})
            LIVE_INPUT_SEEN = True
        self._send_json(200, {"ok": True})

    def _handle_event(self):
        global LIVE_INPUT_SEEN
        payload = self._read_json()
        if payload is None:
            return
        kind = payload.get("event_type")
        if kind not in ("fall_detected", "caregiver_alert", "person_safe", "manual_clear"):
            return self._send_json(400, {"error": "Unrecognized event_type"})
        event_id = payload.get("event_id")
        if event_id is None and kind == "fall_detected":
            event_id = uuid.uuid4().hex
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 80:
            return self._send_json(400, {"error": "event_id is required and must be a short string"})
        source = payload.get("source", "fall_detector")
        reason = payload.get("reason", "Possible fall")
        person_id = payload.get("person_id")
        demo = payload.get("demo", source == "demo")
        if not isinstance(source, str) or not 1 <= len(source) <= 80 or not isinstance(reason, str) or len(reason) > 200:
            return self._send_json(400, {"error": "Invalid source or reason"})
        if not isinstance(demo, bool) or (person_id is not None and (type(person_id) is not int or person_id < 1)):
            return self._send_json(400, {"error": "Invalid demo flag or person_id"})
        with STATE_LOCK:
            incident = find_incident(event_id)
            if kind == "fall_detected":
                if incident is None:
                    incident = {"id": uuid.uuid4().hex, "event_id": event_id, "event_type": "Fall detected", "timestamp": now_iso(), "source": source, "demo": demo, "reason": reason, "person_id": person_id, "status": "active", "acknowledged_at": None, "resolved_at": None, "resolution": None, "escalation": None}
                    INCIDENTS.insert(0, incident)
                    del INCIDENTS[MAX_INCIDENTS:]
                    if not demo:
                        LIVE_INPUT_SEEN = True
                status_code = 201
            elif incident is None:
                status_code = 404
            elif kind == "caregiver_alert":
                if incident["status"] == "active":
                    incident["status"] = "escalated"
                    incident["escalation"] = reason
                status_code = 200
            else:
                if incident["status"] != "resolved":
                    incident["status"] = "resolved"
                    incident["resolved_at"] = now_iso()
                    incident["resolution"] = "Voice confirmed safe" if kind == "person_safe" else "Manually cleared"
                status_code = 200
            snapshot = dict(incident) if incident else None
        if snapshot is None:
            return self._send_json(404, {"error": "No matching incident. Start the dashboard before the fall detector."})
        self._send_json(status_code, {"incident": snapshot, "state": dashboard_state()})

    def _handle_acknowledgement(self):
        payload = self._read_json()
        if payload is None:
            return
        with STATE_LOCK:
            incident = next((i for i in INCIDENTS if i["status"] in ("active", "escalated")), None)
            if incident is not None:
                incident["status"] = "acknowledged"
                incident["acknowledged_at"] = now_iso()
        if incident is None:
            return self._send_json(409, {"error": "There is no active alert to acknowledge"})
        self._send_json(200, {"state": dashboard_state()})

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8000), DashboardHandler)
    print("Fall Guardian prototype dashboard: http://127.0.0.1:8000")
    print("Start this on the SAME laptop as multi_fall_test.py. No notifications or emergency calls are sent.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping dashboard.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
