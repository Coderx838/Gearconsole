"""
=============================================================================
BLE CAR DRIVER (REVERSE-ENGINEERED PROTOCOL FOR LCW RC CAR / JD-JM01)
=============================================================================
This module provides a complete, low-level asynchronous interface for controlling
the Bluetooth LE RC Car discovered in the APK (0_LCW_RCcar_1.0.3).

Packet Architecture (10 Bytes Total):
  Byte 0..6 : Header [0xAA, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00]
  Byte 7    : 8-bit Control Byte (Byte 8 in 1-indexed spec)
              - Bit 7: Light Mode (1=ON, 0=OFF)
              - Bit 6..5: Play Mode ("10"=Manual, "01"=Auto Demo/Show)
              - Bit 4: Spray/Smoke Mode (1=ON, 0=OFF)
              - Bit 3: Speed D (Steer Right / Motor D)
              - Bit 2: Speed C (Steer Left / Motor C)
              - Bit 1: Speed B (Reverse / Motor B)
              - Bit 0: Speed A (Forward / Motor A)
  Byte 8    : 8-bit Accessory Byte (Byte 9 in 1-indexed spec)
              - Bit 7..6: Reserved ("00")
              - Bit 5: Right Steer Mode (1=Right)
              - Bit 4: Left Steer Mode (1=Left)
              - Bit 3: Reverse / RB Mode (1=Reverse)
              - Bit 2: Tower / Turret Rotate (1=Active)
              - Bit 1: Bucket / Dumper Tilt (1=Active)
              - Bit 0: Excavator Arm Up/Down (1=Active)
  Byte 9    : Flag Bit (Byte 10 in 1-indexed spec)
              - 0x01: Standard RC Car / Supercar
              - 0x02: Dump Truck
              - 0x03: Excavator / Heavy Machinery
=============================================================================
"""

import asyncio
import logging
from typing import Optional, Callable

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    BleakClient = None
    BleakScanner = None

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("BLECarDriver")

import os
import json

# Default UUIDs reverse-engineered from app-service.js
DEFAULT_MAC = None
NOTIFY_CHAR_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID  = "0000fff2-0000-1000-8000-00805f9b34fb"

# Vehicle Profiles
PROFILE_SUPERCAR = 0x01
PROFILE_DUMPER   = 0x02
PROFILE_EXCAVATOR = 0x03


def load_mac_address() -> Optional[str]:
    """Dynamically loads car MAC address from environment, .env, or config.json. Returns None if not configured."""
    if os.environ.get("CAR_MAC"):
        return os.environ.get("CAR_MAC").strip()
    if os.environ.get("CAR_MAC_ADDRESS"):
        return os.environ.get("CAR_MAC_ADDRESS").strip()

    # Check root config.json
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg_path = os.path.join(root_dir, "config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                mac = data.get("car_mac") or data.get("mac_address")
                if mac:
                    return mac.strip()
        except Exception:
            pass

    # Check root .env
    env_path = os.path.join(root_dir, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("CAR_MAC=") or line.startswith("CAR_MAC_ADDRESS="):
                        return line.split("=", 1)[1].strip()
        except Exception:
            pass

    return None


def save_mac_address(mac_address: str):
    """Saves configured car MAC address to config.json and .env for persistence."""
    mac_address = mac_address.strip()
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg_path = os.path.join(root_dir, "config.json")
    try:
        data = {}
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        data["car_mac"] = mac_address
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save MAC to config.json: {e}")

    env_path = os.path.join(root_dir, ".env")
    try:
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = [l for l in f if not (l.startswith("CAR_MAC=") or l.startswith("CAR_MAC_ADDRESS="))]
        lines.append(f"CAR_MAC={mac_address}\n")
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception as e:
        logger.warning(f"Could not save MAC to .env: {e}")


async def scan_for_ble_cars(timeout: float = 5.0):
    """Scans for nearby BLE devices and returns list of discovered candidates."""
    if BleakScanner is None:
        logger.error("BleakScanner is not available.")
        return []

    logger.info(f"Scanning for nearby Bluetooth devices for {timeout}s...")
    devices = await BleakScanner.discover(timeout=timeout)
    results = []
    for d in devices:
        name = d.name or "Unknown BLE Device"
        results.append({"mac": d.address, "name": name, "rssi": getattr(d, "rssi", 0)})
    return results


class BLECarDriver:
    def __init__(self, mac_address: Optional[str] = None, flag_bit: int = PROFILE_SUPERCAR):
        self.mac_address = mac_address or load_mac_address()
        self.flag_bit = flag_bit
        self.client: Optional[BleakClient] = None
        self.is_connected = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

        # Motion & Accessory State Flags
        self.forward = False
        self.backward = False
        self.left = False
        self.right = False
        self.light_on = False
        self.spray_on = False
        self.demo_mode = False

        # Accessory motions (for construction variants)
        self.tower_active = False
        self.bucket_active = False
        self.arm_active = False

        # Telemetry & Disconnect callback hooks
        self.on_telemetry_callback: Optional[Callable[[bytes], None]] = None
        self.on_disconnect_callback: Optional[Callable[[], None]] = None
        self._reconnecting = False

    def _handle_disconnection(self, client: BleakClient):
        """Called automatically when the physical car is turned off or disconnected."""
        logger.warning(f"[BLE LINK LOST] Car [{self.mac_address}] disconnected!")
        self.is_connected = False
        if self.on_disconnect_callback and not self._reconnecting:
            try:
                self.on_disconnect_callback()
            except Exception as e:
                logger.error(f"Error in disconnect callback: {e}")

    def build_packet(self) -> bytes:
        """Constructs the exact 10-byte binary packet expected by the onboard MCU."""
        # Byte 8: light(1) + play(2) + spray(1) + speedD(1) + speedC(1) + speedB(1) + speedA(1)
        light_bit = "1" if self.light_on else "0"
        play_bits = "01" if self.demo_mode else "10"
        spray_bit = "1" if self.spray_on else "0"

        speed_a = "1" if self.forward else "0"
        speed_b = "1" if self.backward else "0"
        speed_c = "1" if self.left else "0"
        speed_d = "1" if self.right else "0"

        byte8_bin = light_bit + play_bits + spray_bit + speed_d + speed_c + speed_b + speed_a
        byte8_val = int(byte8_bin, 2)

        # Byte 9: 00 + right(1) + left(1) + rb(1) + tower(1) + bucket(1) + arm(1)
        right_bit = "1" if self.right else "0"
        left_bit  = "1" if self.left else "0"
        rb_bit    = "1" if self.backward else "0"
        tower_bit = "1" if self.tower_active else "0"
        bucket_bit = "1" if self.bucket_active else "0"
        arm_bit   = "1" if self.arm_active else "0"

        byte9_bin = "00" + right_bit + left_bit + rb_bit + tower_bit + bucket_bit + arm_bit
        byte9_val = int(byte9_bin, 2)

        # Byte 10: flagBit
        byte10_val = self.flag_bit & 0xFF

        packet = bytes([
            0xAA, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00,
            byte8_val,
            byte9_val,
            byte10_val
        ])
        return packet

    def _notification_handler(self, sender, data: bytearray):
        raw_bytes = bytes(data)
        logger.debug(f"Telemetry from {sender}: {raw_bytes.hex()}")
        if self.on_telemetry_callback:
            try:
                self.on_telemetry_callback(raw_bytes)
            except Exception as e:
                logger.error(f"Telemetry callback error: {e}")

    async def connect(self, timeout: float = 10.0) -> bool:
        """Connects to the car via BLE GATT client and validates vehicle characteristics."""
        if not self.mac_address:
            logger.info("No car MAC address configured. Running in Standby / Simulation mode.")
            self.is_connected = False
            return False

        if BleakClient is None:
            logger.error("bleak is not installed. Please install bleak (pip install bleak).")
            return False

        logger.info(f"Connecting to car [{self.mac_address}]...")
        self.client = BleakClient(self.mac_address, timeout=timeout, disconnected_callback=self._handle_disconnection)
        try:
            await self.client.connect()

            # Validate that the connected device is actually a compatible RC car
            char_found = False
            for service in self.client.services:
                for char in service.characteristics:
                    if char.uuid.lower() == WRITE_CHAR_UUID.lower():
                        char_found = True
                        break

            if not char_found:
                logger.warning(f"[INCOMPATIBLE DEVICE] Device [{self.mac_address}] connected, but is NOT an RC Car (Missing GATT 0xFFF2 write service).")
                try:
                    await self.client.disconnect()
                except Exception:
                    pass
                self.is_connected = False
                return False

            self.is_connected = True
            logger.info("Connected to BLE Car successfully!")

            # Subscribe to notifications if characteristic exists
            try:
                await self.client.start_notify(NOTIFY_CHAR_UUID, self._notification_handler)
                logger.info("Notification stream subscribed (0xFFF1).")
            except Exception as e:
                logger.warning(f"Notification subscription optional/skipped: {e}")

            await asyncio.sleep(0.15)
            # Send initial stop frame to clear any previous state
            await self.send_packet(self.build_packet())

            # Launch the 140ms heartbeat streaming loop
            self._running = True
            self._write_fail_count = 0
            if self._heartbeat_task is None or self._heartbeat_task.done():
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            return True
        except Exception as e:
            logger.error(f"Failed to connect to car [{self.mac_address}]: {e}")
            self.is_connected = False
            return False

    async def reconnect(self, max_attempts: int = 5, delay_seconds: float = 3.0) -> bool:
        """
        Attempts to automatically reconnect to the car when connection is lost.
        Returns True if reconnected, False if all attempts fail.
        """
        self._reconnecting = True
        logger.info(f"[AUTO-RECONNECT] Initiating reconnection loop (Max attempts: {max_attempts})...")
        for attempt in range(1, max_attempts + 1):
            print(f"  [RETRY {attempt}/{max_attempts}] Looking for car [{self.mac_address}] (Turn power ON)...")
            try:
                if self.client:
                    try:
                        await self.client.disconnect()
                    except Exception:
                        pass
                success = await self.connect(timeout=4.0)
                if success:
                    logger.info(f"[SUCCESS] Reconnected to BLE Car on attempt {attempt}!")
                    self._reconnecting = False
                    return True
            except Exception as e:
                logger.debug(f"Attempt {attempt} failed: {e}")
            await asyncio.sleep(delay_seconds)

        self._reconnecting = False
        logger.error(f"[AUTO-RECONNECT] Failed to reconnect after {max_attempts} attempts.")
        return False

    async def send_packet(self, packet_bytes: bytes):
        """Sends a 10-byte control frame to the car characteristic with write-lock and circuit breaker."""
        if self.client and self.client.is_connected:
            if not hasattr(self, "_write_lock") or self._write_lock is None:
                self._write_lock = asyncio.Lock()
            if not hasattr(self, "_write_fail_count"):
                self._write_fail_count = 0

            async with self._write_lock:
                try:
                    # response=False prevents WinRT queue blockage during 140ms streaming
                    await self.client.write_gatt_char(WRITE_CHAR_UUID, packet_bytes, response=False)
                    self._write_fail_count = 0
                except Exception:
                    try:
                        await self.client.write_gatt_char(WRITE_CHAR_UUID, packet_bytes, response=True)
                        self._write_fail_count = 0
                    except Exception as e:
                        self._write_fail_count += 1
                        if self._write_fail_count <= 2:
                            logger.error(f"BLE write error: {e}")
                        elif self._write_fail_count == 3:
                            logger.error(f"Consecutive BLE write failures on [{self.mac_address}]. Halting heartbeat.")
                            self._running = False
                            self.is_connected = False

    async def _heartbeat_loop(self):
        """Streams control frames at ~140ms interval matching the APK orderTimer."""
        logger.info("Heartbeat loop started (140ms stream rate).")
        while self._running and self.client and self.client.is_connected:
            try:
                packet = self.build_packet()
                await self.send_packet(packet)
                await asyncio.sleep(0.14)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop exception: {e}")
                break

    def stop(self):
        """Immediate full stop of all propulsion and steering motors."""
        self.forward = False
        self.backward = False
        self.left = False
        self.right = False
        self.demo_mode = False

    def move_forward(self, steer: Optional[str] = None):
        """Set forward movement, optionally with 'left' or 'right' steering."""
        self.backward = False
        self.forward = True
        self.left = (steer == "left")
        self.right = (steer == "right")

    def move_backward(self, steer: Optional[str] = None):
        """Set reverse movement, optionally with 'left' or 'right' steering."""
        self.forward = False
        self.backward = True
        self.left = (steer == "left")
        self.right = (steer == "right")

    def steer_left_only(self):
        """Pivot / steer left without forward or backward thrust."""
        self.forward = False
        self.backward = False
        self.left = True
        self.right = False

    def steer_right_only(self):
        """Pivot / steer right without forward or backward thrust."""
        self.forward = False
        self.backward = False
        self.left = False
        self.right = True

    async def pulse(self, direction: str, duration: float, steer: Optional[str] = None):
        """
        Executes a timed impulse movement, then automatically stops.
        Direction: 'forward', 'backward', 'left', 'right', 'stop'
        Duration: duration in seconds (e.g. 0.5, 1.2)
        """
        direction = direction.lower()
        if direction == "forward":
            self.move_forward(steer)
        elif direction == "backward":
            self.move_backward(steer)
        elif direction == "left":
            self.steer_left_only()
        elif direction == "right":
            self.steer_right_only()
        elif direction == "stop":
            self.stop()
            return

        await asyncio.sleep(duration)
        self.stop()

    def set_lights(self, enable: bool):
        self.light_on = enable

    def toggle_lights(self):
        self.light_on = not self.light_on
        return self.light_on

    def set_spray(self, enable: bool):
        self.spray_on = enable

    def toggle_spray(self):
        self.spray_on = not self.spray_on
        return self.spray_on

    def set_demo_mode(self, enable: bool):
        self.demo_mode = enable

    async def disconnect(self):
        """Gracefully cancels heartbeat, sends stop frame, and disconnects GATT."""
        logger.info("Disconnecting car...")
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self.client and self.client.is_connected:
            self.stop()
            await self.send_packet(self.build_packet())
            await asyncio.sleep(0.1)
            await self.client.disconnect()
            self.is_connected = False
        logger.info("Car disconnected cleanly.")


# Quick standalone driver self-test
if __name__ == "__main__":
    async def test_run():
        driver = BLECarDriver()
        if await driver.connect():
            logger.info("Flashing headlights...")
            driver.set_lights(True)
            await asyncio.sleep(1.0)
            driver.set_lights(False)

            logger.info("Pulsing forward for 1 second...")
            await driver.pulse("forward", 1.0)

            logger.info("Pulsing backward for 1 second...")
            await driver.pulse("backward", 1.0)

            await driver.disconnect()

    asyncio.run(test_run())
