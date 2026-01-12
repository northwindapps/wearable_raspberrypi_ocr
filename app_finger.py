import cv2
import os
import threading
import mediapipe as mp
import time
from flask import Flask
from gtts import gTTS

app = Flask(__name__)

# 保存ディレクトリ
AUDIO_DIR = "audio_outputs"
os.makedirs(AUDIO_DIR, exist_ok=True)

# MediaPipe設定
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

last_speech_time = 0

def speak_direct(text):
    global last_speech_time
    current_time = time.time()
    if current_time - last_speech_time > 5:  # 5秒のクールタイム
        last_speech_time = current_time
        try:
            tts = gTTS(text=text, lang='en')
            temp_file = os.path.join(AUDIO_DIR, "temp_voice.mp3")
            tts.save(temp_file)
            print(f"!!! TRIGGERED VOICE: {text} !!!")
            # 3Bで軽量に再生
            os.system(f"mpg123 -q {temp_file}") 
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception as e:
            print(f"Speech error: {e}")

def camera_process():
    from picamera2 import Picamera2
    picam2 = Picamera2()
    
    # 1. 解像度を 640x480 (4:3) に設定して全視野を取得
    config = picam2.create_preview_configuration(
        main={"format": "RGB888", "size": (640, 480)}
    )
    picam2.configure(config)

    # 2. オートフォーカスを「継続的」に設定
    # これにより、近づいても遠ざかっても自動でピントが合います
    picam2.set_controls({"AfMode": 2}) 
    
    # 3. 視野（ScalerCrop）を明示的に全域にリセット
    # picam2.set_controls({"ScalerCrop": (0, 0, 1, 1)})
    
    picam2.start()
    print("InnoMaker IMX708 Camera Active. Monitoring English mode...")

    while True:
        # フレーム取得
        frame_rgb = picam2.capture_array()
        results = hands.process(frame_rgb)

        if results.multi_hand_landmarks:
            for hand_lms in results.multi_hand_landmarks:
                idx_tip = hand_lms.landmark[8]
                
                # 画面の左右判定
                side = "LEFT" if idx_tip.x < 0.5 else "RIGHT"
                print(f"Index Finger X: {idx_tip.x:.2f} -> {side}")

                if side == "LEFT":
                    threading.Thread(target=speak_direct, args=("Object detected on your left",)).start()

    picam2.stop()

# カメラを別スレッドで起動
threading.Thread(target=camera_process, daemon=True).start()

@app.route('/')
def status():
    return "InnoMaker MIPI Camera: Running with AF enabled."

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
