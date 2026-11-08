import cv2
import mediapipe as mp
import numpy as np
import time
import math
from pathlib import Path
from collections import deque

URL = "tcp://100.82.46.93:8888"

# Settings we can tune during testing
FALL_DROP = 0.09
FALL_TILT = 45
LYING_TILT = 50
LYING_SECONDS = 4.0
ALERT_SECONDS = 10

model_path = str(
    Path(__file__).with_name("pose_landmarker_lite.task")
)

options = mp.tasks.vision.PoseLandmarkerOptions(
    base_options=mp.tasks.BaseOptions(
        model_asset_path=model_path
    ),
    running_mode=mp.tasks.vision.RunningMode.VIDEO,
    num_poses=1
)

connections = [
    (11, 12), (11, 13), (13, 15),
    (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27),
    (24, 26), (26, 28)
]

camera = cv2.VideoCapture(URL, cv2.CAP_FFMPEG)

if not camera.isOpened():
    print("Camera connection failed!")
    raise SystemExit

history = deque()
lying_since = None
fall_motion_at = None
last_pose_time = None

alert = False
alert_start = None
alert_reason = ""
notification_sent = False
dismiss_until = 0

print("Fall Guardian started!")
print("F = test alert | C = I'm OK | Q = quit")

with mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:

    while True:
        success, frame = camera.read()

        if not success:
            print("Camera disconnected")
            break

        now = time.monotonic()
        height, width = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=np.ascontiguousarray(rgb)
        )

        result = detector.detect_for_video(
            image, int(now * 1000)
        )

        tilt = 0
        drop = 0
        valid_pose = False

        if result.pose_landmarks:
            landmarks = result.pose_landmarks[0]
            points = {}

            for i, lm in enumerate(landmarks):
                if lm.visibility is None or lm.visibility > 0.4:
                    points[i] = (
                        int(lm.x * width),
                        int(lm.y * height)
                    )

            # Draw body skeleton
            for a, b in connections:
                if a in points and b in points:
                    cv2.line(
                        frame, points[a], points[b],
                        (0, 255, 0), 2
                    )

            for i in points:
                if i in [11, 12, 13, 14, 15, 16,
                         23, 24, 25, 26, 27, 28]:
                    cv2.circle(
                        frame, points[i], 4,
                        (0, 0, 255), -1
                    )

            # Track shoulders and hips
            if all(i in points for i in [11, 12, 23, 24]):
                valid_pose = True
                last_pose_time = now

                sx = (landmarks[11].x + landmarks[12].x) / 2
                sy = (landmarks[11].y + landmarks[12].y) / 2
                hx = (landmarks[23].x + landmarks[24].x) / 2
                hy = (landmarks[23].y + landmarks[24].y) / 2

                # 0 = upright, 90 = horizontal
                tilt = math.degrees(math.atan2(
                    abs(hx - sx),
                    abs(hy - sy) + 0.000001
                ))

                # Recent hip positions
                history.append((now, hy))

                while history and now - history[0][0] > 1.5:
                    history.popleft()

                earlier_y = min(y for t, y in history)
                drop = hy - earlier_y

                if not alert and now >= dismiss_until:

                    # METHOD 1: Sudden falling movement
                    if (
                        drop > FALL_DROP
                        and tilt > 25
                        and fall_motion_at is None
                    ):
                        fall_motion_at = now

                    if fall_motion_at is not None:
                        elapsed = now - fall_motion_at

                        if elapsed > 2.0:
                            fall_motion_at = None

                        elif elapsed >= 0.7 and tilt >= FALL_TILT:
                            alert = True
                            alert_start = now
                            alert_reason = "Sudden fall detected"
                            fall_motion_at = None

                    # METHOD 2: Lying down for several seconds
                    if tilt >= LYING_TILT:
                        if lying_since is None:
                            lying_since = now

                        elif now - lying_since >= LYING_SECONDS:
                            if not alert:
                                alert = True
                                alert_start = now
                                alert_reason = "Lying posture detected"
                    else:
                        lying_since = None

                elif not alert:
                    lying_since = None
                    fall_motion_at = None

        # Allow brief tracking interruptions
        if (
            not valid_pose
            and last_pose_time is not None
            and now - last_pose_time > 0.75
        ):
            history.clear()
            lying_since = None
            fall_motion_at = None

        # Display monitoring information
        if not alert:
            cv2.putText(
                frame, "MONITORING", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (0, 255, 0), 2
            )

            if valid_pose:
                cv2.putText(
                    frame, f"Body tilt: {tilt:.0f} degrees",
                    (10, 65),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (255, 255, 255), 2
                )

                if lying_since is not None:
                    seconds = now - lying_since
                    cv2.putText(
                        frame,
                        f"Lying posture: {seconds:.1f}s",
                        (10, 100),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 165, 255), 2
                    )

        # Alert screen
        if alert:
            cv2.putText(
                frame, "POSSIBLE FALL!",
                (10, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9, (0, 0, 255), 3
            )

            cv2.putText(
                frame, "ARE YOU OKAY?",
                (10, 85),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.85, (0, 0, 255), 3
            )

            cv2.putText(
                frame, "Press C if you are OK",
                (10, 125),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (0, 0, 255), 2
            )

            remaining = max(
                0, ALERT_SECONDS - int(now - alert_start)
            )

            cv2.putText(
                frame, f"Alert in: {remaining}s",
                (10, 165),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (0, 0, 255), 2
            )

            if remaining == 0:
                cv2.putText(
                    frame, "DEMO: CAREGIVER ALERT",
                    (10, 205),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 0, 255), 2
                )

                if not notification_sent:
                    print("DEMO caregiver notification!")
                    print("Reason:", alert_reason)
                    notification_sent = True

        cv2.imshow("Fall Guardian", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

        elif key == ord("f"):
            alert = True
            alert_start = time.monotonic()
            alert_reason = "Manual test"
            notification_sent = False
            print("Manual fall simulation")

        elif key == ord("c"):
            alert = False
            notification_sent = False
            lying_since = None
            fall_motion_at = None
            history.clear()
            dismiss_until = time.monotonic() + 30
            print("Person confirmed OK")

        # Print newly detected alerts once
        if alert and alert_reason != "Manual test":
            if alert_start == now:
                print("ALERT:", alert_reason)

camera.release()
cv2.destroyAllWindows()