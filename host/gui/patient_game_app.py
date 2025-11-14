# host/gui/patient_game_app.py
#
# Gamified patient GUI:
# - 4 channels (e.g., Index, Middle, Ring, Pinky)
# - Color-coded bars: orange (very low), yellow (low), green (in target),
#   red (too high)
# - Start / Stop session
# - Per-channel 5-second hold timers when in target band
# - Counts successful holds and persists totals in data/patient_stats.json

import os
import sys
import json
import time
import threading

from collections import deque

import serial

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QSlider,
    QProgressBar,
    QMessageBox,
    QGroupBox,
)


# ------------ PATH SETUP ------------
# This file is .../cardinal-grip/host/gui/patient_game_app.py
GUI_DIR = os.path.dirname(__file__)          # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
LOG_DIR = os.path.join(DATA_DIR, "logs")
STATS_PATH = os.path.join(DATA_DIR, "patient_stats.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
# ------------------------------------


# ---------- MULTICHANNEL SERIAL BACKEND ----------

class MultiChannelSerialBackend:
    """
    Threaded serial backend for reading multiple integer channels from the ESP32.

    Expected line formats (examples):
        "1234,567,890,321"
        "1234 567 890 321"

    We store the most recent list of ints (e.g. length 4).
    """

    def __init__(self, port="/dev/cu.usbmodem14101", baud=115200,
                 timeout=0.01, num_channels=4):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.num_channels = num_channels

        self.ser = None
        self._thread = None
        self._running = False

        self._latest = None  # list[int] or None
        self._lock = threading.Lock()

    def open(self):
        """Open the serial port (no thread yet)."""
        self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)

    def start(self):
        """Start the background reader thread."""
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
        """Close the serial port if open."""
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def _read_loop(self):
        """Continuously read lines and parse into a list of ints."""
        while self._running and self.ser is not None:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
            except Exception:
                time.sleep(0.01)
                continue

            if not line:
                time.sleep(0.001)
                continue

            # Split by comma or whitespace
            raw_parts = line.replace(",", " ").split()
            vals = []
            for p in raw_parts:
                try:
                    vals.append(int(p))
                except ValueError:
                    # ignore non-int fragments
                    pass

            if not vals:
                continue

            # Normalize to fixed num_channels (pad or slice)
            if len(vals) < self.num_channels:
                vals = vals + [0] * (self.num_channels - len(vals))
            elif len(vals) > self.num_channels:
                vals = vals[:self.num_channels]

            with self._lock:
                self._latest = vals

        # Cleanup
        self.close()

    def get_latest(self):
        """
        Return the most recent list of ints, or None.
        Non-blocking, safe for GUI thread.
        """
        with self._lock:
            return self._latest


# ---------- GAMIFIED PATIENT WINDOW ----------

class GamePatientWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Patient (Game Mode)")
        self.resize(900, 600)

        # Serial backend
        self.backend = None
        self.num_channels = 4

        # Session state
        self.session_active = False

        # Per-channel live values
        self.current_values = [0] * self.num_channels

        # Per-channel hold logic
        self.hold_target_seconds = 5.0
        self.hold_remaining = [None] * self.num_channels  # seconds remaining or None
        self.session_success_counts = [0] * self.num_channels

        # Persistent totals
        self.total_success_counts = [0] * self.num_channels
        self._load_persistent_stats()

        # For “FPS” / update timing
        self.last_tick = time.time()

        # Build UI
        self._build_ui()

        # Timer to poll sensor + update game logic
        self.timer = QTimer()
        self.timer.setInterval(100)  # 100 ms -> 10 Hz game loop
        self.timer.timeout.connect(self._tick)

    # ---------- Persistence ----------

    def _load_persistent_stats(self):
        if not os.path.exists(STATS_PATH):
            self.total_success_counts = [0] * self.num_channels
            return
        try:
            with open(STATS_PATH, "r") as f:
                data = json.load(f)
            arr = data.get("total_successes", [])
            if isinstance(arr, list) and len(arr) >= self.num_channels:
                self.total_success_counts = arr[: self.num_channels]
            else:
                self.total_success_counts = [0] * self.num_channels
        except Exception:
            self.total_success_counts = [0] * self.num_channels

    def _save_persistent_stats(self):
        data = {"total_successes": self.total_success_counts}
        try:
            with open(STATS_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    # ---------- UI BUILD ----------

    def _build_ui(self):
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Top row: serial config + connect/disconnect
        top_row = QHBoxLayout()

        top_row.addWidget(QLabel("Serial port:"))
        self.port_edit = QLineEdit("/dev/cu.usbmodem14101")
        top_row.addWidget(self.port_edit)

        top_row.addWidget(QLabel("Baud:"))
        self.baud_edit = QLineEdit("115200")
        self.baud_edit.setFixedWidth(80)
        top_row.addWidget(self.baud_edit)

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.handle_connect)
        top_row.addWidget(self.connect_button)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.handle_disconnect)
        self.disconnect_button.setEnabled(False)
        top_row.addWidget(self.disconnect_button)

        main_layout.addLayout(top_row)

        # Session controls
        session_row = QHBoxLayout()

        self.start_button = QPushButton("Start Session")
        self.start_button.clicked.connect(self.start_session)
        session_row.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Session")
        self.stop_button.clicked.connect(self.stop_session)
        self.stop_button.setEnabled(False)
        session_row.addWidget(self.stop_button)

        self.status_label = QLabel("Status: Not connected")
        session_row.addWidget(self.status_label, stretch=1)

        main_layout.addLayout(session_row)

        # Target band sliders
        band_group = QGroupBox("Target Band (applies to all fingers)")
        band_layout = QHBoxLayout()
        band_group.setLayout(band_layout)

        band_layout.addWidget(QLabel("Min (ADC):"))
        self.target_min_slider = QSlider(Qt.Orientation.Horizontal)
        self.target_min_slider.setRange(0, 4095)
        self.target_min_slider.setValue(1200)
        band_layout.addWidget(self.target_min_slider)

        band_layout.addWidget(QLabel("Max (ADC):"))
        self.target_max_slider = QSlider(Qt.Orientation.Horizontal)
        self.target_max_slider.setRange(0, 4095)
        self.target_max_slider.setValue(2000)
        band_layout.addWidget(self.target_max_slider)

        main_layout.addWidget(band_group)

        # Bars group (one per channel)
        bars_group = QGroupBox("Finger Force Game")
        bars_layout = QHBoxLayout()
        bars_group.setLayout(bars_layout)
        main_layout.addWidget(bars_group, stretch=1)

        # Names for fingers (you can rename to Index/Middle/Ring/Pinky etc.)
        finger_names = ["Index", "Middle", "Ring", "Pinky"]

        self.bar_widgets = []
        self.bar_status_labels = []
        self.hold_labels = []
        self.session_count_labels = []
        self.total_count_labels = []

        for i in range(self.num_channels):
            col = QVBoxLayout()

            name_label = QLabel(f"{finger_names[i]} finger")
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(name_label)

            bar = QProgressBar()
            bar.setRange(0, 4095)
            bar.setFormat("%v")  # show raw ADC
            col.addWidget(bar)
            self.bar_widgets.append(bar)

            status = QLabel("Status: —")
            status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(status)
            self.bar_status_labels.append(status)

            hold = QLabel("Hold: —")
            hold.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(hold)
            self.hold_labels.append(hold)

            sess = QLabel("Session successes: 0")
            sess.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(sess)
            self.session_count_labels.append(sess)

            total = QLabel(f"Total successes: {self.total_success_counts[i]}")
            total.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(total)
            self.total_count_labels.append(total)

            bars_layout.addLayout(col)

        # Bottom hint
        hint = QLabel(
            "Instructions: Squeeze each finger into the green zone and hold it "
            "for 5 seconds to score repetitions. "
            "Orange/yellow = too low, red = too high."
        )
        hint.setStyleSheet("color: gray;")
        main_layout.addWidget(hint)

    # ---------- CONNECTION / SESSION CONTROL ----------

    def handle_connect(self):
        if self.backend is not None:
            return

        port = self.port_edit.text().strip()
        try:
            baud = int(self.baud_edit.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid baud rate.")
            return

        try:
            self.backend = MultiChannelSerialBackend(
                port=port,
                baud=baud,
                timeout=0.01,
                num_channels=self.num_channels,
            )
            self.backend.start()
        except Exception as e:
            QMessageBox.critical(self, "Serial error", f"Failed to open {port}:\n{e}")
            self.backend = None
            return

        self.status_label.setText(f"Status: Connected to {port} @ {baud}")
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)

        # Start ticking even if session not started (to see live bars)
        self.last_tick = time.time()
        self.timer.start()

    def handle_disconnect(self):
        self.timer.stop()
        self.stop_session()

        if self.backend is not None:
            self.backend.stop()
            self.backend = None

        self.status_label.setText("Status: Disconnected")
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)

    def start_session(self):
        if self.backend is None:
            QMessageBox.information(
                self, "Not connected", "Please connect to the device first."
            )
            return

        self.session_active = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        # Reset per-session counters & hold timers
        self.session_success_counts = [0] * self.num_channels
        self.hold_remaining = [None] * self.num_channels
        for i in range(self.num_channels):
            self.session_count_labels[i].setText("Session successes: 0")
            self.hold_labels[i].setText("Hold: —")

        self.status_label.setText("Status: Session running – aim for green!")

    def stop_session(self):
        self.session_active = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        # Clear hold timers
        self.hold_remaining = [None] * self.num_channels
        for i in range(self.num_channels):
            self.hold_labels[i].setText("Hold: —")

        if self.backend is not None:
            self.status_label.setText("Status: Connected (session stopped)")
        else:
            self.status_label.setText("Status: Not connected")

    # ---------- GAME LOOP ----------

    def _tick(self):
        now = time.time()
        dt = now - self.last_tick
        self.last_tick = now

        if self.backend is None:
            return

        vals = self.backend.get_latest()
        if vals is None:
            return

        # Update current values
        if len(vals) != self.num_channels:
            vals = (vals + [0] * self.num_channels)[: self.num_channels]
        self.current_values = vals

        tmin = self.target_min_slider.value()
        tmax = self.target_max_slider.value()

        # For each channel: update bar, color, status, hold timer
        for i in range(self.num_channels):
            val = self.current_values[i]

            # Update bar value
            bar = self.bar_widgets[i]
            bar.setValue(val)

            # Decide color + text based on zones
            color, status_text = self._classify_value(val, tmin, tmax)
            self._set_bar_color(bar, color)
            self.bar_status_labels[i].setText(f"Status: {status_text}")

            # Hold timer only counts during an active session
            if not self.session_active:
                continue

            # In target zone?
            in_zone = (tmin <= val <= tmax)

            if in_zone:
                # Start or continue the hold
                if self.hold_remaining[i] is None:
                    self.hold_remaining[i] = self.hold_target_seconds

                self.hold_remaining[i] -= dt
                remaining = max(0.0, self.hold_remaining[i])

                if remaining <= 0.0:
                    # Success! Increment counters & reset hold
                    self.session_success_counts[i] += 1
                    self.total_success_counts[i] += 1
                    self._save_persistent_stats()

                    self.session_count_labels[i].setText(
                        f"Session successes: {self.session_success_counts[i]}"
                    )
                    self.total_count_labels[i].setText(
                        f"Total successes: {self.total_success_counts[i]}"
                    )

                    self.hold_labels[i].setText("Hold: ✅ Completed!")
                    self.hold_remaining[i] = None
                else:
                    self.hold_labels[i].setText(
                        f"Hold: {remaining:.1f} s remaining"
                    )

            else:
                # Left the zone: reset hold
                self.hold_remaining[i] = None
                self.hold_labels[i].setText("Hold: —")

    # ---------- HELPER METHODS ----------

    @staticmethod
    def _classify_value(val, tmin, tmax):
        """
        Map ADC value to a color + status text.

        Zones (heuristic):
            val < 0.5 * tmin        -> orange  ("very low")
            0.5 * tmin <= val < tmin -> yellow ("squeeze a bit harder")
            tmin <= val <= tmax      -> green  ("in target zone")
            val > tmax               -> red    ("ease off slightly")
        """
        if tmin <= tmax:
            if val < 0.5 * tmin:
                return ("orange", "Very low")
            elif val < tmin:
                return ("yellow", "Squeeze a bit harder")
            elif val <= tmax:
                return ("green", "In target zone")
            else:
                return ("red", "Ease off slightly")
        else:
            # degenerate setting; just treat everything as neutral
            return ("gray", "Check target sliders")

    @staticmethod
    def _set_bar_color(bar: QProgressBar, color_name: str):
        # Simple color style; you can tweak fonts/border as you like.
        bar.setStyleSheet(
            f"""
            QProgressBar {{
                border: 1px solid #666;
                border-radius: 4px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {color_name};
            }}
            """
        )

    # Clean up backend on window close
    def closeEvent(self, event):
        try:
            self.timer.stop()
        except Exception:
            pass
        if self.backend is not None:
            self.backend.stop()
            self.backend = None
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = GamePatientWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()