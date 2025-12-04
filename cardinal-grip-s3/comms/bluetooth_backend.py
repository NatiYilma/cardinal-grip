# comms/bluetooth_backend.py

"""
Bluetooth (BLE) backend for reading FSR data from the ESP32-S3.

Firmware side (esp32_generic.cpp):

- Service UUID:  6E400001-B5A3-F393-E0A9-E50E24DCCA9E
- TX Char UUID:  6E400003-B5A3-F393-E0A9-E50E24DCCA9E (notify-only)
- Device name:   "CardinalGrip_S3"
- Payload:       ASCII CSV "v0,v1,v2,v3"

This backend:

- Scans for a device matching the given name (default "CardinalGrip_S3").
- Connects via BLE.
- Subscribes to the TX characteristic notifications.
- Parses CSV into a list of ints.
- Invokes `on_data(values)`.

It is designed to match the same interface as WifiBackend / SerialBackend:

    bt = BluetoothBackend(on_data=cb)
    bt.start()
    ...
    bt.stop()

Requires:
    pip install bleak
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

FSRCallback = Callable[[Sequence[int]], None]

try:
    from bleak import BleakScanner, BleakClient  # type: ignore
except ImportError:  # pragma: no cover
    BleakScanner = None  # type: ignore
    BleakClient = None   # type: ignore


# ----------------------------------------------------------------------
# Simple struct for BLE scan results (for Qt dialogs etc.)
# ----------------------------------------------------------------------


@dataclass
class BLEDeviceInfo:
    name: str
    address: str
    rssi: int


async def _scan_devices_async(timeout: float = 5.0) -> List[BLEDeviceInfo]:
    """
    Async helper for one-shot BLE scans.

    Returns a list of BLEDeviceInfo objects.
    """
    if BleakScanner is None:
        raise RuntimeError(
            "Bluetooth scanning requires 'bleak'. "
            "Install with: pip install bleak"
        )

    devices = await BleakScanner.discover(timeout=timeout)  # type: ignore
    results: List[BLEDeviceInfo] = []
    for d in devices:
        name = d.name or ""
        address = getattr(d, "address", "")
        rssi = int(getattr(d, "rssi", 0) or 0)
        results.append(BLEDeviceInfo(name=name, address=address, rssi=rssi))
    return results


def scan_devices(timeout: float = 5.0) -> List[BLEDeviceInfo]:
    """
    Synchronous wrapper to perform a one-shot BLE scan.

    This is convenient for a controller that wants to populate a Qt dialog:
    call this on a worker thread, then feed the resulting list into the UI.

    If already inside an event loop (e.g. some Qt setups), it falls back to
    creating a temporary loop.
    """
    import asyncio

    if BleakScanner is None:
        raise RuntimeError(
            "Bluetooth scanning requires 'bleak'. "
            "Install with: pip install bleak"
        )

    try:
        return asyncio.run(_scan_devices_async(timeout=timeout))
    except RuntimeError:
        # Likely "asyncio.run() cannot be called from a running event loop".
        # Fall back to our own loop.
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(_scan_devices_async(timeout=timeout))
        finally:
            asyncio.set_event_loop(None)
            loop.close()


class BluetoothBackend:
    """
    Threaded BLE client for the Cardinal Grip ESP32-S3.

    Parameters
    ----------
    on_data : callable or None
        Called as `on_data([v0, v1, v2, v3])` whenever a new frame arrives.
    device_name : str
        BLE advertised name to look for. Default: "CardinalGrip_S3".
    service_uuid : str
        GATT service UUID (from firmware).
    char_uuid : str
        Notify characteristic UUID that carries CSV samples.
    reconnect_delay : float
        Seconds to wait before attempting a reconnect on error/disconnect.
    """

    def __init__(
        self,
        on_data: Optional[FSRCallback] = None,
        device_name: str = "CardinalGrip_S3",
        service_uuid: str = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E",
        char_uuid: str = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E",
        reconnect_delay: float = 3.0,
    ) -> None:
        self.on_data = on_data
        self.device_name = device_name
        self.service_uuid = service_uuid
        self.char_uuid = char_uuid
        self.reconnect_delay = reconnect_delay

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Set after first successful scan so we don't re-scan every time
        self._device_address: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_callback(self, cb: FSRCallback) -> None:
        self.on_data = cb

    def start(self) -> None:
        """
        Start the BLE worker thread.
        """
        if BleakScanner is None or BleakClient is None:
            raise RuntimeError(
                "BluetoothBackend requires 'bleak'. "
                "Install with: pip install bleak"
            )

        if self._thread and self._thread.is_alive():
            return  # already running

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_thread, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """
        Signal the worker thread to stop and return immediately.

        The actual BLE disconnect will occur shortly thereafter when the
        async loop sees the stop event.
        """
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Internal implementation
    # ------------------------------------------------------------------

    def _run_thread(self) -> None:
        """
        Own an asyncio event loop in this background thread and
        run the BLE client logic inside it.
        """
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_loop())
        except Exception:
            logging.exception("BluetoothBackend: async loop crashed")
        finally:
            loop.close()

    async def _run_loop(self) -> None:
        """
        Outer reconnect loop. Attempts to connect, then subscribe,
        then stays connected until stop or disconnect, then retries.
        """
        import asyncio

        while not self._stop_event.is_set():
            try:
                # 1) Discover device address once (or re-discover if needed)
                if self._device_address is None:
                    logging.info(
                        "BluetoothBackend: scanning for '%s'...",
                        self.device_name,
                    )
                    device = await self._find_device_by_name(self.device_name)
                    if device is None:
                        logging.warning(
                            "BluetoothBackend: device '%s' not found; retrying in %.1fs",
                            self.device_name,
                            self.reconnect_delay,
                        )
                        await asyncio.sleep(self.reconnect_delay)
                        continue

                    self._device_address = device.address
                    logging.info(
                        "BluetoothBackend: found '%s' at %s",
                        self.device_name,
                        self._device_address,
                    )

                # 2) Connect
                logging.info(
                    "BluetoothBackend: connecting to %s (%s)",
                    self.device_name,
                    self._device_address,
                )
                async with BleakClient(self._device_address) as client:  # type: ignore
                    if not client.is_connected:
                        logging.warning(
                            "BluetoothBackend: failed to connect to %s",
                            self._device_address,
                        )
                        await asyncio.sleep(self.reconnect_delay)
                        continue

                    logging.info("BluetoothBackend: connected, starting notify")

                    # notification callback
                    def _handle_notify(
                        _handle: int,
                        data: bytearray,
                    ) -> None:
                        self._on_notification(bytes(data))

                    await client.start_notify(self.char_uuid, _handle_notify)  # type: ignore

                    try:
                        # 3) Stay alive until stop or disconnect
                        while (
                            not self._stop_event.is_set()
                            and client.is_connected
                        ):
                            await asyncio.sleep(0.1)
                    finally:
                        # 4) Clean up notifications
                        try:
                            await client.stop_notify(self.char_uuid)  # type: ignore
                        except Exception:
                            pass

                    logging.info("BluetoothBackend: disconnected")

            except Exception as e:
                logging.exception("BluetoothBackend: BLE error: %s", e)

            if self._stop_event.is_set():
                break

            # small pause before reconnect
            await asyncio.sleep(self.reconnect_delay)

    async def _find_device_by_name(self, name: str):
        """
        Scan for a BLE device whose advertised name matches `name`.
        """
        if BleakScanner is None:
            return None

        from bleak import BleakScanner as _Scanner  # type: ignore

        def _match(d, _ad) -> bool:
            return (d.name or "") == name

        device = await _Scanner.find_device_by_filter(_match, timeout=5.0)  # type: ignore
        return device

    # ------------------------------------------------------------------
    # Notification parsing
    # ------------------------------------------------------------------

    def _on_notification(self, payload: bytes) -> None:
        """
        Parse CSV "v0,v1,v2,v3" from notification payload.
        """
        msg = payload.decode("ascii", errors="ignore").strip()
        if not msg:
            return

        parts = msg.split(",")
        if len(parts) < 4:
            logging.debug("BluetoothBackend: ignoring short message: %r", msg)
            return

        try:
            values = [int(p) for p in parts[:4]]
        except ValueError:
            logging.debug("BluetoothBackend: ignoring malformed message: %r", msg)
            return

        if self.on_data:
            try:
                self.on_data(values)
            except Exception:
                logging.exception(
                    "BluetoothBackend: error in on_data callback"
                )