# host/fsr_reader.py

import serial
import time
from collections import deque


DEFAULT_PORT = "/dev/cu.usbserial-0001"  # or "/dev/tty.usbserial-0001" on macOS
DEFAULT_BAUD = 115200


class FSRReader:
    """
    Reads integer ADC values from the ESP32 over USB serial.
    Expects the firmware to print ONE integer per line (e.g. `Serial.println(avg);`).
    """

    def __init__(self, port=DEFAULT_PORT, baud=DEFAULT_BAUD,
                 smooth_window=3, timeout=0.01):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
        # Give the ESP32 a moment to reset after opening the port
        time.sleep(2)
        self._window = deque(maxlen=smooth_window)

    def read_raw(self):
        """
        Return one raw line from serial, or None if nothing / error.
        """
        try:
            line = self.ser.readline()
        except serial.SerialException as e:
            print("Serial error:", e)
            return None

        if not line:
            # No bytes (can happen if nothing has been printed yet)
            return None

        return line

    def read(self):
        """
        Return a smoothed integer value, or None if no valid data.
        """
        raw = self.read_raw()
        if raw is None:
            return None

        try:
            val = int(raw.decode(errors="ignore").strip())
        except ValueError:
            return None

        self._window.append(val)
        return int(sum(self._window) / len(self._window))

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()


if __name__ == "__main__":
    """
    Standalone test: run

        python host/fsr_reader.py

    from the project root (cardinal-grip), with the ESP32 plugged in and
    the esp32_fsr_serial.ino firmware running.
    """
    reader = FSRReader()
    print(f"Reading from {reader.port} at {reader.baud} baud (Ctrl+C to stop).")
    try:
        while True:
            v = reader.read()
            if v is not None:
                print(v)
            time.sleep(0.02)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        reader.close()