import cv2
import os
import time
import requests

# 保存ディレクトリ作成
SAVE_DIR = "/dev/shm/captured_images"
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

IMAGE_PATH = os.path.join(SAVE_DIR, "current_frame.jpg")

# OCR/TTSを行うリモートデバイスのエンドポイント（環境変数で上書き可能）
REMOTE_ENDPOINT = os.environ.get("PROCESS_ENDPOINT", "http://192.168.237.57:5001/process")


def camera_process():
    # picamera2のインポート（実行時に読み込み）
    from picamera2 import Picamera2
    picam2 = Picamera2()

    # 1. 解析速度を稼ぐため 1280x960 に設定
    config = picam2.create_preview_configuration(
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

            # 3. 「0.5秒に1枚」のタイミングかチェック
            current_time = time.time()
            if current_time - last_save_time < 0.5:
                time.sleep(0.1)  # CPUを休ませる
                continue

            # メタデータ取得
            metadata = picam2.capture_metadata()
            current_lens_pos = metadata.get('LensPosition', 0)

            # 距離判定：0以下（無限遠）はスキップ
            if current_lens_pos <= 0:
                print("Focus: Infinity or Unknown (Skipping...)")
                last_save_time = current_time
                continue

            # 距離計算（ログ用）
            distance_m = 1.0 / current_lens_pos

            if distance_m > 0.80:
                print(f"Skipping: Distance too far (distance: {distance_m:.2f})")
                last_save_time = current_time
                continue

            print(f"Target detected: {distance_m:.2f}メートル")

            # --- 保存・送信処理 ---
            frame_gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
            cv2.imwrite(IMAGE_PATH, frame_gray, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            last_save_time = current_time

            try:
                with open(IMAGE_PATH, 'rb') as f:
                    files = {'imagefile': f}
                    payload = {'distance': distance_m}
                    response = requests.post(REMOTE_ENDPOINT, files=files, data=payload, timeout=5)
                    print(f"Server response: {response.status_code}")
            except Exception as e:
                print(f"Upload failed: {e}")

            # CPU負荷を抑えるための微小なスリープ
            time.sleep(0.05)

    except Exception as e:
        print(f"Error in camera loop: {e}")
    finally:
        picam2.stop()


if __name__ == "__main__":
    camera_process()
