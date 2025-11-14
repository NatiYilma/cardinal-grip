# host/gui/patient_game_app.py

import os
import sys
import json
import time
from datetime import datetime

from PyQt6.QtCore import QTimer, Qt
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
from PyQt6.QtGui import QFont

# -------- PATH SETUP (same pattern as other GUIs) --------
GUI_DIR = os.path.dirname(__file__)          # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from comms.serial_backend import SerialBackend  # noqa: E402
# --------------------------------------------------------


NUM_CHANNELS = 4
CHANNEL_NAMES = ["Index", "Middle", "Ring", "Pinky"]

# Seconds the finger must stay in target band to count a rep
HOLD_SECONDS = 5.0


class PatientGameWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Patient Game Mode")
        self.resize(1100, 650)

        # --- Serial + data state ---
        self.backend: SerialBackend | None = None
        self.last_time = None  # for dt calculation in timer

        # One hold timer per channel (seconds spent continuously in band)
        self.hold_time = [0.0] * NUM_CHANNELS
        self.in_band_prev = [False] * NUM_CHANNELS

        # Persistent reps per channel, loaded/saved from JSON
        self.reps_per_channel = [0] * NUM_CHANNELS
        self.sessions_completed = 0
        self.stats_path = os.path.join(PROJECT_ROOT, "data", "patient_stats.json")
        self._load_stats()

        # --- UI ---
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # ===== TOP: serial + control bar =====
        top_row = QHBoxLayout()

        top_row.addWidget(QLabel("Serial port:"))
        self.port_edit = QLineEdit("/dev/cu.usbmodem14101")
        self.port_edit.setFixedWidth(200)
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

        self.start_button = QPushButton("Start Session")
        self.start_button.clicked.connect(self.start_session)
        self.start_button.setEnabled(False)
        top_row.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Session")
        self.stop_button.clicked.connect(self.stop_session)
        self.stop_button.setEnabled(False)
        top_row.addWidget(self.stop_button)

        main_layout.addLayout(top_row)

        # Status line
        self.status_label = QLabel("Status: Not connected")
        self.status_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(self.status_label)

        # ===== TARGET BAND CONTROLS =====
        band_group = QGroupBox("Target Zone (applies to all fingers)")
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

        self.band_hint_label = QLabel("Stay in the green zone for 5 seconds to earn a rep.")
        band_layout.addWidget(self.band_hint_label)

        main_layout.addWidget(band_group)

        # ===== CENTER: game bars =====
        center_row = QHBoxLayout()
        main_layout.addLayout(center_row, stretch=1)

        self.bar_widgets = []
        self.value_labels = []
        self.countdown_labels = []
        self.rep_labels = []

        for i in range(NUM_CHANNELS):
            col = QVBoxLayout()

            # Finger name
            name_label = QLabel(CHANNEL_NAMES[i])
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            col.addWidget(name_label)

            # Vertical bar (force)
            bar = QProgressBar()
            bar.setOrientation(Qt.Orientation.Vertical)
            bar.setRange(0, 4095)
            bar.setValue(0)
            bar.setFixedWidth(60)
            bar.setStyleSheet("QProgressBar::chunk { background-color: orange; }")
            col.addWidget(bar, stretch=1, alignment=Qt.AlignmentFlag.AlignHCenter)
            self.bar_widgets.append(bar)

            # Current value label
            val_label = QLabel("Force: 0")
            val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(val_label)
            self.value_labels.append(val_label)

            # Countdown label
            cd_label = QLabel("Hold: –")
            cd_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cd_label.setStyleSheet("font-size: 11pt;")
            col.addWidget(cd_label)
            self.countdown_labels.append(cd_label)

            # Rep count label (persistent over runs)
            rep_label = QLabel(f"Reps: {self.reps_per_channel[i]}")
            rep_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rep_label.setStyleSheet("font-size: 11pt; font-weight: bold;")
            col.addWidget(rep_label)
            self.rep_labels.append(rep_label)

            center_row.addLayout(col)

        # ===== BOTTOM: overall stats =====
        bottom_row = QHBoxLayout()
        self.total_reps_label = QLabel(self._total_reps_text())
        self.total_reps_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        bottom_row.addWidget(self.total_reps_label)

        self.session_count_label = QLabel(f"Sessions completed (game mode): {self.sessions_completed}")
        bottom_row.addWidget(self.session_count_label)

        main_layout.addLayout(bottom_row)

        # ===== TIMER =====
        self.timer = QTimer()
        self.timer.setInterval(50)  # 20 Hz
        self.timer.timeout.connect(self.game_tick)

    # ------------- STATS PERSISTENCE (JSON) -------------

    def _load_stats(self):
        os.makedirs(os.path.join(PROJECT_ROOT, "data"), exist_ok=True)
        if not os.path.isfile(self.stats_path):
            # default structure
            self.reps_per_channel = [0] * NUM_CHANNELS
            self.sessions_completed = 0
            return
        try:
            with open(self.stats_path, "r") as f:
                data = json.load(f)
            self.reps_per_channel = data.get("reps_per_channel", [0] * NUM_CHANNELS)
            if len(self.reps_per_channel) != NUM_CHANNELS:
                self.reps_per_channel = [0] * NUM_CHANNELS
            self.sessions_completed = int(data.get("sessions_completed", 0))
        except Exception:
            # If corrupted, reset
            self.reps_per_channel = [0] * NUM_CHANNELS
            self.sessions_completed = 0

    def _save_stats(self):
        data = {
            "reps_per_channel": self.reps_per_channel,
            "sessions_completed": self.sessions_completed,
            "last_updated": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            with open(self.stats_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            # Don't crash GUI if writing fails
            pass

    def _total_reps_text(self):
        total = sum(self.reps_per_channel)
        return f"Total reps across fingers: {total}"

    # ------------- CONNECTION / SESSION CONTROL -------------

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
            self.backend = SerialBackend(port=port, baud=baud, timeout=0.01)
            self.backend.start()
        except Exception as e:
            QMessageBox.critical(self, "Serial error", f"Failed to open {port}:\n{e}")
            self.backend = None
            return

        self.status_label.setText(f"Status: Connected to {port} @ {baud}")
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        self.start_button.setEnabled(True)

    def handle_disconnect(self):
        self.stop_session()
        if self.backend is not None:
            self.backend.stop()
            self.backend = None
        self.status_label.setText("Status: Disconnected")
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.start_button.setEnabled(False)

    def start_session(self):
        # Reset per-session hold timers ONLY (not reps)
        self.hold_time = [0.0] * NUM_CHANNELS
        self.in_band_prev = [False] * NUM_CHANNELS
        self.last_time = time.time()

        self.timer.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Status: Session running – squeeze to hit the green zone!")

    def stop_session(self):
        if self.timer.isActive():
            self.timer.stop()
            self.sessions_completed += 1
            self._save_stats()
            self.session_count_label.setText(
                f"Sessions completed (game mode): {self.sessions_completed}"
            )
        self.start_button.setEnabled(self.backend is not None)
        self.stop_button.setEnabled(False)

    # ------------- GAME LOOP -------------

    def game_tick(self):
        if self.backend is None:
            return

        vals = self.backend.get_latest()
        if vals is None:
            return

        # Ensure vals is a list/tuple of length NUM_CHANNELS
        if isinstance(vals, (int, float)):
            vals = [vals] * NUM_CHANNELS
        elif isinstance(vals, (list, tuple)):
            if len(vals) < NUM_CHANNELS:
                vals = list(vals) + [0] * (NUM_CHANNELS - len(vals))
        else:
            return

        now = time.time()
        if self.last_time is None:
            dt = 0.0
        else:
            dt = now - self.last_time
        self.last_time = now

        tmin = self.target_min_slider.value()
        tmax = self.target_max_slider.value()

        for i in range(NUM_CHANNELS):
            val = int(vals[i])
            if val < 0:
                val = 0
            if val > 4095:
                val = 4095

            # Update bar & numeric text
            self.bar_widgets[i].setValue(val)
            self.value_labels[i].setText(f"Force: {val}")

            # Determine zone and color
            if val < tmin:
                zone = "low"
                color = "orange"
            elif val > tmax:
                zone = "high"
                color = "red"
            else:
                zone = "in_band"
                color = "green"

            self._set_bar_color(self.bar_widgets[i], color)

            # ---- Countdown logic ----
            # Only accumulate hold_time while in the band during an active session
            if self.timer.isActive() and zone == "in_band":
                self.hold_time[i] += dt
                remaining = max(0.0, HOLD_SECONDS - self.hold_time[i])
                if remaining > 0:
                    self.countdown_labels[i].setText(f"Hold: {remaining:0.1f} s")
                else:
                    # Rep achieved
                    self.reps_per_channel[i] += 1
                    self.rep_labels[i].setText(f"Reps: {self.reps_per_channel[i]}")
                    self.total_reps_label.setText(self._total_reps_text())
                    self.countdown_labels[i].setText("Nice! ✅")
                    # Reset hold timer so they must do another full 5 s
                    self.hold_time[i] = 0.0
                    # Save to disk on each successful rep
                    self._save_stats()
            else:
                # Not in band or session not running → reset hold timer
                self.hold_time[i] = 0.0
                self.countdown_labels[i].setText("Hold: –")

    def _set_bar_color(self, bar: QProgressBar, color: str):
        if color == "green":
            chunk_color = "#4CAF50"
        elif color == "red":
            chunk_color = "#F44336"
        else:  # orange / default
            chunk_color = "#FF9800"
        bar.setStyleSheet(
            "QProgressBar {"
            "border: 1px solid #999;"
            "border-radius: 3px;"
            "background: #eee;"
            "}"
            f"QProgressBar::chunk {{ background-color: {chunk_color}; }}"
        )


def main():
    app = QApplication(sys.argv)
    win = PatientGameWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()