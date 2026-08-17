import os
import subprocess
import tempfile

# Piperの音声モデル(.onnx)へのパス
PIPER_MODEL = os.environ.get("PIPER_MODEL", "/models/en_US-lessac-medium.onnx")


def speak(text: str) -> None:
    if not text:
        return
    with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
        subprocess.run(
            ["piper", "--model", PIPER_MODEL, "--output_file", audio_file.name],
            input=text.encode("utf-8"),
            check=True,
        )
        # macOSには aplay(ALSA) がないため afplay を使用
        subprocess.run(["afplay", audio_file.name], check=True)
