# Glasses-Mounted Camera System — Design Document

Last updated: 2026-10-11

## 1. Overview

A glasses-mounted camera and microphone unit (not integrated smart glasses): a Raspberry Pi device attached to
ordinary glasses with an arm (bracket), paired with an iPhone app that acts as an LLM agent. The user says a wake
word; the phone takes a photo through the device's camera and asks an LLM about what the user is looking at.

```
 ┌──────────── Glasses device (Raspberry Pi) ───────────┐          ┌──────────── iPhone app ─────────────┐
 │                                                       │  Wi-Fi   │                                      │
 │  Voice HAT mic ──► arecord ──► 16kHz PCM ──► /api/audio/stream ──┼─► Wake word (on-device speech)      │
 │                                                       │  (HTTP)  │        │                             │
 │  IMX708 camera ◄──────────────────────── /api/capture ◄──────────┼── take photo                        │
 │                                                       │          │        │                             │
 │  sudo halt ◄──────────────────────────── /api/shutdown ◄─────────┼── "hey glasses, halt"              │
 │                                                       │          │        ▼                             │
 │  app_shoot.py (Flask :5000), started by systemd       │          │  Chat ──► OpenAI API (HTTPS)         │
 └───────────────────────────────────────────────────────┘          └──────────────────────────────────────┘
```

| Part            | Repository / file                                   |
|-----------------|-----------------------------------------------------|
| Pi server       | `wearable_raspberrypi_ocr/app_shoot.py`             |
| Enclosure / arm | `wearable_raspberrypi_ocr/*.scad`, `*.3mf`, `*.amf` |
| iPhone app      | `smartglasses_app/` (SwiftUI)                       |

## 2. Hardware

| Item        | Part                                   | Notes                                              |
|-------------|----------------------------------------|----------------------------------------------------|
| Computer    | Raspberry Pi Zero 2 W                  | Raspberry Pi OS, user `yano`, host `raspberrypi.local` |
| Camera      | InnoMaker IMX708 (Camera Module 3 class) | Autofocus; `dtoverlay=imx708`, `camera_auto_detect=0` |
| Microphone  | Google Voice HAT (`sndrpigooglevoi`)   | 2ch / 48kHz / S32_LE                                |
| Enclosure   | 3D-printed "bento box" top + bottom    | `pizero2_top_fix.scad`, `pizero2_bottom.scad`; mic hole, GPIO slit |
| Glasses arm | 3D-printed L bracket                   | `Lbracket*.amf`; M2 screws                          |
| Power       | USB 5V (mobile battery)                | Check with `vcgencmd get_throttled` (0x0 = OK)       |

## 3. Pi Part — Features

Single process `app_shoot.py`: Flask HTTP server on port 5000 (`threaded=True`), plus an audio thread.

### P-1. Audio stream

- `arecord` captures 48kHz / 2ch / S32_LE from the Voice HAT.
- Converted to 16kHz / mono / int16: average channels, take the upper 16 bits, average 3 samples and drop 2
  (simple low-pass filter), then apply `GAIN` (10.0).
- Sent out in 80ms chunks to every connected client. A slow client drops chunks; the mic never blocks.
- The last 10 seconds are kept in a ring buffer.
- An RMS / peak level is logged every 5 seconds (`CLIPPING` is shown if the signal saturates).

| Endpoint            | Method | Response                                                    |
|---------------------|--------|-------------------------------------------------------------|
| `/api/audio/stream` | GET    | Endless raw PCM 16kHz mono int16 (`?format=wav` adds a WAV header) |
| `/api/audio`        | GET    | WAV of the last N seconds (`?seconds=2`, max 10), for polling |

### P-2. Shoot camera

- Picamera2, 1280×960 RGB, continuous autofocus, AWB = Incandescent.
- On request: capture a frame, convert it to grayscale, rotate it 90° to the left to correct the mounting
  angle, and encode it as JPEG (quality 90).
- A camera lock makes sure only one capture runs at a time.

| Endpoint       | Method     | Response                                   |
|----------------|------------|--------------------------------------------|
| `/api/capture` | POST / GET | `image/jpeg`; 503 if the camera isn't ready |

### P-3. Shutdown Pi

- Replies first, then runs `sudo halt` after 1 second in a background thread.
- POST only, so a link preview or prefetch can't trigger it.
- Requires passwordless sudo for `yano`.

| Endpoint        | Method | Response                                    |
|-----------------|--------|---------------------------------------------|
| `/api/shutdown` | POST   | `{"status": "ok", "message": "Shutting down"}` |

### P-4. Auto start (systemd) — supplement

- `/etc/systemd/system/glasses.service` runs `python3 /home/yano/app_shoot.py` as user `yano` at boot.
- `Restart=always` (3s delay); logs are kept in the system journal.
- Operations: `systemctl status glasses`, `journalctl -u glasses -f`, `sudo systemctl restart glasses`.
- Deploy: `scp app_shoot.py yano@raspberrypi.local:~/`, then restart the service.

## 4. LLM Agent App Part — Features

SwiftUI iPhone app. Files: `ContentView.swift`, `SettingsView.swift`, `ChatStore.swift`, `WakeWordListener.swift`.

### A-1. Configuration

Saved in UserDefaults (prototype; the API key should move to the Keychain).

| Setting        | Key              | Default                  |
|----------------|------------------|--------------------------|
| OpenAI API key | `openai_api_key` | (empty)                  |
| Model          | `openai_model`   | `gpt-5-mini`             |
| Glasses host   | `glasses_host`   | `raspberrypi.local:5000` |
| Wake word      | `wake_word`      | `hey glasses`            |
| Speech language | `speech_locale` | `en-US` (`ja-JP` available) |
| Listening on/off | `listening`    | on                       |

### A-2. Chat

- Message list with text and an optional image; replies are streamed from OpenAI Chat Completions (SSE).
- Images are sent as base64 JPEG data URLs.
- The system prompt explains the glasses context (grayscale camera, transcripts that start with the wake word).
- Glasses button = manual capture; the photo is attached to the next message. Also: Stop, New Chat.
- Errors are shown in an alert.

### A-3. Wake word / voice commands — supplement

- Connects to `/api/audio/stream` and feeds the audio to `SFSpeechRecognizer` with on-device recognition only,
  so no audio leaves the phone.
- A sentence ends after 1.2 seconds without new words; the recognition task is restarted at least every 50 seconds.
- Matching ignores case, spaces and punctuation.

| Utterance                                  | Action                                         |
|--------------------------------------------|------------------------------------------------|
| `<wake word>` + anything                   | Capture a photo, then send it with the sentence to the LLM |
| `<wake word>` + only `halt` / `stop` / `shut down` / `power off` | Call `/api/shutdown`          |

- Listening runs only while the app is in the foreground.
- Reconnect: the stream times out after 10 seconds without data, and the app retries every 2 seconds.

## 5. Non-functional — supplement

| Area         | Current design                                                    | Notes / TODO                                   |
|--------------|-------------------------------------------------------------------|------------------------------------------------|
| Network      | Same Wi-Fi (phone hotspot); plain HTTP on the LAN                 | iOS needs `NSAllowsLocalNetworking`; turn off Pi Wi-Fi power save (it causes drops) |
| Security     | No authentication on Pi endpoints                                 | Add a shared token header, at least for `/api/shutdown` |
| Privacy      | Speech recognition on the phone; only the wake-word sentence and photo go to OpenAI | Show users what gets sent         |
| Reliability  | systemd restart; app auto-reconnect; slow clients drop audio      | Health endpoint (`/api/status`) for the app UI |
| Power        | USB battery                                                       | Measure runtime; battery level / low-voltage warning |
| Latency      | 1.2s end-of-speech wait, then capture, then LLM                   | Measure end-to-end time                         |
| Logging      | Pi: journal; app: `print` to the console                          |                                                |

## 6. Known Limitations / Future Work

- Background listening: iOS stops the listener when the app leaves the foreground.
- Text-to-speech of replies (device speaker or AirPods) for hands-free use.
- Wake word false positives / misses; tune GAIN and the 1.2s pause.
- Store the API key in the Keychain.
- Battery status and a graceful shutdown on low battery.
- Color images (currently grayscale) if the model benefits from color.
