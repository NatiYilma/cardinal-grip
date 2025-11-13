# host/gui/patient_qt.py

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
)
import pyqtgraph as pg

# # Add parent folder ("host") to import path so we can import comms.serial_backend
# HOST_DIR = os.path.dirname(os.path.dirname(__file__))  # .../cardinal-grip/host
# if HOST_DIR not in sys.path:
#     sys.path.append(HOST_DIR)

# Add project root (cardinal-grip/) to sys.path so we can import comms.serial_backend
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
# /.../cardinal-grip/host/gui → /host → /cardinal-grip
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from comms.serial_backend import SerialBackend  # noqa: E402


class PatientWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Patient (PyQt)")
        self.resize(900, 600)

        # Serial + data
        self.backend = None
        self.values = deque(maxlen=2000)
        self.times = deque(maxlen=2000)
        self.start_time = None

        # ---------- UI LAYOUT ----------

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Top row: port/baud + connect/disconnect
        top_row = QHBoxLayout()

        top_row.addWidget(QLabel("Serial port:"))
        self.port_edit = QLineEdit("/dev/cu.usbserial-0001")
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

        # Row: target band sliders
        band_row = QHBoxLayout()

        self.target_min_slider = QSlider(Qt.Orientation.Horizontal)
        self.target_min_slider.setRange(0, 4095)
        self.target_min_slider.setValue(1200)

        self.target_max_slider = QSlider(Qt.Orientation.Horizontal)
        self.target_max_slider.setRange(0, 4095)
        self.target_max_slider.setValue(2000)

        band_row.addWidget(QLabel("Target min"))
        band_row.addWidget(self.target_min_slider)
        band_row.addWidget(QLabel("Target max"))
        band_row.addWidget(self.target_max_slider)

        main_layout.addLayout(band_row)

        # Status + current value
        status_row = QHBoxLayout()
        self.status_label = QLabel("Status: Not connected")
        self.current_label = QLabel("Current force: 0")
        self.current_bar = QProgressBar()
        self.current_bar.setRange(0, 4095)

        status_row.addWidget(self.status_label)
        status_row.addWidget(self.current_label)
        status_row.addWidget(self.current_bar)

        main_layout.addLayout(status_row)

        # Plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel("left", "Force", units="ADC")
        self.plot_widget.setLabel("bottom", "Time", units="s")
        self.curve = self.plot_widget.plot([], [])
        main_layout.addWidget(self.plot_widget)

        # Bottom row: reset + save
        bottom_row = QHBoxLayout()

        self.reset_button = QPushButton("Reset session")
        self.reset_button.clicked.connect(self.reset_session)
        bottom_row.addWidget(self.reset_button)

        self.save_button = QPushButton("Save CSV")
        self.save_button.clicked.connect(self.save_csv)
        bottom_row.addWidget(self.save_button)

        main_layout.addLayout(bottom_row)

        # Timer to poll sensor via SerialBackend
        self.timer = QTimer()
        self.timer.setInterval(20)  # 20 ms → ~50 Hz
        self.timer.timeout.connect(self.poll_sensor)

    # ---------- LOGIC ----------

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
            self.backend.open()
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
            self.backend.close()
            self.backend = None

        self.status_label.setText("Status: Disconnected")
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)

    def reset_session(self):
        self.values.clear()
        self.times.clear()
        self.start_time = time.time()
        self.curve.setData([], [])
        self.current_label.setText("Current force: 0")
        self.current_bar.setValue(0)

    def poll_sensor(self):
        if self.backend is None:
            return

        val = self.backend.read_value()
        if val is None:
            return

        now = time.time()
        if self.start_time is None:
            self.start_time = now
        t = now - self.start_time

        self.values.append(val)
        self.times.append(t)

        # Update numeric + bar
        self.current_label.setText(f"Current force: {val}")
        self.current_bar.setValue(val)

        # Target band logic
        tmin = self.target_min_slider.value()
        tmax = self.target_max_slider.value()

        if tmin <= val <= tmax:
            self.status_label.setText("Status: ✅ In target zone")
        elif val < tmin:
            self.status_label.setText("Status: Squeeze a bit harder")
        else:
            self.status_label.setText("Status: Ease off slightly")

        # Update plot
        self.curve.setData(list(self.times), list(self.values))

    def save_csv(self):
        if not self.values or not self.times:
            QMessageBox.information(self, "No data", "No samples to save yet.")
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"session_{ts}.csv"

        # project root is one level above HOST_DIR
        project_root = os.path.dirname(HOST_DIR)
        data_dir = os.path.join(project_root, "data", "logs")
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
                writer.writerow(["time_s", "force_adc"])
                for t, v in zip(self.times, self.values):
                    writer.writerow([t, v])

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