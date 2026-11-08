# Fall Guardian: Integrated Hackathon Demo

This package connects the **existing** Raspberry Pi camera / MediaPipe multi-person detector and audio check to the local caregiver dashboard. It does not change `audio_test.py` or the Raspberry Pi configuration.

**Important:** This is a hackathon prototype. Fall identification and microphone recognition can make mistakes; the interface does NOT send messages, texts, emergency calls, or real caregiver notifications. "Caregiver alert" is an on-screen demonstration event only. Do not rely on this project for real-world emergency monitoring.

## Quick start (same Windows laptop)

1. Commit or stash any local changes, and **pull Ian's latest GitHub changes** before applying the integration package.
2. Place `fallguardian_install.py` in the **Fall-Guardian project folder**, open a VS Code terminal in that folder, and run:
   ```powershell
   python .\fallguardian_install.py
   ```
   The installer checks the expected code before editing and keeps a backup in your temporary folder. It leaves `audio_test.py` alone.
3. In **terminal 1**, start the dashboard:
   ```powershell
   python .\dashboard\server.py
   ```
4. Visit http://127.0.0.1:8000 in Chrome. The camera should initially show **Offline**, because the detection process is not yet running. Click **Simulate fall**, then **Acknowledge alert** to verify the interface.
5. Ensure Raspberry Pi camera stream and Tailscale are connected on the detector's laptop. In **terminal 2** on that same computer, use the known-working Python virtual environment:
   ```powershell
   .\.venv\Scripts\python.exe -u .\multi_fall_test.py
   ```
   The dashboard should change its camera status to **Online**, update the number of visible people, and report fall events. **F** triggers a simulated fall, **C** manually clears the alerts, **Q** quits.
6. Check that the speaker asks "Are you okay?" and confirm that the dashboard responds to an actual spoken answer. **Do not assume the microphone works just because a standalone recording played back.**

### Why both processes must be on the same laptop for the simplest demo

The dashboard intentionally listens on `127.0.0.1` (localhost), so it is available only to programs and browsers on that computer. If you and Ian code on separate computers, you can still push/pull independently. For the **final integrated demo**, run both terminal commands on Ian's Windows laptop (the laptop already connected to the Pi and microphone). The dashboard frontend can be developed on another laptop, but the same-machine setup avoids network/security complications.

### API for testing without a camera

The dashboard uses standard Python libraries only. You can test it without Pi hardware:

```powershell
python -m unittest discover -s tests -v
```

API:
- `GET /api/state` returns current monitoring status and incident history.
- `POST /api/heartbeat` receives `{"camera_online": true, "monitoring_active": true, "people_visible": 1}`. Without a recent heartbeat, the dashboard reports Offline rather than pretending a camera is connected.
- `POST /api/events` accepts `fall_detected`, `caregiver_alert`, `person_safe`, `manual_clear`; the latter three refer to the original fall's unique `event_id`.
- `POST /api/alerts/acknowledge` acknowledges an active dashboard alert but does **not** declare the person safe.

Events are saved **only in memory** and reset when the server stops. There is no video recording or cloud upload in this integration. The existing `audio_test.py` uses SpeechRecognition's Google recognizer, which sends recorded audio to an internet speech-recognition service when run; this is an independent aspect of Ian's audio prototype, not handled by the dashboard. Use informed consent for anyone filmed or recorded in the demo.

## If a test fails

- Camera Offline: verify Pi power, Tailscale, port 8888 and that you started `multi_fall_test.py` on the same laptop as `server.py`. Do not use VLC concurrently with the detector camera stream.
- Voice fails: verify microphone device index 1 / 4 channels on Ian's laptop; test `audio_test.py` separately. The dashboard can still show fallback alerts even when speech recognition fails.
- Dashboard does not update: check the detector terminal for `Dashboard not reachable`, start the dashboard first, and retry F.
- If the installer refuses to apply, its file anchors no longer match the code. **Do not force or overwrite Ian's latest edits.** Send the error message for an updated integration.

## Git workflow

After tests pass: `git status`, `git add dashboard multi_fall_test.py tests INTEGRATION.md .gitignore`, `git commit -m "Integrate dashboard with detector and voice status"`, then `git pull --rebase origin main` (resolve conflicts if any) and `git push origin main`. Run `git status` again to verify clean. Do not commit `.venv`, microphone `.wav` files, passwords, or API keys.
