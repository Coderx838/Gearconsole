"""
=============================================================================
MULTI-ROOM FLOORPLAN & WAYPOINT NAVIGATION SYSTEM
=============================================================================
Manages home floor plans, starting anchors, rooms, landmarks, and pathfinding:
  1. Loads customizable layout from `home_map.json`
  2. Identifies current room from (X, Y) coordinates
  3. Finds landmark locations (Sofa, TV, Desk, Bed, etc.)
  4. Plans waypoint routes through doorways to navigate between rooms
  5. Computes required steering angles and drive durations
=============================================================================
"""

import os
import json
import math
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("RoomMapper")

# Look in root directory or local module directory
DEFAULT_ROOT_MAP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "home_map.json")
LOCAL_MODULE_MAP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "home_map.json")
MAP_FILE = DEFAULT_ROOT_MAP if os.path.exists(DEFAULT_ROOT_MAP) else (LOCAL_MODULE_MAP if os.path.exists(LOCAL_MODULE_MAP) else DEFAULT_ROOT_MAP)


class RoomMapper:
    def __init__(self, map_file: str = MAP_FILE):
        self.map_file = map_file
        self.rooms: List[Dict[str, Any]] = []
        self.doorways: List[Dict[str, Any]] = []
        self.starting_anchor: Dict[str, Any] = {
            "name": "Main Door",
            "x": 0.0,
            "y": 0.0,
            "heading_degrees": 0.0
        }
        self.landmarks: Dict[str, Tuple[float, float, str]] = {}  # name -> (x, y, room_name)
        self.load_map()

    def load_map(self):
        """Loads rooms, doorways, landmarks, and starting anchor from home_map.json."""
        if not os.path.exists(self.map_file):
            logger.warning(f"Map file {self.map_file} not found. Creating default.")
            self._create_default_map()

        try:
            with open(self.map_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.starting_anchor = data.get("starting_anchor", self.starting_anchor)
                self.rooms = data.get("rooms", [])
                self.doorways = data.get("doorways", [])

                # Index landmarks
                self.landmarks.clear()
                for r in self.rooms:
                    r_name = r.get("name")
                    for lm in r.get("landmarks", []):
                        self.landmarks[lm.get("name").lower()] = (lm.get("x"), lm.get("y"), r_name)
                logger.info(f"Loaded {len(self.rooms)} rooms, {len(self.doorways)} doors, {len(self.landmarks)} landmarks.")
        except Exception as e:
            logger.error(f"Error loading map: {e}")

    def get_current_room(self, x: float, y: float) -> str:
        """Determines which room contains the given (x, y) coordinates."""
        for r in self.rooms:
            if (r["x_min"] <= x <= r["x_max"]) and (r["y_min"] <= y <= r["y_max"]):
                return r["name"]
        return "Hallway / Open Zone"

    def find_landmark(self, name: str) -> Optional[Tuple[float, float, str]]:
        """Finds (x, y, room_name) for a landmark query (e.g. 'sofa', 'desk', 'bed', 'tv')."""
        name_clean = name.lower().strip()
        for k, v in self.landmarks.items():
            if name_clean in k or k in name_clean:
                return v
        return None

    def plan_path_to_target(self, start_x: float, start_y: float, target_x: float, target_y: float) -> List[Tuple[float, float, str]]:
        """
        Plans sequential waypoints from (start_x, start_y) to (target_x, target_y)
        routing safely through room doorways.
        """
        start_room = self.get_current_room(start_x, start_y)
        target_room = self.get_current_room(target_x, target_y)

        waypoints = []

        # If already in the same room, navigate directly to target
        if start_room == target_room:
            waypoints.append((target_x, target_y, f"Target in {target_room}"))
            return waypoints

        # Cross-room routing (Living Room <-> Hallway <-> Bedroom)
        if start_room == "Living Room":
            if target_room == "Hallway":
                waypoints.append((4.0, 1.75, "Hallway Doorway"))
                waypoints.append((target_x, target_y, "Hallway Destination"))
            elif target_room == "Bedroom":
                waypoints.append((4.0, 1.75, "Hallway Doorway"))
                waypoints.append((6.5, 1.75, "Bedroom Doorway"))
                waypoints.append((target_x, target_y, "Bedroom Destination"))

        elif start_room == "Bedroom":
            if target_room == "Hallway":
                waypoints.append((6.5, 1.75, "Hallway Doorway"))
                waypoints.append((target_x, target_y, "Hallway Destination"))
            elif target_room == "Living Room":
                waypoints.append((6.5, 1.75, "Hallway Doorway"))
                waypoints.append((4.0, 1.75, "Living Room Doorway"))
                waypoints.append((target_x, target_y, "Living Room Destination"))

        elif start_room == "Hallway":
            if target_room == "Living Room":
                waypoints.append((4.0, 1.75, "Living Room Doorway"))
                waypoints.append((target_x, target_y, "Living Room Destination"))
            elif target_room == "Bedroom":
                waypoints.append((6.5, 1.75, "Bedroom Doorway"))
                waypoints.append((target_x, target_y, "Bedroom Destination"))

        if not waypoints:
            waypoints.append((target_x, target_y, "Direct Destination"))

        return waypoints

    def get_navigation_telemetry(self, current_x: float, current_y: float) -> Dict[str, Any]:
        """Returns structured map context for LLM prompt."""
        curr_room = self.get_current_room(current_x, current_y)
        return {
            "current_room": curr_room,
            "starting_anchor": self.starting_anchor,
            "rooms": [{"name": r["name"], "bounds": [r["x_min"], r["x_max"], r["y_min"], r["y_max"]]} for r in self.rooms],
            "landmarks": [{"name": k.title(), "x": v[0], "y": v[1], "room": v[2]} for k, v in self.landmarks.items()],
            "doorways": self.doorways
        }

    def get_ascii_floorplan(self, current_x: float, current_y: float) -> str:
        """Renders an ASCII multi-room floor plan showing car location and landmarks."""
        curr_room = self.get_current_room(current_x, current_y)
        lines = [
            "+---------------------- HOME MULTI-ROOM FLOORPLAN ----------------------+",
            "| [Room 1: Living Room]       [Room 2: Hallway]       [Room 3: Bedroom] |",
            "| (0.0m - 4.0m)              (4.0m - 6.5m)           (6.5m - 10.0m)    |",
            "| Landmarks: Sofa, TV        Landmarks: Shoes        Landmarks: Desk,Bed|",
            "| +--------------------+     +---------------+     +------------------+ |",
            "| |                    |=====|               |=====|                  | |",
            f"| | Car Body: ({current_x:+.1f}m, {current_y:+.1f}m) in [{curr_room}]",
            "| |                    |=====|  Door (4.0m)  |=====|  Door (6.5m)     | |",
            "| +--------------------+     +---------------+     +------------------+ |",
            "+-----------------------------------------------------------------------+"
        ]
        return "\n".join(lines)
