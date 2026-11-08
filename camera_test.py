import cv2

url = "tcp://100.82.46.93:8888"

camera = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

if not camera.isOpened():
    print("Could not connect to camera")
    exit()

print("Camera connected!")

while True:
    success, frame = camera.read()

    if not success:
        print("Camera disconnected")
        break

    cv2.imshow("Fall Guardian Live Camera", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

camera.release()
cv2.destroyAllWindows()
