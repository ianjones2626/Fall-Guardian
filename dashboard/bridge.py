"""Non-blocking local dashboard event publisher for the camera loop."""

import json
import os
import queue
import threading
import time
from urllib.request import Request, urlopen


class DashboardBridge:
    def __init__(self):
        # Localhost is intentional: the dashboard is a hackathon prototype,
        # not an authenticated public notification service.
        self.base_url = os.environ.get("FG_DASHBOARD_URL", "http://127.0.0.1:8000").rstrip("/")
        self.messages = queue.Queue(maxsize=128)
        self.last_heartbeat = 0.0
        self.last_error = 0.0
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def _enqueue(self, endpoint, data):
        try:
            self.messages.put_nowait((endpoint, data))
        except queue.Full:
            print("Dashboard queue full; an event could not be reported")

    def event(self, event_type, **details):
        self._enqueue("/api/events", {"event_type": event_type, "source": "fall_detector", **details})

    def heartbeat(self, visible_people=0, camera_online=True, monitoring_active=True, force=False):
        now = time.monotonic()
        if not force and now - self.last_heartbeat < 2.0:
            return
        self.last_heartbeat = now
        self._enqueue("/api/heartbeat", {"camera_online": bool(camera_online), "monitoring_active": bool(monitoring_active), "people_visible": int(visible_people)})

    def _run(self):
        while True:
            message = self.messages.get()
            try:
                if message is None:
                    return
                endpoint, data = message
                body = json.dumps(data).encode("utf-8")
                req = Request(self.base_url + endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(req, timeout=1.5) as response:
                    response.read()
            except Exception as error:
                # Never block fall-detection frames just because the dashboard is down.
                now = time.monotonic()
                if now - self.last_error > 12:
                    print(f"Dashboard not reachable at {self.base_url}: {error}")
                    print("Run python dashboard/server.py on this laptop before starting the camera")
                    self.last_error = now
            finally:
                self.messages.task_done()

    def close(self):
        # Flush queued events on normal exit when the server is available.
        try:
            self.messages.put_nowait(None)
        except queue.Full:
            return
        self.worker.join(timeout=2.0)
