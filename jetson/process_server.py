import os
import subprocess
import tempfile

import ollama
from flask import Flask, request

app = Flask(__name__)

# ollama pull した VLM のタグ名（例: qwen2.5vl:3b, moondream, llava）
VLM_MODEL = os.environ.get("VLM_MODEL", "qwen2.5vl:3b")
# Piperの音声モデル(.onnx)へのパス
PIPER_MODEL = os.environ.get("PIPER_MODEL", "/models/en_US-lessac-medium.onnx")

PROMPT = (
    "Read the text visible in this image exactly as written. "
    "Reply with only the transcribed text, nothing else. "
    "If there is no readable text, reply with an empty string."
)


def extract_text(image_bytes: bytes) -> str:
    response = ollama.chat(
        model=VLM_MODEL,
        messages=[{
            "role": "user",
            "content": PROMPT,
            "images": [image_bytes],
        }],
    )
    return response["message"]["content"].strip()


def speak(text: str) -> None:
    with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
        subprocess.run(
            ["piper", "--model", PIPER_MODEL, "--output_file", audio_file.name],
            input=text.encode("utf-8"),
            check=True,
        )
        subprocess.run(["aplay", "-q", audio_file.name], check=True)


@app.route("/process", methods=["POST"])
def process():
    image_file = request.files.get("imagefile")
    if image_file is None:
        return {"status": "error", "message": "imagefile is required"}, 400

    distance = request.form.get("distance")
    image_bytes = image_file.read()

    text = extract_text(image_bytes)
    print(f"[distance={distance}] Detected text: {text!r}")

    if not text:
        return {"status": "success", "detected_text": ""}, 200

    speak(text)
    return {"status": "success", "detected_text": text}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
