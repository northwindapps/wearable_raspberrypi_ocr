import queue
import sys

import numpy as np
import ollama
import sounddevice as sd
from faster_whisper import WhisperModel
from openwakeword.model import Model as WakeWordModel

from tts import speak

SAMPLE_RATE = 16000
WAKEWORD_CHUNK = 1280  # openwakeword が要求するフレーム長 (80ms @16kHz)
WAKEWORD_THRESHOLD = 0.5
COMMAND_SECONDS = 5  # ウェイクワード検知後にコマンドとして録音する秒数

CHAT_MODEL = "qwen2.5vl:3b"  # 対話応答生成に使うLLM（OCR用VLMと共用）
WHISPER_MODEL_SIZE = "small"  # tiny/base/small/medium

SYSTEM_PROMPT = (
    "You are a helpful voice assistant for a visually assistive wearable device. "
    "Answer briefly and conversationally, in one or two sentences."
)


def record_seconds(seconds: float) -> np.ndarray:
    frames = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    return frames.flatten()


def transcribe(whisper: WhisperModel, audio: np.ndarray) -> str:
    audio_float = audio.astype(np.float32) / 32768.0
    segments, _ = whisper.transcribe(audio_float, language="en")
    return "".join(segment.text for segment in segments).strip()


def ask_llm(text: str) -> str:
    response = ollama.chat(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )
    return response["message"]["content"].strip()


def main():
    print("Loading wake word model...")
    wakeword = WakeWordModel()

    print(f"Loading Whisper model ({WHISPER_MODEL_SIZE})...")
    whisper = WhisperModel(WHISPER_MODEL_SIZE, device="cuda", compute_type="int8_float16")

    audio_q = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        audio_q.put(indata.copy())

    print("Voice assistant listening for wake word...")
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=WAKEWORD_CHUNK,
        callback=callback,
    ):
        while True:
            chunk = audio_q.get().flatten()
            predictions = wakeword.predict(chunk)
            triggered = any(score > WAKEWORD_THRESHOLD for score in predictions.values())
            if not triggered:
                continue

            print("Wake word detected. Listening for command...")
            command_audio = record_seconds(COMMAND_SECONDS)

            text = transcribe(whisper, command_audio)
            if not text:
                print("No speech recognized.")
                continue
            print(f"User said: {text!r}")

            reply = ask_llm(text)
            print(f"Assistant: {reply!r}")
            speak(reply)


if __name__ == "__main__":
    main()
