import cv2
import os
import threading
import time
import requests
from collections import deque

# 保存ディレクトリ作成
SAVE_DIR = "/dev/shm/captured_images"
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

IMAGE_PATH = os.path.join(SAVE_DIR, "current_frame.jpg")

# OCR/TTSを行うリモートデバイスのエンドポイント（環境変数で上書き可能）
REMOTE_ENDPOINT = os.environ.get("PROCESS_ENDPOINT", "http://192.168.237.57:5001/process")

# 同一ページの重複送信を避けるための、レンズ位置(ピント距離)の判定パラメータ
LENS_HISTORY_SIZE = 5        # 直近何フレーム分のレンズ位置を見て「静止」を判定するか
LENS_STABLE_THRESHOLD = 0.05  # この範囲内のブレなら「静止」とみなす
LENS_SAME_PAGE_THRESHOLD = 0.05  # 前回送信時との差がこの範囲内なら「同じページ」とみなしスキップ


def send_frame(image_bytes, distance_m):
    # カメラループをブロックしないよう別スレッドで送信
    try:
        files = {'imagefile': ('current_frame.jpg', image_bytes, 'image/jpeg')}
        payload = {'distance': distance_m}
        response = requests.post(REMOTE_ENDPOINT, files=files, data=payload, timeout=5)
        print(f"Server response: {response.status_code}")
    except Exception as e:
        print(f"Upload failed: {e}")


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
    lens_history = deque(maxlen=LENS_HISTORY_SIZE)
    last_sent_lens_pos = None

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

            # 4. レンズ位置の履歴を更新し、カメラが静止しているか判定
            lens_history.append(current_lens_pos)
            last_save_time = current_time

            if len(lens_history) < LENS_HISTORY_SIZE:
                # 履歴が十分に溜まるまで（静止確認中）は送信しない
                continue

            lens_spread = max(lens_history) - min(lens_history)
            if lens_spread > LENS_STABLE_THRESHOLD:
                # まだカメラが動いている（ブレ画像を避けるため待機）
                continue

            if (last_sent_lens_pos is not None
                    and abs(current_lens_pos - last_sent_lens_pos) < LENS_SAME_PAGE_THRESHOLD):
                # 前回送信時とほぼ同じ位置 → 同じページとみなしスキップ
                print(f"Skipping: Same page as last sent (distance: {distance_m:.2f})")
                continue

            print(f"Target detected: {distance_m:.2f}メートル")

            # --- 保存・送信処理 ---
            frame_gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
            cv2.imwrite(IMAGE_PATH, frame_gray, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            last_sent_lens_pos = current_lens_pos

            # HTTP送信はカメラループをブロックしないよう非同期で実行
            success, encoded = cv2.imencode('.jpg', frame_gray, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            if success:
                threading.Thread(
                    target=send_frame, args=(encoded.tobytes(), distance_m), daemon=True
                ).start()

            # CPU負荷を抑えるための微小なスリープ
            time.sleep(0.05)

    except Exception as e:
        print(f"Error in camera loop: {e}")
    finally:
        picam2.stop()


if __name__ == "__main__":
    camera_process()
