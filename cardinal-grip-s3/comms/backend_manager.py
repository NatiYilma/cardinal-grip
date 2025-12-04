# comms/backend_manager.py

"""
Backend manager that normalizes FSR data from multiple transport layers.

Backends:
- SerialBackend      (USB serial)
- WifiBackend        (WebSocket)
- BluetoothBackend   (BLE)

The manager:
- Owns exactly one *active* backend at a time.
- Receives `[v0, v1, v2, v3]` from that backend.
- Fans out to any number of listeners (GUI / logging / recording),
  and includes the backend name as metadata.

The GUI should only talk to a higher-level controller, which then calls:
    use_serial(...)
    use_wifi(...)
    use_bluetooth(...)
    stop()

All connection logic, auto-detection, etc. lives here.
"""

import logging
from typing import Callable, List, Literal, Optional, Sequence

from .serial_backend import SerialBackend
from .wifi_backend import WifiBackend
from .bluetooth_backend import BluetoothBackend

BackendName = Literal["serial", "wifi", "bluetooth"]

# Listener signature for the GUI / app:
#   values: [v0, v1, v2, v3]
#   source: "serial" | "wifi" | "bluetooth"
ListenerCallback = Callable[[Sequence[int], BackendName], None]

try:
    # Used for serial auto-detection
    from serial.tools import list_ports  # type: ignore
except Exception:  # pragma: no cover
    list_ports = None  # type: ignore


class BackendManager:
    """
    High-level façade: choose a backend and broadcast FSR samples to listeners.

    Listeners are simple callables:

        def listener(values: Sequence[int], source: BackendName) -> None:
            ...

    They are called whenever a new FSR frame arrives from the active backend.
    """

    def __init__(self, default_backend: BackendName = "serial") -> None:
        self._listeners: List[ListenerCallback] = []
        self._backend_name: BackendName = default_backend
        self._backend = None  # type: ignore

    # ------------------------------------------------------------------
    # Listener registration
    # ------------------------------------------------------------------

    def add_listener(self, cb: ListenerCallback) -> None:
        """Register a callback to receive `[v0, v1, v2, v3]` plus backend name."""
        if cb not in self._listeners:
            self._listeners.append(cb)

    def remove_listener(self, cb: ListenerCallback) -> None:
        """Unregister a callback."""
        if cb in self._listeners:
            self._listeners.remove(cb)

    # ------------------------------------------------------------------
    # Public high-level API for controller / GUI
    # ------------------------------------------------------------------

    def use_serial(
        self,
        port: Optional[str] = None,
        baudrate: int = 115200,
        reconnect: bool = True,
        reconnect_delay: float = 3.0,
    ) -> None:
        """
        Switch to Serial backend and start it.

        - If `port` is None, attempt auto-detection (macOS/Linux/Windows).
        - Otherwise, use the given port.
        """
        if port is None:
            port = self._auto_detect_serial_port()

        logging.info("BackendManager: selecting SERIAL backend (port=%s)", port)

        self.set_backend(
            "serial",
            port=port,
            baudrate=baudrate,
            reconnect=reconnect,
            reconnect_delay=reconnect_delay,
        )
        self.start()

    def use_wifi(
        self,
        uri: Optional[str] = None,
        reconnect_delay: float = 3.0,
    ) -> None:
        """
        Switch to Wi-Fi backend and start it.

        - If `uri` is None, we use WifiBackend's default:
              ws://cardinal-grip.local:81/
        """
        kwargs = {
            "reconnect_delay": reconnect_delay,
        }
        if uri is not None:
            kwargs["uri"] = uri

        logging.info(
            "BackendManager: selecting WIFI backend (uri=%s)",
            kwargs.get("uri", "default ws://cardinal-grip.local:81/"),
        )

        self.set_backend("wifi", **kwargs)
        self.start()

    def use_bluetooth(
        self,
        device_name: str = "CardinalGrip_S3",
        reconnect_delay: float = 3.0,
    ) -> None:
        """
        Switch to Bluetooth (BLE) backend and start it.

        - `device_name` should match the ESP32 BLE advertised name.
        """
        logging.info(
            "BackendManager: selecting BLUETOOTH backend (device_name=%s)",
            device_name,
        )

        self.set_backend(
            "bluetooth",
            device_name=device_name,
            reconnect_delay=reconnect_delay,
        )
        self.start()

    def stop(self) -> None:
        """Stop the active backend."""
        if self._backend is not None:
            logging.info(
                "BackendManager: stopping %s backend", self._backend_name
            )
            try:
                self._backend.stop()
            except Exception:
                logging.exception("BackendManager: error stopping backend")

    @property
    def active_backend(self) -> BackendName:
        return self._backend_name

    # ------------------------------------------------------------------
    # Optional helper: guess a serial port for placeholder text
    # ------------------------------------------------------------------

    def guess_serial_port(self) -> Optional[str]:
        """
        Try to guess a reasonable serial port for display in the GUI as
        a placeholder. Returns None if detection fails or pyserial
        isn't available.
        """
        try:
            return self._auto_detect_serial_port()
        except Exception as e:
            logging.warning("BackendManager: guess_serial_port failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Core backend management (used by the helpers above)
    # ------------------------------------------------------------------

    def set_backend(self, name: BackendName, **backend_kwargs) -> None:
        """
        Switch the active backend.

        Any existing backend is stopped. `backend_kwargs` are passed directly
        to the backend constructor. The manager always injects its own
        callback, so you do NOT pass `on_data` yourself.
        """
        # Stop existing backend
        if self._backend is not None:
            try:
                self._backend.stop()
            except Exception:
                logging.exception("BackendManager: error stopping old backend")

        self._backend_name = name

        # Wrap backend -> manager dispatch with a source tag
        def make_on_data(source: BackendName):
            return lambda values: self._dispatch(values, source)

        on_data_cb = make_on_data(self._backend_name)

        # Create new backend, wiring up dispatch callback
        if name == "serial":
            self._backend = SerialBackend(on_data=on_data_cb, **backend_kwargs)
        elif name == "wifi":
            self._backend = WifiBackend(on_data=on_data_cb, **backend_kwargs)
        elif name == "bluetooth":
            self._backend = BluetoothBackend(on_data=on_data_cb, **backend_kwargs)
        else:
            raise ValueError(f"Unknown backend name: {name}")

    def start(self, **backend_kwargs) -> None:
        """
        Start the current backend.

        - If no backend instance exists yet, it is created using
          `self._backend_name` and `backend_kwargs`.
        - If one already exists, `backend_kwargs` are ignored and
          we simply call `start()` on it.

        In practice the GUI should prefer the convenience methods:
            use_serial(...)
            use_wifi(...)
            use_bluetooth(...)
        """
        if self._backend is None:
            self.set_backend(self._backend_name, **backend_kwargs)

        logging.info("BackendManager: starting %s backend", self._backend_name)
        self._backend.start()

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, values: Sequence[int], source: BackendName) -> None:
        """
        Called by the backend wrapper whenever a new frame `[v0, v1, v2, v3]` arrives.

        Forwards to all registered listeners. Any listener exceptions are
        logged but do not stop the others.
        """
        for cb in list(self._listeners):
            try:
                cb(values, source)
            except Exception:
                logging.exception("BackendManager: listener callback error")

    # ------------------------------------------------------------------
    # Serial auto-detection helper
    # ------------------------------------------------------------------

    def _auto_detect_serial_port(self) -> str:
        """
        Try to guess a reasonable serial port for the ESP32-S3.

        Strategy:
        - Use `serial.tools.list_ports.comports()`
        - Prefer ports whose name contains 'usbmodem' or 'usbserial' (macOS/Linux)
        - Otherwise, just take the first available port.

        Raises RuntimeError if no ports can be found or pyserial isn't present.
        """
        if list_ports is None:
            raise RuntimeError(
                "BackendManager: pyserial not available, cannot auto-detect serial port. "
                "Install with: pip install pyserial"
            )

        ports = list(list_ports.comports())
        if not ports:
            raise RuntimeError("BackendManager: no serial ports detected")

        # Prefer USB-style ports on macOS / Linux
        preferred = [
            p
            for p in ports
            if ("usbmodem" in (p.device or "").lower())
            or ("usbserial" in (p.device or "").lower())
        ]
        candidate = preferred[0] if preferred else ports[0]

        logging.info(
            "BackendManager: auto-detected serial port: %s (%s)",
            candidate.device,
            candidate.description,
        )
        return candidate.device
