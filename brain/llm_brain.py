"""
=============================================================================
LLM BRAIN (EMBODIED PHYSICAL CONSCIOUSNESS & 2D SPATIAL AUTOPILOT)
=============================================================================
Equips Google Gemini with true Physical Embodiment:
  1. Real-time 2D Cartesian Coordinates (X, Y in meters) & Compass Heading
  2. Top-Down 2D Spatial Occupancy & Exploration Grid Map
  3. Visual Multimodal Perception (Eye camera snapshot)
  4. Autonomous Sense-Plan-Act Embodied Navigation Loop
  5. Multilingual Natural Language Voice Dialogue
=============================================================================
"""

import os
import json
import logging
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger("LLMBrain")

EMBODIED_SYSTEM_PROMPT = """You are the autonomous consciousness inhabiting the physical body of this RC Car.
You are physically embodied in the room. You have:
- A physical chassis with front steering wheels and rear drive motor.
- Real-time 2D spatial coordinates: (X, Y) in meters, relative to your start position (0.0m, 0.0m).
- A compass heading angle: 0° (North/Forward), 90° (East/Right), 180° (South/Reverse), 270° (West/Left).
- An "eye" camera capturing the physical environment in front of your bumper.
- Obstacle sensors detecting immediate proximity hazards (Left, Center, Right).
- A voice synthesizer to speak aloud to humans.

Your Consciousness & Rules:
1. YOU ARE THE CAR. Use first-person language ("I am at (0.5m, 1.2m)", "I am steering right to avoid the table leg", "Main aage badh raha hoon").
2. ALWAYS observe your 2D coordinates and 2D Spatial Map. Understand where you are in the room.
3. Respond in JSON format with 3 fields:
   - "thought": Internal reasoning about your location, spatial map, visual scene, and action plan (in English).
   - "speech": What you say out loud to the user (MUST BE IN THE SAME LANGUAGE the user spoke!).
   - "actions": Sequential list of physical actions to execute.

Available Physical Motor Actions:
- {"action": "forward", "steer": null | "left" | "right", "duration": float_seconds} (0.3s - 3.0s, moves ~0.85 m/s)
- {"action": "backward", "steer": null | "left" | "right", "duration": float_seconds} (0.3s - 2.0s, moves ~0.65 m/s)
- {"action": "left", "duration": float_seconds} (pivot turn, ~140 deg/s)
- {"action": "right", "duration": float_seconds} (pivot turn, ~140 deg/s)
- {"action": "stop"}
- {"action": "lights", "state": true | false}
- {"action": "spray", "state": true | false}

Safety:
- If obstacle_center is True or image shows an obstacle directly in front of your bumper, DO NOT drive forward. Back up and pivot turn.

Example output:
{
  "thought": "I am at position (+0.8m, +1.2m) facing 45° North-East. The camera shows clear space ahead. Cruising forward 1.5s to explore deeper into the room.",
  "speech": "Main aage badh raha hoon aur room explore kar raha hoon.",
  "actions": [
    {"action": "forward", "duration": 1.5}
  ]
}
"""


def load_api_key() -> Optional[str]:
    """Loads Gemini API key from environment, .env file, or config.json."""
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ.get("GEMINI_API_KEY").strip()
    if os.environ.get("GOOGLE_API_KEY"):
        return os.environ.get("GOOGLE_API_KEY").strip()

    # Check root and module directories for .env
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        os.path.join(os.getcwd(), ".env")
    ]
    for env_path in candidates:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("GEMINI_API_KEY="):
                            return line.split("=", 1)[1].strip()
            except Exception:
                pass

    # Check config.json
    cfg_candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
        os.path.join(os.getcwd(), "config.json")
    ]
    for cfg_path in cfg_candidates:
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    val = data.get("gemini_api_key")
                    if val:
                        return val.strip()
            except Exception:
                pass

    return None


def save_api_key(api_key: str):
    """Saves Gemini API key to local .env and config.json in root directory."""
    api_key = api_key.strip()
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg_path = os.path.join(root_dir, "config.json")
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"gemini_api_key": api_key}, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not write config.json: {e}")

    env_path = os.path.join(root_dir, ".env")
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"GEMINI_API_KEY={api_key}\n")
    except Exception as e:
        logger.warning(f"Could not write .env: {e}")


class LLMBrain:
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3.5-flash-lite"):
        self.api_key = api_key or load_api_key()
        self.model = model
        self.session = requests.Session()
        self.candidate_models = [
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.6-flash"
        ]

    def set_api_key(self, api_key: str):
        self.api_key = api_key.strip()
        save_api_key(self.api_key)

    def plan_next_move(self, user_goal: str, sensory_state: Dict[str, Any],
                       spatial_telemetry: Optional[Dict[str, Any]] = None,
                       spatial_map_ascii: Optional[str] = None,
                       floorplan_telemetry: Optional[Dict[str, Any]] = None,
                       floorplan_ascii: Optional[str] = None,
                       image_base64: Optional[str] = None) -> Dict[str, Any]:
        """
        Queries Gemini with embodied coordinates + 2D spatial map + multi-room floorplan + vision + goal.
        Returns parsed JSON plan containing thoughts, speech, and actions.
        """
        if not self.api_key:
            return self._heuristic_fallback_plan(user_goal, sensory_state, spatial_telemetry)

        spatial_context = ""
        if spatial_telemetry:
            spatial_context += f"\nEmbodied Spatial Telemetry:\n{json.dumps(spatial_telemetry, indent=2)}\n"
        if floorplan_telemetry:
            spatial_context += f"\nMulti-Room Floorplan Telemetry:\n{json.dumps(floorplan_telemetry, indent=2)}\n"
        if floorplan_ascii:
            spatial_context += f"\nMulti-Room Floorplan Map:\n{floorplan_ascii}\n"
        if spatial_map_ascii:
            spatial_context += f"\n2D Spatial Top-Down Occupancy Map:\n{spatial_map_ascii}\n"

        prompt_text = f"""Active Goal / User Input: "{user_goal}"
{spatial_context}
Vision & Sensor Telemetry:
{json.dumps(sensory_state, indent=2)}

You are the embodied car body navigating this home floorplan. Examine your room, coordinates, heading, floorplan map, and vision, then provide your JSON action plan."""

        parts = [{"text": EMBODIED_SYSTEM_PROMPT}, {"text": prompt_text}]

        if image_base64:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": image_base64
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

        models_to_try = [self.model] + [m for m in self.candidate_models if m != self.model]
        for m in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.api_key}"
            try:
                response = self.session.post(url, headers=headers, json=payload, timeout=8.0)
                if response.status_code == 200:
                    data = response.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if raw_text.startswith("```"):
                        raw_text = raw_text.split("\n", 1)[1]
                    if raw_text.endswith("```"):
                        raw_text = raw_text.rsplit("```", 1)[0]
                    raw_text = raw_text.strip()

                    plan = json.loads(raw_text)
                    logger.info(f"[EMBODIED BRAIN ({m})] Decision: {plan.get('thought')}")
                    return plan
                else:
                    logger.warning(f"Gemini {m} returned {response.status_code}: {response.text[:200]}")
            except Exception as e:
                logger.error(f"Error calling Gemini {m}: {e}")

        return self._heuristic_fallback_plan(user_goal, sensory_state, spatial_telemetry)

    def _heuristic_fallback_plan(self, user_goal: str, sensory_state: Dict[str, Any],
                                 spatial_telemetry: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Local embodied fallback planner when offline."""
        import re
        g = user_goal.lower().strip()

        duration = 1.2
        meter_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:meter|meters|metre|metres|m\b)', g)
        sec_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:second|seconds|sec|secs|s\b)', g)
        if meter_match:
            duration = min(float(meter_match.group(1)) * 1.2, 4.0)
        elif sec_match:
            duration = min(float(sec_match.group(1)), 4.0)

        # Return to origin (0, 0)
        if any(w in g for w in ["return", "go home", "origin", "wapas", "start point", "ghar", "base"]):
            if spatial_telemetry:
                x = spatial_telemetry.get("position", {}).get("x_meters", 0.0)
                y = spatial_telemetry.get("position", {}).get("y_meters", 0.0)
                return {
                    "thought": f"I am at ({x}m, {y}m). Navigating back toward origin (0,0).",
                    "speech": "Origin ki taraf wapas ja raha hoon.",
                    "actions": [{"action": "backward", "duration": 1.5}]
                }

        # Check for forward intent
        if any(w in g for w in ["forward", "mode forward", "straight", "ahead", "aage", "chalo", "chal", "head"]):
            steer = "left" if any(w in g for w in ["left", "baye", "ulta"]) else "right" if any(w in g for w in ["right", "daye", "sidha"]) else None
            return {
                "thought": f"Cruising forward for {duration:.1f}s.",
                "speech": f"Moving forward {meter_match.group(0) if meter_match else ''}." if any(w in g for w in ["forward", "ahead", "head"]) else "Aage badh raha hoon.",
                "actions": [{"action": "forward", "steer": steer, "duration": round(duration, 1)}]
            }

        # Check for backward intent
        if any(w in g for w in ["backward", "reverse", "back", "peeche", "piche"]):
            steer = "left" if any(w in g for w in ["left", "baye"]) else "right" if any(w in g for w in ["right", "daye"]) else None
            return {
                "thought": f"Reversing for {duration:.1f}s.",
                "speech": "Reversing." if "reverse" in g or "back" in g else "Peeche ja raha hoon.",
                "actions": [{"action": "backward", "steer": steer, "duration": round(duration, 1)}]
            }

        # Check for turning intent
        if any(w in g for w in ["left", "baye", "left turn"]):
            return {
                "thought": "Steering left.",
                "speech": "Turning left.",
                "actions": [{"action": "left", "duration": 0.8}]
            }
        if any(w in g for w in ["right", "daye", "right turn"]):
            return {
                "thought": "Steering right.",
                "speech": "Turning right.",
                "actions": [{"action": "right", "duration": 0.8}]
            }

        # Check for lights
        if any(w in g for w in ["light", "headlight", "batti"]):
            return {
                "thought": "Toggling headlights.",
                "speech": "Headlights toggled.",
                "actions": [{"action": "lights", "state": True}]
            }

        # Check for smoke/spray
        if any(w in g for w in ["spray", "smoke", "exhaust", "dhuan"]):
            return {
                "thought": "Toggling smoke generator.",
                "speech": "Smoke generator active.",
                "actions": [{"action": "spray", "state": True}]
            }

        # Obstacle avoidance heuristics
        if sensory_state.get("obstacle_center"):
            return {
                "thought": "Obstacle directly in front of my bumper. Backing up and turning left.",
                "speech": "Obstacle detected. Dodging left.",
                "actions": [{"action": "backward", "duration": 0.5}, {"action": "left", "duration": 0.8}]
            }

        return {
            "thought": "Holding position at current coordinates. Standing by.",
            "speech": "Main taiyar hoon.",
            "actions": [{"action": "stop"}]
        }
