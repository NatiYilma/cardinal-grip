# comms/serial_backend.py #version 5

import threading
import time
from collections import deque
from typing import List, Tuple, Deque, Optional

import serial
import serial.tools.list_ports

from .base_backend import BaseBackend


def auto_detect_port() -> Optional[str]:
    """
    Try to automatically find a USB serial port that looks like an ESP32 / Feather.

    On macOS, these are typically:
      - /dev/cu.usbmodemXXXX
      - /dev/cu.usbserial-XXXX
    
    On Terminal (bash/zsh): "ls /dev/cu.*" to find list of ports

    Example 1 --port /dev/cu.usbserial-0001
    Example 2 --port /dev/cu.usbserial-0002
    Example 3 --port /dev/cu.usbmodem14101
    Example 4 --port /dev/cu.usbmodem14201
    Example 5 --port /dev/cu.usbmodem14301

    Returns the device path as a string, or None if nothing suitable is found.
    """
    ports = serial.tools.list_ports.comports()
    candidates: list[str] = []

    # Debug print (list of ports):
    print("Available serial ports:")
    for p in ports:
        print(f"  {p.device}  –  {p.description}")

    for p in ports:
        dev = p.device or ""
        desc = (p.description or "").lower()

        # Heuristics for macOS + ESP32 / Adafruit
        if dev.startswith("/dev/cu.usbmodem") or dev.startswith("/dev/cu.usbserial"):
            candidates.append(dev)
            continue

        if "esp32" in desc or "feather" in desc:
            candidates.append(dev)

    if not candidates:
        return None

    # Prefer usbmodem over usbserial if both exist
    candidates.sort(key=lambda d: (not d.startswith("/dev/cu.usbmodem"), d))
    return candidates[0]


class SerialBackend(BaseBackend):
    """
    Threaded serial backend for reading *four* FSR channels from the ESP32.

    - Opens a serial port.
    - Starts a background thread that reads lines continuously.
    - Expects each line to include 4 ADC values, either as:
        "v0,v1,v2,v3"
      or with metadata prefix, e.g.:
        "seq,t_ms,v0,v1,v2,v3"
      In all cases, the *last* 4 comma-separated fields are treated as channels.
    - Stores the most recent list of 4 integers.
    - GUI can call get_latest() at any time without blocking.

    Channel order matches firmware CSV:
        [0] -> A0  (red)
        [1] -> A1  (green)
        [2] -> A2  (blue)
        [3] -> A3  (yellow)
    """

    def __init__(
        self,
        port: Optional[str] = None,   # None or "" => auto-detect
        baud: int = 115200,
        timeout: float = 0.01,
        num_channels: int = 4,
        history_size: int = 0,        # >0 => keep last N samples for stats
        reconnect_backoff: float = 1.0,
    ):
        self.port = port or None
        self.baud = baud
        self.timeout = timeout
        self.num_channels = num_channels
        self.reconnect_backoff = max(0.1, reconnect_backoff)

        self.ser: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # latest will be a list of ints: [ch0, ch1, ch2, ch3]
        self._latest: List[int] = [0] * self.num_channels
        self._lock = threading.Lock()

        # Optional history: deque of (timestamp, [ch0..])
        self._history: Optional[Deque[Tuple[float, List[int]]]] = (
            deque(maxlen=history_size) if history_size > 0 else None
        )

        # Separate lock for writes (send_command)
        self._write_lock = threading.Lock()

    # ---------- lifecycle ----------

    def open(self) -> None:
        """
        Open the serial port (no thread yet).

        If self.port is None or empty, auto-detect a suitable port.
        """
        # Auto-detect if port not specified
        if not self.port:
            detected = auto_detect_port()
            if detected is None:
                raise RuntimeError(
                    "No suitable serial ports found. "
                    "Plug in your board and try again."
                )
            self.port = detected

        self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)

    def start(self) -> None:
        """
        Start the background reader thread.

        If the port is not open yet, open it first.
        """
        if self._thread is not None and self._thread.is_alive():
            return

        if self.ser is None:
            self.open()

        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the reader thread and close the port."""
        self._running = False
        if self._thread is not None:
            try:
                self._thread.join(timeout=0.5)
            except Exception:
                pass
            self._thread = None

        self.close()

    def close(self) -> None:
        """Close the serial port, if open."""
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    # ---------- background loop ----------

    def _read_loop(self) -> None:
        """
        Continuously read lines from serial and store the most recent 4-channel vector.

        Runs in a background thread and will attempt to reconnect if the
        device disappears.
        """
        while self._running:
            # Ensure port is open
            if self.ser is None or not self.ser.is_open:
                try:
                    self.open()
                except Exception:
                    # Wait before retrying, to avoid a tight loop if unplugged
                    time.sleep(self.reconnect_backoff)
                    continue

            try:
                raw = self.ser.readline()
            except Exception:
                # IO error: close and retry later
                self.close()
                time.sleep(self.reconnect_backoff)
                continue

            line = raw.decode(errors="ignore").strip()
            if not line:
                # no data this tick; yield a bit
                time.sleep(0.001)
                continue

            parts = [p.strip() for p in line.split(",") if p.strip()]
            if len(parts) < self.num_channels:
                # malformed / short line; ignore
                continue

            # Take the last N fields as channel values, so metadata prefixes are OK
            chan_fields = parts[-self.num_channels :]
            try:
                vals = [int(float(p)) for p in chan_fields]
            except ValueError:
                # ignore non-numeric noise
                continue

            # Clamp to 0..4095 range
            vals = [max(0, min(4095, v)) for v in vals]
            ts = time.time()

            with self._lock:
                self._latest = vals
                if self._history is not None:
                    self._history.append((ts, list(vals)))

        # cleanup if loop exits
        self.close()

    # ---------- public API ----------

    def get_latest(self) -> List[int]:
        """
        Return the most recent [v0, v1, v2, v3] list.

        Non-blocking and safe to call from GUI thread.
        """
        with self._lock:
            return list(self._latest)

    def get_window(self, n: int) -> List[List[int]]:
        """
        Return up to the last n samples (most recent last).

        If history is disabled, this falls back to repeating the latest sample.
        """
        if n <= 0:
            return []

        with self._lock:
            if self._history is None or not self._history:
                # No history: just repeat current sample n times
                return [list(self._latest) for _ in range(n)]

            items = list(self._history)[-n:]
        return [vals for (_ts, vals) in items]

    def send_command(self, cmd: str) -> None:
        """
        Optional host -> device control channel.

        Writes a single line (cmd + '\\n') to the serial port if open.
        """
        if not cmd:
            return
        if self.ser is None or not self.ser.is_open:
            # Silently ignore if not connected
            return

        if not cmd.endswith("\n"):
            cmd = cmd + "\n"

        data = cmd.encode("utf-8", errors="ignore")
        try:
            with self._write_lock:
                self.ser.write(data)
                self.ser.flush()
        except Exception:
            # Don't propagate IO errors into GUI
            pass

    def handle_char(self, ch: str, is_press: bool) -> None:
        """
        Hardware backends don't use keyboard input; this is a no-op.

        It exists so the class satisfies BaseBackend and can be swapped
        with SimBackend without special-casing.
        """
        return

    @staticmethod
    def list_ports() -> list[tuple[str, str]]:
        """
        Convenience helper: return a list of (device, description) for all ports.
        """
        out: list[tuple[str, str]] = []
        for p in serial.tools.list_ports.comports():
            out.append((p.device, p.description))
        return out
