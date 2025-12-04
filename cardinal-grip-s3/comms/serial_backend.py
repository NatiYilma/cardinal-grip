# comms/serial_backend.py

"""
Serial backend for reading FSR data from the ESP32-S3.

Expected input format per line (from firmware):
    "v0,v1,v2,v3"

Requires:
    pip install pyserial
"""

import logging
import threading
import time
from typing import Callable, Optional, Sequence

try:
    import serial  # type: ignore
    from serial import SerialException  # type: ignore
except ImportError:  # pragma: no cover
    serial = None
    SerialException = Exception


FSRCallback = Callable[[Sequence[int]], None]


class SerialBackend:
    """
    Simple threaded serial reader.

    - Opens the given serial port.
    - Reads text lines.
    - Parses comma-separated integers (first 4 values).
    - Calls `on_data(values)` for each valid line.
    """

    def __init__(
        self,
        port: str = "/dev/cu.usbmodem14201",
        baudrate: int = 115200,
        on_data: Optional[FSRCallback] = None,
        reconnect: bool = True,
        reconnect_delay: float = 3.0,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.on_data = on_data

        self._reconnect = reconnect
        self._reconnect_delay = reconnect_delay

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._ser: Optional["serial.Serial"] = None  # type: ignore

    # ---- public API -----------------------------------------------------

    def set_callback(self, cb: FSRCallback) -> None:
        """Set the callback that receives `[v0, v1, v2, v3]`."""
        self.on_data = cb

    def start(self) -> None:
        """Start the background reader thread."""
        if serial is None:
            raise RuntimeError(
                "serial_backend requires 'pyserial'. Install with: pip install pyserial"
            )

        if self._thread and self._thread.is_alive():
            return  # already running

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the thread to stop and close the port."""
        self._stop_event.set()
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass

    # ---- internal loop --------------------------------------------------

    def _open_port(self) -> Optional["serial.Serial"]:  # type: ignore
        try:
            logging.info(
                "SerialBackend: opening %s at %d baud", self.port, self.baudrate
            )
            ser = serial.Serial(self.port, self.baudrate, timeout=1.0)  # type: ignore
            return ser
        except SerialException as e:  # type: ignore
            logging.error("SerialBackend: failed to open port %s: %s", self.port, e)
            return None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            # Ensure port is open
            self._ser = self._open_port()
            if self._ser is None:
                if not self._reconnect:
                    break
                time.sleep(self._reconnect_delay)
                continue

            logging.info("SerialBackend: port opened: %s", self.port)

            try:
                self._read_loop()
            finally:
                try:
                    self._ser.close()
                except Exception:
                    pass
                self._ser = None
                logging.info("SerialBackend: port closed")

            if not self._reconnect or self._stop_event.is_set():
                break

            time.sleep(self._reconnect_delay)

    def _read_loop(self) -> None:
        assert self._ser is not None
        while not self._stop_event.is_set():
            try:
                line = self._ser.readline().decode("utf-8", errors="ignore").strip()
            except SerialException as e:  # type: ignore
                logging.error("SerialBackend: serial error: %s", e)
                break

            if not line:
                continue

            values = self._parse_line(line)
            if values is not None and self.on_data:
                try:
                    self.on_data(values)
                except Exception:
                    logging.exception("SerialBackend: error in on_data callback")

    @staticmethod
    def _parse_line(line: str) -> Optional[list[int]]:
        """
        Parse lines like "0,0,0,0" into [0, 0, 0, 0].
        Extra columns are ignored; fewer than 4 are rejected.
        """
        parts = line.split(",")
        if len(parts) < 4:
            logging.debug("SerialBackend: ignoring short line: %r", line)
            return None
        try:
            return [int(p) for p in parts[:4]]
        except ValueError:
            logging.debug("SerialBackend: ignoring malformed line: %r", line)
            return None
