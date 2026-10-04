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

# --- マイク設定 (Google Voice HAT) ---
ALSA_DEVICE = "plughw:CARD=sndrpigooglevoi,DEV=0"
HW_RATE = 48000
HW_CHANNELS = 2
TARGET_RATE = 16000                  # iOS 側のウェイクワード検出用 16kHz / mono / int16
DECIMATE = HW_RATE // TARGET_RATE    # 3
CHUNK = 1280                         # 16kHz で 80ms
CHUNK_BYTES = CHUNK * DECIMATE * HW_CHANNELS * 4  # S32_LE = 4 bytes
GAIN = 4.0                           # 音が小さい場合は上げる (ログに CLIPPING が出たら下げる)
BUFFER_SECONDS = 10                  # 直近何秒分を保持するか
LOG_SECONDS = 5                      # 何秒ごとに音量ログを出すか

# 直近の音声 (リングバッファ) と ストリーミング中のクライアント
audio_buffer = np.zeros(0, dtype=np.int16)
buffer_lock = threading.Lock()
subscribers = []
subscribers_lock = threading.Lock()


def wav_header(rate, data_size=0xFFFFFFFF - 36):
    # ストリーミング用: サイズ不明なので最大値を入れる
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
    # 16kHz mono int16 の生PCMを流し続ける (?format=wav でWAVヘッダ付き)
    q = queue.Queue(maxsize=50)
    with subscribers_lock:
        subscribers.append(q)

    def generate():
        try:
            if request.args.get("format") == "wav":
                yield wav_header(TARGET_RATE)
            while True:
                yield q.get()
        finally:
            with subscribers_lock:
                subscribers.remove(q)

    return Response(generate(), mimetype="application/octet-stream")


@app.route('/api/audio', methods=['GET'])
def get_audio():
    # 直近 N 秒を WAV で返す (ポーリング用)  例: /api/audio?seconds=2
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
    # iOS がウェイクワードを検出したら呼ぶ → その場で撮影して JPEG を返す
    if picam2 is None:
        return {"status": "error", "message": "Camera not ready"}, 503
    with camera_lock:
        frame_rgb = picam2.capture_array()
    frame_gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
    ok, buf = cv2.imencode(".jpg", frame_gray, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        return {"status": "error", "message": "Encode failed"}, 500
    return Response(buf.tobytes(), mimetype="image/jpeg")


def to_16k_mono(raw):
    # S32_LE 2ch 48kHz -> int16 mono 16kHz
    samples = np.frombuffer(raw, dtype='<i4').reshape(-1, HW_CHANNELS)
    mono = samples.astype(np.float32).mean(axis=1) / 65536.0  # 上位16bit相当
    n = len(mono) // DECIMATE * DECIMATE
    mono = mono[:n].reshape(-1, DECIMATE).mean(axis=1)        # 簡易ローパス + 間引き
    return np.clip(mono * GAIN, -32768, 32767).astype(np.int16)


# --- カメラ ---
picam2 = None
camera_lock = threading.Lock()


def init_camera():
    global picam2
    # picamera2のインポート（実行時に読み込み）
    from picamera2 import Picamera2
    cam = Picamera2()
    config = cam.create_preview_configuration(
        main={"format": "RGB888", "size": (1280, 960)}
    )
    cam.configure(config)
    cam.start()
    cam.set_controls({
        "AfMode": 2,          # オートフォーカス常時
        "AwbMode": 1,         # 1 = Incandescent (電球色/暖かい光)
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
    block = []    # ログ用: 直近5秒分
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
                        pass  # 遅いクライアントは取りこぼす (マイクは止めない)
                n_clients = len(subscribers)

            # --- 5秒ごとにログ ---
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
    # 0. カメラ起動
    init_camera()

    # 1. 音声処理を別スレッドで開始
    thread = threading.Thread(target=audio_process, daemon=True)
    thread.start()

    # 2. Flaskサーバーを起動 (iOSアプリからアクセスできるように host='0.0.0.0' にする)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
