import cv2
import mediapipe as mp
import numpy as np
import math
import time
from pathlib import Path
from collections import deque

# Same Raspberry Pi camera stream you already use
URL = "tcp://100.82.46.93:8888"
MAX_PEOPLE = 3
LYING_TILT = 50
LYING_SECONDS = 4.0
FALL_DROP = 0.09
FALL_TILT = 45
ALERT_SECONDS = 10

model_path = str(Path(__file__).with_name("pose_landmarker_lite.task"))
options = mp.tasks.vision.PoseLandmarkerOptions(
    base_options=mp.tasks.BaseOptions(model_asset_path=model_path),
    running_mode=mp.tasks.vision.RunningMode.VIDEO,
    num_poses=MAX_PEOPLE,
)

# Each person gets a separate movement history
tracks = {}
next_id = 1
alerts = {}
connections = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24), (23, 25), (25, 27),
    (24, 26), (26, 28),
]
colors = [(0, 255, 0), (255, 180, 0), (255, 0, 255)]


def alert_person(person_id, reason, now):
    if person_id not in alerts:
        alerts[person_id] = {"since": now, "reason": reason, "notified": False}
        print(f"ALERT: Person {person_id}: {reason}")


camera = cv2.VideoCapture(URL, cv2.CAP_FFMPEG)
if not camera.isOpened():
    raise SystemExit("Camera unavailable. Check the Pi stream and try again.")

print("Multiplayer Fall Guardian running. F = test, C = clear alerts, Q = quit")

with mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:
    while True:
        ok, frame = camera.read()
        if not ok:
            print("Video disconnected")
            break
        now = time.monotonic()
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        result = detector.detect_for_video(mp_image, int(now * 1000))

        # Collect all people who have visible shoulders and hips
        people = []
        for pose in result.pose_landmarks:
            visible = lambda i: pose[i].visibility is None or pose[i].visibility > 0.4
            if not all(visible(i) for i in (11, 12, 23, 24)):
                continue
            sx = (pose[11].x + pose[12].x) / 2
            sy = (pose[11].y + pose[12].y) / 2
            hx = (pose[23].x + pose[24].x) / 2
            hy = (pose[23].y + pose[24].y) / 2
            tilt = math.degrees(math.atan2(abs(hx - sx), abs(hy - sy) + 0.000001))
            people.append((pose, hx, hy, tilt))

        # Associate new detections with existing people by hip position.
        # This is approximate tracking, not facial recognition or persistent identity.
        candidates = []
        for p_index, (_, hx, hy, _) in enumerate(people):
            for track_id, track in tracks.items():
                if now - track["last_seen"] > 1.0:
                    continue
                dist = math.hypot(hx - track["hx"], hy - track["hy"])
                if dist < 0.35:
                    candidates.append((dist, p_index, track_id))
        matches = {}
        used_tracks = set()
        for _, p_index, track_id in sorted(candidates):
            if p_index not in matches and track_id not in used_tracks:
                matches[p_index] = track_id
                used_tracks.add(track_id)

        for p_index, (pose, hx, hy, tilt) in enumerate(people):
            if p_index in matches:
                track_id = matches[p_index]
            else:
                track_id = next_id
                next_id += 1
                tracks[track_id] = {
                    "hx": hx, "hy": hy, "last_seen": now,
                    "history": deque(), "lying_since": None,
                    "motion_since": None, "dismiss_until": 0,
                }

            track = tracks[track_id]
            track["hx"], track["hy"], track["last_seen"] = hx, hy, now
            track["history"].append((now, hy))
            while track["history"] and now - track["history"][0][0] > 1.5:
                track["history"].popleft()

            drop = hy - min(y for t, y in track["history"])

            if track_id not in alerts and now >= track["dismiss_until"]:
                # Sudden downward movement followed by lying posture
                if drop > FALL_DROP and tilt > 25 and track["motion_since"] is None:
                    track["motion_since"] = now
                if track["motion_since"] is not None:
                    since = now - track["motion_since"]
                    if since > 2:
                        track["motion_since"] = None
                    elif since >= 0.7 and tilt >= FALL_TILT:
                        alert_person(track_id, "Possible rapid fall", now)
                        track["motion_since"] = None

                # Independently detect someone staying horizontal
                if tilt >= LYING_TILT:
                    if track["lying_since"] is None:
                        track["lying_since"] = now
                    elif now - track["lying_since"] >= LYING_SECONDS:
                        alert_person(track_id, "Lying posture detected", now)
                else:
                    track["lying_since"] = None
            else:
                track["motion_since"] = None
                track["lying_since"] = None

            color = (0, 0, 255) if track_id in alerts else colors[(track_id - 1) % len(colors)]
            pixels = {}
            for i, point in enumerate(pose):
                if point.visibility is None or point.visibility > 0.4:
                    pixels[i] = (int(point.x * w), int(point.y * h))
            for a, b in connections:
                if a in pixels and b in pixels:
                    cv2.line(frame, pixels[a], pixels[b], color, 2)
            for i in (11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28):
                if i in pixels:
                    cv2.circle(frame, pixels[i], 4, color, -1)

            label = f"Person {track_id} | tilt {tilt:.0f}"
            x, y = int(hx * w), int(hy * h)
            cv2.putText(frame, label, (max(5, min(x - 70, w - 230)), max(25, y - 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Forget old movement histories; keep alerts until C is pressed
        for track_id in list(tracks):
            if now - tracks[track_id]["last_seen"] > 2.0:
                del tracks[track_id]

        cv2.putText(frame, f"People visible: {len(people)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        if alerts:
            first_id = next(iter(alerts))
            alert = alerts[first_id]
            remaining = max(0, ALERT_SECONDS - int(now - alert["since"]))
            cv2.putText(frame, f"POSSIBLE FALL: PERSON {first_id}", (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 255), 2)
            cv2.putText(frame, f"Are you okay? Press C | {remaining}s", (10, 105),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            for person_id, event in alerts.items():
                if now - event["since"] >= ALERT_SECONDS and not event["notified"]:
                    print(f"DEMO caregiver alert: Person {person_id}, {event['reason']}")
                    event["notified"] = True
            if alert["notified"]:
                cv2.putText(frame, "DEMO: CAREGIVER ALERT", (10, 140),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)

        cv2.imshow("Fall Guardian - Multiple People", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("f"):
            if tracks:
                alert_person(next(iter(tracks)), "Manual test", now)
            else:
                print("Stand in front of the camera before pressing F")
        if key == ord("c"):
            for track in tracks.values():
                track["dismiss_until"] = now + 20
                track["lying_since"] = None
                track["motion_since"] = None
                track["history"].clear()
            alerts.clear()
            print("All alerts cleared (20-second demo cooldown)")

camera.release()
cv2.destroyAllWindows()