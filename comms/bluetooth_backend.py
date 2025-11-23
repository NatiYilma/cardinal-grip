# comms/bluetooth_backend.py

from __future__ import annotations

import threading
import time
import logging
from collections import deque
from typing import List, Tuple, Deque, Optional

from .base_backend import BaseBackend

logger = logging.getLogger("cardinal_grip.comms.bluetooth")


class BluetoothBackend(BaseBackend):
    """
    Skeleton Bluetooth/BLE backend for Cardinal Grip.

    Current behavior:
      - Starts a background thread that keeps _latest as zeros.
      - Provides the same BaseBackend API as SerialBackend / WifiBackend.
      - Designed so you can later integrate a real BLE client (e.g. via 'bleak').

    TODO (future):
      - Connect to ESP32-S3 BLE service/characteristic.
      - Subscribe to notifications and parse CSV payloads.
    """

    def __init__(
        self,
        num_channels: int = 4,
        history_size: int = 0,
        update_interval: float = 0.02,
        reconnect_backoff: float = 1.0,
        # BLE-specific placeholders (fill in when you implement):
        ble_address: Optional[str] = None,
        service_uuid: Optional[str] = None,
        characteristic_uuid: Optional[str] = None,
    ) -> None:
        self.num_channels = num_channels
        self.update_interval = max(0.005, update_interval)
        self.reconnect_backoff = max(0.1, reconnect_backoff)

        self.ble_address = ble_address
        self.service_uuid = service_uuid
        self.characteristic_uuid = characteristic_uuid

        # Thread / state
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Latest sample + history
        self._latest: List[int] = [0] * self.num_channels
        self._last_timestamp: float = 0.0
        self._history: Optional[Deque[Tuple[float, List[int]]]] = (
            deque(maxlen=history_size) if history_size > 0 else None
        )

        logger.debug(
            "BluetoothBackend initialized (num_channels=%d, history_size=%d, "
            "update_interval=%.3f)",
            self.num_channels,
            history_size,
            self.update_interval,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Start the background "Bluetooth" thread.

        Right now this just runs a dummy loop. Later you can:
          - connect to BLE
          - subscribe to notifications
          - parse incoming data into _latest
        """
        if self._thread is not None and self._thread.is_alive():
            logger.debug(
                "BluetoothBackend.start() called but thread already running."
            )
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("BluetoothBackend thread started.")

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            try:
                self._thread.join(timeout=0.5)
            except Exception:
                logger.exception("Error while joining BluetoothBackend thread.")
            self._thread = None
        logger.info("BluetoothBackend stopped.")

    # ------------------------------------------------------------------
    # Internal loop (dummy for now)
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """
        Main loop.

        For now:
          - keeps _latest at zeros (or whatever you want)
          - updates _last_timestamp periodically

        When you implement BLE:
          - connect to device
          - set up notification callback that writes into _latest
          - handle reconnection / backoff similar to Serial/Wi-Fi
        """
        logger.debug("BluetoothBackend run loop entering.")
        while self._running:
            now = time.time()
            with self._lock:
                # Here you could keep any simulation or just idle.
                self._last_timestamp = now
                if self._history is not None:
                    # Store zeros in history for now
                    self._history.append((now, list(self._latest)))

            time.sleep(self.update_interval)

        logger.debug("BluetoothBackend run loop exiting.")

    # ------------------------------------------------------------------
    # BaseBackend API
    # ------------------------------------------------------------------

    def get_latest(self) -> List[int]:
        with self._lock:
            return list(self._latest)

    def get_last_timestamp(self) -> Optional[float]:
        with self._lock:
            ts = self._last_timestamp
        return ts or None

    def get_window(self, n: int) -> List[List[int]]:
        if n <= 0:
            return []

        with self._lock:
            if self._history is None or not self._history:
                return [list(self._latest) for _ in range(n)]
            items = list(self._history)[-n:]

        return [vals for (_ts, vals) in items]

    def send_command(self, cmd: str) -> None:
        """
        Placeholder for BLE control commands.

        When implemented, this could write to a BLE characteristic.
        """
        if not cmd:
            return
        logger.debug("BluetoothBackend.send_command(%r) (no-op for now).", cmd)

    def handle_char(self, ch: str, is_press: bool) -> None:
        """
        Bluetooth backend doesn't care about keyboard events; no-op.
        """
        return
