"""
=============================================================================
SPATIAL ODOMETRY & 2D LOCALIZATION ENGINE (EMBODIED CAR STATE)
=============================================================================
Maintains physical spatial awareness for the Embodied LLM Brain:
  1. Estimated 2D Coordinates (X, Y in meters) relative to start position (0, 0)
  2. Orientation / Heading Angle (Theta in degrees: 0°=North/Forward, 90°=East, 180°=South, 270°=West)
  3. Visited Waypoint Trail & Spatial Memory Grid
  4. Dead-Reckoning kinematics with velocity calibration
  5. Distance and Vector calculations to target coordinates
=============================================================================
"""

import math
import time
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("SpatialOdometry")

# Kinematic Calibration Constants for standard LCW RC Car
DEFAULT_LINEAR_SPEED = 0.85    # meters per second at full speed forward
DEFAULT_REVERSE_SPEED = 0.65   # meters per second in reverse
DEFAULT_ANGULAR_SPEED = 140.0  # degrees per second during pivot turn
DEFAULT_STEER_CURVATURE = 45.0 # angular degrees per second during forward-turn


class SpatialOdometry:
    def __init__(self):
        # 2D Position & Heading
        self.x = 0.0          # meters (+X = East / Right of start)
        self.y = 0.0          # meters (+Y = North / Forward of start)
        self.theta = 0.0      # degrees (0° = North, 90° = East, 180° = South, 270° = West)

        # Odometry statistics
        self.total_distance_traveled = 0.0
        self.start_time = time.time()
        self.path_history: List[Tuple[float, float]] = [(0.0, 0.0)]
        self.detected_obstacles: List[Tuple[float, float, str]] = []  # (x, y, type)

        # Velocity calibration factors
        self.linear_speed = DEFAULT_LINEAR_SPEED
        self.reverse_speed = DEFAULT_REVERSE_SPEED
        self.angular_speed = DEFAULT_ANGULAR_SPEED
        self.steer_curvature = DEFAULT_STEER_CURVATURE

    def reset_origin(self):
        """Resets spatial coordinates to origin (0,0) facing 0 degrees."""
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.total_distance_traveled = 0.0
        self.path_history = [(0.0, 0.0)]
        self.detected_obstacles.clear()
        logger.info("Spatial coordinates reset to origin (0.0m, 0.0m, 0°).")

    def update_from_action(self, action: str, duration: float, steer: str = None):
        """
        Updates internal dead-reckoning kinematics based on physical motor action executed.
        """
        rad = math.radians(self.theta)
        action = action.lower()

        if action == "forward":
            dist = self.linear_speed * duration
            self.total_distance_traveled += dist

            if steer == "left":
                d_theta = -self.steer_curvature * duration
                self.theta = (self.theta + d_theta) % 360.0
                rad_mid = math.radians((self.theta - d_theta / 2) % 360.0)
                self.x += dist * math.sin(rad_mid)
                self.y += dist * math.cos(rad_mid)
            elif steer == "right":
                d_theta = self.steer_curvature * duration
                self.theta = (self.theta + d_theta) % 360.0
                rad_mid = math.radians((self.theta - d_theta / 2) % 360.0)
                self.x += dist * math.sin(rad_mid)
                self.y += dist * math.cos(rad_mid)
            else:
                self.x += dist * math.sin(rad)
                self.y += dist * math.cos(rad)

        elif action == "backward":
            dist = self.reverse_speed * duration
            self.total_distance_traveled += dist

            if steer == "left":
                d_theta = self.steer_curvature * duration
                self.theta = (self.theta + d_theta) % 360.0
                rad_mid = math.radians((self.theta - d_theta / 2) % 360.0)
                self.x -= dist * math.sin(rad_mid)
                self.y -= dist * math.cos(rad_mid)
            elif steer == "right":
                d_theta = -self.steer_curvature * duration
                self.theta = (self.theta + d_theta) % 360.0
                rad_mid = math.radians((self.theta - d_theta / 2) % 360.0)
                self.x -= dist * math.sin(rad_mid)
                self.y -= dist * math.cos(rad_mid)
            else:
                self.x -= dist * math.sin(rad)
                self.y -= dist * math.cos(rad)

        elif action == "left":
            d_theta = -self.angular_speed * duration
            self.theta = (self.theta + d_theta) % 360.0

        elif action == "right":
            d_theta = self.angular_speed * duration
            self.theta = (self.theta + d_theta) % 360.0

        # Record position in trail
        self.path_history.append((round(self.x, 2), round(self.y, 2)))

    def record_obstacle(self, zone: str, distance_estimate: float = 0.5):
        """Calculates global coordinate of detected obstacle and stores in spatial memory."""
        rad = math.radians(self.theta)
        if zone == "center":
            obs_x = self.x + (distance_estimate * math.sin(rad))
            obs_y = self.y + (distance_estimate * math.cos(rad))
        elif zone == "left":
            rad_left = math.radians((self.theta - 35) % 360.0)
            obs_x = self.x + (distance_estimate * math.sin(rad_left))
            obs_y = self.y + (distance_estimate * math.cos(rad_left))
        elif zone == "right":
            rad_right = math.radians((self.theta + 35) % 360.0)
            obs_x = self.x + (distance_estimate * math.sin(rad_right))
            obs_y = self.y + (distance_estimate * math.cos(rad_right))
        else:
            return

        self.detected_obstacles.append((round(obs_x, 2), round(obs_y, 2), zone))

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns complete embodied telemetry for LLM cognitive context."""
        return {
            "position": {
                "x_meters": round(self.x, 2),
                "y_meters": round(self.y, 2),
                "heading_degrees": round(self.theta, 1),
                "cardinal_direction": self.get_cardinal_direction()
            },
            "distance_traveled_meters": round(self.total_distance_traveled, 2),
            "waypoints_visited_count": len(self.path_history),
            "recent_path_trail": self.path_history[-5:],
            "detected_obstacles_count": len(self.detected_obstacles)
        }

    def get_cardinal_direction(self) -> str:
        """Returns 8-way cardinal compass direction string."""
        deg = self.theta % 360.0
        if 337.5 <= deg or deg < 22.5:
            return "North (0 deg - Forward)"
        elif 22.5 <= deg < 67.5:
            return "North-East (45 deg)"
        elif 67.5 <= deg < 112.5:
            return "East (90 deg - Right)"
        elif 112.5 <= deg < 157.5:
            return "South-East (135 deg)"
        elif 157.5 <= deg < 202.5:
            return "South (180 deg - Backward)"
        elif 202.5 <= deg < 247.5:
            return "South-West (225 deg)"
        elif 247.5 <= deg < 292.5:
            return "West (270 deg - Left)"
        else:
            return "North-West (315 deg)"

    def get_ascii_spatial_map(self, grid_size: int = 11, cell_resolution: float = 0.5) -> str:
        """
        Renders a 2D top-down ASCII map with the car's body '^/>/v/<',
        trail '.', and detected obstacles '#' for LLM spatial reasoning.
        """
        grid = [[" " for _ in range(grid_size)] for _ in range(grid_size)]
        center = grid_size // 2

        # Draw path history
        for px, py in self.path_history:
            gx = center + int(round(px / cell_resolution))
            gy = center - int(round(py / cell_resolution))
            if 0 <= gx < grid_size and 0 <= gy < grid_size:
                grid[gy][gx] = "."

        # Draw obstacles
        for ox, oy, _ in self.detected_obstacles:
            gx = center + int(round(ox / cell_resolution))
            gy = center - int(round(oy / cell_resolution))
            if 0 <= gx < grid_size and 0 <= gy < grid_size:
                grid[gy][gx] = "#"

        # Draw start origin
        grid[center][center] = "S"

        # Draw car icon based on heading
        cx = center + int(round(self.x / cell_resolution))
        cy = center - int(round(self.y / cell_resolution))
        car_icon = "^"
        deg = self.theta % 360.0
        if 45 <= deg < 135:
            car_icon = ">"
        elif 135 <= deg < 225:
            car_icon = "v"
        elif 225 <= deg < 315:
            car_icon = "<"

        if 0 <= cx < grid_size and 0 <= cy < grid_size:
            grid[cy][cx] = car_icon

        lines = ["+--- 2D Spatial Map (1 cell = 0.5m) ---+"]
        for row in grid:
            lines.append("| " + " ".join(row) + " |")
        lines.append("+-------------------------------------+")
        lines.append(f"Legend: '{car_icon}'=Car Body, 'S'=Start(0,0), '.'=Trail, '#'=Obstacle")
        return "\n".join(lines)
