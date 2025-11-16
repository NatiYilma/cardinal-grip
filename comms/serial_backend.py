# comms/serial_backend.py

import serial
import serial.tools.list_ports
import threading
import time


# Single FSR
# class SerialBackend:
#     """
#     Threaded serial backend for reading integer values from the ESP32.

#     - Opens a serial port.
#     - Starts a background thread that reads lines continuously.
#     - Stores the most recent valid integer.
#     - GUI can call get_latest() at any time without blocking.
#     """

#     def __init__(self, port="/dev/cu.usbserial-0001", baud=115200, timeout=0.01):
#         self.port = port
#         self.baud = baud
#         self.timeout = timeout

#         self.ser = None
#         self._thread = None
#         self._running = False

#         self._latest = None
#         self._lock = threading.Lock()

#     # ---------- lifecycle ----------

#     def open(self):
#         """Open the serial port (no thread yet)."""
#         self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)

#     def start(self):
#         """
#         Start the background reader thread.

#         If the port is not open yet, open it first.
#         """
#         if self.ser is None:
#             self.open()

#         if self._thread is not None and self._thread.is_alive():
#             return

#         self._running = True
#         self._thread = threading.Thread(target=self._read_loop, daemon=True)
#         self._thread.start()

#     def stop(self):
#         """Stop the reader thread and close the port."""
#         self._running = False
#         if self._thread is not None:
#             try:
#                 self._thread.join(timeout=0.5)
#             except Exception:
#                 pass
#             self._thread = None

#         self.close()

#     def close(self):
#         """Close the serial port, if open."""
#         if self.ser is not None:
#             try:
#                 self.ser.close()
#             except Exception:
#                 pass
#             self.ser = None

#     # ---------- background loop ----------

#     def _read_loop(self):
#         """
#         Continuously read lines from serial and store the most recent int.

#         Runs in a background thread.
#         """
#         while self._running and self.ser is not None:
#             try:
#                 line = self.ser.readline().decode(errors="ignore").strip()
#             except Exception:
#                 # small pause to avoid a tight error loop
#                 time.sleep(0.01)
#                 continue

#             if not line:
#                 # no data this tick; yield a bit
#                 time.sleep(0.001)
#                 continue

#             try:
#                 value = int(line)
#             except ValueError:
#                 # ignore non-integer noise
#                 continue

#             with self._lock:
#                 self._latest = value

#         # cleanup if loop exits
#         self.close()

#     # ---------- public API ----------

#     def get_latest(self):
#         """
#         Return the most recent integer value read from serial, or None.

#         Non-blocking and safe to call from GUI thread.
#         """
#         with self._lock:
#             return self._latest

#========================  Four FSRs =========================================

# class SerialBackend:
#     """
#     Threaded serial backend for reading *four* FSR channels from the ESP32.

#     - Opens a serial port.
#     - Starts a background thread that reads lines continuously.
#     - Expects each line to look like: "v0,v1,v2,v3".
#     - Stores the most recent list of 4 integers.
#     - GUI can call get_latest() at any time without blocking.

#     Channel order matches firmware CSV:
#         [0] -> A0  (currently your yellow wire)
#         [1] -> A1  (orange)
#         [2] -> A2  (green)
#         [3] -> A3  (white)
#     """

#     def __init__(
#         self,
#         port="/dev/cu.usbserial-0001",  # change to /dev/cu.usbmodemXXXX on the Feather
#         baud=115200,
#         timeout=0.01,
#         num_channels=4,
#     ):
#         self.port = port
#         self.baud = baud
#         self.timeout = timeout
#         self.num_channels = num_channels

#         self.ser = None
#         self._thread = None
#         self._running = False

#         # latest will be a list of ints: [ch0, ch1, ch2, ch3]
#         self._latest = [0] * self.num_channels
#         self._lock = threading.Lock()

#     # ---------- lifecycle ----------

#     def open(self):
#         """Open the serial port (no thread yet)."""
#         self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)

#     def start(self):
#         """
#         Start the background reader thread.

#         If the port is not open yet, open it first.
#         """
#         if self.ser is None:
#             self.open()

#         if self._thread is not None and self._thread.is_alive():
#             return

#         self._running = True
#         self._thread = threading.Thread(target=self._read_loop, daemon=True)
#         self._thread.start()

#     def stop(self):
#         """Stop the reader thread and close the port."""
#         self._running = False
#         if self._thread is not None:
#             try:
#                 self._thread.join(timeout=0.5)
#             except Exception:
#                 pass
#             self._thread = None

#         self.close()

#     def close(self):
#         """Close the serial port, if open."""
#         if self.ser is not None:
#             try:
#                 self.ser.close()
#             except Exception:
#                 pass
#             self.ser = None

#     # ---------- background loop ----------

#     def _read_loop(self):
#         """
#         Continuously read lines from serial and store the most recent 4-channel vector.

#         Runs in a background thread.
#         """
#         while self._running and self.ser is not None:
#             try:
#                 line = self.ser.readline().decode(errors="ignore").strip()
#             except Exception:
#                 # small pause to avoid a tight error loop
#                 time.sleep(0.01)
#                 continue

#             if not line:
#                 # no data this tick; yield a bit
#                 time.sleep(0.001)
#                 continue

#             parts = line.split(",")

#             # If we don't get the right number of channels, skip this line.
#             if len(parts) < self.num_channels:
#                 continue

#             try:
#                 vals = [int(p) for p in parts[: self.num_channels]]
#             except ValueError:
#                 # ignore non-integer noise
#                 continue

#             with self._lock:
#                 self._latest = vals

#         # cleanup if loop exits
#         self.close()

#     # ---------- public API ----------

#     def get_latest(self):
#         """
#         Return the most recent [v0, v1, v2, v3] list.

#         Non-blocking and safe to call from GUI thread.
#         """
#         with self._lock:
#             return list(self._latest)
        

#########===================== Serial Backend  V2 ==============================##########

# comms/serial_backend.py



def auto_detect_port():
    """
    Try to automatically find a USB serial port that looks like an ESP32 / Feather.

    On macOS, these are typically:
      - /dev/cu.usbmodemXXXX
      - /dev/cu.usbserial-XXXX

    Returns the device path as a string, or None if nothing suitable is found.
    """
    ports = serial.tools.list_ports.comports()
    candidates = []

    for p in ports:
        dev = p.device or ""
        desc = (p.description or "").lower()

        # Heuristics for macOS + ESP32 / Adafruit
        if dev.startswith("/dev/cu.usbmodem") or dev.startswith("/dev/cu.usbserial"):
            candidates.append(dev)
            continue

        # Extra safety: check description for esp32 / feather etc.
        if "esp32" in desc or "feather" in desc:
            candidates.append(dev)

    if not candidates:
        return None

    # Prefer usbmodem over usbserial if both exist
    candidates.sort(key=lambda d: (not d.startswith("/dev/cu.usbmodem"), d))
    return candidates[0]


class SerialBackend:
    """
    Threaded serial backend for reading *four* FSR channels from the ESP32.

    - Opens a serial port.
    - Starts a background thread that reads lines continuously.
    - Expects each line to look like: "v0,v1,v2,v3".
    - Stores the most recent list of 4 integers.
    - GUI can call get_latest() at any time without blocking.

    Channel order matches firmware CSV:
        [0] -> A0  (yellow)
        [1] -> A1  (orange)
        [2] -> A2  (green)
        [3] -> A3  (white)
    """

    def __init__(
        self,
        port=None,          # None or "" => auto-detect
        baud=115200,
        timeout=0.01,
        num_channels=4,
    ):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.num_channels = num_channels

        self.ser = None
        self._thread = None
        self._running = False

        # latest will be a list of ints: [ch0, ch1, ch2, ch3]
        self._latest = [0] * self.num_channels
        self._lock = threading.Lock()

    # ---------- lifecycle ----------

    def open(self):
        """
        Open the serial port (no thread yet).

        If self.port is None or empty, auto-detect a suitable port.
        """
        # Auto-detect if port not specified
        if not self.port:  # None or ""
            detected = auto_detect_port()
            if detected is None:
                raise RuntimeError(
                    "No suitable serial ports found. "
                    "Plug in your board and try again."
                )
            self.port = detected

        self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)

    def start(self):
        """
        Start the background reader thread.

        If the port is not open yet, open it first.
        """
        if self.ser is None:
            self.open()

        if self._thread is not None and self._thread.is_alive():
            return

        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the reader thread and close the port."""
        self._running = False
        if self._thread is not None:
            try:
                self._thread.join(timeout=0.5)
            except Exception:
                pass
            self._thread = None

        self.close()

    def close(self):
        """Close the serial port, if open."""
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    # ---------- background loop ----------

    def _read_loop(self):
        """
        Continuously read lines from serial and store the most recent 4-channel vector.

        Runs in a background thread.
        """
        while self._running and self.ser is not None:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
            except Exception:
                # small pause to avoid a tight error loop
                time.sleep(0.01)
                continue

            if not line:
                # no data this tick; yield a bit
                time.sleep(0.001)
                continue

            parts = line.split(",")

            # If we don't get the right number of channels, skip this line.
            if len(parts) < self.num_channels:
                continue

            try:
                vals = [int(p) for p in parts[: self.num_channels]]
            except ValueError:
                # ignore non-integer noise
                continue

            with self._lock:
                self._latest = vals

        # cleanup if loop exits
        self.close()

    # ---------- public API ----------

    def get_latest(self):
        """
        Return the most recent [v0, v1, v2, v3] list.

        Non-blocking and safe to call from GUI thread.
        """
        with self._lock:
            return list(self._latest)

    @staticmethod
    def list_ports():
        """
        Convenience helper: return a list of (device, description) for all ports.
        """
        out = []
        for p in serial.tools.list_ports.comports():
            out.append((p.device, p.description))
        return out