"""Laptop/desktop BLE receiver for the AyuDrishti wearable band.

This is the reference implementation of the receiver described in the hardware
guide: it discovers the ESP32 band, subscribes to its telemetry
characteristic, decodes each JSON packet, and forwards the readings to the
backend's ``/wearables/data`` endpoint. It is the same job the in-app Web
Bluetooth bridge does (frontend/src/wearable/useWearable.js) -- provided here
so the hardware path can be tested from a laptop, without the mobile app.

Usage
-----
    pip install bleak httpx          # bleak is only needed for this script
    python -m wearable.sensor_processing.ble_receiver \
        --backend http://localhost:8000 \
        --token   "$JWT" \
        --session 42

The JWT comes from POST /auth/login. Without --token the script still prints
decoded packets to the console (a useful hardware smoke test) but does not
forward them.

The band is OPTIONAL and this is a wellness accessory, not a medical device.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import List, Optional

# Must match wearable/esp32/ayudrishti_wearable.ino.
DEVICE_NAME = "AyuDrishti-Band"
SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
TELEMETRY_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

FLUSH_EVERY = 5  # forward to the backend once this many valid samples buffer


def _clamp(value, low, high) -> Optional[float]:
    """Firmware emits -1 for an unreadable value; map that (and out-of-range
    noise) to None so it can be dropped rather than rejected by the API."""
    if value is None or value < 0 or value < low or value > high:
        return None
    return float(value)


def packet_to_sample(pkt: dict) -> dict:
    """Firmware packet {hr,spo2,gsr,motion,t,ok} -> backend WearableSample."""
    return {
        "heart_rate": _clamp(pkt.get("hr"), 20, 250),
        "spo2": _clamp(pkt.get("spo2"), 50, 100),
        "gsr": _clamp(pkt.get("gsr"), 0, 100),
        "motion": _clamp(pkt.get("motion"), 0, 64),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


async def run(backend: str, token: Optional[str], session: Optional[int]) -> None:
    try:
        from bleak import BleakClient, BleakScanner
    except ImportError:  # pragma: no cover - dependency hint
        raise SystemExit(
            "bleak is required for the BLE receiver. Install it with: pip install bleak"
        )

    import httpx

    print(f"Scanning for '{DEVICE_NAME}' ...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=15.0)
    if device is None:
        device = await BleakScanner.find_device_by_filter(
            lambda d, ad: SERVICE_UUID.lower() in [u.lower() for u in (ad.service_uuids or [])]
        )
    if device is None:
        raise SystemExit("Band not found. Is it powered on and advertising?")

    print(f"Found {device.address}. Connecting ...")

    buffer: List[dict] = []
    http = httpx.AsyncClient(timeout=10.0)

    async def flush() -> None:
        if not buffer or not token:
            buffer.clear()
            return
        batch, buffer[:] = list(buffer), []
        try:
            resp = await http.post(
                f"{backend.rstrip('/')}/wearables/data",
                headers={"Authorization": f"Bearer {token}"},
                json={"samples": batch, "session_id": session, "device_id": DEVICE_NAME},
            )
            resp.raise_for_status()
            print(f"  -> forwarded {len(batch)} sample(s)")
        except Exception as exc:  # best-effort: don't kill the stream
            print(f"  ! forward failed: {exc}")

    def on_notify(_char, data: bytearray) -> None:
        try:
            pkt = json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        print(f"  {pkt}")
        if pkt.get("ok") is not False:
            buffer.append(packet_to_sample(pkt))

    async with BleakClient(device) as client:
        print("Connected. Subscribing to telemetry (Ctrl+C to stop).")
        await client.start_notify(TELEMETRY_UUID, on_notify)
        try:
            while True:
                await asyncio.sleep(FLUSH_EVERY)
                await flush()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await flush()
            await http.aclose()
            print("\nStopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="AyuDrishti wearable BLE receiver")
    parser.add_argument("--backend", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--token", default=None, help="JWT from /auth/login (omit to only print)")
    parser.add_argument("--session", type=int, default=None, help="Practice session id to attach")
    args = parser.parse_args()

    try:
        asyncio.run(run(args.backend, args.token, args.session))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
