# 🕹️ GEAR CONSOLE: Autonomous AI RC Vehicle Intelligence System

<p align="center">
  <img src="https://img.shields.io/badge/Release-v1.0.3-00ffff.svg?style=for-the-badge&logo=appveyor" alt="Version">
  <img src="https://img.shields.io/badge/Status-Under%20Active%20Development-yellow.svg?style=for-the-badge" alt="Status">
  <img src="https://img.shields.io/badge/Python-3.10%2B-00ff88.svg?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/UI-Cyberpunk%20Rich%20Terminal-b800ff.svg?style=for-the-badge" alt="Terminal UI">
  <img src="https://img.shields.io/badge/Brain-Google%20Gemini%20VLM-ffaa00.svg?style=for-the-badge&logo=google" alt="Gemini">
  <img src="https://img.shields.io/badge/Protocol-BLE%20GATT%20140ms-7000ff.svg?style=for-the-badge&logo=bluetooth" alt="BLE">
  <img src="https://img.shields.io/badge/License-MIT-brightgreen.svg?style=for-the-badge" alt="License">
</p>

```
  ____  _____     _     ____     ____  _____  _   _  ____  _____  _      _____ 
 / ___|| ____|   / \   |  _ \   / ___|/ _ \ \| \ | |/ ___|| _ \ || |    | ____|
| |  _ |  _|    / _ \  | |_) | | |   | | | | |  \| |\___ \| | | || |    |  _|  
| |_| || |___  / ___ \ |  _ <  | |___| |_| | | |\  | ___) | |_| || |___ | |___ 
 \____||_____|/_/   \_\|_| \_\  \____|\___/ /|_| \_||____/|____/ |_____||_____|
   >> GEAR CONSOLE   v1.0.3  --- Autonomous AI RC Vehicle Intelligence System
```

> [!WARNING]
> ### ⚠️ Project Status & Honest Developer Disclaimer
> **This project is an experimental work-in-progress (WIP) and is actively under development.**
> - **Expect bugs, quirks, and rough edges**: Bluetooth disconnects, optical tracker sensitivity to room lighting, and API latency can affect performance.
> - **No False Claims / Hardware Reality**: Toy RC cars lack expensive hardware like onboard LiDAR, wheel encoders, or IMUs. Spatial tracking is done via **overhead camera color tracking** or **time-based dead-reckoning kinematics** (which accumulates wheel slip on smooth tiles/carpets over time). LLM reasoning latency depends on cloud API roundtrip times (~1.5s - 2.5s).
> - You are welcome to test, tinker, report bugs, and submit pull requests!

---

## 📑 Table of Contents
- [🌟 Real Features & How They Work](#-real-features--how-they-work)
- [🏛️ System Architecture](#-system-architecture)
- [🕹️ Autonomous Operating Modes](#-autonomous-operating-modes)
- [📡 Reverse-Engineered Binary Protocol](#-reverse-engineered-binary-protocol)
- [📦 Modular Codebase Structure](#-modular-codebase-structure)
- [🚀 Quick Start Guide](#-quick-start-guide)
- [📱 Mobile Phone Camera Setup (Overhead Satellite / FPV)](#-mobile-phone-camera-setup-overhead-satellite--fpv)
- [⚙️ Configuration & Environment Variables](#-configuration--environment-variables)
- [⚠️ Known Limitations & Troubleshooting](#-known-limitations--troubleshooting)
- [📄 License & Credits](#-license--credits)

---

## 🌟 Real Features & How They Work

### 1. Embodied Multimodal AI Control (Mode 5)
- Passes camera frames, current room name, estimated $(X, Y)$ position, and 2D ASCII grid representations to Google's **Gemini 3.5 Flash-Lite** API.
- The model outputs structured JSON with a thought process, natural spoken reply, and sequential pulse movements (`forward`, `left`, `right`, `backward`).

### 2. AI Video Walkthrough Multi-Room Floorplan Scanner (Mode S)
- Captures keyframe snapshots while you walk around your home holding your phone camera.
- Sends the images to Gemini Vision to detect visible rooms and furniture landmarks, writing the output into [`home_map.json`](home_map.json).

### 3. Overhead Satellite Green Cross Optical Tracker
- Designed for small RC cars that cannot carry a heavy smartphone.
- An overhead phone or laptop camera tracks a small cross of **green tape** on the car roof using OpenCV HSV color thresholding (`[35, 60, 60]` to `[85, 255, 255]`) to calculate metric position $(X, Y)$ and heading angle $\theta$.

### 4. 20Hz Obstacle Reflex Auto-Brake
- Runs a fast 20Hz OpenCV contour and brightness analysis on the active camera stream.
- If a large obstacle suddenly fills the forward safety zone, it overrides software commands and sends an immediate stop packet to prevent collisions.

### 5. Fault-Tolerant Auto-Reconnection
- Catches Bleak `disconnected_callback` when the physical car is switched off or battery drops.
- Pauses active driving routines, gives voice alerts via pyttsx3/SAPI5, and enters a 5-attempt reconnect loop (15s total) before cleanly exiting.

### 6. Dynamic Bluetooth Device Discovery (Mode B)
- Scans for nearby BLE devices using `BleakScanner`, lists names/MACs/RSSI values, and lets you select and save your car's MAC address without hardcoding.

### 7. Cyberpunk Rich Terminal Cockpit
- Built with Python's `rich` library with an animated boot sequence, colored status badges (`(*) CONNECTED`, `⚡ STREAM: 140ms`), and flight telemetry tables.

---

## 🏛️ System Architecture

```
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
|                               | 20Hz Auto-Brake Reflexes  |                                    |
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

---

## 🕹️ Autonomous Operating Modes

| Mode | Key | Description |
|:---:|:---:|---|
| **`[1]`** | **MANUAL DRIVING** | WASD keyboard control with headlights (`L`), exhaust smoke (`K`), origin reset (`R`), and E-Stop (`SPACE`). |
| **`[2]`** | **VOICE NAVIGATION** | SpeechRecognition (Google STT) listening for natural movement commands in English, Hindi, or other languages. |
| **`[3]`** | **TARGET TRACKING** | OpenCV color contour tracking that drives toward recognized visual targets. |
| **`[4]`** | **AUTONOMOUS EXPLORER** | Basic wander & turn logic that backs up and steers away when obstacles appear in camera view. |
| **`[5]`** | **EMBODIED LLM BRAIN** | Multimodal Gemini VLM conscious agent navigating using floorplans, coordinates, and visual input. |
| **`[S]`** | **AI ROOM SCANNER** | Phone video walkthrough tool that asks Gemini Vision to construct `home_map.json`. |
| **`[B]`** | **BLE AUTO-DISCOVERY** | Scans and lists nearby BLE devices so you can connect to any RC car. |
| **`[C]`** | **CAMERA CONFIG** | Switch between Laptop Webcam and Mobile Phone IP Camera stream over WiFi. |
| **`[Q]`** | **QUIT CONSOLE** | Disconnects BLE GATT links and exits cleanly. |

---

## 📡 Reverse-Engineered Binary Protocol

The vehicle communicates over BLE GATT using 10-byte binary command frames streamed at a **140ms heartbeat** to characteristic `0xFFF2`:

```
Byte:    0     1     2     3     4     5     6      7        8        9
Value: [0xAA, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00, <Byte 8>, <Byte 9>, <Byte 10>]
```

### Bitmask Definitions:
- **Byte 8**: `[Light(1)][PlayMode(2)][Spray(1)][SpeedD(1)][SpeedC(1)][SpeedB(1)][SpeedA(1)]`
  - `SpeedA`: Forward Drive
  - `SpeedB`: Reverse Drive
  - `SpeedC`: Steer Left
  - `SpeedD`: Steer Right
  - `Light`: Headlights Toggle (1=ON, 0=OFF)
  - `Spray`: Exhaust Smoke Generator (1=ON, 0=OFF)
- **Byte 9**: `00 + [RightMode(1)][LeftMode(1)][RBMode(1)][Tower(1)][Bucket(1)][Arm(1)]`
  - Directional overrides and accessory motors for construction variants.
- **Byte 10 (`flagBit`)**: `0x01` (Supercar/Sport), `0x02` (Dump Truck), `0x03` (Heavy Machinery).

---

## 📦 Modular Codebase Structure

```
RC_controller/
├── controller.py          # Master Gear Console Orchestrator (Main Entry Point)
├── home_map.json          # AI-generated / customizable multi-room home layout
├── requirements.txt       # Python package dependencies
├── .gitignore             # Git ignore configuration
├── LICENSE                # MIT License
├── README.md              # Documentation
│
├── driver/                # Hardware & BLE Motor Driver Subsystem
│   ├── __init__.py
│   └── car_driver.py      # BLE GATT driver, 140ms streaming & auto-reconnection
│
├── vision/                # Computer Vision, Optical Tracking & Video Scanner
│   ├── __init__.py
│   ├── vision_engine.py   # OpenCV visual perception, HUD & obstacle sonar
│   ├── green_tracker.py   # Overhead satellite green cross marker tracker
│   └── ai_room_scanner.py # AI walkthrough video floorplan generator
│
├── brain/                 # Multimodal AI Cognition & Voice Synthesis
│   ├── __init__.py
│   ├── llm_brain.py       # Gemini VLM multimodal reasoning & multilingual speech
│   ├── voice_engine.py    # Speech recognition (STT) & audio feedback (TTS)
│   └── ui_theme.py        # Cyberpunk Rich Terminal UI & animation engine
│
└── spatial/               # 2D Localization, Odometry & Multi-Room Mapping
    ├── __init__.py
    ├── spatial_odometry.py# 2D localization kinematics & spatial ASCII maps
    └── room_mapper.py     # Multi-room floorplan management & pathfinding
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+
- Bluetooth 4.0+ adapter on your PC/laptop
- Google Gemini API Key

### 2. Installation

```powershell
# Clone the repository
git clone https://github.com/Coderx838/Gearconsole.git
cd Gearconsole

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Set Gemini API Key

Create a `.env` file in the root directory:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. Launch Gear Console

```powershell
# Default launch (Laptop Webcam)
python controller.py

# Launch with Phone IP Camera stream
python controller.py --cam "http://192.168.31.239:8080/video"
```

---

## 📱 Mobile Phone Camera Setup (Overhead Satellite / FPV)

1. Install **IP Webcam** (Android) or **IP Camera Lite** (iOS).
2. Connect your phone and laptop to the same WiFi network.
3. Tap **"Start Server"** in the app.
4. Launch Gear Console with your phone's URL (make sure it ends with `/video`):
   ```powershell
   python controller.py --cam "http://<PHONE_IP>:8080/video"
   ```
5. *(Optional)* Stick a small cross of **green tape** on top of your car roof. Point your phone camera down at the floor, and the **Green Cross Satellite Tracker** will track $(X, Y)$ position and heading angle.

---

## ⚙️ Configuration & Environment Variables

| Variable / Key | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | `None` | Google Gemini API Key for VLM brain and AI room mapping. |
| `CAR_MAC` | `None` | Bluetooth MAC Address of the physical RC car (or auto-discover via `[B]`). |
| `DEFAULT_CAMERA` | `0` | Default camera device index or Phone stream URL. |

---

## ⚠️ Known Limitations & Troubleshooting

- **Bluetooth Packet Drops**: Cheap BLE toy car receivers have small buffers. Fast write commands can occasionally drop packets if Windows Bluetooth is congested. We mitigate this with an `asyncio.Lock()` and unblocked `response=False` writes.
- **Dead-Reckoning Drift**: Estimated $(X, Y)$ coordinates will drift during long drives due to wheel slip on tiles/carpets. Use the overhead Green Cross Tracker or press `[R]` to re-zero.
- **Lighting Sensitivity**: Optical green cross tracking relies on HSV color ranges. Extremely dim rooms or harsh yellow light may require fine-tuning HSV bounds in [`vision/green_tracker.py`](vision/green_tracker.py).
- **IP Webcam URL**: Always ensure your IP camera URL ends with `/video` or `/videofeed` (not the root HTML page), or OpenCV will fail to stream frames.

---

## 📄 License & Credits

Distributed under the **MIT License**. See `LICENSE` for more information.

Developed with ❤️ for Autonomous Robotics & Embodied AI enthusiasts.
