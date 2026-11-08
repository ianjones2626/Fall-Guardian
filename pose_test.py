import cv2
import mediapipe as mp
import numpy as np
import time
from pathlib import Path

# Raspberry Pi camera stream
url = "tcp://100.82.46.93:8888"

# Load Google's body-tracking model
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

# Skeleton connections
connections = [
    (11, 12), (11, 13), (13, 15),
    (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27),
    (24, 26), (26, 28)
]

camera = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

if not camera.isOpened():
    print("Camera connection failed!")
    raise SystemExit

print("Camera connected! Starting body tracking...")

with mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:
    while True:
        success, frame = camera.read()

        if not success:
            print("Video stream disconnected")
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=np.ascontiguousarray(rgb)
        )

        timestamp = time.monotonic_ns() // 1_000_000
        result = detector.detect_for_video(image, timestamp)

        if result.pose_landmarks:
            landmarks = result.pose_landmarks[0]
            height, width = frame.shape[:2]
            points = {}

            for i in range(len(landmarks)):
                lm = landmarks[i]

                if lm.visibility is None or lm.visibility > 0.5:
                    x = int(lm.x * width)
                    y = int(lm.y * height)
                    points[i] = (x, y)

            for start, end in connections:
                if start in points and end in points:
                    cv2.line(
                        frame, points[start], points[end],
                        (0, 255, 0), 3
                    )

            for i in points:
                if i in [11, 12, 13, 14, 15, 16,
                         23, 24, 25, 26, 27, 28]:
                    cv2.circle(frame, points[i], 5,
                               (0, 0, 255), -1)

            status = "BODY DETECTED"
        else:
            status = "NO BODY DETECTED"

        cv2.putText(
            frame, status, (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7,
            (0, 255, 0), 2
        )

        cv2.imshow("Fall Guardian Body Tracking", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

camera.release()
cv2.destroyAllWindows()
