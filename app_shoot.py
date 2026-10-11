import cv2
import os
import io
import queue
import threading
import time
import wave
import subprocess
import numpy as np
from flask import Flask, Response, send_file, request

app = Flask(__name__)

# --- Microphone settings (Google Voice HAT) ---
ALSA_DEVICE = "plughw:CARD=sndrpigooglevoi,DEV=0"
HW_RATE = 48000
HW_CHANNELS = 2
TARGET_RATE = 16000                  # 16kHz / mono / int16 for wake-word detection on iOS
DECIMATE = HW_RATE // TARGET_RATE    # 3
CHUNK = 1280                         # 80ms at 16kHz
CHUNK_BYTES = CHUNK * DECIMATE * HW_CHANNELS * 4  # S32_LE = 4 bytes
GAIN = 10.0                           # Raise if audio is too quiet (lower if CLIPPING appears in logs)
BUFFER_SECONDS = 10                  # How many recent seconds of audio to keep
LOG_SECONDS = 5                      # Interval (seconds) for volume logging

# Recent audio (ring buffer) and currently streaming clients
audio_buffer = np.zeros(0, dtype=np.int16)
buffer_lock = threading.Lock()
subscribers = []
subscribers_lock = threading.Lock()


def wav_header(rate, data_size=0xFFFFFFFF - 36):
    # For streaming: size is unknown, so use the max value
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write((data_size + 36).to_bytes(4, "little"))
    buf.write(b"WAVEfmt ")
    buf.write((16).to_bytes(4, "little"))
    buf.write((1).to_bytes(2, "little"))            # PCM
    buf.write((1).to_bytes(2, "little"))            # mono
    buf.write(rate.to_bytes(4, "little"))
    buf.write((rate * 2).to_bytes(4, "little"))     # byte rate
    buf.write((2).to_bytes(2, "little"))            # block align
    buf.write((16).to_bytes(2, "little"))           # bits
    buf.write(b"data")
    buf.write(data_size.to_bytes(4, "little"))
    return buf.getvalue()


@app.route('/api/audio/stream', methods=['GET'])
def audio_stream():
    # Continuously stream raw 16kHz mono int16 PCM (?format=wav adds a WAV header)
    # generate() runs after the request context ends, so read request args here first
    want_wav = request.args.get("format") == "wav"
    q = queue.Queue(maxsize=50)
    with subscribers_lock:
        subscribers.append(q)

    def generate():
        try:
            if want_wav:
                yield wav_header(TARGET_RATE)
            while True:
                yield q.get()
        finally:
            with subscribers_lock:
                subscribers.remove(q)

    return Response(generate(), mimetype="application/octet-stream")


@app.route('/api/audio', methods=['GET'])
def get_audio():
    # Return the last N seconds as WAV (for polling)  e.g. /api/audio?seconds=2
    seconds = min(float(request.args.get("seconds", 2)), BUFFER_SECONDS)
    with buffer_lock:
        pcm = audio_buffer[-int(seconds * TARGET_RATE):].copy()

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(TARGET_RATE)
        wf.writeframes(pcm.tobytes())
    buf.seek(0)
    return send_file(buf, mimetype="audio/wav")


@app.route('/api/capture', methods=['POST', 'GET'])
def capture():
    # Called by iOS when the wake word is detected -> capture a photo and return JPEG
    if picam2 is None:
        return {"status": "error", "message": "Camera not ready"}, 503
    with camera_lock:
        frame_rgb = picam2.capture_array()
    frame_gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
    frame_gray = cv2.rotate(frame_gray, cv2.ROTATE_90_COUNTERCLOCKWISE)   # Correct for camera mounting orientation (rotate 90° left)
    ok, buf = cv2.imencode(".jpg", frame_gray, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        return {"status": "error", "message": "Encode failed"}, 500
    return Response(buf.tobytes(), mimetype="image/jpeg")


@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    # Shut down the Pi (delay slightly so the response is sent before halting)
    def do_halt():
        time.sleep(1)
        subprocess.run(["sudo", "halt"])
    threading.Thread(target=do_halt, daemon=True).start()
    return {"status": "ok", "message": "Shutting down"}


def to_16k_mono(raw):
    # S32_LE 2ch 48kHz -> int16 mono 16kHz
    samples = np.frombuffer(raw, dtype='<i4').reshape(-1, HW_CHANNELS)
    mono = samples.astype(np.float32).mean(axis=1) / 65536.0  # Equivalent to the upper 16 bits
    n = len(mono) // DECIMATE * DECIMATE
    mono = mono[:n].reshape(-1, DECIMATE).mean(axis=1)        # Simple low-pass + decimation
    return np.clip(mono * GAIN, -32768, 32767).astype(np.int16)


# --- Camera ---
picam2 = None
camera_lock = threading.Lock()


def init_camera():
    global picam2
    # Import picamera2 lazily (loaded at runtime)
    from picamera2 import Picamera2
    cam = Picamera2()
    config = cam.create_preview_configuration(
        main={"format": "RGB888", "size": (1280, 960)}
    )
    cam.configure(config)
    cam.start()
    cam.set_controls({
        "AfMode": 2,          # Continuous autofocus
        "AwbMode": 1,         # 1 = Incandescent (warm light)
        "Saturation": 1.0
    })
    picam2 = cam
    print("InnoMaker IMX708 Camera Active (AF-Continuous)...")


def audio_process():
    global audio_buffer
    cmd = [
        "arecord", "-D", ALSA_DEVICE,
        "-c", str(HW_CHANNELS), "-r", str(HW_RATE), "-f", "S32_LE",
        "-t", "raw", "-q",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=CHUNK_BYTES)
    print("Microphone active...")

    max_samples = BUFFER_SECONDS * TARGET_RATE
    log_samples = LOG_SECONDS * TARGET_RATE
    block = []    # For logging: last 5 seconds
    try:
        while True:
            raw = proc.stdout.read(CHUNK_BYTES)
            if len(raw) < CHUNK_BYTES:
                print("arecord stopped")
                break

            pcm = to_16k_mono(raw)

            with buffer_lock:
                audio_buffer = np.concatenate((audio_buffer, pcm))[-max_samples:]

            data = pcm.tobytes()
            with subscribers_lock:
                for q in subscribers:
                    try:
                        q.put_nowait(data)
                    except queue.Full:
                        pass  # Drop data for slow clients (never block the mic)
                n_clients = len(subscribers)

            # --- Log every 5 seconds ---
            block.append(pcm)
            if sum(len(b) for b in block) >= log_samples:
                x = np.concatenate(block).astype(np.float32)
                rms = np.sqrt(np.mean(x ** 2))
                peak = np.max(np.abs(x))
                clip = " CLIPPING" if peak >= 32767 else ""
                print(f"[audio] {time.strftime('%H:%M:%S')} {len(x) / TARGET_RATE:.1f}s "
                      f"rms={rms:.0f} peak={peak:.0f}{clip} stream_clients={n_clients}")
                block = []

    except Exception as e:
        print(f"Error in audio loop: {e}")
    finally:
        proc.terminate()


if __name__ == "__main__":
    # 0. Start the camera
    init_camera()

    # 1. Start audio processing in a separate thread
    thread = threading.Thread(target=audio_process, daemon=True)
    thread.start()

    # 2. Start the Flask server (host='0.0.0.0' so the iOS app can access it)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
