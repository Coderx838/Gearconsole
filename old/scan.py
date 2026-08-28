import asyncio
from bleak import BleakClient

TARGET_MAC = "XX:XX:XX:XX:XX:XX"

async def scan_services():
    print(f"Connecting to {TARGET_MAC} to list all services and characteristics...")
    async with BleakClient(TARGET_MAC) as client:
        print(f"Connected: {client.is_connected}\n")
        for service in client.services:
            print(f"Service: {service.uuid} ({service.description})")
            for char in service.characteristics:
                print(f"  └─ Characteristic: {char.uuid} | Handle: {char.handle} | Properties: {char.properties}")

if __name__ == "__main__":
    asyncio.run(scan_services())