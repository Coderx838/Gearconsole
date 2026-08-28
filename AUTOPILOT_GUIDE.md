# AI Autopilot & LLM Brain Engine for Bluetooth RC Car

This repository contains a full reverse-engineered driver and autonomous AI autopilot engine for the **LCW RC Car / JD-JM01 Series**, built using Python, OpenCV Computer Vision, Speech Recognition, and Multimodal LLM Reasoning.

---

## 1. Reverse-Engineered APK Protocol Breakdown

From deep inspection of the APK (`0_LCW_RCcar_1.0.3.apk`) and decompilation of `app-service.js`, the car communicates over **Bluetooth Low Energy (BLE)** using a 10-byte binary packet transmitted every **140 milliseconds**.

### BLE GATT Services & Characteristics
- **Target MAC Address**: `D6:C5:29:61:63:AE` (or discovered via scan)
- **Notify Characteristic UUID**: `0000fff1-0000-1000-8000-00805f9b34fb` (Telemetry handshake)
- **Write Characteristic UUID**: `0000fff2-0000-1000-8000-00805f9b34fb` (Motor control stream)

### 10-Byte Packet Bitwise Architecture

| Byte Index | Name | Structure / Bitmask | Description |
|---|---|---|---|
| **0 - 6** | Header | `0xAA, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00` | Fixed sync header |
| **7 (Byte 8)** | Motor & Feature Byte | `[Light][PlayMode (2 bits)][Spray][SpeedD][SpeedC][SpeedB][SpeedA]` | **Bit 7**: Headlight (1=ON, 0=OFF)<br>**Bit 6..5**: `10` = Manual, `01` = Demo Mode<br>**Bit 4**: Exhaust Smoke/Spray<br>**Bit 3**: Motor D (Steer Right)<br>**Bit 2**: Motor C (Steer Left)<br>**Bit 1**: Motor B (Reverse)<br>**Bit 0**: Motor A (Forward) |
| **8 (Byte 9)** | Accessory Byte | `00 + [Right][Left][RB][Tower][Bucket][Arm]` | **Bit 5**: Right Turn Mode<br>**Bit 4**: Left Turn Mode<br>**Bit 3**: Reverse (RB) Mode<br>**Bit 2**: Turret Rotation<br>**Bit 1**: Dump Bed Tilt<br>**Bit 0**: Excavator Arm |
| **9 (Byte 10)** | Flag Bit (Profile) | `0x01` / `0x02` / `0x03` | `0x01` = Supercar / RC Car<br>`0x02` = Dump Truck<br>`0x03` = Heavy Excavator |

---

## 2. Architecture Overview

```
+--------------------------------------------------------------------+
|                         AUTOPILOT ENGINE                           |
+---------------------------------+----------------------------------+
                                  |
         +------------------------+------------------------+
         |                        |                        |
+--------v---------+    +---------v--------+    +----------v---------+
|  VISION ENGINE   |    |   VOICE ENGINE   |    |     LLM BRAIN      |
|  (Eye Vision)    |    |  (Audio / Speech)|    | (Cognitive Planner)|
| - OpenCV HUD     |    | - SpeechRec (STT)|    | - Gemini Vision /  |
| - Target Tracker |    | - SAPI5 / pyttsx3|    |   Multimodal VLM   |
| - Obstacle Sonar |    | - Intent Parsing |    | - Tool Calling     |
| - Lane Detector  |    | - Spoken Feedback|    | - Spatial Analysis |
+--------+---------+    +---------+--------+    +----------+---------+
         |                        |                        |
         +------------------------+------------------------+
                                  | Action Dispatch
                        +---------v--------+
                        |  CAR DRIVER BLE  |
                        | - 140ms Heartbeat|
                        | - GATT Stream    |
                        | - Emergency Stop |
                        +---------+--------+
                                  |
                         [ Physical RC Car ]
```

---

## 3. Autonomous Operating Modes

1. **Mode 1: `MANUAL`**:
   - Drive directly using Keyboard keys (`W`, `A`, `S`, `D`), toggle headlights (`L`), exhaust smoke (`K`), reset coordinates (`R`), and E-Stop (`SPACE`).
2. **Mode 2: `VOICE`**:
   - Spoken commands processed in real-time with continuous dead-reckoning odometry tracking.
3. **Mode 3: `TRACK` (Visual Servoing)**:
   - Locks onto and follows colored objects/markers with PID steering.
4. **Mode 4: `EXPLORE` (Autonomous Collision Avoidance & 2D Mapping)**:
   - Roams the room autonomously, detects obstacles in front/sides, builds a 2D spatial occupancy grid, and dodges obstacles.
5. **Mode 5: `EMBODIED LLM BRAIN` (True Physical Car Consciousness)**:
   - The LLM receives its live physical body state:
     - **2D Cartesian Coordinates**: $(X, Y)$ in meters relative to start $(0,0)$.
     - **Compass Heading**: $\theta$ (0° North, 90° East, 180° South, 270° West).
     - **Top-Down 2D Spatial Occupancy Map**: showing trail '.', obstacles '#', and car body '^/>/v/<'.
     - **Eye Camera Snapshot**: visual surroundings in front of bumper.
   - Operates as a conscious agent in first person (*"I am at (0.8m, 1.2m) facing East. I see clear space ahead. Cruising forward."*), understanding multilingual voice/text commands and self-controlling its body.

---

## 4. Quickstart & Running

### Using the Python Virtual Environment
All dependencies are isolated inside the `./venv` directory.

```powershell
# 1. Activate the virtual environment
.\venv\Scripts\Activate.ps1

# 2. Run the Full AI Autopilot Engine
python autopilot_engine.py

# Optional Arguments:
# --mac   <MAC_ADDRESS>   (Default: D6:C5:29:61:63:AE)
# --cam   <CAMERA_INDEX>  (Default: 0 for built-in/USB webcam)
# --key   <GEMINI_API_KEY> (For multimodal LLM vision brain)
```

### Direct Testing of Individual Subsystems
- Test BLE Driver only:
  ```powershell
  python car_driver.py
  ```
- Test Computer Vision stream:
  ```powershell
  python vision_engine.py
  ```
- Test Voice Engine & TTS:
  ```powershell
  python voice_engine.py
  ```
