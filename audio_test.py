import array
import math
import queue
import re
import subprocess
import threading
import time

try:
    import pyaudio
except ImportError:
    import pyaudiowpatch as pyaudio

import speech_recognition as sr

MICROPHONE_DEVICE_INDEX = 1
CHANNELS = 1
SAMPLE_RATE = 44100
CHUNK_SIZE = 1024
RECORD_SECONDS = 5
SAMPLE_FORMAT = pyaudio.paInt16


def speak_prompt():
    print("Speaking the question through the laptop speakers...")
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            (
                "Add-Type -AssemblyName System.Speech; "
                "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "$voice.Speak('A possible fall has been detected. Are you okay?')"
            ),
        ],
        check=True,
    )


def record_mono_audio(countdown_seconds=3):
    audio_interface = pyaudio.PyAudio()
    stream = None
    try:
        device = audio_interface.get_device_info_by_index(
            MICROPHONE_DEVICE_INDEX
        )
        print(
            f"Using microphone: {device['name']} "
            f"(device {MICROPHONE_DEVICE_INDEX})"
        )
        print(
            f"Capture format: {CHANNELS} channels, 16-bit PCM, "
            f"{SAMPLE_RATE} Hz, {CHUNK_SIZE}-frame chunks"
        )
        audio_interface.is_format_supported(
            SAMPLE_RATE,
            input_device=MICROPHONE_DEVICE_INDEX,
            input_channels=CHANNELS,
            input_format=SAMPLE_FORMAT,
        )
        stream = audio_interface.open(
            format=SAMPLE_FORMAT,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            input_device_index=MICROPHONE_DEVICE_INDEX,
            frames_per_buffer=CHUNK_SIZE,
        )

        print("Get ready to answer: I'm okay, Yes, Help me, or No.")
        for seconds_left in range(countdown_seconds, 0, -1):
            print(f"Listening starts in {seconds_left}...")
            time.sleep(1)
        print(f"LISTENING NOW: speak for up to {RECORD_SECONDS} seconds.")

        frames = []
        chunk_count = math.ceil(SAMPLE_RATE / CHUNK_SIZE * RECORD_SECONDS)
        for _ in range(chunk_count):
            frames.append(
                stream.read(CHUNK_SIZE, exception_on_overflow=False)
            )
        raw_audio = b"".join(frames)
    finally:
        if stream is not None:
            stream.stop_stream()
            stream.close()
        audio_interface.terminate()

    samples = array.array("h")
    samples.frombytes(raw_audio)
    mono_samples = array.array("h")
    for offset in range(0, len(samples), CHANNELS):
        frame = samples[offset:offset + CHANNELS]
        if len(frame) == CHANNELS:
            mono_samples.append(round(sum(frame) / CHANNELS))

    mono_audio = mono_samples.tobytes()
    mono_values = array.array("h", mono_samples)
    rms = math.sqrt(
        sum(sample * sample for sample in mono_values)
        / max(1, len(mono_values))
    )
    print(f"Captured mono audio: {len(mono_audio):,} bytes; RMS={rms:.1f}")
    return sr.AudioData(mono_audio, SAMPLE_RATE, 2), rms


def classify_response(response):
    words = set(re.findall(r"[a-z']+", response.lower()))
    if "help" in words or "no" in words:
        return "HELP REQUESTED - simulated caregiver alert"
    positive_words = {"okay", "ok", "yes", "yeah", "yep", "yup"}
    if "not" in words and positive_words.intersection(words):
        return "HELP REQUESTED - simulated caregiver alert"
    if positive_words.intersection(words):
        return "PERSON IS SAFE - confirmed by voice"
    return "NO CONFIRMED RESPONSE - unclear words"


def perform_voice_check(countdown_seconds=3):
    speak_prompt()
    audio_data, rms = record_mono_audio(countdown_seconds)

    if rms < 30:
        print("No speech-level audio detected; no confirmed response.")
        return "no_response", "", "NO CONFIRMED RESPONSE - no speech detected"

    recognizer = sr.Recognizer()
    print("Sending the mono recording to speech recognition...")
    try:
        response = recognizer.recognize_google(
            audio_data, language="en-US"
        )
    except sr.UnknownValueError:
        return "unclear", "", "NO CONFIRMED RESPONSE - speech was unclear"
    except sr.RequestError as error:
        return "error", "", f"Speech recognition service/network error: {error}"

    return "recognized", response, classify_response(response)


def _voice_check_worker(results):
    try:
        results.put(perform_voice_check(countdown_seconds=0))
    except Exception as error:
        results.put(("error", "", f"Audio check failed: {error}"))


def start_voice_check(results):
    thread = threading.Thread(
        target=_voice_check_worker,
        args=(results,),
        daemon=True,
    )
    thread.start()
    return thread


def main():
    status, response, result = perform_voice_check()
    if response:
        print(f"Recognized words: {response}")
    print(f"Result: {result}")
    if status == "error":
        print("Audio test did not complete successfully.")


if __name__ == "__main__":
    main()