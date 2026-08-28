import asyncio
from bleak import BleakClient

TARGET_MAC = "D6:C5:29:61:63:AE"
NOTIFY_CHAR_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID  = "0000fff2-0000-1000-8000-00805f9b34fb"
FLAG_BIT = 0x01

# Packet with playMode = "01" (Auto / Demo Show Mode)
# Byte 8 = 0 (light) + 01 (playMode) + 0 (spray) + 0000 (speeds) = 00100000 (0x20)
AUTO_MODE_PACKET = bytes([
    0xAA, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00,
    0x20,  # Auto / Demo Mode bit
    0x00,
    FLAG_BIT
])

STOP_PACKET = bytes([
    0xAA, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00,
    0x40,  # Manual Mode idle bit
    0x00,
    FLAG_BIT
])

received_telemetry = []

def notify_callback(sender, data):
    hex_data = data.hex()
    received_telemetry.append(hex_data)
    print(f"[SENSOR TELEMETRY RECEIVED] -> Hex: {hex_data} | Raw Bytes: {list(data)}")

async def run_diagnostic():
    print(f"Connecting to {TARGET_MAC}...")
    async with BleakClient(TARGET_MAC) as client:
        print("Connected! Listening on characteristic 0xFFF1 for telemetry...\n")
        
        # Subscribe to notify
        await client.start_notify(NOTIFY_CHAR_UUID, notify_callback)
        await asyncio.sleep(0.5)

        print("=== Test 1: Manual Mode Sensor Probe ===")
        print("Pick up the car, press on the front wheels/bumper, and hold the motor.")
        print("Listening for 5 seconds...")
        await asyncio.sleep(5.0)

        print("\n=== Test 2: Enabling Onboard Auto/Demo Mode ===")
        print("Sending Auto Mode command (aa000200000000200001)...")
        
        for _ in range(35):  # Stream for ~5 seconds
            await client.write_gatt_char(WRITE_CHAR_UUID, AUTO_MODE_PACKET, response=True)
            await asyncio.sleep(0.14)

        print("\nStopping car...")
        for _ in range(5):
            await client.write_gatt_char(WRITE_CHAR_UUID, STOP_PACKET, response=True)
            await asyncio.sleep(0.14)

        print("\n=== Test Results ===")
        if received_telemetry:
            print(f"Sensor packets detected ({len(received_telemetry)} events):")
            for t in set(received_telemetry):
                print(f"  - {t}")
        else:
            print("No telemetry returned from car (0xFFF1 remained silent).")
            print("Conclusion: The car operates on open-loop blind motor routines or local H-bridge stall cutoffs.")

if __name__ == "__main__":
    asyncio.run(run_diagnostic())