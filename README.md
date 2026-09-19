# Gear Console

Autonomous AI control software for a Bluetooth Low Energy (BLE) remote-control vehicle.

## Project status and disclaimer

This project is an experimental work in progress and is actively under development. It has not been validated as a safety-critical vehicle-control system.

Known limitations include:

- Bluetooth disconnects and packet loss may occur, especially with inexpensive toy-car receivers.
- Optical tracking performance depends on camera placement, lighting, floor contrast, and the visibility of the tracking marker.
- AI responses introduce network latency and may be incomplete or incorrect.
- Toy RC cars generally do not include LiDAR, wheel encoders, or inertial measurement units (IMUs). Spatial estimates are therefore based on overhead-camera color tracking and/or dead reckoning rather than onboard sensors.
- The obstacle-detection and emergency-stop features are software safeguards and do not guarantee collision avoidance.

Use the system in a controlled environment. Test at low speed, keep a manual emergency stop available, and do not use it around people, animals, traffic, or property where an unintended movement could cause harm. Contributions, bug reports, and pull requests are welcome.

## Contents

- [Features](#features)
- [System architecture](#system-architecture)
- [Operating modes](#operating-modes)
- [BLE command protocol](#ble-command-protocol)
- [Repository structure](#repository-structure)
- [Quick start](#quick-start)
- [Mobile phone camera setup](#mobile-phone-camera-setup)
- [Configuration](#configuration)
- [Known limitations and troubleshooting](#known-limitations-and-troubleshooting)
- [License](#license)

## Features

### Multimodal AI control

Mode 5 sends camera frames, the current room name, an estimated `(X, Y)` position, and a two-dimensional ASCII grid to Google's Gemini API. The model is expected to return structured JSON containing a response and a sequence of movement pulses such as `forward`, `left`, `right`, and `backward`.

The exact model name and API behavior depend on the implementation and the configured SDK. AI output should be treated as advisory control input rather than a guaranteed plan.

### AI-assisted room scanning

Mode S captures keyframes while the operator walks through a home with a phone camera. The images are sent to Gemini Vision to identify visible rooms and furniture landmarks. The resulting map is written to [`home_map.json`](home_map.json) and should be reviewed manually before use.

### Overhead optical tracking

An overhead phone or laptop camera can track a cross made from green tape on the vehicle roof. OpenCV HSV thresholding uses the range `[35, 60, 60]` to `[85, 255, 255]` to estimate the vehicle's metric position and heading.

This approach is intended for small vehicles that cannot carry a smartphone or other substantial sensor payload.

### Obstacle detection and automatic braking

The active camera stream is processed at a target rate of 20 Hz using OpenCV contour and brightness analysis. When an object appears to occupy the forward safety zone, the software can override normal commands and send a stop packet.

This is a best-effort software feature and should not be considered a substitute for physical safety controls.

### BLE reconnection

The driver handles Bleak disconnection callbacks when the vehicle is switched off or loses power. Active routines are paused, an audio notification may be produced through `pyttsx3`/SAPI5, and the driver attempts to reconnect up to five times over approximately 15 seconds before exiting cleanly.

### BLE device discovery

Mode B uses `BleakScanner` to list nearby BLE devices, including names, addresses, and RSSI values. A selected vehicle address can be saved instead of being hardcoded.

### Terminal interface

The terminal interface uses the `rich` library to display startup information, connection state, camera status, and telemetry tables.

## System architecture

```text
                                  +-----------------------------+
                                  |    User (Voice / Terminal)  |
                                  +--------------+--------------+
                                                 |
                                                 v
+------------------------------------------------------------------------------------------------+
|                                    GEAR CONSOLE v1.0.3                                         |
|                                                                                                |
|  +--------------------------+  +--------------------------+  +-------------------------------+ |
|  |     AI Room Scanner      |  |   Spatial Localization   |  |     Multimodal LLM Brain      | |
|  | (Walkthrough Video Map)  |  |  (Green Cross + Odometry)|  |  (Gemini VLM + Multilingual)  | |
|  +------------+-------------+  +------------+-------------+  +---------------+---------------+ |
|               |                             |                                |                 |
|               +-----------------------------+--------------------------------+                 |
|                                             |                                                  |
|                                             v                                                  |
|                               +---------------------------+                                    |
|                               | 20Hz Auto-Brake Reflexes |                                    |
|                               +-------------+-------------+                                    |
|                                             |                                                  |
|                                             v                                                  |
|                               +---------------------------+                                    |
|                               | BLE Motor Driver (140ms)  |                                    |
|                               +-------------+-------------+                                    |
+---------------------------------------------|--------------------------------------------------+
                                              | (Bluetooth Low Energy GATT)
                                              v
                              +-------------------------------+
                              |    Physical RC Car Vehicle    |
                              |   (Pair via [B] Scan Option)  |
                              +-------------------------------+
```

## Operating modes

| Mode | Key | Description |
|:---:|:---:|---|
| Manual driving | `[1]` | WASD keyboard control with headlights (`L`), exhaust smoke (`K`), origin reset (`R`), and emergency stop (`SPACE`). |
| Voice navigation | `[2]` | SpeechRecognition-based input for movement commands in English, Hindi, or other supported languages. |
| Target tracking | `[3]` | OpenCV color-contour tracking that drives toward a recognized visual target. |
| Autonomous explorer | `[4]` | Basic wandering and turn logic that reverses and steers away when an obstacle is detected in the camera view. |
| Multimodal AI control | `[5]` | Gemini-based navigation using floorplans, estimated coordinates, and camera input. |
| AI room scanner | `[S]` | Phone-video walkthrough tool that generates or updates `home_map.json` using Gemini Vision. |
| BLE device discovery | `[B]` | Scans for nearby BLE devices and helps select a vehicle. |
| Camera configuration | `[C]` | Switches between a laptop webcam and a mobile-phone IP camera stream over Wi-Fi. |
| Quit | `[Q]` | Disconnects BLE links and exits the console cleanly. |

## BLE command protocol

The vehicle communicates over BLE GATT using 10-byte binary command frames sent to characteristic `0xFFF2`. The driver targets a 140 ms command heartbeat.

```text
Byte:    0     1     2     3     4     5     6      7        8        9
Value: [0xAA, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00, <Byte 8>, <Byte 9>, <Byte 10>]
```

### Bitmask definitions

- **Byte 8:** `[Light(1)][PlayMode(2)][Spray(1)][SpeedD(1)][SpeedC(1)][SpeedB(1)][SpeedA(1)]`
  - `SpeedA`: forward drive
  - `SpeedB`: reverse drive
  - `SpeedC`: steer left
  - `SpeedD`: steer right
  - `Light`: headlights (`1` = on, `0` = off)
  - `Spray`: exhaust smoke generator (`1` = on, `0` = off)
- **Byte 9:** `00 + [RightMode(1)][LeftMode(1)][RBMode(1)][Tower(1)][Bucket(1)][Arm(1)]`
  - Directional overrides and accessory motors for construction-vehicle variants.
- **Byte 10 (`flagBit`):** `0x01` for supercar/sport, `0x02` for dump truck, and `0x03` for heavy machinery.

This protocol was reverse-engineered for the supported vehicle hardware. Other vehicles may use different services, characteristics, packet layouts, or timing requirements.

## Repository structure

```text
Gearconsole/
├── controller.py          # Main application entry point
├── home_map.json          # AI-generated or user-edited multi-room layout
├── requirements.txt       # Python dependencies
├── .gitignore
├── LICENSE
├── README.md
│
├── driver/                # Hardware and BLE motor-driver subsystem
│   ├── __init__.py
│   └── car_driver.py      # BLE GATT driver, command streaming, and reconnection
│
├── vision/                # Computer vision and video-scanning subsystem
│   ├── __init__.py
│   ├── vision_engine.py   # Visual perception, HUD, and obstacle detection
│   ├── green_tracker.py   # Overhead green-marker tracking
│   └── ai_room_scanner.py # AI walkthrough and floorplan generation
│
├── brain/                 # AI and voice subsystem
│   ├── __init__.py
│   ├── llm_brain.py       # Gemini multimodal reasoning and speech output
│   ├── voice_engine.py    # Speech recognition and text-to-speech
│   └── ui_theme.py        # Rich terminal interface
│
└── spatial/               # Localization and mapping subsystem
    ├── __init__.py
    ├── spatial_odometry.py# Two-dimensional localization and ASCII maps
    └── room_mapper.py     # Room management and pathfinding
```

## Quick start

### Prerequisites

- Python 3.10 or later
- A Bluetooth 4.0 or later adapter
- A Google Gemini API key for AI features
- A compatible BLE-controlled RC vehicle
- A camera for vision features

### Installation

```powershell
git clone https://github.com/Coderx838/Gearconsole.git
cd Gearconsole

python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### Configure the Gemini API key

Create a `.env` file in the repository root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

Do not commit this file or expose the API key in logs, screenshots, or source code.

### Launch

Use the default laptop webcam:

```powershell
python controller.py
```

Use a phone IP-camera stream:

```powershell
python controller.py --cam "http://192.168.31.239:8080/video"
```

## Mobile phone camera setup

1. Install IP Webcam on Android or IP Camera Lite on iOS.
2. Connect the phone and computer to the same Wi-Fi network.
3. Start the camera server in the mobile application.
4. Launch Gear Console with the stream URL. Depending on the application, the URL may end in `/video` or `/videofeed`.

```powershell
python controller.py --cam "http://<PHONE_IP>:8080/video"
```

For overhead tracking, optionally attach a small green-tape cross to the vehicle roof and point the phone camera toward the driving area. Keep the camera stationary and ensure that the marker is visible throughout the operating area.

## Configuration

| Variable or key | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | Not set | Google Gemini API key used by the multimodal brain and room scanner. |
| `CAR_MAC` | Not set | BLE address of the RC vehicle; the vehicle can also be selected through `[B]`. |
| `DEFAULT_CAMERA` | `0` | Camera device index or phone IP-camera stream URL. |

## Known limitations and troubleshooting

- **Bluetooth packet drops:** Inexpensive BLE receivers may have small buffers. Fast writes can be dropped when the Bluetooth adapter or operating system is busy. The driver uses periodic command streaming, but it cannot guarantee delivery.
- **Dead-reckoning drift:** Estimated `(X, Y)` coordinates drift over time because of wheel slip and uneven surfaces. Use the overhead tracker or press `[R]` to reset the origin.
- **Lighting sensitivity:** Green-marker tracking depends on the configured HSV range. Dim lighting, reflections, shadows, or yellow lighting may require changes in `vision/green_tracker.py`.
- **Camera stream errors:** Use the camera application's video endpoint, such as `/video` or `/videofeed`, rather than its root HTML page.
- **AI latency or invalid responses:** Network conditions, API quotas, model changes, and malformed responses can affect Mode 5 and Mode S. Verify API credentials and review generated navigation or map data before use.
- **BLE discovery issues:** Confirm that the vehicle is powered on, within range, and not already connected to another device. On some platforms, Bluetooth permissions or adapter drivers may also be required.
- **Obstacle detection limitations:** Camera-based detection can miss transparent, low-contrast, or poorly lit obstacles. Keep speeds low and supervise the vehicle.

## License

This project is distributed under the MIT License. See [`LICENSE`](LICENSE) for the complete license text.

Developed with ❤️ for Autonomous Robotics & Embodied AI enthusiasts.
