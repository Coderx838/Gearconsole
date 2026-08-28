"""
=============================================================================
AI VISUAL ROOM SCANNER & FLOORPLAN GENERATOR
=============================================================================
Uses Phone IP Camera Walkthrough + Gemini Multimodal Vision to automatically
scan and generate a complete home map:
  1. Captures keyframe snapshots while user walks around holding their phone.
  2. Sends room keyframes to Gemini Multimodal Vision.
  3. Gemini reconstructs the floorplan: room boundaries, doorways, furniture & obstacles.
  4. Automatically outputs and saves `home_map.json` without any manual coding!
=============================================================================
"""

from __future__ import annotations
import os
import time
import json
import base64
import logging
from typing import List, Dict, Any, Optional

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    np = None
    CV2_AVAILABLE = False

import requests
try:
    from brain.llm_brain import load_api_key
except ImportError:
    try:
        from llm_brain import load_api_key
    except ImportError:
        def load_api_key():
            return os.environ.get("GEMINI_API_KEY")

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("RoomScanner")

MAP_OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "home_map.json")

SCANNER_SYSTEM_PROMPT = """You are an expert Spatial Robotics & Architectural 3D/2D Mapping AI.
You are given a sequence of camera images captured by a user walking through their home with a smartphone camera.

Your Task:
Analyze the images, reconstruct the multi-room floor plan, and output a valid JSON object matching the exact structure below.

Identify:
1. "starting_anchor": The main doorway / starting entrance where the car starts (at x: 0.0, y: 0.0).
2. "rooms": Each distinct room (Living Room, Bedroom, Hallway, Kitchen, etc.) with estimated bounds [x_min, y_min, x_max, y_max] in meters (assume a typical room is 3m - 5m wide).
3. "landmarks": Detect furniture/objects (Sofa, Bed, Desk, TV Table, Chair, Wardrobe) with estimated (x, y) coordinates.
4. "doorways": Connecting doors between rooms with (x, y) coordinates.

Required Output JSON Schema:
{
  "starting_anchor": {
    "name": "Main Entrance",
    "x": 0.0,
    "y": 0.0,
    "heading_degrees": 0.0,
    "description": "Starting entrance location"
  },
  "rooms": [
    {
      "name": "Living Room",
      "x_min": 0.0,
      "y_min": 0.0,
      "x_max": 4.0,
      "y_max": 3.5,
      "description": "Main living area with sofa and TV",
      "landmarks": [
        {"name": "Sofa", "x": 1.5, "y": 2.5},
        {"name": "TV Stand", "x": 3.2, "y": 0.8}
      ]
    }
  ],
  "doorways": [
    {
      "name": "Living Room to Hallway Door",
      "from_room": "Living Room",
      "to_room": "Hallway",
      "x": 4.0,
      "y": 1.75
    }
  ]
}

Return ONLY the raw JSON object without markdown fences or extra chatter.
"""


def normalize_camera_url(url: Any) -> Any:
    """Auto-formats phone IP addresses to ensure video stream endpoint is used."""
    if isinstance(url, str) and url.startswith("http"):
        url = url.strip().rstrip("/")
        if not any(url.endswith(ep) for ep in ["/video", "/videofeed", "/mjpeg", "/stream", ".mjpg"]):
            url = url + "/video"
    return url


class AIRoomScanner:
    def __init__(self, camera_source: Any = 0, gemini_api_key: Optional[str] = None):
        self.camera_source = normalize_camera_url(camera_source)
        self.api_key = gemini_api_key or load_api_key()
        self.captured_frames: List[np.ndarray] = []

    def start_interactive_scan(self, duration_seconds: int = 25, sample_interval: float = 3.0) -> Optional[Dict[str, Any]]:
        """
        Connects to phone IP stream, prompts user to walk around the rooms,
        captures keyframe snapshots, and sends them to Gemini for floorplan reconstruction.
        """
        if not CV2_AVAILABLE:
            logger.error("OpenCV is required for visual scanning.")
            return None

        self.camera_source = normalize_camera_url(self.camera_source)
        print("\n" + "=" * 65)
        print("       AI VISUAL ROOM SCANNER & 3D/2D MAPPER")
        print("=" * 65)
        print(f"Connecting to camera stream: [{self.camera_source}]...")

        cap = cv2.VideoCapture(self.camera_source)
        if not cap.isOpened():
            print(f"[ERROR] Could not open camera stream [{self.camera_source}].")
            print("Please ensure your IP Webcam app is running and your phone is on the same WiFi.")
            return None

        print("\n>>> STREAM CONNECTED! <<<")
        print("Instructions:")
        print("  1. Hold your phone and walk slowly through each room (Living Room, Hallway, Bedroom).")
        print("  2. Point camera at corners, doorways, furniture, and open floor space.")
        print(f"  3. Scanning will run for {duration_seconds} seconds (or press 'S' to finish early).")
        print("=" * 65 + "\n")

        self.captured_frames.clear()
        start_time = time.time()
        last_sample_time = 0.0

        while (time.time() - start_time) < duration_seconds:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.1)
                continue

            elapsed = int(time.time() - start_time)
            remaining = duration_seconds - elapsed

            # Overlay recording HUD
            hud = frame.copy()
            cv2.putText(hud, f"AI SCANNING: {remaining}s remaining", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            cv2.putText(hud, f"Keyframes: {len(self.captured_frames)} | Press 'S' to Save", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.imshow("AI Room Walkthrough Scanner", hud)

            # Sample keyframe every interval
            if time.time() - last_sample_time >= sample_interval:
                # Resize for lightweight VLM transfer
                small = cv2.resize(frame, (480, 360), interpolation=cv2.INTER_AREA)
                self.captured_frames.append(small)
                last_sample_time = time.time()
                print(f"  [Captured Keyframe #{len(self.captured_frames)}] at {elapsed}s")

            key = cv2.waitKey(1) & 0xFF
            if key == ord('s') or key == 27:  # 'S' or ESC
                break

        cap.release()
        cv2.destroyAllWindows()

        if not self.captured_frames:
            print("[ERROR] No keyframes were captured during the scan.")
            return None

        print(f"\n[SUCCESS] Captured {len(self.captured_frames)} room keyframes.")
        print("Analyzing walkthrough with Gemini Vision to reconstruct home map...")
        return self._generate_map_from_keyframes()

    def _generate_map_from_keyframes(self) -> Optional[Dict[str, Any]]:
        """Sends captured walkthrough keyframes to Gemini to reconstruct the full home map."""
        if not self.api_key:
            print("[ERROR] Gemini API key required for AI visual mapping.")
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={self.api_key}"

        parts = [
            {"text": SCANNER_SYSTEM_PROMPT},
            {"text": f"Here are {len(self.captured_frames)} sequential keyframe images from the walkthrough scan. Please reconstruct the full multi-room layout and output the JSON map:"}
        ]

        # Attach up to 6 keyframes as base64 JPEG
        for idx, img in enumerate(self.captured_frames[:6]):
            _, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
            b64_data = base64.b64encode(buf).decode("utf-8")
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": b64_data
                }
            })

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2
            }
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=25.0)
            if response.status_code == 200:
                raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if raw_text.startswith("```"):
                    raw_text = raw_text.split("\n", 1)[1]
                if raw_text.endswith("```"):
                    raw_text = raw_text.rsplit("```", 1)[0]
                raw_text = raw_text.strip()

                map_data = json.loads(raw_text)

                # Save generated map to home_map.json
                with open(MAP_OUTPUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(map_data, f, indent=2)

                print("\n" + "=" * 65)
                print("    [AI ROOM MAPPER] RECONSTRUCTED HOME MAP")
                print("=" * 65)
                print(f"Rooms Detected: {[r['name'] for r in map_data.get('rooms', [])]}")
                print(f"Doorways: {len(map_data.get('doorways', []))}")
                print(f"Saved to: {MAP_OUTPUT_FILE}")
                print("=" * 65 + "\n")
                return map_data
            else:
                logger.error(f"Gemini API error ({response.status_code}): {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error during AI room mapping: {e}")
            return None


if __name__ == "__main__":
    scanner = AIRoomScanner()
    scanner.start_interactive_scan()
