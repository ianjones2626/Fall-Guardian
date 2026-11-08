from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "multi_fall_test.py"
MODULE = ROOT / "caregiver_voice.py"

MODULE_SOURCE = '''"""Speak a caregiver DEMO alert after the microphone check, off the camera loop."""
import subprocess
import threading
import time

_SPEECH_LOCK = threading.Lock()


def announce_caregiver_alert(reason="timeout", audio_thread=None, should_announce=None):
    """Speech only. No caregiver messages, emergency calls, or outbound alerts."""
    def _worker():
        try:
            # Do not talk over the microphone listening for "I'm okay" or "Help me".
            if audio_thread is not None and audio_thread.is_alive():
                audio_thread.join(timeout=15)
            time.sleep(0.8)
            if should_announce is not None and not should_announce():
                return
            with _SPEECH_LOCK:
                if should_announce is not None and not should_announce():
                    return
                words = (
                    "Help requested. Contacting caregivers. This is a demonstration."
                    if reason == "help" else
                    "No response received. Contacting caregivers. This is a demonstration."
                )
                powershell = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    "$voice.Speak('" + words + "')"
                )
                subprocess.run(
                    ["powershell.exe", "-NoProfile", "-Command", powershell],
                    check=True, timeout=20,
                )
        except Exception as error:
            print(f"Demo caregiver voice unavailable: {error}")

    threading.Thread(target=_worker, daemon=True).start()
'''

IMPORT_ANCHOR = 'from dashboard.bridge import DashboardBridge\n'
HELP_ANCHOR = ' dashboard.event("caregiver_alert", event_id=event["event_id"], person_id=person_id, reason="Voice requested help")\n'
TIMEOUT_ANCHOR = ' dashboard.event("caregiver_alert", event_id=event["event_id"], person_id=person_id, reason="No confirmed response within ten seconds")\n'


def main():
    if not TARGET.exists():
        raise SystemExit("ERROR: Put this installer next to multi_fall_test.py in Fall-Guardian.")
    source = TARGET.read_text(encoding="utf-8")

    # Important: check the ORIGINAL source before attempting any changes.
    try:
        compile(source, str(TARGET), "exec")
    except SyntaxError as error:
        raise SystemExit(
            "STOP: The existing multi_fall_test.py has a syntax/indentation error "
            f"at line {error.lineno}, BEFORE this installer made any changes. "
            "No files were changed. Ask for help restoring that file safely."
        ) from error

    if 'from caregiver_voice import announce_caregiver_alert' in source:
        print("Already installed. No changes made.")
        return
    if MODULE.exists():
        raise SystemExit("STOP: caregiver_voice.py already exists; refusing to overwrite it.")
    for anchor in (IMPORT_ANCHOR, HELP_ANCHOR, TIMEOUT_ANCHOR):
        if source.count(anchor) != 1:
            raise SystemExit("STOP: The current code differs from the known working version. No files changed.")

    # Keep each new call on a SINGLE line with the same indentation as the
    # existing dashboard.event call. This avoids the previous indentation issue.
    help_line = (
        ' announce_caregiver_alert("help", audio_thread, '
        'lambda pid=person_id: pid in alerts and alerts[pid]["notified"])\n'
    )
    timeout_line = (
        ' announce_caregiver_alert("timeout", audio_thread, '
        'lambda pid=person_id: pid in alerts and alerts[pid]["notified"])\n'
    )
    modified = source.replace(
        IMPORT_ANCHOR,
        IMPORT_ANCHOR + 'from caregiver_voice import announce_caregiver_alert\n', 1
    ).replace(HELP_ANCHOR, HELP_ANCHOR + help_line, 1).replace(
        TIMEOUT_ANCHOR, TIMEOUT_ANCHOR + timeout_line, 1
    )

    try:
        compile(modified, str(TARGET), "exec")
        compile(MODULE_SOURCE, str(MODULE), "exec")
    except SyntaxError as error:
        raise SystemExit(
            f"STOP: Proposed change failed syntax check at line {error.lineno}; "
            "nothing was written. Send the error and your code for review."
        ) from error

    backup_dir = Path(tempfile.mkdtemp(prefix="fallguardian_spoken_alert_backup_"))
    backup = backup_dir / "multi_fall_test.py"
    shutil.copy2(TARGET, backup)
    try:
        MODULE.write_text(MODULE_SOURCE, encoding="utf-8")
        TARGET.write_text(modified, encoding="utf-8")
    except Exception:
        shutil.copy2(backup, TARGET)
        MODULE.unlink(missing_ok=True)
        raise
    print("SUCCESS: Spoken caregiver demo alerts installed.")
    print("Backup:", backup)
    print("No camera or microphone settings were changed.")
    print("Next: run python -m py_compile .\\multi_fall_test.py")


if __name__ == "__main__":
    main()