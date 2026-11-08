"""Apply safe targeted changes to existing Fall Guardian code."""

from pathlib import Path
import shutil
import hashlib
import zlib
import base64
import json
import tempfile
import sys


def once(text, old, new, name):
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{name}: expected code block {old[:65]!r} exactly once, found {count}. Ian may have edited this file. No files were changed.")
    return text.replace(old, new, 1)


def patch_multi(text):
    name = "multi_fall_test.py"
    # Already installed? Detect rather than duplicate initialization.
    if "from dashboard.bridge import DashboardBridge" in text:
        raise ValueError("multi_fall_test.py is already integrated; refusing to install twice.")
    text = once(text, "import queue\n", "import queue\nimport uuid\n", name)
    text = once(text, "from audio_test import start_voice_check\n", "from audio_test import start_voice_check\nfrom dashboard.bridge import DashboardBridge\n", name)
    text = once(text, "alerts = {}\naudio_results = queue.Queue()", "alerts = {}\ndashboard = DashboardBridge()\naudio_results = queue.Queue()", name)
    text = once(text,
        'alerts[person_id] = {"since": now, "reason": reason, "notified": False}\n        print(f"ALERT: Person {person_id}: {reason}")',
        'event_id = uuid.uuid4().hex\n        alerts[person_id] = {"since": now, "reason": reason, "notified": False, "event_id": event_id}\n        dashboard.event("fall_detected", event_id=event_id, person_id=person_id, reason=reason, demo=(reason == "Manual test"))\n        print(f"ALERT: Person {person_id}: {reason}")', name)
    text = once(text, '        if not ok:\n            print("Video disconnected")\n            break',
        '        if not ok:\n            print("Video disconnected")\n            dashboard.heartbeat(camera_online=False, monitoring_active=False, force=True)\n            break', name)
    text = once(text, '        # Associate new detections with existing people by hip position.\n',
        '        # Report live status without slowing down frame processing.\n        dashboard.heartbeat(visible_people=len(people))\n\n        # Associate new detections with existing people by hip position.\n', name)
    text = once(text, '                    alerts.pop(person_id)\n                    audio_attempted.discard(person_id)',
        '                    resolved_alert = alerts.pop(person_id)\n                    dashboard.event("person_safe", event_id=resolved_alert["event_id"], person_id=person_id, reason="Confirmed by voice")\n                    audio_attempted.discard(person_id)', name)
    text = once(text,
        '                        event["notified"] = True\n\n        eligible_people = [',
        '                        event["notified"] = True\n                        dashboard.event("caregiver_alert", event_id=event["event_id"], person_id=person_id, reason="Voice requested help")\n\n        eligible_people = [', name)
    text = once(text,
        '                    event["notified"] = True\n            if alert["notified"]:',
        '                    event["notified"] = True\n                    dashboard.event("caregiver_alert", event_id=event["event_id"], person_id=person_id, reason="No confirmed response within ten seconds")\n            if alert["notified"]:', name)
    text = once(text,
        '            alerts.clear()\n            audio_attempted.clear()',
        '            for person_id, event in list(alerts.items()):\n                dashboard.event("manual_clear", event_id=event["event_id"], person_id=person_id, reason="Cleared with C key")\n            alerts.clear()\n            audio_attempted.clear()', name)
    text = once(text, 'camera.release()\ncv2.destroyAllWindows()',
        'dashboard.heartbeat(camera_online=False, monitoring_active=False, force=True)\ndashboard.close()\ncamera.release()\ncv2.destroyAllWindows()', name)
    return text


def patch_js(text):
    name = 'dashboard/static/app.js'
    text = once(text,
        '''    const statusText = incident.status === "active"
      ? "Needs attention"
      : incident.status === "acknowledged"
        ? "Acknowledged"
        : "Recorded";''',
        '''    const statusText = incident.status === "active"
      ? "Needs attention"
      : incident.status === "escalated" ? "Demo escalation"
      : incident.status === "acknowledged" ? "Acknowledged"
      : incident.status === "resolved" ? "Resolved"
      : "Recorded";''', name)
    text = once(text,
        'incident.status === "active" ? " is-active" : incident.status === "acknowledged" ? " is-acknowledged" : ""',
        '(incident.status === "active" || incident.status === "escalated") ? " is-active" : incident.status === "acknowledged" ? " is-acknowledged" : ""', name)
    text = once(text,
        '  document.getElementById("monitor-status").textContent = monitoringActive ? "Active" : "Paused";',
        '''  document.getElementById("monitor-status").textContent = monitoringActive ? "Active" : "Not connected";
  document.getElementById("camera-detail").textContent = cameraOnline ? `${state.people_visible ?? 0} person(s) visible · Raspberry Pi` : "Waiting for detector heartbeat";
  document.getElementById("monitor-detail").textContent = monitoringActive ? "Fall detection process running" : "Start detector on this laptop";
  document.getElementById("connection-indicator").style.background = monitoringActive ? "#2ca47e" : "#c28b29";''', name)
    text = once(text, 'state.demo_mode ? "DEMO DATA" : "DETECTOR EVENT"',
        'state.demo_mode ? "DEMO DATA" : "PROTOTYPE · LIVE INPUT"', name)
    text = once(text, 'Boolean(alert && alert.status === "active")',
        'Boolean(alert && (alert.status === "active" || alert.status === "escalated"))', name)
    text = once(text, '''    document.getElementById("safety-status").textContent = "All clear";
    document.getElementById("safety-detail").textContent = "No active fall alerts";''',
        '''    document.getElementById("safety-status").textContent = monitoringActive ? "No active alerts" : "Not connected";
    document.getElementById("safety-detail").textContent = monitoringActive ? "No fall alerts currently recorded" : "Start the detector to enable monitoring";''', name)
    text = once(text, '  } else if (alert.status === "active") {',
        '  } else if (alert.status !== "acknowledged") {', name)
    text = once(text, '''    document.getElementById("alert-kicker").textContent =
      alert.status === "active" ? "IMMEDIATE ATTENTION" : "CAREGIVER ACKNOWLEDGED";
    document.getElementById("alert-title").textContent =
      alert.status === "active" ? "Fall detected" : "Alert acknowledged";
    document.getElementById("alert-description").textContent =
      alert.status === "active"
        ? "A potential fall was reported. Please check in with the person."
        : "This alert was acknowledged. The fall report remains in incident history.";''',
        '''    document.getElementById("alert-kicker").textContent =
      alert.status === "acknowledged" ? "CAREGIVER ACKNOWLEDGED" : alert.status === "escalated" ? "DEMO ESCALATION" : "POSSIBLE FALL";
    document.getElementById("alert-title").textContent =
      alert.status === "acknowledged" ? "Alert acknowledged" : alert.status === "escalated" ? "Caregiver attention needed" : "Possible fall detected";
    document.getElementById("alert-description").textContent =
      alert.status === "acknowledged" ? "An acknowledgement was recorded. Please still check on the person."
      : `${alert.person_id ? `Person ${alert.person_id}: ` : ""}${alert.reason || "Possible fall"}. ${alert.status === "escalated" ? "Simulated caregiver alert only. No call or text sent." : "Checking for a voice response..."}`;''', name)
    text = once(text, '    acknowledgeButton.disabled = alert.status !== "active";',
        '    acknowledgeButton.disabled = alert.status === "acknowledged";', name)
    return text


def patch_html(text):
    name = 'dashboard/static/index.html'
    text = once(text, '<span class="live-indicator"></span>', '<span class="live-indicator" id="connection-indicator"></span>', name)
    text = once(text, '<span>Live dashboard</span>', '<span>Prototype live session</span>', name)
    text = once(text, '<span class="status-detail">Living room · Raspberry Pi</span>', '<span class="status-detail" id="camera-detail">Waiting for detector heartbeat</span>', name)
    text = once(text, '<span class="status-detail">Fall detection enabled</span>', '<span class="status-detail" id="monitor-detail">Start detector on this laptop</span>', name)
    return text


def patch_ignore(text):
    text = text.replace('.cursorindexingignoremic_test.wav', '.cursorindexingignore\nmic_test.wav')
    if 'mic_test.wav' not in text.splitlines():
        text += '\nmic_test.wav\n'
    return text


_BUNDLE = json.loads(zlib.decompress(base64.b64decode(
    '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'
)).decode('utf-8'))


def install(root, bundle):
    if not (root / '.git').exists() or not (root / 'multi_fall_test.py').exists():
        raise ValueError(f'{root} is not the Fall-Guardian Git clone (missing .git or detector).')
    current_server = (root / 'dashboard/server.py').read_bytes().replace(b'\r\n', b'\n')
    blob_header = f'blob {len(current_server)}\0'.encode('utf-8')
    blob_sha = hashlib.sha1(blob_header + current_server).hexdigest()
    # Do not silently overwrite the user's dashboard code if it changed since review.
    if blob_sha != '958a21ce6f3c540416d9ed5dd8118bdb5736c572':
        raise ValueError('dashboard/server.py has changed since review. Refusing to overwrite newer dashboard code.')
    files = {
        'dashboard/server.py': _BUNDLE['dashboard/server.py'],
        'dashboard/bridge.py': _BUNDLE['dashboard/bridge.py'],
        'tests/test_dashboard_api.py': _BUNDLE['tests/test_dashboard_api.py'],
        'INTEGRATION.md': _BUNDLE['INTEGRATION.md'],
    }
    for path, patch in (
        ('multi_fall_test.py', patch_multi),
        ('dashboard/static/app.js', patch_js),
        ('dashboard/static/index.html', patch_html),
        ('.gitignore', patch_ignore),
    ):
        original = (root / path).read_text(encoding='utf-8')
        newline = '\r\n' if '\r\n' in original else '\n'
        updated = patch(original.replace('\r\n', '\n'))
        files[path] = updated.replace('\n', newline)
    # Validate all changes before editing anything; preserve existing new files.
    for path in ('dashboard/bridge.py', 'tests/test_dashboard_api.py', 'INTEGRATION.md'):
        if (root / path).exists():
            raise ValueError(f'{path} already exists; refusing to overwrite it.')
    # Keep original versions in the system temp folder (not inside Git).
    backup_dir = Path(tempfile.mkdtemp(prefix='fallguardian_backup_'))
    for path in files:
        original = root / path
        if original.exists():
            dest = backup_dir / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, dest)
    for path, content in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
    print(f'Integration applied to {root}')
    print(f'Backups saved in {backup_dir}')
    print('Next: run python -m unittest discover -s tests -v')
    print('Then run python dashboard/server.py in one terminal and the detector in another.')
    print('audio_test.py was NOT changed.')


if __name__ == '__main__':
    try:
        install(Path.cwd().resolve(), Path(__file__).resolve().parent)
    except (OSError, ValueError) as error:
        print(f'INSTALL CANCELLED: {error}', file=sys.stderr)
        raise SystemExit(1)
