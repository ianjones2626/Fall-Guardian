import argparse
import array
import io
import math
import struct
import time
import wave
from pathlib import Path

import pyaudio


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = PROJECT_DIR / "mic_test.wav"
RECORD_SECONDS = 5
CHUNK_SIZE = 1024
SAMPLE_FORMAT = pyaudio.paInt16


def get_recording_format(audio, device_index, device, requested_channels):
    rates = dict.fromkeys(
        (int(device["defaultSampleRate"]), 48000, 44100, 16000)
    )
    channel_options = (requested_channels,) if requested_channels else (1, 2, 4)
    for channels in channel_options:
        if channels > int(device["maxInputChannels"]):
            continue
        for sample_rate in rates:
            try:
                audio.is_format_supported(
                    sample_rate,
                    input_device=device_index,
                    input_channels=channels,
                    input_format=SAMPLE_FORMAT,
                )
                return channels, sample_rate
            except ValueError:
                continue
    raise RuntimeError(
        f"Microphone '{device['name']}' has no supported 16-bit input "
        "format at its default rate, 48 kHz, 44.1 kHz, or 16 kHz."
    )


def measure_signal(raw_audio, channels):
    samples = struct.unpack(
        "<" + "h" * (len(raw_audio) // 2),
        raw_audio[:len(raw_audio) // 2 * 2],
    )
    channel_levels = []
    for channel in range(channels):
        channel_samples = samples[channel::channels]
        peak = max((abs(sample) for sample in channel_samples), default=0)
        rms = math.sqrt(
            sum(sample * sample for sample in channel_samples)
            / max(1, len(channel_samples))
        )
        channel_levels.append((peak, rms))
    return channel_levels


def play_recording():
    try:
        import winsound
    except ImportError:
        print("Automatic playback is available only on Windows.")
        return

    print("Playing the recording now. Listen for your voice.")
    with wave.open(str(OUTPUT_PATH), "rb") as wav_file:
        channels = wav_file.getnchannels()
        raw_audio = wav_file.readframes(wav_file.getnframes())
        sample_rate = wav_file.getframerate()

    if channels > 1:
        samples = struct.unpack(
            "<" + "h" * (len(raw_audio) // 2),
            raw_audio[:len(raw_audio) // 2 * 2],
        )
        levels = [
            math.sqrt(
                sum(sample * sample for sample in samples[channel::channels])
                / max(1, len(samples[channel::channels]))
            )
            for channel in range(channels)
        ]
        selected_channel = max(range(channels), key=levels.__getitem__)
        mono_samples = array.array("h", samples[selected_channel::channels])
        preview = io.BytesIO()
        with wave.open(preview, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(mono_samples.tobytes())
        winsound.PlaySound(preview.getvalue(), winsound.SND_MEMORY)
    else:
        winsound.PlaySound(str(OUTPUT_PATH), winsound.SND_FILENAME)


def main():
    parser = argparse.ArgumentParser(
        description="Record and measure five seconds from the default microphone."
    )
    parser.add_argument(
        "--play",
        action="store_true",
        help="Play the existing mic_test.wav without recording again.",
    )
    parser.add_argument(
        "--device-index",
        type=int,
        help="Record from this PyAudio input device instead of the default.",
    )
    parser.add_argument(
        "--channels",
        type=int,
        choices=(1, 2, 4),
        help="Force a channel count, useful for testing microphone arrays.",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available input devices and exit.",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Skip the ready prompt and start after the countdown.",
    )
    args = parser.parse_args()

    if args.play:
        if not OUTPUT_PATH.exists():
            raise SystemExit(f"Recording not found: {OUTPUT_PATH}")
        play_recording()
        return

    audio = pyaudio.PyAudio()
    stream = None
    try:
        if args.list_devices:
            for index in range(audio.get_device_count()):
                device_info = audio.get_device_info_by_index(index)
                if device_info.get("maxInputChannels", 0) > 0:
                    host_api = audio.get_host_api_info_by_index(
                        int(device_info["hostApi"])
                    )["name"]
                    print(
                        f"Input {index}: {device_info['name']} "
                        f"({host_api}, {device_info['maxInputChannels']} channels, "
                        f"{int(device_info['defaultSampleRate'])} Hz default)"
                    )
            return

        try:
            if args.device_index is None:
                device = audio.get_default_input_device_info()
                device_index = int(device["index"])
            else:
                device_index = args.device_index
                device = audio.get_device_info_by_index(device_index)
                if device.get("maxInputChannels", 0) <= 0:
                    raise RuntimeError(
                        f"Device {device_index} is not an input device."
                    )
        except (OSError, IOError) as error:
            raise RuntimeError(
                "Windows did not provide a default microphone to Python. "
                "Check Windows Settings > Privacy & security > Microphone, "
                "and make sure desktop apps are allowed to use it."
            ) from error

        channels, sample_rate = get_recording_format(
            audio, device_index, device, args.channels
        )
        print(f"Microphone: {device['name']} (device {device_index})")
        print(
            f"Recording format: {channels} channel(s), "
            f"16-bit PCM, {sample_rate} Hz"
        )
        print(f"Output WAV: {OUTPUT_PATH}")
        print(f"Recording for {RECORD_SECONDS} seconds. Speak at a normal volume.")
        if not args.no_wait:
            input("Press Enter when ready; speak as soon as the countdown starts: ")
        for seconds_left in range(3, 0, -1):
            print(f"Starting in {seconds_left}...")
            time.sleep(1)
        print("RECORDING NOW: say a full sentence until recording stops.")

        try:
            stream = audio.open(
                format=SAMPLE_FORMAT,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=CHUNK_SIZE,
            )
        except (OSError, IOError) as error:
            raise RuntimeError(
                f"Could not open the default microphone '{device['name']}'. "
                "Check Windows microphone privacy settings and close other "
                f"apps that may be using the microphone. Details: {error}"
            ) from error

        frames = []
        for _ in range(math.ceil(sample_rate / CHUNK_SIZE * RECORD_SECONDS)):
            frames.append(
                stream.read(CHUNK_SIZE, exception_on_overflow=False)
            )
        raw_audio = b"".join(frames)
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
    finally:
        if stream is not None:
            stream.stop_stream()
            stream.close()
        audio.terminate()

    with wave.open(str(OUTPUT_PATH), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(audio.get_sample_size(SAMPLE_FORMAT))
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(raw_audio)

    channel_levels = measure_signal(raw_audio, channels)
    peak = max(level[0] for level in channel_levels)
    rms = max(level[1] for level in channel_levels)
    duration = len(raw_audio) / (2 * sample_rate * channels)
    print(f"Recording saved: {OUTPUT_PATH}")
    print(f"File size: {OUTPUT_PATH.stat().st_size:,} bytes")
    print(f"Captured duration: {duration:.2f} seconds")
    print(f"Signal level: peak={peak}/32767, RMS={rms:.1f}/32767")
    for channel, (channel_peak, channel_rms) in enumerate(channel_levels, start=1):
        print(
            f"  Channel {channel}: peak={channel_peak}/32767, "
            f"RMS={channel_rms:.1f}/32767"
        )
    if peak < 500 or rms < 50:
        print("WARNING: Very little microphone signal was captured.")
        print("Check the Windows input level and speak closer to the mic.")
    else:
        print("Microphone produced a measurable signal.")
    play_recording()


if __name__ == "__main__":
    main()