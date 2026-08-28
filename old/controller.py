# import asyncio
# from bleak import BleakClient
# from pynput import keyboard

# TARGET_MAC = "XX:XX:XX:XX:XX:XX"
# NOTIFY_CHAR_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
# WRITE_CHAR_UUID  = "0000fff2-0000-1000-8000-00805f9b34fb"

# class BLECarController:
#     def __init__(self):
#         self.client = None
#         self.running = True
        
#         # Movement flags
#         self.forward = False
#         self.backward = False
#         self.left = False
#         self.right = False
        
#         # Feature toggles
#         self.light_on = False

#     def build_packet(self) -> bytes:
#         """
#         Replicates the exact JavaScript binary-string assembly from remote.vue
#         """
#         # --- Byte 8: n (lightMode + playMode + sprayMode + 4 speed bits) ---
#         light_bit = "1" if self.light_on else "0"
#         play_bits = "10"   # default playMode in app
#         spray_bit = "0"
        
#         # If moving (forward or backward), send full speed (1111), else 0000
#         if self.forward or self.backward or self.left or self.right:
#             speed_bits = "1111"
#         else:
#             speed_bits = "0000"
            
#         byte8_bin = light_bit + play_bits + spray_bit + speed_bits
#         byte8_val = int(byte8_bin, 2)

#         # --- Byte 9: o (00 + rightMode + leftMode + RBMode + tower + bucket + arm) ---
#         right_bit = "1" if self.right else "0"
#         left_bit  = "1" if self.left else "0"
#         rb_bit    = "1" if self.backward else "0"  # Reverse / Backward mode
#         accessory_bits = "000"                     # tower, bucket, arm modes
        
#         byte9_bin = "00" + right_bit + left_bit + rb_bit + accessory_bits
#         byte9_val = int(byte9_bin, 2)

#         # --- Byte 10: flagBit ---
#         byte10_val = 0x00

#         # Construct full 10-byte packet
#         packet = bytes([
#             0xAA, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00,
#             byte8_val,
#             byte9_val,
#             byte10_val
#         ])
#         return packet

#     def notification_handler(self, sender, data):
#         print(f"[CAR NOTIFY] {data.hex()}")

#     async def connect(self):
#         print(f"Connecting to car [{TARGET_MAC}]...")
#         self.client = BleakClient(TARGET_MAC)
#         try:
#             await self.client.connect()
#             print("BLE Connection established!")
            
#             # Subscribe to notifications (handshake)
#             await self.client.start_notify(NOTIFY_CHAR_UUID, self.notification_handler)
#             await asyncio.sleep(0.1)

#             # Send initial stop frame
#             await self.send_packet(self.build_packet())
#             return True
#         except Exception as e:
#             print(f"Connection failed: {e}")
#             return False

#     async def send_packet(self, packet_bytes):
#         if self.client and self.client.is_connected:
#             try:
#                 await self.client.write_gatt_char(WRITE_CHAR_UUID, packet_bytes, response=True)
#             except Exception as e:
#                 print(f"Write error: {e}")

#     async def heartbeat_loop(self):
#         """Continuously streams the command packet at ~20Hz (50ms interval)"""
#         while self.running and self.client and self.client.is_connected:
#             packet = self.build_packet()
#             await self.send_packet(packet)
#             await asyncio.sleep(0.05)

#     async def run(self):
#         if not await self.connect():
#             return

#         print("\n--- Controls Active ---")
#         print("  [W / UP]    : Forward")
#         print("  [S / DOWN]  : Reverse")
#         print("  [A / LEFT]  : Turn Left")
#         print("  [D / RIGHT] : Turn Right")
#         print("  [L]         : Toggle Headlights")
#         print("  [Release]   : Stop")
#         print("  [ESC]       : Exit\n")

#         pressed_keys = set()

#         def on_press(key):
#             pressed_keys.add(key)
#             self._update_state(pressed_keys)
            
#             # Toggle light on 'L' press
#             if key == keyboard.KeyCode.from_char('l'):
#                 self.light_on = not self.light_on
#                 print(f"Lights: {'ON' if self.light_on else 'OFF'}")

#         def on_release(key):
#             if key in pressed_keys:
#                 pressed_keys.remove(key)
#             if key == keyboard.Key.esc:
#                 self.running = False
#                 return False
#             self._update_state(pressed_keys)

#         listener = keyboard.Listener(on_press=on_press, on_release=on_release)
#         listener.start()

#         await self.heartbeat_loop()

#         listener.stop()
#         if self.client and self.client.is_connected:
#             self.forward = self.backward = self.left = self.right = False
#             await self.send_packet(self.build_packet())
#             await self.client.disconnect()
#         print("Disconnected.")

#     def _update_state(self, keys):
#         self.forward  = keyboard.Key.up in keys or keyboard.KeyCode.from_char('w') in keys
#         self.backward = keyboard.Key.down in keys or keyboard.KeyCode.from_char('s') in keys
#         self.left     = keyboard.Key.left in keys or keyboard.KeyCode.from_char('a') in keys
#         self.right    = keyboard.Key.right in keys or keyboard.KeyCode.from_char('d') in keys


# if __name__ == "__main__":
#     controller = BLECarController()
#     asyncio.run(controller.run())


import asyncio
from bleak import BleakClient
from pynput import keyboard

TARGET_MAC = "XX:XX:XX:XX:XX:XX"
NOTIFY_CHAR_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID  = "0000fff2-0000-1000-8000-00805f9b34fb"

# Try 0x01 first; if light doesn't stop blinking, change to 0x03
FLAG_BIT = 0x01  # Options: 0x01, 0x03, 0x02

class BLECarController:
    def __init__(self):
        self.client = None
        self.running = True
        
        # State flags
        self.forward = False
        self.backward = False
        self.left = False
        self.right = False
        self.light_on = False

    def build_packet(self) -> bytes:
        # --- Byte 8: lightMode(1) + playMode(2)="10" + sprayMode(1)="0" + speedD,C,B,A ---
        light = "1" if self.light_on else "0"
        play = "10"
        spray = "0"
        speed_d = "0"
        speed_c = "0"
        speed_b = "1" if self.backward else "0"
        speed_a = "1" if self.forward else "0"
        
        byte8_bin = light + play + spray + speed_d + speed_c + speed_b + speed_a
        byte8_val = int(byte8_bin, 2)

        # --- Byte 9: 00 + rightMode(1) + leftMode(1) + RBMode(1) + tower(1) + bucket(1) + arm(1) ---
        right = "1" if self.right else "0"
        left = "1" if self.left else "0"
        rb = "0"
        accessories = "000"
        
        byte9_bin = "00" + right + left + rb + accessories
        byte9_val = int(byte9_bin, 2)

        # --- Byte 10: flagBit ---
        byte10_val = FLAG_BIT

        # 10-byte packet: aa 00 02 00 00 00 00 <byte8> <byte9> <byte10>
        return bytes([
            0xAA, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00,
            byte8_val,
            byte9_val,
            byte10_val
        ])

    def notification_handler(self, sender, data):
        print(f"[CAR NOTIFY] {data.hex()}")

    async def connect(self):
        print(f"Connecting to car [{TARGET_MAC}]...")
        self.client = BleakClient(TARGET_MAC)
        try:
            await self.client.connect()
            print("BLE Connection established!")
            
            # Subscribe to notification characteristic
            await self.client.start_notify(NOTIFY_CHAR_UUID, self.notification_handler)
            await asyncio.sleep(0.2)

            # Send initial keep-alive packet
            await self.send_packet(self.build_packet())
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    async def send_packet(self, packet_bytes):
        if self.client and self.client.is_connected:
            try:
                await self.client.write_gatt_char(WRITE_CHAR_UUID, packet_bytes, response=True)
            except Exception as e:
                print(f"Write error: {e}")

    async def heartbeat_loop(self):
        """Streams the exact packet every 140ms matching orderTimer from app-service.js."""
        while self.running and self.client and self.client.is_connected:
            packet = self.build_packet()
            await self.send_packet(packet)
            await asyncio.sleep(0.14)  # 140 ms interval

    async def run(self):
        if not await self.connect():
            return

        print("\n--- Controls Active ---")
        print("  [W / UP]    : Forward")
        print("  [S / DOWN]  : Reverse")
        print("  [A / LEFT]  : Turn Left")
        print("  [D / RIGHT] : Turn Right")
        print("  [L]         : Toggle Headlights")
        print("  [Release]   : Stop")
        print("  [ESC]       : Exit\n")

        pressed_keys = set()

        def on_press(key):
            pressed_keys.add(key)
            self._update_state(pressed_keys)
            
            if key == keyboard.KeyCode.from_char('l'):
                self.light_on = not self.light_on
                print(f"Lights: {'ON' if self.light_on else 'OFF'}")

        def on_release(key):
            if key in pressed_keys:
                pressed_keys.remove(key)
            if key == keyboard.Key.esc:
                self.running = False
                return False
            self._update_state(pressed_keys)

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()

        await self.heartbeat_loop()

        listener.stop()
        if self.client and self.client.is_connected:
            self.forward = self.backward = self.left = self.right = False
            await self.send_packet(self.build_packet())
            await self.client.disconnect()
        print("Disconnected.")

    def _update_state(self, keys):
        self.forward  = keyboard.Key.up in keys or keyboard.KeyCode.from_char('w') in keys
        self.backward = keyboard.Key.down in keys or keyboard.KeyCode.from_char('s') in keys
        self.left     = keyboard.Key.left in keys or keyboard.KeyCode.from_char('a') in keys
        self.right    = keyboard.Key.right in keys or keyboard.KeyCode.from_char('d') in keys


if __name__ == "__main__":
    controller = BLECarController()
    asyncio.run(controller.run())