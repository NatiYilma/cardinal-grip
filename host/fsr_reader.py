# host/fsr_reader.py

import serial
import time
from collections import deque

class FSRReader:
    def __init__(self, port="/dev/cu.usbserial-0001", baud=115200,
                 smooth_window=3, timeout=0.01):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
        time.sleep(2)  # let ESP32 reset
        self._window = deque(maxlen=smooth_window)

    def read_raw(self):
        try:
            line = self.ser.readline()
        except serial.SerialException as e:
            print("Serial error:", e)
            return None
        if not line:
            return None
        return line

    def read(self):
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