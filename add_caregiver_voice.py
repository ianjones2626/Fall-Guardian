"""Apply a small spoken caregiver-alert enhancement to Fall Guardian.

Run from the Fall-Guardian repo root: python add_caregiver_voice.py
Requires no extra Python packages. Does not modify audio_test.py.
"""
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "multi_fall_test.py"
MODULE = ROOT / "caregiver_voice.py"

MODULE_SOURCE = '''"""Speak one honest, simulated caregiver escalation without blocking camera frames."""
import subprocess
import threading
import time

_SPEECH_LOCK = threading.Lock()


def announce_caregiver_alert(reason="timeout", audio_thread=None, should_announce=None):
    """Announce an escalation once, after the microphone finishes listening.

    The callback prevents an obsolete announcement after a voice-safe or C-clear.
    This never contacts a real caregiver.
    """
    def _worker():
        try:
            if audio_thread is not None and audio_thread.is_alive():
                audio_thread.join(timeout=15)
            # Give the detector loop a moment to process its completed voice result.
            time.sleep(0.8)
            if should_announce is not None and not should_announce():
                return
            with _SPEECH_LOCK:
                if should_announce is not None and not should_announce():
                    return
                text = (
                    "Help requested. Contacting caregivers. This is a demonstration."
                    if reason == "help" else
                    "No response received. Contacting caregivers. This is a demonstration."
                )
                ps = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    "$voice.Speak('" + text + "')"
                )
                subprocess.run(
                    ["powershell.exe", "-NoProfile", "-Command", ps],
                    check=True, timeout=20,
                )
        except Exception as exc:
            # Do not let audio errors interrupt the camera or dashboard.
            print(f"Caregiver voice announcement unavailable: {exc}")

    threading.Thread(target=_worker, daemon=True).start()
'''

IMPORT_ANCHOR = 'from dashboard.bridge import DashboardBridge\n'
HELP_ANCHOR = ' dashboard.event("caregiver_alert", event_id=event["event_id"], person_id=person_id, reason="Voice requested help")\n'
TIMEOUT_ANCHOR = ' dashboard.event("caregiver_alert", event_id=event["event_id"], person_id=person_id, reason="No confirmed response within ten seconds")\n'

HELP_INSERT = ''' announce_caregiver_alert(
                            reason="help",
                            audio_thread=audio_thread,
                            should_announce=lambda pid=person_id: pid in alerts and alerts[pid]["notified"],
                        )
'''
TIMEOUT_INSERT = ''' announce_caregiver_alert(
                        reason="timeout",
                        audio_thread=audio_thread,
                        should_announce=lambda pid=person_id: pid in alerts and alerts[pid]["notified"],
                    )
'''


def main():
    if not TARGET.is_file():
        raise SystemExit("ERROR: Put this file next to multi_fall_test.py in Fall-Guardian.")
    src = TARGET.read_text(encoding="utf-8")
    if 'from caregiver_voice import announce_caregiver_alert' in src:
        print("Already installed. No changes made.")
        return
    anchors = [IMPORT_ANCHOR, HELP_ANCHOR, TIMEOUT_ANCHOR]
    for anchor in anchors:
        if src.count(anchor) != 1:
            raise SystemExit("ERROR: Source code has changed; installer did not edit anything. Send me the current file before retrying.")
    if MODULE.exists():
        raise SystemExit("ERROR: caregiver_voice.py already exists; no files changed to avoid overwriting it.")

    updated = src.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + 'from caregiver_voice import announce_caregiver_alert\n', 1)
    updated = updated.replace(HELP_ANCHOR, HELP_ANCHOR + HELP_INSERT, 1)
    updated = updated.replace(TIMEOUT_ANCHOR, TIMEOUT_ANCHOR + TIMEOUT_INSERT, 1)
    compile(updated, str(TARGET), "exec")
    compile(MODULE_SOURCE, str(MODULE), "exec")

    backup_dir = Path(tempfile.mkdtemp(prefix="fallguardian_voice_backup_"))
    backup = backup_dir / "multi_fall_test.py"
    shutil.copy2(TARGET, backup)
    try:
        MODULE.write_text(MODULE_SOURCE, encoding="utf-8")
        TARGET.write_text(updated, encoding="utf-8")
    except Exception:
        shutil.copy2(backup, TARGET)
        if MODULE.exists():
            MODULE.unlink()
        raise
    print("SUCCESS: Spoken caregiver alerts added to Fall Guardian.")
    print("Backup:", backup)
    print("When no one confirms safety, it says:")
    print(' "No response received. Contacting caregivers. This is a demonstration."')
    print("A spoken help request uses a corresponding announcement.")
    print("Neither announcement sends a real notification.")
    print("Next: run multi_fall_test.py and test F + silence or 'Help me'.")


if __name__ == "__main__":
    main()