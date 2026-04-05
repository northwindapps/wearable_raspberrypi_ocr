import cv2
import os
import threading
import time
import requests
from flask import Flask, send_file

app = Flask(__name__)



# 保存ディレクトリ作成
SAVE_DIR = "/dev/shm/captured_images"
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

IMAGE_PATH = os.path.join(SAVE_DIR, "current_frame.jpg")

@app.route('/api/capture', methods=['GET'])
def capture():
    if os.path.exists(IMAGE_PATH):
        return send_file(IMAGE_PATH, mimetype='image/jpeg')
    return {"status": "error", "message": "Image not found"}, 404

def camera_process():
    # picamera2のインポート（実行時に読み込み）
    from picamera2 import Picamera2
    picam2 = Picamera2()
    
    # 1. 解析速度を稼ぐため 640x480 に設定
    config = picam2.create_preview_configuration(
        # main={"format": "RGB888", "size": (2304, 1296)} 
        main={"format": "RGB888", "size": (1280, 960)} 
    )


    picam2.configure(config)

    picam2.start() 

    # 2. オートフォーカス設定 (2 = Continuous / 常時)

    picam2.set_controls({
        "AfMode": 2,          # オートフォーカス常時
        "AwbMode": 1,         # 1 = Incandescent (電球色/暖かい光)
        "Saturation": 1.0     # 彩度を少し強調して色の鮮やかさを改善
    })

    print("InnoMaker IMX708 Camera Active (AF-Continuous)...")

    last_save_time = time.time()

    try:
        while True:
            # フレーム取得 (RGB形式)
            frame_rgb = picam2.capture_array()

            # 3. 「2秒に1枚」のタイミングかチェック
            current_time = time.time()
            if current_time - last_save_time < 0.5:
                time.sleep(0.1) # CPUを休ませる
                continue
                
            # メタデータ取得
            metadata = picam2.capture_metadata()
            current_lens_pos = metadata.get('LensPosition', 0)

            # 距離判定：0以下（無限遠）または0.4m(2.5ディオプター)より遠い場合はスキップ
            if current_lens_pos <= 0:
                print("Focus: Infinity or Unknown (Skipping...)")
                last_save_time = current_time # 次の2秒後まで待つ
                continue

            # 距離計算（ログ用）
            distance_m = 1.0 / current_lens_pos

            if distance_m > 0.80:
                print(f"Skipping: Distance too far (distance: {distance_m:.2f})")
                last_save_time = current_time
                continue

            print(f"Target detected: {distance_m:.2f}メートル")

            # --- 保存・送信処理 ---
            #frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            frame_gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
            filename = f"{SAVE_DIR}/current_frame.jpg"
            cv2.imwrite(filename, frame_gray, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            
            last_save_time = current_time


            # CPU負荷を抑えるための微小なスリープ
            time.sleep(0.05)

    except Exception as e:
        print(f"Error in camera loop: {e}")
    finally:
        picam2.stop()

# カメラ処理を別スレッドで実行
# threading.Thread(target=camera_process, daemon=True).start()


if __name__ == "__main__":
    # 2026年のRaspberry Pi 3B環境でも安定するようにホストを指定
    # app.run(host='0.0.0.0', port=5000, debug=False)
    # 1. カメラ処理を別スレッドで開始
    thread = threading.Thread(target=camera_process, daemon=True)
    thread.start()

    # 2. Flaskサーバーを起動 (Macからアクセスできるように host='0.0.0.0' にする)
    # ポートは5000番1つだけ使用します
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

