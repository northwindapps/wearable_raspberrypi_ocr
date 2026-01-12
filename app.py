import cv2
import mediapipe as mp
import os
import threading
from flask import Flask, request
from gtts import gTTS

app = Flask(__name__)

SAVE_DIR = "captured_images"
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

# MediaPipeの初期化
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.7)
mp_draw = mp.solutions.drawing_utils

def speak_process(text, lang):
    try:
        # 音声ファイルを生成して一時保存
        tts = gTTS(text=text, lang=lang)
        filename = "speech.mp3"
        tts.save(filename)
        
        # mpg123で再生 (再生が終わるまで待機)
        os.system(f"mpg123 {filename}")
        
        # 使用後にファイルを削除
        if os.path.exists(filename):
            os.remove(filename)
    except Exception as e:
        print(f"Error: {e}")

@app.route('/api/speak', methods=['GET'])
def speak():
    # パラメータ取得 (デフォルトは英語)
    text = request.args.get('text', 'Hello')
    lang = request.args.get('lang', 'en')
    
    # 非同期で再生開始 (APIのレスポンスを速くするため)
    threading.Thread(target=speak_process, args=(text, lang)).start()
    
    return {
        "status": "success",
        "playing": text,
        "language": lang
    }

@app.route('/api/capture', methods=['GET'])
def capture_max():
    # カメラの初期化
    cam = cv2.VideoCapture(0, cv2.CAP_V4L2) # V4L2バックエンドを明示的に指定（Piで安定します）

    # 1. 解像度を1080pに強制設定
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    
    # 2. バッファをクリア（AW635のオートフォーカスと露出調整を待つ）
    # AW635は起動直後の数フレームは暗かったりボケたりするため、20フレームほど読み飛ばします
    for _ in range(20):
        cam.read()

    ret, frame = cam.read()
    
    if ret:
        filename = f"{SAVE_DIR}/ausdom_1080p_{os.urandom(2).hex()}.jpg"
        
        # 3. JPG圧縮を最小（最高画質 100）にする
        cv2.imwrite(filename, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        
        h, w, _ = frame.shape
        cam.release()
        return {
            "status": "success", 
            "file": filename, 
            "resolution": f"{w}x{h}",
            "info": "Captured with AUSDOM AW635 at 1080p"
        }
    else:
        cam.release()
        return {"status": "error"}, 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
