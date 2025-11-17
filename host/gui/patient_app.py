# host/gui/patient_app.py #version 7

import os
import sys
import time
import csv
from collections import deque
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
    QFileDialog,
    QMessageBox,
    QGroupBox,
)
from PyQt6.QtGui import QFont
import pyqtgraph as pg

# ------------ PATH SETUP ------------
# This file is .../cardinal-grip/host/gui/patient_app.py
GUI_DIR = os.path.dirname(__file__)          # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# ========= BACKEND SELECTION (REAL SERIAL VS SIMULATED) =========
# For real ESP32-S3 over serial, use:
# from comms.serial_backend import SerialBackend  # multi-channel backend
#
# For simulated backend with keyboard-driven values, use:
from comms.sim_backend import SimBackend as SerialBackend  # simulated FSR + keyboard
# ================================================================

NUM_CHANNELS = 4
CHANNEL_NAMES = ["Index", "Middle", "Ring", "Pinky"]


class PatientWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Patient (Multi-Finger)")
        self.resize(1100, 700)

        # Serial + data
        self.backend: SerialBackend | None = None
        self.start_time = None

        # values[c] is a deque of samples for channel c
        self.values = [deque(maxlen=2000) for _ in range(NUM_CHANNELS)]
        self.times = deque(maxlen=2000)   # shared time axis

        # ---------- MAIN LAYOUT ----------
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # ===== TOP: Serial config & connection =====
        top_row = QHBoxLayout()

        top_row.addWidget(QLabel("Serial port:"))
        self.port_edit = QLineEdit("/dev/cu.usbmodem14101")
        self.port_edit.setFixedWidth(220)
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

        # Status line
        self.status_label = QLabel("Status: Not connected")
        self.status_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(self.status_label)

        # ===== TARGET BAND (global band) =====
        band_group = QGroupBox("Target Zone (applies to all fingers)")
        band_layout = QHBoxLayout()
        band_group.setLayout(band_layout)

        # Min slider + numeric label
        band_layout.addWidget(QLabel("Min (ADC):"))
        self.target_min_slider = QSlider(Qt.Orientation.Horizontal)
        self.target_min_slider.setRange(0, 4095)
        self.target_min_slider.setValue(1200)
        band_layout.addWidget(self.target_min_slider)

        self.target_min_value_label = QLabel(str(self.target_min_slider.value()))
        self.target_min_value_label.setFixedWidth(60)
        self.target_min_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        band_layout.addWidget(self.target_min_value_label)

        # Max slider + numeric label
        band_layout.addWidget(QLabel("Max (ADC):"))
        self.target_max_slider = QSlider(Qt.Orientation.Horizontal)
        self.target_max_slider.setRange(0, 4095)
        self.target_max_slider.setValue(2000)
        band_layout.addWidget(self.target_max_slider)

        self.target_max_value_label = QLabel(str(self.target_max_slider.value()))
        self.target_max_value_label.setFixedWidth(60)
        self.target_max_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        band_layout.addWidget(self.target_max_value_label)

        band_hint = QLabel("Status text uses this band for ALL channels.")
        band_hint.setStyleSheet("color: gray;")
        band_layout.addWidget(band_hint)

        main_layout.addWidget(band_group)

        # Hook sliders to update visuals (numeric labels + threshold lines)
        self.target_min_slider.valueChanged.connect(self._update_band_visuals)
        self.target_max_slider.valueChanged.connect(self._update_band_visuals)

        # ===== CENTER: Four finger bars =====
        bars_row = QHBoxLayout()
        main_layout.addLayout(bars_row)

        self.bar_widgets = []
        self.value_labels = []

        for i in range(NUM_CHANNELS):
            col = QVBoxLayout()

            name_label = QLabel(CHANNEL_NAMES[i])
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            col.addWidget(name_label)

            bar = QProgressBar()
            bar.setOrientation(Qt.Orientation.Vertical)
            bar.setRange(0, 4095)
            bar.setValue(0)
            bar.setFixedWidth(60)
            col.addWidget(bar, stretch=1, alignment=Qt.AlignmentFlag.AlignHCenter)
            self.bar_widgets.append(bar)

            val_label = QLabel("Force: 0")
            val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(val_label)
            self.value_labels.append(val_label)

            bars_row.addLayout(col)

        # ===== PLOT: 4 curves over time =====
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel("left", "Force", units="ADC")
        self.plot_widget.setLabel("bottom", "Time", units="s")
        self.plot_widget.addLegend()
        main_layout.addWidget(self.plot_widget, stretch=1)

        colors = ["r", "g", "b", "y"]
        self.curves = []
        for c in range(NUM_CHANNELS):
            curve = self.plot_widget.plot(
                [], [],
                pen=pg.mkPen(colors[c % len(colors)], width=2),
                name=f"Ch{c} ({CHANNEL_NAMES[c]})",
            )
            self.curves.append(curve)

        # ---- Threshold lines on plot (create BEFORE any call to _update_band_visuals) ----
        initial_tmin = self.target_min_slider.value()
        initial_tmax = self.target_max_slider.value()

        self.min_line = pg.InfiniteLine(
            angle=0,
            pos=initial_tmin,
            pen=pg.mkPen((150, 0, 150), width=1, style=Qt.PenStyle.DashLine),
        )
        self.max_line = pg.InfiniteLine(
            angle=0,
            pos=initial_tmax,
            pen=pg.mkPen((0, 150, 150), width=1, style=Qt.PenStyle.DashLine),
        )
        self.plot_widget.addItem(self.min_line)
        self.plot_widget.addItem(self.max_line)

        # Ensure visuals match initial slider values
        self._update_band_visuals()

        # ===== BOTTOM: Reset & Save =====
        bottom_row = QHBoxLayout()

        self.reset_button = QPushButton("Reset session")
        self.reset_button.clicked.connect(self.reset_session)
        bottom_row.addWidget(self.reset_button)

        self.save_button = QPushButton("Save CSV")
        self.save_button.clicked.connect(self.save_csv)
        bottom_row.addWidget(self.save_button)

        main_layout.addLayout(bottom_row)

        # ===== TIMER =====
        self.timer = QTimer()
        self.timer.setInterval(20)  # 20 ms -> ~50 Hz
        self.timer.timeout.connect(self.poll_sensor)

        # ==== SIM BACKEND / KEYBOARD INPUT HOOK (comment out for real hardware) ====
        # When using SimBackend with keyboard input, make sure this window has
        # focus so key presses reach keyPressEvent / keyReleaseEvent.
        # For real Serial/WiFi/BLE backends, you can safely comment this out.
        self.setFocus()
        # ==== END SIM BACKEND HOOK ================================================

    # ---------- BAND VISUALS / HELPERS ----------

    def _update_band_visuals(self):
        """
        Update numeric labels and threshold lines on the plot.
        This is also aliased as _update_band_labels() so the dual launcher
        can call it without caring about the exact name.
        """
        tmin = self.target_min_slider.value()
        tmax = self.target_max_slider.value()

        # Enforce Min <= Max logically (but allow sliders to cross visually if you want).
        if tmax < tmin:
            tmax = tmin
            self.target_max_slider.blockSignals(True)
            self.target_max_slider.setValue(tmax)
            self.target_max_slider.blockSignals(False)

        self.target_min_value_label.setText(str(tmin))
        self.target_max_value_label.setText(str(tmax))

        # Update threshold lines on plot
        if hasattr(self, "min_line") and self.min_line is not None:
            self.min_line.setPos(tmin)
        if hasattr(self, "max_line") and self.max_line is not None:
            self.max_line.setPos(tmax)

    # Alias so patient_dual_launcher can call gw._update_band_labels()
    def _update_band_labels(self):
        self._update_band_visuals()

    # ---------- CONNECTION LOGIC ----------

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
            # NOTE: For SimBackend, port/baud/timeout are accepted but ignored.
            self.backend = SerialBackend(port=port, baud=baud, timeout=0.01)
            self.backend.start()
        except Exception as e:
            QMessageBox.critical(self, "Serial error", f"Failed to open {port}:\n{e}")
            self.backend = None
            return

        self.status_label.setText(f"Status: Connected to {port} @ {baud}")
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)

        self.reset_session()
        self.start_time = time.time()
        self.timer.start()

    def handle_disconnect(self):
        self.timer.stop()
        if self.backend is not None:
            self.backend.stop()
            self.backend = None

        self.status_label.setText("Status: Disconnected")
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)

    # ---------- SESSION RESET ----------

    def reset_session(self):
        for c in range(NUM_CHANNELS):
            self.values[c].clear()
        self.times.clear()
        self.start_time = time.time()

        for curve in self.curves:
            curve.setData([], [])

        for i in range(NUM_CHANNELS):
            self.bar_widgets[i].setValue(0)
            self.value_labels[i].setText("Force: 0")

        self.status_label.setText("Status: Ready")

    # ---------- DATA / PLOTTING ----------

    def poll_sensor(self):
        if self.backend is None:
            return

        vals = self.backend.get_latest()  # expected [v0, v1, v2, v3]
        if vals is None:
            return

        if isinstance(vals, (int, float)):
            vals = [int(vals)] * NUM_CHANNELS
        elif isinstance(vals, (list, tuple)):
            vals = list(vals)
        else:
            return

        if len(vals) < NUM_CHANNELS:
            vals += [0] * (NUM_CHANNELS - len(vals))

        now = time.time()
        if self.start_time is None:
            self.start_time = now
        t = now - self.start_time

        self.times.append(t)

        tmin = self.target_min_slider.value()
        tmax = self.target_max_slider.value()

        # Collect per-channel zone to summarise in status
        zones = []

        for c in range(NUM_CHANNELS):
            v = max(0, min(4095, int(vals[c])))
            self.values[c].append(v)

            # Update bar and label
            self.bar_widgets[c].setValue(v)
            self.value_labels[c].setText(f"Force: {v}")

            # Determine zone for status
            if tmin <= v <= tmax:
                zone = "in"
            elif v < tmin:
                zone = "low"
            else:
                zone = "high"
            zones.append(zone)

        # Multi-channel status summary
        parts = []
        for name, zone in zip(CHANNEL_NAMES, zones):
            if zone == "in":
                sym = "✅"
            elif zone == "low":
                sym = "⬇️"
            else:
                sym = "⬆️"
            parts.append(f"{name}:{sym}")
        self.status_label.setText("Status: " + "  ".join(parts))

        # Update plot
        t_list = list(self.times)
        for c in range(NUM_CHANNELS):
            self.curves[c].setData(t_list, list(self.values[c]))

    # ==== SIM BACKEND / KEYBOARD INPUT HOOK (comment out for real hardware) ====
    # Generic key forwarding: sends raw characters to any backend that
    # exposes a `handle_char(ch: str, is_press: bool)` method.
    # For real Serial/WiFi/BLE backends, you can safely comment out this
    # entire block and the rest of the GUI stays backend-agnostic.
    def keyPressEvent(self, event):
        if self.backend is not None and hasattr(self.backend, "handle_char"):
            ch = event.text()
            if ch:
                self.backend.handle_char(ch, True)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if self.backend is not None and hasattr(self.backend, "handle_char"):
            ch = event.text()
            if ch:
                self.backend.handle_char(ch, False)
        super().keyReleaseEvent(event)
    # ==== END SIM BACKEND HOOK ================================================

    # ---------- CSV SAVING ----------

    def save_csv(self):
        """
        Save the current session's data:
            time_s, ch0_adc, ch1_adc, ch2_adc, ch3_adc
        """
        if not self.times:
            QMessageBox.information(self, "No data", "No samples to save yet.")
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"patient_session_{ts}.csv"

        data_dir = os.path.join(PROJECT_ROOT, "data", "logs")
        os.makedirs(data_dir, exist_ok=True)
        default_path = os.path.join(data_dir, default_name)

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save session CSV",
            default_path,
            "CSV Files (*.csv)",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                header = ["time_s"] + [f"ch{c}_adc" for c in range(NUM_CHANNELS)]
                writer.writerow(header)

                length = len(self.times)
                for i in range(length):
                    row = [self.times[i]]
                    for c in range(NUM_CHANNELS):
                        row.append(self.values[c][i])
                    writer.writerow(row)

            QMessageBox.information(self, "Saved", f"Session saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save CSV:\n{e}")


def main():
    app = QApplication(sys.argv)
    win = PatientWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
