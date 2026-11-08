# Fall-Guardian
Fall Guardian 🛡️

AI-Powered Fall Detection & Caregiver Assistance

MakeUC 2026 | Hardware + Social Issues

Fall Guardian is a Raspberry Pi-powered fall detection prototype designed to help older adults and people at risk of falling. By combining computer vision, voice recognition, and a caregiver dashboard, Fall Guardian demonstrates how technology could help identify emergencies and support faster responses.

The Problem

According to the CDC, more than 14 million older Americans report falling each year, approximately one in four adults aged 65 and older.

For someone living alone, a fall can become especially dangerous when they're unable to get up or ask for help.

Our goal: Detect a possible fall, check whether the person needs assistance, and demonstrate how a caregiver could be notified.

How It Works

1. Monitor: A Raspberry Pi camera streams live video to a computer.
2. Detect: AI pose tracking identifies people and analyzes their body positions and movements.
3. Check: When a possible fall is detected, the system asks, "Are you okay?"
4. Respond: Speech recognition checks whether the person says they're okay or requests assistance.
5. Escalate: If help is requested or no confirmed response is received, Fall Guardian displays a simulated caregiver alert.
6. Display: A web dashboard shows camera status, detected incidents, and alert information.

Technology Stack

Component| Technology
Hardware| Raspberry Pi 5, Camera Module 3
Programming| Python, JavaScript, HTML, CSS
Computer vision| MediaPipe, OpenCV
Body tracking| Multi-person pose estimation
Voice recognition| Python SpeechRecognition
Voice output| Windows text-to-speech
Networking| Tailscale, TCP video streaming
Dashboard| Python HTTP server, HTML/CSS/JavaScript
Collaboration| Git, GitHub

Key Features

- Live camera streaming from Raspberry Pi hardware
- AI-based tracking of multiple people
- Detection of possible falls using posture and movement
- Spoken safety check-ins
- Recognition of spoken responses such as "I'm okay" and "Help me"
- Automatic demonstration alerts when assistance may be needed
- Interactive caregiver dashboard
- Incident tracking and alert acknowledgement
- Manual fall simulation for demonstrations

System Architecture

Raspberry Pi 5 + Camera
          |
          v
    Live Video Stream
          |
          v
 Python + MediaPipe AI
          |
          v
   Possible Fall?
      /       \
     No       Yes
     |         |
 Continue   Voice Check
 Monitoring    |
          +----+----+
          |         |
       I'm okay   Help / No
          |       Response
          v         |
      Clear Alert   v
               Demo Caregiver
                    Alert
                     |
                     v
               Web Dashboard

Running the Project

The current integrated demo runs on Windows and requires the Raspberry Pi camera stream to be accessible from the computer.

1. Install Python dependencies

pip install opencv-python mediapipe numpy SpeechRecognition PyAudioWPatch

Microphone settings and the Raspberry Pi stream address may need adjustment for your setup.

2. Start the dashboard

Open a terminal in the project folder:

python .\dashboard\server.py

Open http://127.0.0.1:8000 in your browser.

3. Start fall detection

Open another terminal:

python .\multi_fall_test.py

Ensure the Raspberry Pi is powered on, its camera stream is running, and Tailscale connectivity is available.

Demo Controls

Key| Action
F| Simulate a fall
C| Clear active alerts
Q| Quit the camera application

Run Dashboard Tests

python -m unittest discover -s tests -v

Current Limitations

Fall Guardian is a hackathon proof of concept, not a certified medical or emergency monitoring system.

- Caregiver alerts are simulated within the application. No real SMS messages, emergency calls, or caregiver notifications are sent.
- Fall detection and voice recognition may produce incorrect results.
- The current implementation requires a Windows computer for voice output.
- Speech recognition uses an online Google recognition service, which means recorded speech is sent to that service for processing.
- The dashboard is intended for local demonstration rather than public deployment.
- More testing, privacy safeguards, and reliability improvements would be required before real-world use.

Future Improvements

- Real caregiver notifications and optional emergency escalation
- Greater accuracy across different fall scenarios
- Fully local voice recognition for improved privacy
- Portable, standalone hardware deployment
- Long-term monitoring and expanded testing

Why Fall Guardian?

We believe accessible hardware and AI can help create practical assistive technology.

Fall Guardian explores how computer vision and simple human interaction can work together to support safer, more independent living.

Built for MakeUC 2026 at the University of Cincinnati.

Source

Centers for Disease Control and Prevention (CDC), "Older Adult Falls Data" (https://www.cdc.gov/falls/data-research/facts-stats/index.html).

