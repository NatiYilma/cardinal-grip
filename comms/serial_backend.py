# comms/serial_backend.py

import serial
import threading
import time


class SerialBackend:
    """
    Threaded serial backend for reading integer values from the ESP32.

    - Opens a serial port.
    - Starts a background thread that reads lines continuously.
    - Stores the most recent valid integer.
    - GUI can call get_latest() at any time without blocking.
    """

    def __init__(self, port="/dev/cu.usbserial-0001", baud=115200, timeout=0.01):
        self.port = port
        self.baud = baud
        self.timeout = timeout

        self.ser = None
        self._thread = None
        self._running = False

        self._latest = None
        self._lock = threading.Lock()

    # ---------- lifecycle ----------

    def open(self):
        """Open the serial port (no thread yet)."""
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
        Continuously read lines from serial and store the most recent int.

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

            try:
                value = int(line)
            except ValueError:
                # ignore non-integer noise
                continue

            with self._lock:
                self._latest = value

        # cleanup if loop exits
        self.close()

    # ---------- public API ----------

    def get_latest(self):
        """
        Return the most recent integer value read from serial, or None.

        Non-blocking and safe to call from GUI thread.
        """
        with self._lock:
            return self._latest