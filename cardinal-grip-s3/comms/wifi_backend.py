# comms/wifi_backend.py

"""
Wi-Fi backend for reading FSR data from the ESP32-S3 over WebSocket.

Assumptions:
- The ESP32 exposes a WebSocket server that streams lines like:
      "v0,v1,v2,v3"
- You know the ws:// URI, e.g.:
      ws://cardinal-grip.local/ws
      ws://192.168.1.73/ws

      websocket (80) OTA Firmware Update
      websocket (81) FSR Output Stream

Requires:
    pip install websocket-client
"""

import logging
import threading
import time
from typing import Callable, Optional, Sequence

try:
    import websocket  # type: ignore
except ImportError:  # pragma: no cover
    websocket = None


FSRCallback = Callable[[Sequence[int]], None]


class WifiBackend:
    """
    Threaded WebSocket client that:

    - Connects to the ESP32 WebSocket URI.
    - Receives text messages.
    - Parses them as CSV "v0,v1,v2,v3".
    - Calls `on_data(values)` with `[v0, v1, v2, v3]`.
    """

    def __init__(
        self,
        # uri: str = "ws://cardinal-grip.local/ws",
        uri: str = "ws://cardinal-grip.local:81/",
        on_data: Optional[FSRCallback] = None,
        reconnect_delay: float = 3.0,
    ) -> None:
        self.uri = uri
        self.on_data = on_data
        self.reconnect_delay = reconnect_delay

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._ws: Optional["websocket.WebSocketApp"] = None  # type: ignore

    # ---- public API -----------------------------------------------------

    def set_callback(self, cb: FSRCallback) -> None:
        self.on_data = cb

    def start(self) -> None:
        if websocket is None:
            raise RuntimeError(
                "wifi_backend requires 'websocket-client'. "
                "Install with: pip install websocket-client"
            )

        if self._thread and self._thread.is_alive():
            return  # already running

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass

    # ---- internal loop --------------------------------------------------

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._ws = websocket.WebSocketApp(  # type: ignore
                    self.uri,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws.on_open = self._on_open  # type: ignore

                logging.info("WifiBackend: connecting to %s", self.uri)
                self._ws.run_forever()  # type: ignore

            except Exception as e:
                logging.exception("WifiBackend: websocket loop error: %s", e)

            if self._stop_event.is_set():
                break

            logging.info(
                "WifiBackend: reconnecting to %s in %.1f s",
                self.uri,
                self.reconnect_delay,
            )
            time.sleep(self.reconnect_delay)

    # ---- WebSocket callbacks -------------------------------------------

    def _on_open(self, ws) -> None:  # type: ignore
        logging.info("WifiBackend: connected to %s", self.uri)

    def _on_close(self, ws, status_code, msg) -> None:  # type: ignore
        logging.info(
            "WifiBackend: connection closed (code=%s, msg=%s)",
            status_code,
            msg,
        )

    def _on_error(self, ws, error) -> None:  # type: ignore
        logging.error("WifiBackend: websocket error: %s", error)

    def _on_message(self, ws, message: str) -> None:  # type: ignore
        message = message.strip()
        if not message:
            return

        parts = message.split(",")
        if len(parts) < 4:
            logging.debug("WifiBackend: ignoring short message: %r", message)
            return

        try:
            values = [int(p) for p in parts[:4]]
        except ValueError:
            logging.debug("WifiBackend: ignoring malformed message: %r", message)
            return

        if self.on_data:
            try:
                self.on_data(values)
            except Exception:
                logging.exception("WifiBackend: error in on_data callback")
