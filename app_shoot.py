import cv2
import os
import threading
import time
import requests
from flask import Flask

app = Flask(__name__)

# 保存ディレクトリ作成
SAVE_DIR = "/dev/shm/captured_images"
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)


def camera_process():
    # picamera2のインポート（実行時に読み込み）
    from picamera2 import Picamera2
    picam2 = Picamera2()
    
    # 1. 解析速度を稼ぐため 640x480 に設定
    config = picam2.create_preview_configuration(
        main={"format": "RGB888", "size": (2304, 1296)} 
    )
    picam2.configure(config)

    # 2. オートフォーカス設定 (2 = Continuous / 常時)
    picam2.start()

    picam2.set_controls({
        "AfMode": 2,          # オートフォーカス常時
        "AwbMode": 1,         # 1 = Incandescent (電球色/暖かい光)
        "Saturation": 1.0     # 彩度を少し強調して色の鮮やかさを改善
    })

    print("InnoMaker IMX708 Camera Active (AF-Continuous)...")

    frame_count = 0
    last_save_time = time.time()

    try:
        while True:
            # フレーム取得 (RGB形式)
            frame_rgb = picam2.capture_array()

            # 3. 「2秒に1枚」のタイミングかチェック
            current_time = time.time()
            if current_time - last_save_time >= 2.0:
                
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

                if distance_m > 0.50:
                    print(f"Skipping: Distance too far (distance: {distance_m:.2f})")
                    last_save_time = current_time
                    continue

                print(f"Target detected: {distance_m:.2f}メートル")

                # --- 保存・送信処理 ---
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                filename = f"{SAVE_DIR}/current_frame.jpg"
                cv2.imwrite(filename, frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                
                # ファイルを確実に閉じるための with
                try:
                    with open(filename, 'rb') as f:
                        url = "http://192.168.23.57:5001/ocr"
                        files = {'imagefile': f}
                        payload = {'filename': filename, 'distance': distance_m}
                        # タイムアウトを設定してフリーズを防止
                        response = requests.post(url, files=files, data=payload, timeout=5)
                        print(f"Server Response: {response.json()}")
                except Exception as e:                    
                    print(f"Upload failed: {e}")
                
                last_save_time = current_time


            # CPU負荷を抑えるための微小なスリープ
            time.sleep(0.01)

    except Exception as e:
        print(f"Error in camera loop: {e}")
    finally:
        picam2.stop()

# カメラ処理を別スレッドで実行
threading.Thread(target=camera_process, daemon=True).start()

@app.route('/')
def status():
    return "IMX708 (AF) + MediaPipe: Recording 1 pic per 2 sec."

if __name__ == "__main__":
    # 2026年のRaspberry Pi 3B環境でも安定するようにホストを指定
    app.run(host='0.0.0.0', port=5000, debug=False)
