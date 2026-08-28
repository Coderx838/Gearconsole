"""
=============================================================================
VISION ENGINE (COMPUTER VISION & EYE PERCEPTION SYSTEM)
=============================================================================
Provides real-time visual perception for the RC Car Autopilot:
  1. Camera Stream Management (Webcam, USB Cam, IP Phone Stream, or Mock)
  2. Color & Target Tracking (Red ball, marker, or target following with PID)
  3. Visual Obstacle Detection / Spatial Sonar (Left / Center / Right zones)
  4. Lane & Path Detection (Hough line floor path following)
  5. Frame Capture & Base64 Encoding for Multimodal LLM Vision
=============================================================================
"""

import time
import base64
import logging
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger("VisionEngine")

# Gracefully import OpenCV and NumPy if available
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    np = None
    CV2_AVAILABLE = False
    logger.warning("OpenCV/NumPy not installed. Running VisionEngine in Mock/Simulated mode.")


def normalize_camera_url(url: Any) -> Any:
    if isinstance(url, str) and url.startswith("http"):
        url = url.strip().rstrip("/")
        if not any(url.endswith(ep) for ep in ["/video", "/videofeed", "/mjpeg", "/stream", ".mjpg"]):
            url = url + "/video"
    return url


class VisionEngine:
    """
    Visual perception engine for the autonomous RC Car.
    Supports camera streams from laptop webcam, USB camera on car, or IP webcam stream.
    """
    def __init__(self, camera_source: Any = 0, width: int = 640, height: int = 480):
        self.camera_source = normalize_camera_url(camera_source)
        self.width = width
        self.height = height
        self.cap = None
        self.is_running = False

        # Visual Tracker Settings (Default: Red Object in HSV)
        # Lower and upper HSV ranges for red (wraps around hue 0/180)
        self.target_color_lower1 = (0, 120, 70)
        self.target_color_upper1 = (10, 255, 255)
        self.target_color_lower2 = (170, 120, 70)
        self.target_color_upper2 = (180, 255, 255)

        # Obstacle Detection Zones
        self.obstacle_threshold = 0.25  # Proportion of zone occupied by close obstacle

        # Last perceived frame & telemetry
        self.last_frame = None
        self.last_analysis: Dict[str, Any] = {
            "target_detected": False,
            "target_center_x": 0.0,    # -1.0 (far left) to +1.0 (far right)
            "target_area_ratio": 0.0,  # 0.0 to 1.0 (size estimate for distance)
            "obstacle_left": False,
            "obstacle_center": False,
            "obstacle_right": False,
            "lane_detected": False,
            "lane_steer_offset": 0.0
        }

    def start(self) -> bool:
        """Initializes and opens the camera feed."""
        if not CV2_AVAILABLE:
            logger.info("VisionEngine started in simulation mode (OpenCV absent).")
            self.is_running = True
            return True

        logger.info(f"Opening camera source [{self.camera_source}]...")
        self.cap = cv2.VideoCapture(self.camera_source)
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.is_running = True
            logger.info("Camera stream initialized successfully.")
            return True
        else:
            logger.error(f"Could not open camera source [{self.camera_source}].")
            self.is_running = False
            return False

    def read_frame(self):
        """Reads a raw frame from the video capture stream."""
        if not CV2_AVAILABLE or not self.cap or not self.is_running:
            return None

        ret, frame = self.cap.read()
        if ret and frame is not None:
            self.last_frame = frame
            return frame
        return None

    def process_frame(self, frame=None) -> Dict[str, Any]:
        """
        Runs full visual perception pipeline:
          - Target tracking (Red / Color centroid)
          - Obstacle proximity detection
          - Lane line tracking
        Returns structured sensory data dict.
        """
        if not CV2_AVAILABLE:
            # Simulated telemetry for testing without camera
            return self.last_analysis

        if frame is None:
            frame = self.read_frame()

        if frame is None:
            return self.last_analysis

        h, w, _ = frame.shape
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # -------------------------------------------------------------
        # 1. COLOR TARGET TRACKING (Red object / Ball / Target)
        # -------------------------------------------------------------
        mask1 = cv2.inRange(hsv, np.array(self.target_color_lower1), np.array(self.target_color_upper1))
        mask2 = cv2.inRange(hsv, np.array(self.target_color_lower2), np.array(self.target_color_upper2))
        target_mask = mask1 | mask2

        # Morphological clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        target_mask = cv2.morphologyEx(target_mask, cv2.MORPH_OPEN, kernel)
        target_mask = cv2.morphologyEx(target_mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(target_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        target_detected = False
        target_center_x = 0.0
        target_area_ratio = 0.0

        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest_contour)
            if area > 400:  # Minimum pixel threshold
                target_detected = True
                M = cv2.moments(largest_contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    # Normalize target_center_x from -1.0 (left) to +1.0 (right)
                    target_center_x = (cx - (w / 2)) / (w / 2)
                    target_area_ratio = area / (w * h)

        # -------------------------------------------------------------
        # 2. OBSTACLE PERCEPTION (Bottom Region-of-Interest & Edge Density)
        # -------------------------------------------------------------
        # Analyze lower half of the frame (ground in front of the car)
        roi_bottom = frame[int(h * 0.5):, :]
        roi_gray = cv2.cvtColor(roi_bottom, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(roi_gray, 50, 150)

        roi_h, roi_w = edges.shape
        zone_w = roi_w // 3

        left_zone = edges[:, :zone_w]
        center_zone = edges[:, zone_w:2 * zone_w]
        right_zone = edges[:, 2 * zone_w:]

        # High edge density or sudden contrast in bottom view signifies close obstacles
        obs_left = (np.count_nonzero(left_zone) / left_zone.size) > self.obstacle_threshold
        obs_center = (np.count_nonzero(center_zone) / center_zone.size) > self.obstacle_threshold
        obs_right = (np.count_nonzero(right_zone) / right_zone.size) > self.obstacle_threshold

        # -------------------------------------------------------------
        # 3. LANE / PATH TRACKING
        # -------------------------------------------------------------
        lane_detected = False
        lane_steer_offset = 0.0
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=40, minLineLength=30, maxLineGap=20)
        if lines is not None and len(lines) > 0:
            midpoints = []
            for l in lines:
                coords = l.flatten()
                if len(coords) >= 4:
                    midpoints.append((float(coords[0]) + float(coords[2])) / 2.0)
            if midpoints:
                lane_detected = True
                avg_mid = sum(midpoints) / len(midpoints)
                lane_steer_offset = (avg_mid - (w / 2)) / (w / 2)

        self.last_analysis = {
            "target_detected": target_detected,
            "target_center_x": round(float(target_center_x), 3),
            "target_area_ratio": round(float(target_area_ratio), 4),
            "obstacle_left": bool(obs_left),
            "obstacle_center": bool(obs_center),
            "obstacle_right": bool(obs_right),
            "lane_detected": bool(lane_detected),
            "lane_steer_offset": round(float(lane_steer_offset), 3)
        }
        return self.last_analysis

    def get_annotated_frame(self, frame=None):
        """Returns frame with visual HUD, bounding boxes, and navigation vectors drawn."""
        if not CV2_AVAILABLE:
            return None

        if frame is None:
            frame = self.last_frame
        if frame is None:
            return None

        annotated = frame.copy()
        h, w, _ = annotated.shape
        analysis = self.last_analysis

        # Draw grid dividing zones
        cv2.line(annotated, (w // 3, 0), (w // 3, h), (100, 100, 100), 1)
        cv2.line(annotated, (2 * w // 3, 0), (2 * w // 3, h), (100, 100, 100), 1)
        cv2.line(annotated, (0, h // 2), (w, h // 2), (100, 100, 100), 1)

        # Draw Target Vector if detected
        if analysis["target_detected"]:
            cx = int((analysis["target_center_x"] * (w / 2)) + (w / 2))
            cv2.circle(annotated, (cx, h // 2), 15, (0, 255, 0), -1)
            cv2.line(annotated, (w // 2, h - 20), (cx, h // 2), (0, 255, 0), 2)
            cv2.putText(annotated, f"TARGET (DistArea: {analysis['target_area_ratio']:.3f})",
                        (cx - 50, (h // 2) - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Draw Obstacle Warnings
        if analysis["obstacle_left"]:
            cv2.putText(annotated, "! WARN LEFT !", (10, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        if analysis["obstacle_center"]:
            cv2.putText(annotated, "!! STOP CENTER !!", (w // 3 + 10, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        if analysis["obstacle_right"]:
            cv2.putText(annotated, "! WARN RIGHT !", (2 * w // 3 + 10, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        return annotated

    def capture_base64_jpeg(self) -> Optional[str]:
        """Encodes lightweight resized camera frame as JPEG Base64 for fast VLM upload."""
        if not CV2_AVAILABLE or self.last_frame is None:
            return None
        try:
            # Resize to lightweight 320x240 for fast internet transfer
            small = cv2.resize(self.last_frame, (320, 240), interpolation=cv2.INTER_AREA)
            _, buffer = cv2.imencode(".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), 55])
            return base64.b64encode(buffer).decode("utf-8")
        except Exception as e:
            logger.error(f"Error encoding frame to base64: {e}")
            return None

    def track_overhead_car(self, frame=None, pixels_per_meter: float = 120.0) -> Dict[str, Any]:
        """
        Overhead Bird's-Eye Tracker:
        When a phone or camera is placed on a table/shelf looking down at the room,
        this tracks the car's exact (X, Y) meter position on the floor and heading angle.
        """
        if not CV2_AVAILABLE:
            return {"car_found": False}
        if frame is None:
            frame = self.last_frame
        if frame is None:
            return {"car_found": False}

        h, w, _ = frame.shape
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, np.array(self.target_color_lower1), np.array(self.target_color_upper1))
        mask2 = cv2.inRange(hsv, np.array(self.target_color_lower2), np.array(self.target_color_upper2))
        car_mask = mask1 | mask2

        contours, _ = cv2.findContours(car_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest) > 200:
                M = cv2.moments(largest)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    x_m = round((cx - (w / 2)) / pixels_per_meter, 2)
                    y_m = round(((h / 2) - cy) / pixels_per_meter, 2)

                    # Estimate heading from min area rect
                    rect = cv2.minAreaRect(largest)
                    angle = rect[2]
                    return {
                        "car_found": True,
                        "x_meters": x_m,
                        "y_meters": y_m,
                        "pixel_coords": (cx, cy),
                        "heading_estimate": round(float(angle), 1)
                    }
        return {"car_found": False}

    def stop(self):
        """Releases camera capture device."""
        self.is_running = False
        if CV2_AVAILABLE and self.cap:
            self.cap.release()
            cv2.destroyAllWindows()
            logger.info("VisionEngine stopped.")
