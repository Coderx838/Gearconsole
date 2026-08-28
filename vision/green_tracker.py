"""
=============================================================================
GREEN CROSS MARKER TRACKER (OVERHEAD SATELLITE CAR LOCALIZATION)
=============================================================================
Tracks the green tape cross placed on top of the RC car roof using
overhead camera view:
  1. HSV Color Segmentation tuned for Green Tape
  2. Centroid $(cx, cy)$ extraction converted to $(X, Y)$ meters on the floor
  3. Orientation $\theta$ (Heading Angle) extracted from cross principal axis
  4. HUD visual overlay showing car bounding box, crosshair, and heading vector
=============================================================================
"""

import math
import logging
from typing import Dict, Any, Tuple, Optional

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    np = None
    CV2_AVAILABLE = False

logger = logging.getLogger("GreenCrossTracker")


class GreenCrossTracker:
    def __init__(self, pixels_per_meter: float = 120.0):
        self.pixels_per_meter = pixels_per_meter

        # Tuned HSV range for Green Tape
        self.hsv_lower = (35, 60, 60)
        self.hsv_upper = (85, 255, 255)

        self.last_car_position = {
            "car_found": False,
            "x_meters": 0.0,
            "y_meters": 0.0,
            "heading_degrees": 0.0,
            "pixel_coords": (0, 0)
        }

    def process_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Detects the green cross on the car roof and computes its 2D coordinates & heading.
        """
        if not CV2_AVAILABLE or frame is None:
            return self.last_car_position

        h, w, _ = frame.shape
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Segment green tape color
        mask = cv2.inRange(hsv, np.array(self.hsv_lower), np.array(self.hsv_upper))

        # Morphological filtering to clean noise and join cross arms
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            # Pick largest green cluster
            largest = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest)

            if area > 150:  # Minimum green cross pixel threshold
                M = cv2.moments(largest)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])

                    # Convert pixel offset from frame center to real-world meters
                    # Origin (0,0) is at frame center (or configurable anchor)
                    x_m = round((cx - (w / 2)) / self.pixels_per_meter, 2)
                    y_m = round(((h / 2) - cy) / self.pixels_per_meter, 2)

                    # Orientation calculation from minimum area rectangle
                    rect = cv2.minAreaRect(largest)
                    angle = rect[2]
                    # Normalize angle
                    if rect[1][0] < rect[1][1]:
                        angle = (angle + 90.0) % 360.0
                    else:
                        angle = angle % 360.0

                    self.last_car_position = {
                        "car_found": True,
                        "x_meters": x_m,
                        "y_meters": y_m,
                        "heading_degrees": round(float(angle), 1),
                        "pixel_coords": (cx, cy),
                        "area": area
                    }
                    return self.last_car_position

        self.last_car_position = {"car_found": False, "x_meters": self.last_car_position.get("x_meters", 0.0), "y_meters": self.last_car_position.get("y_meters", 0.0), "heading_degrees": self.last_car_position.get("heading_degrees", 0.0)}
        return self.last_car_position

    def draw_hud(self, frame: np.ndarray) -> np.ndarray:
        """Draws bounding box, crosshair, and heading vector on frame."""
        if not CV2_AVAILABLE or frame is None:
            return frame

        annotated = frame.copy()
        h, w, _ = annotated.shape
        pos = self.last_car_position

        if pos.get("car_found") and "pixel_coords" in pos:
            cx, cy = pos["pixel_coords"]
            hdg = pos["heading_degrees"]
            x_m = pos["x_meters"]
            y_m = pos["y_meters"]

            # Draw green crosshair & tracking circle on the car
            cv2.circle(annotated, (cx, cy), 22, (0, 255, 0), 2)
            cv2.circle(annotated, (cx, cy), 4, (0, 0, 255), -1)

            # Draw heading orientation arrow (length 35px)
            rad = math.radians(hdg - 90)  # -90 because 0° is up in image space
            arrow_x = int(cx + 35 * math.cos(rad))
            arrow_y = int(cy + 35 * math.sin(rad))
            cv2.arrowedLine(annotated, (cx, cy), (arrow_x, arrow_y), (0, 255, 255), 2, tipLength=0.3)

            # Text label
            label = f"CAR: ({x_m:+.2f}m, {y_m:+.2f}m) | HDG: {hdg:.0f}deg"
            cv2.putText(annotated, label, (max(10, cx - 80), max(20, cy - 30)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

        return annotated
