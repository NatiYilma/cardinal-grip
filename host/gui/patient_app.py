# host/gui/patient_app.py

import os
import sys
import time
import csv
from collections import deque
from datetime import datetime

# Single FSR
# from PyQt6.QtCore import QTimer, Qt
# from PyQt6.QtWidgets import (
#     QApplication,
#     QWidget,
#     QVBoxLayout,
#     QHBoxLayout,
#     QLabel,
#     QPushButton,
#     QLineEdit,
#     QSlider,
#     QProgressBar,
#     QFileDialog,
#     QMessageBox,
# )
# import pyqtgraph as pg

# # ------------ PATH SETUP ------------
# # This file is .../cardinal-grip/host/gui/patient_app.py
# GUI_DIR = os.path.dirname(__file__)          # .../host/gui
# HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
# PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

# if PROJECT_ROOT not in sys.path:
#     sys.path.append(PROJECT_ROOT)

# from comms.serial_backend import SerialBackend  # noqa: E402
# # ------------------------------------


# class PatientWindow(QWidget):
#     def __init__(self):
#         super().__init__()

#         self.setWindowTitle("Cardinal Grip – Patient")
#         self.resize(900, 600)

#         # Serial + data
#         self.backend = None
#         self.values = deque(maxlen=2000)  # force values
#         self.times = deque(maxlen=2000)   # time stamps
#         self.start_time = None

#         # ---------- UI LAYOUT ----------

#         main_layout = QVBoxLayout()
#         self.setLayout(main_layout)

#         # Top row: serial config + connect/disconnect
#         top_row = QHBoxLayout()

#         top_row.addWidget(QLabel("Serial port:"))
#         self.port_edit = QLineEdit("/dev/cu.usbserial-0001")
#         top_row.addWidget(self.port_edit)

#         top_row.addWidget(QLabel("Baud:"))
#         self.baud_edit = QLineEdit("115200")
#         self.baud_edit.setFixedWidth(80)
#         top_row.addWidget(self.baud_edit)

#         self.connect_button = QPushButton("Connect")
#         self.connect_button.clicked.connect(self.handle_connect)
#         top_row.addWidget(self.connect_button)

#         self.disconnect_button = QPushButton("Disconnect")
#         self.disconnect_button.clicked.connect(self.handle_disconnect)
#         self.disconnect_button.setEnabled(False)
#         top_row.addWidget(self.disconnect_button)

#         main_layout.addLayout(top_row)

#         # Target band sliders (min/max)
#         band_row = QHBoxLayout()

#         self.target_min_slider = QSlider(Qt.Orientation.Horizontal)
#         self.target_min_slider.setRange(0, 4095)
#         self.target_min_slider.setValue(1200)

#         self.target_max_slider = QSlider(Qt.Orientation.Horizontal)
#         self.target_max_slider.setRange(0, 4095)
#         self.target_max_slider.setValue(2000)

#         band_row.addWidget(QLabel("Target min"))
#         band_row.addWidget(self.target_min_slider)
#         band_row.addWidget(QLabel("Target max"))
#         band_row.addWidget(self.target_max_slider)

#         main_layout.addLayout(band_row)

#         # Status + current value + progress bar
#         status_row = QHBoxLayout()
#         self.status_label = QLabel("Status: Not connected")
#         self.current_label = QLabel("Current force: 0")
#         self.current_bar = QProgressBar()
#         self.current_bar.setRange(0, 4095)

#         status_row.addWidget(self.status_label)
#         status_row.addWidget(self.current_label)
#         status_row.addWidget(self.current_bar)

#         main_layout.addLayout(status_row)

#         # Plot widget
#         self.plot_widget = pg.PlotWidget()
#         self.plot_widget.setLabel("left", "Force", units="ADC")
#         self.plot_widget.setLabel("bottom", "Time", units="s")
#         self.curve = self.plot_widget.plot([], [])
#         main_layout.addWidget(self.plot_widget)

#         # Bottom row: reset + save
#         bottom_row = QHBoxLayout()

#         self.reset_button = QPushButton("Reset session")
#         self.reset_button.clicked.connect(self.reset_session)
#         bottom_row.addWidget(self.reset_button)

#         self.save_button = QPushButton("Save CSV")
#         self.save_button.clicked.connect(self.save_csv)
#         bottom_row.addWidget(self.save_button)

#         main_layout.addLayout(bottom_row)

#         # Timer to poll latest sensor value from backend
#         self.timer = QTimer()
#         self.timer.setInterval(20)  # 20 ms -> ~50 Hz
#         self.timer.timeout.connect(self.poll_sensor)

#     # ---------- CONNECTION LOGIC ----------

#     def handle_connect(self):
#         if self.backend is not None:
#             return

#         port = self.port_edit.text().strip()

#         try:
#             baud = int(self.baud_edit.text().strip())
#         except ValueError:
#             QMessageBox.warning(self, "Error", "Invalid baud rate.")
#             return

#         try:
#             self.backend = SerialBackend(port=port, baud=baud, timeout=0.01)
#             # start background reader thread
#             self.backend.start()
#         except Exception as e:
#             QMessageBox.critical(self, "Serial error", f"Failed to open {port}:\n{e}")
#             self.backend = None
#             return

#         self.status_label.setText(f"Status: Connected to {port} @ {baud}")
#         self.connect_button.setEnabled(False)
#         self.disconnect_button.setEnabled(True)

#         self.reset_session()
#         self.start_time = time.time()
#         self.timer.start()

#     def handle_disconnect(self):
#         self.timer.stop()
#         if self.backend is not None:
#             self.backend.stop()   # stops thread + closes port
#             self.backend = None

#         self.status_label.setText("Status: Disconnected")
#         self.connect_button.setEnabled(True)
#         self.disconnect_button.setEnabled(False)

#     def reset_session(self):
#         self.values.clear()
#         self.times.clear()
#         self.start_time = time.time()
#         self.curve.setData([], [])
#         self.current_label.setText("Current force: 0")
#         self.current_bar.setValue(0)

#     # ---------- DATA / PLOTTING ----------

#     def poll_sensor(self):
#         if self.backend is None:
#             return

#         # Non-blocking: just grab the most recent value
#         val = self.backend.get_latest()
#         if val is None:
#             return

#         now = time.time()
#         if self.start_time is None:
#             self.start_time = now
#         t = now - self.start_time

#         self.values.append(val)
#         self.times.append(t)

#         # Update numeric displays
#         self.current_label.setText(f"Current force: {val}")
#         self.current_bar.setValue(val)

#         # Target band logic
#         tmin = self.target_min_slider.value()
#         tmax = self.target_max_slider.value()

#         if tmin <= val <= tmax:
#             self.status_label.setText("Status: ✅ In target zone")
#         elif val < tmin:
#             self.status_label.setText("Status: Squeeze a bit harder")
#         else:
#             self.status_label.setText("Status: Ease off slightly")

#         # Update plot
#         self.curve.setData(list(self.times), list(self.values))

#     # ---------- CSV SAVING ----------

#     def save_csv(self):
#         """
#         Save the current session's data (time_s, force_adc) to a CSV file.
#         """
#         if not self.values or not self.times:
#             QMessageBox.information(self, "No data", "No samples to save yet.")
#             return

#         ts = datetime.now().strftime("%Y%m%d_%H%M%S")
#         default_name = f"session_{ts}.csv"

#         # Default dir: project_root/data/logs
#         data_dir = os.path.join(PROJECT_ROOT, "data", "logs")
#         os.makedirs(data_dir, exist_ok=True)
#         default_path = os.path.join(data_dir, default_name)

#         path, _ = QFileDialog.getSaveFileName(
#             self,
#             "Save session CSV",
#             default_path,
#             "CSV Files (*.csv)",
#         )
#         if not path:
#             return  # user cancelled

#         try:
#             with open(path, "w", newline="") as f:
#                 writer = csv.writer(f)
#                 writer.writerow(["time_s", "force_adc"])
#                 for t, v in zip(self.times, self.values):
#                     writer.writerow([t, v])

#             QMessageBox.information(self, "Saved", f"Session saved to:\n{path}")
#         except Exception as e:
#             QMessageBox.critical(self, "Error", f"Failed to save CSV:\n{e}")


# def main():
#     app = QApplication(sys.argv)
#     win = PatientWindow()
#     win.show()
#     sys.exit(app.exec())


# if __name__ == "__main__":
#     main()

#========================  Four FSRs =========================================
# host/gui/patient_app.py

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

# ------------ PATH SETUP ------------
# This file is .../cardinal-grip/host/gui/patient_app.py
GUI_DIR = os.path.dirname(__file__)          # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from comms.serial_backend import SerialBackend  # noqa: E402
# ------------------------------------


NUM_CHANNELS = 4  # 4 FSRs (A0–A3)


class PatientWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Patient")
        self.resize(900, 600)

        # Serial + data
        self.backend = None

        # values[c] is a deque of samples for channel c
        self.values = [deque(maxlen=2000) for _ in range(NUM_CHANNELS)]
        self.times = deque(maxlen=2000)   # shared time axis
        self.start_time = None

        # ---------- UI LAYOUT ----------

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Top row: serial config + connect/disconnect
        top_row = QHBoxLayout()

        top_row.addWidget(QLabel("Serial port:"))
        self.port_edit = QLineEdit("/dev/cu.usbmodem14101") #/dev/cu.usbmodem14101 #/dev/cu.usbserial-0001
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

        # Target band sliders (min/max) – applied to channel 0 for now
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

        # Status + current values + progress bar (for channel 0)
        status_row = QHBoxLayout()
        self.status_label = QLabel("Status: Not connected")

        self.current_label = QLabel("Ch0 (A0) force: 0")
        self.current_bar = QProgressBar()
        self.current_bar.setRange(0, 4095)

        status_row.addWidget(self.status_label)
        status_row.addWidget(self.current_label)
        status_row.addWidget(self.current_bar)

        main_layout.addLayout(status_row)

        # Row of labels for all 4 channels
        chan_row = QHBoxLayout()
        self.chan_labels = []
        for c in range(NUM_CHANNELS):
            lbl = QLabel(f"Ch{c}: 0")
            self.chan_labels.append(lbl)
            chan_row.addWidget(lbl)
        main_layout.addLayout(chan_row)

        # Plot widget with 4 curves
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel("left", "Force", units="ADC")
        self.plot_widget.setLabel("bottom", "Time", units="s")
        self.plot_widget.addLegend()

        # One curve per channel
        colors = ["r", "g", "b", "y"]
        self.curves = []
        for c in range(NUM_CHANNELS):
            curve = self.plot_widget.plot(
                [], [],
                pen=pg.mkPen(colors[c % len(colors)], width=2),
                name=f"Ch{c}"
            )
            self.curves.append(curve)

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

        # Timer to poll latest sensor values from backend
        self.timer = QTimer()
        self.timer.setInterval(20)  # 20 ms -> ~50 Hz
        self.timer.timeout.connect(self.poll_sensor)

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
            # Make sure your SerialBackend is the new 4-channel version
            self.backend = SerialBackend(port=port, baud=baud, timeout=0.01)
            self.backend.start()  # start background reader thread
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
            self.backend.stop()   # stops thread + closes port
            self.backend = None

        self.status_label.setText("Status: Disconnected")
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)

    def reset_session(self):
        for c in range(NUM_CHANNELS):
            self.values[c].clear()
        self.times.clear()
        self.start_time = time.time()
        for curve in self.curves:
            curve.setData([], [])
        self.current_label.setText("Ch0 (A0) force: 0")
        self.current_bar.setValue(0)
        for c, lbl in enumerate(self.chan_labels):
            lbl.setText(f"Ch{c}: 0")

    # ---------- DATA / PLOTTING ----------

    def poll_sensor(self):
        if self.backend is None:
            return

        vals = self.backend.get_latest()  # should be [v0, v1, v2, v3]
        if not vals or len(vals) < NUM_CHANNELS:
            return

        now = time.time()
        if self.start_time is None:
            self.start_time = now
        t = now - self.start_time

        # Store time + channel values
        self.times.append(t)
        for c in range(NUM_CHANNELS):
            self.values[c].append(vals[c])

        # Update numeric labels
        for c, lbl in enumerate(self.chan_labels):
            lbl.setText(f"Ch{c}: {vals[c]}")

        # Use channel 0 for patient feedback (for now)
        ch0_val = vals[0]
        self.current_label.setText(f"Ch0 (A0) force: {ch0_val}")
        self.current_bar.setValue(ch0_val)

        # Target band logic on channel 0
        tmin = self.target_min_slider.value()
        tmax = self.target_max_slider.value()

        if tmin <= ch0_val <= tmax:
            self.status_label.setText("Status: ✅ In target zone")
        elif ch0_val < tmin:
            self.status_label.setText("Status: Squeeze a bit harder")
        else:
            self.status_label.setText("Status: Ease off slightly")

        # Update plots
        t_list = list(self.times)
        for c in range(NUM_CHANNELS):
            self.curves[c].setData(t_list, list(self.values[c]))

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

        # Default dir: project_root/data/logs
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
            return  # user cancelled

        try:
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                header = ["time_s"] + [f"ch{c}_adc" for c in range(NUM_CHANNELS)]
                writer.writerow(header)

                # assume all channels have same length as times
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