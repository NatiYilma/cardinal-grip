
# import os
# import sys
# import time
# import csv
# from collections import deque
# from datetime import datetime

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

# import os
# import sys
# import time
# import csv
# from collections import deque
# from datetime import datetime

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


# NUM_CHANNELS = 4  # 4 FSRs (A0–A3)


# class PatientWindow(QWidget):
#     def __init__(self):
#         super().__init__()

#         self.setWindowTitle("Cardinal Grip – Patient")
#         self.resize(900, 600)

#         # Serial + data
#         self.backend = None

#         # values[c] is a deque of samples for channel c
#         self.values = [deque(maxlen=2000) for _ in range(NUM_CHANNELS)]
#         self.times = deque(maxlen=2000)   # shared time axis
#         self.start_time = None

#         # ---------- UI LAYOUT ----------

#         main_layout = QVBoxLayout()
#         self.setLayout(main_layout)

#         # Top row: serial config + connect/disconnect
#         top_row = QHBoxLayout()

#         top_row.addWidget(QLabel("Serial port:"))
#         self.port_edit = QLineEdit("/dev/cu.usbmodem14101") #/dev/cu.usbmodem14101 #/dev/cu.usbserial-0001
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

#         # Target band sliders (min/max) – applied to channel 0 for now
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

#         # Status + current values + progress bar (for channel 0)
#         status_row = QHBoxLayout()
#         self.status_label = QLabel("Status: Not connected")

#         self.current_label = QLabel("Ch0 (A0) force: 0")
#         self.current_bar = QProgressBar()
#         self.current_bar.setRange(0, 4095)

#         status_row.addWidget(self.status_label)
#         status_row.addWidget(self.current_label)
#         status_row.addWidget(self.current_bar)

#         main_layout.addLayout(status_row)

#         # Row of labels for all 4 channels
#         chan_row = QHBoxLayout()
#         self.chan_labels = []
#         for c in range(NUM_CHANNELS):
#             lbl = QLabel(f"Ch{c}: 0")
#             self.chan_labels.append(lbl)
#             chan_row.addWidget(lbl)
#         main_layout.addLayout(chan_row)

#         # Plot widget with 4 curves
#         self.plot_widget = pg.PlotWidget()
#         self.plot_widget.setLabel("left", "Force", units="ADC")
#         self.plot_widget.setLabel("bottom", "Time", units="s")
#         self.plot_widget.addLegend()

#         # One curve per channel
#         colors = ["r", "g", "b", "y"]
#         self.curves = []
#         for c in range(NUM_CHANNELS):
#             curve = self.plot_widget.plot(
#                 [], [],
#                 pen=pg.mkPen(colors[c % len(colors)], width=2),
#                 name=f"Ch{c}"
#             )
#             self.curves.append(curve)

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

#         # Timer to poll latest sensor values from backend
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
#             # Make sure your SerialBackend is the new 4-channel version
#             self.backend = SerialBackend(port=port, baud=baud, timeout=0.01)
#             self.backend.start()  # start background reader thread
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
#         for c in range(NUM_CHANNELS):
#             self.values[c].clear()
#         self.times.clear()
#         self.start_time = time.time()
#         for curve in self.curves:
#             curve.setData([], [])
#         self.current_label.setText("Ch0 (A0) force: 0")
#         self.current_bar.setValue(0)
#         for c, lbl in enumerate(self.chan_labels):
#             lbl.setText(f"Ch{c}: 0")

#     # ---------- DATA / PLOTTING ----------

#     def poll_sensor(self):
#         if self.backend is None:
#             return

#         vals = self.backend.get_latest()  # should be [v0, v1, v2, v3]
#         if not vals or len(vals) < NUM_CHANNELS:
#             return

#         now = time.time()
#         if self.start_time is None:
#             self.start_time = now
#         t = now - self.start_time

#         # Store time + channel values
#         self.times.append(t)
#         for c in range(NUM_CHANNELS):
#             self.values[c].append(vals[c])

#         # Update numeric labels
#         for c, lbl in enumerate(self.chan_labels):
#             lbl.setText(f"Ch{c}: {vals[c]}")

#         # Use channel 0 for patient feedback (for now)
#         ch0_val = vals[0]
#         self.current_label.setText(f"Ch0 (A0) force: {ch0_val}")
#         self.current_bar.setValue(ch0_val)

#         # Target band logic on channel 0
#         tmin = self.target_min_slider.value()
#         tmax = self.target_max_slider.value()

#         if tmin <= ch0_val <= tmax:
#             self.status_label.setText("Status: ✅ In target zone")
#         elif ch0_val < tmin:
#             self.status_label.setText("Status: Squeeze a bit harder")
#         else:
#             self.status_label.setText("Status: Ease off slightly")

#         # Update plots
#         t_list = list(self.times)
#         for c in range(NUM_CHANNELS):
#             self.curves[c].setData(t_list, list(self.values[c]))

#     # ---------- CSV SAVING ----------

#     def save_csv(self):
#         """
#         Save the current session's data:
#             time_s, ch0_adc, ch1_adc, ch2_adc, ch3_adc
#         """
#         if not self.times:
#             QMessageBox.information(self, "No data", "No samples to save yet.")
#             return

#         ts = datetime.now().strftime("%Y%m%d_%H%M%S")
#         default_name = f"patient_session_{ts}.csv"

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
#                 header = ["time_s"] + [f"ch{c}_adc" for c in range(NUM_CHANNELS)]
#                 writer.writerow(header)

#                 # assume all channels have same length as times
#                 length = len(self.times)
#                 for i in range(length):
#                     row = [self.times[i]]
#                     for c in range(NUM_CHANNELS):
#                         row.append(self.values[c][i])
#                     writer.writerow(row)

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

#########===================== PATIENT GUI V2 ==============================##########

## host/gui/patient_app.py

# import os
# import sys
# import time
# import csv
# from collections import deque
# from datetime import datetime

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
#     QGroupBox,
# )
# from PyQt6.QtGui import QFont
# import pyqtgraph as pg

# # ------------ PATH SETUP ------------
# # This file is .../cardinal-grip/host/gui/patient_app.py
# GUI_DIR = os.path.dirname(__file__)          # .../host/gui
# HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
# PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

# if PROJECT_ROOT not in sys.path:
#     sys.path.append(PROJECT_ROOT)

# from comms.serial_backend import SerialBackend  # multi-channel backend
# # ------------------------------------

# NUM_CHANNELS = 4
# CHANNEL_NAMES = ["Index", "Middle", "Ring", "Pinky"]

# class PatientWindow(QWidget):
#     def __init__(self):
#         super().__init__()

#         self.setWindowTitle("Cardinal Grip – Patient (Multi-Finger)")
#         self.resize(1100, 700)

#         # Serial + data
#         self.backend: SerialBackend | None = None
#         self.start_time = None

#         # values[c] is a deque of samples for channel c
#         self.values = [deque(maxlen=2000) for _ in range(NUM_CHANNELS)]
#         self.times = deque(maxlen=2000)   # shared time axis

#         # ---------- MAIN LAYOUT ----------
#         main_layout = QVBoxLayout()
#         self.setLayout(main_layout)

#         # ===== TOP: Serial config & connection =====
#         top_row = QHBoxLayout()

#         top_row.addWidget(QLabel("Serial port:"))
#         self.port_edit = QLineEdit("/dev/cu.usbmodem14101")
#         self.port_edit.setFixedWidth(220)
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

#         # Status line
#         self.status_label = QLabel("Status: Not connected")
#         self.status_label.setStyleSheet("font-weight: bold;")
#         main_layout.addWidget(self.status_label)

#         # ===== TARGET BAND (for now: global band, but feedback based on Ch0) =====
#         band_group = QGroupBox("Target Zone (applies to Channel 0 for feedback)")
#         band_layout = QHBoxLayout()
#         band_group.setLayout(band_layout)

#         band_layout.addWidget(QLabel("Min (ADC):"))
#         self.target_min_slider = QSlider(Qt.Orientation.Horizontal)
#         self.target_min_slider.setRange(0, 4095)
#         self.target_min_slider.setValue(1200)
#         band_layout.addWidget(self.target_min_slider)

#         band_layout.addWidget(QLabel("Max (ADC):"))
#         self.target_max_slider = QSlider(Qt.Orientation.Horizontal)
#         self.target_max_slider.setRange(0, 4095)
#         self.target_max_slider.setValue(2000)
#         band_layout.addWidget(self.target_max_slider)

#         band_hint = QLabel("Channel 0 bar and status text use this band.")
#         band_hint.setStyleSheet("color: gray;")
#         band_layout.addWidget(band_hint)

#         main_layout.addWidget(band_group)

#         # ===== CENTER: Four finger bars =====
#         bars_row = QHBoxLayout()
#         main_layout.addLayout(bars_row)

#         self.bar_widgets = []
#         self.value_labels = []

#         for i in range(NUM_CHANNELS):
#             col = QVBoxLayout()

#             name_label = QLabel(CHANNEL_NAMES[i])
#             name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#             name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
#             col.addWidget(name_label)

#             bar = QProgressBar()
#             bar.setOrientation(Qt.Orientation.Vertical)
#             bar.setRange(0, 4095)
#             bar.setValue(0)
#             bar.setFixedWidth(60)
#             col.addWidget(bar, stretch=1, alignment=Qt.AlignmentFlag.AlignHCenter)
#             self.bar_widgets.append(bar)

#             val_label = QLabel("Force: 0")
#             val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#             col.addWidget(val_label)
#             self.value_labels.append(val_label)

#             bars_row.addLayout(col)

#         # ===== PLOT: 4 curves over time =====
#         self.plot_widget = pg.PlotWidget()
#         self.plot_widget.setLabel("left", "Force", units="ADC")
#         self.plot_widget.setLabel("bottom", "Time", units="s")
#         self.plot_widget.addLegend()
#         main_layout.addWidget(self.plot_widget, stretch=1)

#         colors = ["r", "g", "b", "y"]
#         self.curves = []
#         for c in range(NUM_CHANNELS):
#             curve = self.plot_widget.plot(
#                 [], [],
#                 pen=pg.mkPen(colors[c % len(colors)], width=2),
#                 name=f"Ch{c} ({CHANNEL_NAMES[c]})",
#             )
#             self.curves.append(curve)

#         # ===== BOTTOM: Reset & Save =====
#         bottom_row = QHBoxLayout()

#         self.reset_button = QPushButton("Reset session")
#         self.reset_button.clicked.connect(self.reset_session)
#         bottom_row.addWidget(self.reset_button)

#         self.save_button = QPushButton("Save CSV")
#         self.save_button.clicked.connect(self.save_csv)
#         bottom_row.addWidget(self.save_button)

#         main_layout.addLayout(bottom_row)

#         # ===== TIMER =====
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
#             self.backend.stop()
#             self.backend = None

#         self.status_label.setText("Status: Disconnected")
#         self.connect_button.setEnabled(True)
#         self.disconnect_button.setEnabled(False)

#     # ---------- SESSION RESET ----------

#     def reset_session(self):
#         for c in range(NUM_CHANNELS):
#             self.values[c].clear()
#         self.times.clear()
#         self.start_time = time.time()

#         for curve in self.curves:
#             curve.setData([], [])

#         for i in range(NUM_CHANNELS):
#             self.bar_widgets[i].setValue(0)
#             self.value_labels[i].setText("Force: 0")

#         self.status_label.setText("Status: Ready")

#     # ---------- DATA / PLOTTING ----------

#     def poll_sensor(self):
#         if self.backend is None:
#             return

#         vals = self.backend.get_latest()  # expected [v0, v1, v2, v3]
#         if vals is None:
#             return

#         if isinstance(vals, (int, float)):
#             vals = [int(vals)] * NUM_CHANNELS
#         elif isinstance(vals, (list, tuple)):
#             vals = list(vals)
#         else:
#             return

#         if len(vals) < NUM_CHANNELS:
#             vals += [0] * (NUM_CHANNELS - len(vals))

#         now = time.time()
#         if self.start_time is None:
#             self.start_time = now
#         t = now - self.start_time

#         self.times.append(t)
#         for c in range(NUM_CHANNELS):
#             v = max(0, min(4095, int(vals[c])))
#             self.values[c].append(v)

#             # Update bar and label
#             self.bar_widgets[c].setValue(v)
#             self.value_labels[c].setText(f"Force: {v}")

#         # Target band feedback based on channel 0
#         ch0 = self.values[0][-1]
#         tmin = self.target_min_slider.value()
#         tmax = self.target_max_slider.value()

#         if tmin <= ch0 <= tmax:
#             self.status_label.setText("Status: ✅ Ch0 in target zone")
#         elif ch0 < tmin:
#             self.status_label.setText("Status: Ch0 – squeeze a bit harder")
#         else:
#             self.status_label.setText("Status: Ch0 – ease off slightly")

#         # Update plot
#         t_list = list(self.times)
#         for c in range(NUM_CHANNELS):
#             self.curves[c].setData(t_list, list(self.values[c]))

#     # ---------- CSV SAVING ----------

#     def save_csv(self):
#         """
#         Save the current session's data:
#             time_s, ch0_adc, ch1_adc, ch2_adc, ch3_adc
#         """
#         if not self.times:
#             QMessageBox.information(self, "No data", "No samples to save yet.")
#             return

#         ts = datetime.now().strftime("%Y%m%d_%H%M%S")
#         default_name = f"patient_session_{ts}.csv"

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
#             return

#         try:
#             with open(path, "w", newline="") as f:
#                 writer = csv.writer(f)
#                 header = ["time_s"] + [f"ch{c}_adc" for c in range(NUM_CHANNELS)]
#                 writer.writerow(header)

#                 length = len(self.times)
#                 for i in range(length):
#                     row = [self.times[i]]
#                     for c in range(NUM_CHANNELS):
#                         row.append(self.values[c][i])
#                     writer.writerow(row)

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



#########===================== PATIENT GUI V3 ==============================##########
## host/gui/patient_app.py

# import os
# import sys
# import time
# import csv
# from collections import deque
# from datetime import datetime

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
#     QGroupBox,
# )
# from PyQt6.QtGui import QFont
# import pyqtgraph as pg

# # ------------ PATH SETUP ------------
# # This file is .../cardinal-grip/host/gui/patient_app.py
# GUI_DIR = os.path.dirname(__file__)          # .../host/gui
# HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
# PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

# if PROJECT_ROOT not in sys.path:
#     sys.path.append(PROJECT_ROOT)

# # ========= BACKEND SELECTION (REAL SERIAL VS SIMULATED) =========
# # For real ESP32-S3 over serial, use:
# # from comms.serial_backend import SerialBackend  # multi-channel backend
# #
# # For simulated backend with keyboard-driven values, use:
# from comms.sim_backend import SimBackend as SerialBackend  # simulated FSR + keyboard
# # ================================================================

# NUM_CHANNELS = 4
# CHANNEL_NAMES = ["Index", "Middle", "Ring", "Pinky"]

# class PatientWindow(QWidget):
#     def __init__(self):
#         super().__init__()

#         self.setWindowTitle("Cardinal Grip – Patient (Multi-Finger)")
#         self.resize(1100, 700)

#         # Serial + data
#         self.backend: SerialBackend | None = None
#         self.start_time = None

#         # values[c] is a deque of samples for channel c
#         self.values = [deque(maxlen=2000) for _ in range(NUM_CHANNELS)]
#         self.times = deque(maxlen=2000)   # shared time axis

#         # ---------- MAIN LAYOUT ----------
#         main_layout = QVBoxLayout()
#         self.setLayout(main_layout)

#         # ===== TOP: Serial config & connection =====
#         top_row = QHBoxLayout()

#         top_row.addWidget(QLabel("Serial port:"))
#         self.port_edit = QLineEdit("/dev/cu.usbmodem14101")
#         self.port_edit.setFixedWidth(220)
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

#         # Status line
#         self.status_label = QLabel("Status: Not connected")
#         self.status_label.setStyleSheet("font-weight: bold;")
#         main_layout.addWidget(self.status_label)

#         # ===== TARGET BAND (for now: global band, but feedback based on Ch0) =====
#         band_group = QGroupBox("Target Zone (applies to Channel 0 for feedback)")
#         band_layout = QHBoxLayout()
#         band_group.setLayout(band_layout)

#         band_layout.addWidget(QLabel("Min (ADC):"))
#         self.target_min_slider = QSlider(Qt.Orientation.Horizontal)
#         self.target_min_slider.setRange(0, 4095)
#         self.target_min_slider.setValue(1200)
#         band_layout.addWidget(self.target_min_slider)

#         band_layout.addWidget(QLabel("Max (ADC):"))
#         self.target_max_slider = QSlider(Qt.Orientation.Horizontal)
#         self.target_max_slider.setRange(0, 4095)
#         self.target_max_slider.setValue(2000)
#         band_layout.addWidget(self.target_max_slider)

#         band_hint = QLabel("Channel 0 bar and status text use this band.")
#         band_hint.setStyleSheet("color: gray;")
#         band_layout.addWidget(band_hint)

#         main_layout.addWidget(band_group)

#         # ===== CENTER: Four finger bars =====
#         bars_row = QHBoxLayout()
#         main_layout.addLayout(bars_row)

#         self.bar_widgets = []
#         self.value_labels = []

#         for i in range(NUM_CHANNELS):
#             col = QVBoxLayout()

#             name_label = QLabel(CHANNEL_NAMES[i])
#             name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#             name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
#             col.addWidget(name_label)

#             bar = QProgressBar()
#             bar.setOrientation(Qt.Orientation.Vertical)
#             bar.setRange(0, 4095)
#             bar.setValue(0)
#             bar.setFixedWidth(60)
#             col.addWidget(bar, stretch=1, alignment=Qt.AlignmentFlag.AlignHCenter)
#             self.bar_widgets.append(bar)

#             val_label = QLabel("Force: 0")
#             val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#             col.addWidget(val_label)
#             self.value_labels.append(val_label)

#             bars_row.addLayout(col)

#         # ===== PLOT: 4 curves over time =====
#         self.plot_widget = pg.PlotWidget()
#         self.plot_widget.setLabel("left", "Force", units="ADC")
#         self.plot_widget.setLabel("bottom", "Time", units="s")
#         self.plot_widget.addLegend()
#         main_layout.addWidget(self.plot_widget, stretch=1)

#         colors = ["r", "g", "b", "y"]
#         self.curves = []
#         for c in range(NUM_CHANNELS):
#             curve = self.plot_widget.plot(
#                 [], [],
#                 pen=pg.mkPen(colors[c % len(colors)], width=2),
#                 name=f"Ch{c} ({CHANNEL_NAMES[c]})",
#             )
#             self.curves.append(curve)

#         # ===== BOTTOM: Reset & Save =====
#         bottom_row = QHBoxLayout()

#         self.reset_button = QPushButton("Reset session")
#         self.reset_button.clicked.connect(self.reset_session)
#         bottom_row.addWidget(self.reset_button)

#         self.save_button = QPushButton("Save CSV")
#         self.save_button.clicked.connect(self.save_csv)
#         bottom_row.addWidget(self.save_button)

#         main_layout.addLayout(bottom_row)

#         # ===== TIMER =====
#         self.timer = QTimer()
#         self.timer.setInterval(20)  # 20 ms -> ~50 Hz
#         self.timer.timeout.connect(self.poll_sensor)

#         # ==== SIM BACKEND / KEYBOARD INPUT HOOK (comment out for real hardware) ====
#         # When using SimBackend with keyboard input, make sure this window has
#         # focus so key presses reach keyPressEvent / keyReleaseEvent.
#         # For real Serial/WiFi/BLE backends, you can safely comment this out.
#         self.setFocus()
#         # ==== END SIM BACKEND HOOK ================================================

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
#             # NOTE: For SimBackend, port/baud/timeout are accepted but ignored.
#             self.backend = SerialBackend(port=port, baud=baud, timeout=0.01)
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
#             self.backend.stop()
#             self.backend = None

#         self.status_label.setText("Status: Disconnected")
#         self.connect_button.setEnabled(True)
#         self.disconnect_button.setEnabled(False)

#     # ---------- SESSION RESET ----------

#     def reset_session(self):
#         for c in range(NUM_CHANNELS):
#             self.values[c].clear()
#         self.times.clear()
#         self.start_time = time.time()

#         for curve in self.curves:
#             curve.setData([], [])

#         for i in range(NUM_CHANNELS):
#             self.bar_widgets[i].setValue(0)
#             self.value_labels[i].setText("Force: 0")

#         self.status_label.setText("Status: Ready")

#     # ---------- DATA / PLOTTING ----------

#     def poll_sensor(self):
#         if self.backend is None:
#             return

#         vals = self.backend.get_latest()  # expected [v0, v1, v2, v3]
#         if vals is None:
#             return

#         if isinstance(vals, (int, float)):
#             vals = [int(vals)] * NUM_CHANNELS
#         elif isinstance(vals, (list, tuple)):
#             vals = list(vals)
#         else:
#             return

#         if len(vals) < NUM_CHANNELS:
#             vals += [0] * (NUM_CHANNELS - len(vals))

#         now = time.time()
#         if self.start_time is None:
#             self.start_time = now
#         t = now - self.start_time

#         self.times.append(t)
#         for c in range(NUM_CHANNELS):
#             v = max(0, min(4095, int(vals[c])))
#             self.values[c].append(v)

#             # Update bar and label
#             self.bar_widgets[c].setValue(v)
#             self.value_labels[c].setText(f"Force: {v}")

#         # Target band feedback based on channel 0
#         ch0 = self.values[0][-1]
#         tmin = self.target_min_slider.value()
#         tmax = self.target_max_slider.value()

#         if tmin <= ch0 <= tmax:
#             self.status_label.setText("Status: ✅ Ch0 in target zone")
#         elif ch0 < tmin:
#             self.status_label.setText("Status: Ch0 – squeeze a bit harder")
#         else:
#             self.status_label.setText("Status: Ch0 – ease off slightly")

#         # Update plot
#         t_list = list(self.times)
#         for c in range(NUM_CHANNELS):
#             self.curves[c].setData(t_list, list(self.values[c]))

#     # ==== SIM BACKEND / KEYBOARD INPUT HOOK (comment out for real hardware) ====
#     # Generic key forwarding: sends raw characters to any backend that
#     # exposes a `handle_char(ch: str, is_press: bool)` method.
#     # For real Serial/WiFi/BLE backends, you can safely comment out this
#     # entire block and the rest of the GUI stays backend-agnostic.
#     def keyPressEvent(self, event):
#         if self.backend is not None and hasattr(self.backend, "handle_char"):
#             ch = event.text()
#             if ch:
#                 self.backend.handle_char(ch, True)
#         super().keyPressEvent(event)

#     def keyReleaseEvent(self, event):
#         if self.backend is not None and hasattr(self.backend, "handle_char"):
#             ch = event.text()
#             if ch:
#                 self.backend.handle_char(ch, False)
#         super().keyReleaseEvent(event)
#     # ==== END SIM BACKEND HOOK ================================================

#     # ---------- CSV SAVING ----------

#     def save_csv(self):
#         """
#         Save the current session's data:
#             time_s, ch0_adc, ch1_adc, ch2_adc, ch3_adc
#         """
#         if not self.times:
#             QMessageBox.information(self, "No data", "No samples to save yet.")
#             return

#         ts = datetime.now().strftime("%Y%m%d_%H%M%S")
#         default_name = f"patient_session_{ts}.csv"

#         data_dir = os.path.join(PROJECT_ROOT, "data", "logs")
#         os.makedirs(data_dir, exist_ok=True)
#         default_path = os.path.join(data_dir, default_name)

#         path, _ = QFileDialog.getSaveFileName(
#             self,
#             "Save session CSV",
#             default_path,
#             "CSV Files (*.csv)",
#             )
#         if not path:
#             return

#         try:
#             with open(path, "w", newline="") as f:
#                 writer = csv.writer(f)
#                 header = ["time_s"] + [f"ch{c}_adc" for c in range(NUM_CHANNELS)]
#                 writer.writerow(header)

#                 length = len(self.times)
#                 for i in range(length):
#                     row = [self.times[i]]
#                     for c in range(NUM_CHANNELS):
#                         row.append(self.values[c][i])
#                     writer.writerow(row)

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

#########===================== PATIENT GUI V4 ==============================##########
## host/gui/patient_app.py

# import os
# import sys
# import time
# import csv
# from collections import deque
# from datetime import datetime

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
#     QGroupBox,
# )
# from PyQt6.QtGui import QFont, QPainter, QPen, QColor
# import pyqtgraph as pg

# # ------------ PATH SETUP ------------
# # This file is .../cardinal-grip/host/gui/patient_app.py
# GUI_DIR = os.path.dirname(__file__)          # .../host/gui
# HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
# PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

# if PROJECT_ROOT not in sys.path:
#     sys.path.append(PROJECT_ROOT)

# # ========= BACKEND SELECTION (REAL SERIAL VS SIMULATED) =========
# # For real ESP32-S3 over serial, use:
# # from comms.serial_backend import SerialBackend  # multi-channel backend
# #
# # For simulated backend with keyboard-driven values, use:
# from comms.sim_backend import SimBackend as SerialBackend  # simulated FSR + keyboard
# # ================================================================

# NUM_CHANNELS = 4
# CHANNEL_NAMES = ["Index", "Middle", "Ring", "Pinky"]


# class ThresholdProgressBar(QProgressBar):
#     """Vertical progress bar with faint dashed lines for min/max thresholds."""

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self._min_thresh: int | None = None
#         self._max_thresh: int | None = None

#     def set_thresholds(self, min_val: int, max_val: int):
#         self._min_thresh = min_val
#         self._max_thresh = max_val
#         self.update()

#     def paintEvent(self, event):
#         # Draw normal progress bar first
#         super().paintEvent(event)

#         if self._min_thresh is None or self._max_thresh is None:
#             return

#         rect = self.contentsRect()
#         if rect.height() <= 0:
#             return

#         minimum = self.minimum()
#         maximum = self.maximum()
#         span = maximum - minimum
#         if span <= 0:
#             return

#         painter = QPainter(self)
#         painter.setRenderHint(QPainter.RenderHint.Antialiasing)

#         pen = QPen(QColor(0, 0, 0, 120))  # faint dark gray
#         pen.setStyle(Qt.PenStyle.DashLine)
#         pen.setWidth(1)
#         painter.setPen(pen)

#         def draw_for_value(v):
#             # Clamp within bar range
#             v_clamped = max(minimum, min(maximum, v))
#             frac = (v_clamped - minimum) / span  # 0 at min, 1 at max
#             # vertical bar: 0 at bottom, 1 at top
#             y = rect.bottom() - frac * rect.height()
#             painter.drawLine(rect.left() + 2, int(y), rect.right() - 2, int(y))

#         draw_for_value(self._min_thresh)
#         draw_for_value(self._max_thresh)

#         painter.end()


# class PatientWindow(QWidget):
#     def __init__(self):
#         super().__init__()

#         self.setWindowTitle("Cardinal Grip – Patient (Multi-Finger)")
#         self.resize(1100, 700)

#         # Serial + data
#         self.backend: SerialBackend | None = None
#         self.start_time = None

#         # values[c] is a deque of samples for channel c
#         self.values = [deque(maxlen=2000) for _ in range(NUM_CHANNELS)]
#         self.times = deque(maxlen=2000)   # shared time axis

#         # ---------- MAIN LAYOUT ----------
#         main_layout = QVBoxLayout()
#         self.setLayout(main_layout)

#         # ===== TOP: Serial config & connection =====
#         top_row = QHBoxLayout()

#         top_row.addWidget(QLabel("Serial port:"))
#         self.port_edit = QLineEdit("/dev/cu.usbmodem14101")
#         self.port_edit.setFixedWidth(220)
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

#         # Status line
#         self.status_label = QLabel("Status: Not connected")
#         self.status_label.setStyleSheet("font-weight: bold;")
#         main_layout.addWidget(self.status_label)

#         # ===== TARGET BAND (global band; status based on Ch0) =====
#         band_group = QGroupBox("Target Zone")
#         band_layout = QHBoxLayout()
#         band_group.setLayout(band_layout)

#         # Min slider + numeric label
#         band_layout.addWidget(QLabel("Min (ADC):"))
#         self.target_min_slider = QSlider(Qt.Orientation.Horizontal)
#         self.target_min_slider.setRange(0, 4095)
#         self.target_min_slider.setValue(1200)
#         band_layout.addWidget(self.target_min_slider)

#         self.target_min_value_label = QLabel(str(self.target_min_slider.value()))
#         self.target_min_value_label.setFixedWidth(60)
#         self.target_min_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#         band_layout.addWidget(self.target_min_value_label)

#         # Max slider + numeric label
#         band_layout.addWidget(QLabel("Max (ADC):"))
#         self.target_max_slider = QSlider(Qt.Orientation.Horizontal)
#         self.target_max_slider.setRange(0, 4095)
#         self.target_max_slider.setValue(2000)
#         band_layout.addWidget(self.target_max_slider)

#         self.target_max_value_label = QLabel(str(self.target_max_slider.value()))
#         self.target_max_value_label.setFixedWidth(60)
#         self.target_max_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#         band_layout.addWidget(self.target_max_value_label)

#         band_hint = QLabel("Bars and graph use this band; status text")
#         band_hint.setStyleSheet("color: gray;")
#         band_layout.addWidget(band_hint)

#         main_layout.addWidget(band_group)

#         # Slider updates → numeric labels + threshold lines on bars/plot
#         self.target_min_slider.valueChanged.connect(self._update_band_labels)
#         self.target_max_slider.valueChanged.connect(self._update_band_labels)

#         # ===== CENTER: Four finger bars =====
#         bars_row = QHBoxLayout()
#         main_layout.addLayout(bars_row)

#         self.bar_widgets: list[ThresholdProgressBar] = []
#         self.value_labels: list[QLabel] = []

#         for i in range(NUM_CHANNELS):
#             col = QVBoxLayout()

#             name_label = QLabel(CHANNEL_NAMES[i])
#             name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#             name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
#             col.addWidget(name_label)

#             bar = ThresholdProgressBar()
#             bar.setOrientation(Qt.Orientation.Vertical)
#             bar.setRange(0, 4095)
#             bar.setValue(0)
#             bar.setFixedWidth(60)
#             col.addWidget(bar, stretch=1, alignment=Qt.AlignmentFlag.AlignHCenter)
#             self.bar_widgets.append(bar)

#             val_label = QLabel("Force: 0")
#             val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#             col.addWidget(val_label)
#             self.value_labels.append(val_label)

#             bars_row.addLayout(col)

#         # ===== PLOT: 4 curves over time + threshold lines =====
#         self.plot_widget = pg.PlotWidget()
#         self.plot_widget.setLabel("left", "Force", units="ADC")
#         self.plot_widget.setLabel("bottom", "Time", units="s")
#         self.plot_widget.addLegend()
#         main_layout.addWidget(self.plot_widget, stretch=1)

#         # Threshold lines (horizontal at min/max ADC)
#         thresh_pen = pg.mkPen(
#             QColor(0, 150, 0, 160),
#             width=2,
#             style=Qt.PenStyle.DashLine,
#         )
#         self.min_line = pg.InfiniteLine(angle=0, movable=False, pen=thresh_pen)
#         self.max_line = pg.InfiniteLine(angle=0, movable=False, pen=thresh_pen)
#         self.plot_widget.addItem(self.min_line)
#         self.plot_widget.addItem(self.max_line)

#         colors = ["r", "g", "b", "y"]
#         self.curves = []
#         for c in range(NUM_CHANNELS):
#             curve = self.plot_widget.plot(
#                 [], [],
#                 pen=pg.mkPen(colors[c % len(colors)], width=2),
#                 name=f"Ch{c} ({CHANNEL_NAMES[c]})",
#             )
#             self.curves.append(curve)

#         # Initialize thresholds on bars and lines
#         self._update_band_labels()

#         # ===== BOTTOM: Reset & Save =====
#         bottom_row = QHBoxLayout()

#         self.reset_button = QPushButton("Reset session")
#         self.reset_button.clicked.connect(self.reset_session)
#         bottom_row.addWidget(self.reset_button)

#         self.save_button = QPushButton("Save CSV")
#         self.save_button.clicked.connect(self.save_csv)
#         bottom_row.addWidget(self.save_button)

#         main_layout.addLayout(bottom_row)

#         # ===== TIMER =====
#         self.timer = QTimer()
#         self.timer.setInterval(20)  # 20 ms -> ~50 Hz
#         self.timer.timeout.connect(self.poll_sensor)

#         # ==== SIM BACKEND / KEYBOARD INPUT HOOK (comment out for real hardware) ====
#         # When using SimBackend with keyboard input, make sure this window has
#         # focus so key presses reach keyPressEvent / keyReleaseEvent.
#         # For real Serial/WiFi/BLE backends, you can safely comment this out.
#         self.setFocus()
#         # ==== END SIM BACKEND HOOK ================================================

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
#             # NOTE: For SimBackend, port/baud/timeout are accepted but ignored.
#             self.backend = SerialBackend(port=port, baud=baud, timeout=0.01)
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
#             self.backend.stop()
#             self.backend = None

#         self.status_label.setText("Status: Disconnected")
#         self.connect_button.setEnabled(True)
#         self.disconnect_button.setEnabled(False)

#     # ---------- SESSION RESET ----------

#     def reset_session(self):
#         for c in range(NUM_CHANNELS):
#             self.values[c].clear()
#         self.times.clear()
#         self.start_time = time.time()

#         for curve in self.curves:
#             curve.setData([], [])

#         for i in range(NUM_CHANNELS):
#             self.bar_widgets[i].setValue(0)
#             self.value_labels[i].setText("Force: 0")

#         self.status_label.setText("Status: Ready")

#     # ---------- BAND LABEL / THRESHOLD UPDATE ----------

#     def _update_band_labels(self):
#         """Update numeric labels, bar thresholds, and graph threshold lines."""
#         tmin = self.target_min_slider.value()
#         tmax = self.target_max_slider.value()

#         self.target_min_value_label.setText(str(tmin))
#         self.target_max_value_label.setText(str(tmax))

#         # Bars
#         for bar in self.bar_widgets:
#             bar.set_thresholds(tmin, tmax)

#         # Plot threshold lines (if created)
#         if hasattr(self, "min_line"):
#             self.min_line.setValue(tmin)
#         if hasattr(self, "max_line"):
#             self.max_line.setValue(tmax)

#     # ---------- DATA / PLOTTING ----------

#     def poll_sensor(self):
#         if self.backend is None:
#             return

#         vals = self.backend.get_latest()  # expected [v0, v1, v2, v3]
#         if vals is None:
#             return

#         if isinstance(vals, (int, float)):
#             vals = [int(vals)] * NUM_CHANNELS
#         elif isinstance(vals, (list, tuple)):
#             vals = list(vals)
#         else:
#             return

#         if len(vals) < NUM_CHANNELS:
#             vals += [0] * (NUM_CHANNELS - len(vals))

#         now = time.time()
#         if self.start_time is None:
#             self.start_time = now
#         t = now - self.start_time

#         self.times.append(t)

#         tmin = self.target_min_slider.value()
#         tmax = self.target_max_slider.value()

#         for c in range(NUM_CHANNELS):
#             v = max(0, min(4095, int(vals[c])))
#             self.values[c].append(v)

#             # Update bar and label
#             self.bar_widgets[c].setValue(v)
#             self.value_labels[c].setText(f"Force: {v}")

#             # Color mapping (richer, like patient_game_app)
#             if v < tmin:
#                 zone = "low"
#                 if tmin > 0:
#                     frac_below = v / tmin  # 0.0 (far below) → 1.0 (just below)
#                 else:
#                     frac_below = 0.0

#                 if frac_below < 1 / 3:
#                     color = "orange"
#                 elif frac_below < 2 / 3:
#                     color = "orangeyellow"
#                 else:
#                     color = "yellow"

#             elif v > tmax:
#                 zone = "high"
#                 over_span = max(4095 - tmax, 1)
#                 frac_above = (v - tmax) / over_span  # 0.0 just over → 1.0 far over

#                 if frac_above < 0.5:
#                     color = "darkred"
#                 else:
#                     color = "red"

#             else:
#                 zone = "in_band"
#                 span = max(tmax - tmin, 1)
#                 frac_in = (v - tmin) / span  # 0.0 at min → 1.0 at max

#                 if frac_in < 1 / 3:
#                     color = "yellowgreen"
#                 elif frac_in < 2 / 3:
#                     color = "green"
#                 else:
#                     color = "darkgreen"

#             self._set_bar_color(self.bar_widgets[c], color)

#         # Target band feedback based on channel 0
#         ch0 = self.values[0][-1]
#         if tmin <= ch0 <= tmax:
#             self.status_label.setText("Status: ✅ – In target zone")
#         elif ch0 < tmin:
#             self.status_label.setText("Status: 👆 – squeeze a bit harder")
#         else:
#             self.status_label.setText("Status: 👇 – ease off slightly")

#         # Update plot
#         t_list = list(self.times)
#         for c in range(NUM_CHANNELS):
#             self.curves[c].setData(t_list, list(self.values[c]))

#     # ==== SIM BACKEND / KEYBOARD INPUT HOOK (comment out for real hardware) ====
#     # Generic key forwarding: sends raw characters to any backend that
#     # exposes a `handle_char(ch: str, is_press: bool)` method.
#     # For real Serial/WiFi/BLE backends, you can safely comment out this
#     # entire block and the rest of the GUI stays backend-agnostic.
#     def keyPressEvent(self, event):
#         if self.backend is not None and hasattr(self.backend, "handle_char"):
#             ch = event.text()
#             if ch:
#                 self.backend.handle_char(ch, True)
#         super().keyPressEvent(event)

#     def keyReleaseEvent(self, event):
#         if self.backend is not None and hasattr(self.backend, "handle_char"):
#             ch = event.text()
#             if ch:
#                 self.backend.handle_char(ch, False)
#         super().keyReleaseEvent(event)
#     # ==== END SIM BACKEND HOOK ================================================

#     # ---------- CSV SAVING ----------

#     def save_csv(self):
#         """
#         Save the current session's data:
#             time_s, ch0_adc, ch1_adc, ch2_adc, ch3_adc
#         """
#         if not self.times:
#             QMessageBox.information(self, "No data", "No samples to save yet.")
#             return

#         ts = datetime.now().strftime("%Y%m%d_%H%M%S")
#         default_name = f"patient_session_{ts}.csv"

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
#             return

#         try:
#             with open(path, "w", newline="") as f:
#                 writer = csv.writer(f)
#                 header = ["time_s"] + [f"ch{c}_adc" for c in range(NUM_CHANNELS)]
#                 writer.writerow(header)

#                 length = len(self.times)
#                 for i in range(length):
#                     row = [self.times[i]]
#                     for c in range(NUM_CHANNELS):
#                         row.append(self.values[c][i])
#                     writer.writerow(row)

#             QMessageBox.information(self, "Saved", f"Session saved to:\n{path}")
#         except Exception as e:
#             QMessageBox.critical(self, "Error", f"Failed to save CSV:\n{e}")

#     # ---------- BAR COLOR HELPER ----------

#     def _set_bar_color(self, bar: QProgressBar, color: str):
#         palette = {
#             "orange": "#FF9800",
#             "orangeyellow": "#FFC107",
#             "yellow": "#FFEB3B",
#             "yellowgreen": "#CDDC39",
#             "green": "#4CAF50",
#             "darkgreen": "#2E7D32",
#             "darkred": "#C62828",
#             "red": "#F44336",
#         }
#         chunk_color = palette.get(color, "#FF9800")

#         bar.setStyleSheet(
#             "QProgressBar {"
#             "  border: 1px solid #999;"
#             "  border-radius: 3px;"
#             "  background: #eee;"
#             "}"
#             f"QProgressBar::chunk {{ background-color: {chunk_color}; }}"
#         )


# def main():
#     app = QApplication(sys.argv)
#     win = PatientWindow()
#     win.show()
#     sys.exit(app.exec())


# if __name__ == "__main__":
#     main()


#########===================== PATIENT GUI V5 ==============================##########


## host/gui/patient_app.py

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
from PyQt6.QtGui import QFont, QPainter, QPen, QColor
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


class ThresholdProgressBar(QProgressBar):
    """Vertical progress bar with faint dashed lines for min/max thresholds."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._min_thresh: int | None = None
        self._max_thresh: int | None = None

    def set_thresholds(self, min_val: int, max_val: int):
        self._min_thresh = min_val
        self._max_thresh = max_val
        self.update()

    def paintEvent(self, event):
        # Draw normal progress bar first
        super().paintEvent(event)

        if self._min_thresh is None or self._max_thresh is None:
            return

        rect = self.contentsRect()
        if rect.height() <= 0:
            return

        minimum = self.minimum()
        maximum = self.maximum()
        span = maximum - minimum
        if span <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(0, 0, 0, 120))  # faint dark gray
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setWidth(1)
        painter.setPen(pen)

        def draw_for_value(v):
            # Clamp within bar range
            v_clamped = max(minimum, min(maximum, v))
            frac = (v_clamped - minimum) / span  # 0 at min, 1 at max
            # vertical bar: 0 at bottom, 1 at top
            y = rect.bottom() - frac * rect.height()
            painter.drawLine(rect.left() + 2, int(y), rect.right() - 2, int(y))

        draw_for_value(self._min_thresh)
        draw_for_value(self._max_thresh)

        painter.end()


class PatientWindow(QWidget):
    def __init__(self, backend: SerialBackend | None = None, owns_backend: bool = True):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Patient (Multi-Finger)")
        self.resize(1100, 700)

        # Shared-backend support
        self.backend: SerialBackend | None = backend
        self.owns_backend = owns_backend

        # values[c] is a deque of samples for channel c
        self.values = [deque(maxlen=2000) for _ in range(NUM_CHANNELS)]
        self.times = deque(maxlen=2000)   # shared time axis
        self.start_time = None

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
        self.status_label = QLabel("Status: Not Connected")
        self.status_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(self.status_label)

        # ===== TARGET BAND (global band; status based on Ch0) =====
        band_group = QGroupBox("Target Zone (applies to Channel 0 for feedback)")
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

        band_hint = QLabel("Bars and graph use this band; status monitored")
        band_hint.setStyleSheet("color: gray;")
        band_layout.addWidget(band_hint)

        main_layout.addWidget(band_group)

        # Slider updates → numeric labels + threshold lines on bars/plot
        self.target_min_slider.valueChanged.connect(self._update_band_labels)
        self.target_max_slider.valueChanged.connect(self._update_band_labels)

        # ===== CENTER: Four finger bars =====
        bars_row = QHBoxLayout()
        main_layout.addLayout(bars_row)

        self.bar_widgets: list[ThresholdProgressBar] = []
        self.value_labels: list[QLabel] = []

        for i in range(NUM_CHANNELS):
            col = QVBoxLayout()

            name_label = QLabel(CHANNEL_NAMES[i])
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            col.addWidget(name_label)

            bar = ThresholdProgressBar()
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

        # ===== PLOT: 4 curves over time + threshold lines =====
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel("left", "Force", units="ADC")
        self.plot_widget.setLabel("bottom", "Time", units="s")
        self.plot_widget.addLegend()
        main_layout.addWidget(self.plot_widget, stretch=1)

        # Threshold lines (horizontal at min/max ADC)
        thresh_pen = pg.mkPen(
            QColor(0, 150, 0, 160),
            width=2,
            style=Qt.PenStyle.DashLine,
        )
        self.min_line = pg.InfiniteLine(angle=0, movable=False, pen=thresh_pen)
        self.max_line = pg.InfiniteLine(angle=0, movable=False, pen=thresh_pen)
        self.plot_widget.addItem(self.min_line)
        self.plot_widget.addItem(self.max_line)

        colors = ["r", "g", "b", "y"]
        self.curves = []
        for c in range(NUM_CHANNELS):
            curve = self.plot_widget.plot(
                [], [],
                pen=pg.mkPen(colors[c % len(colors)], width=2),
                name=f"Ch{c} ({CHANNEL_NAMES[c]})",
            )
            self.curves.append(curve)

        # Initialize thresholds on bars and lines
        self._update_band_labels()

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
        self.setFocus()
        # ==== END SIM BACKEND HOOK ================================================

    # ---------- CONNECTION LOGIC ----------

    def handle_connect(self):
        # If using a shared backend, just start our timer/session logic.
        if self.backend is not None and not self.owns_backend:
            self.status_label.setText("Status: Connected")
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(False)
            self.reset_session()
            self.start_time = time.time()
            self.timer.start()
            return

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
            self.owns_backend = True
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

        # Only stop backend if we created it
        if self.backend is not None and self.owns_backend:
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

    # ---------- BAND LABEL / THRESHOLD UPDATE ----------

    def _update_band_labels(self):
        """Update numeric labels, bar thresholds, and graph threshold lines."""
        tmin = self.target_min_slider.value()
        tmax = self.target_max_slider.value()

        self.target_min_value_label.setText(str(tmin))
        self.target_max_value_label.setText(str(tmax))

        # Bars
        for bar in self.bar_widgets:
            bar.set_thresholds(tmin, tmax)

        # Plot threshold lines
        if hasattr(self, "min_line"):
            self.min_line.setValue(tmin)
        if hasattr(self, "max_line"):
            self.max_line.setValue(tmax)

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

        for c in range(NUM_CHANNELS):
            v = max(0, min(4095, int(vals[c])))
            self.values[c].append(v)

            # Update bar and label
            self.bar_widgets[c].setValue(v)
            self.value_labels[c].setText(f"Force: {v}")

            # Color mapping: below band → orange→orangeyellow→yellow,
            # in band → yellowgreen→green→darkgreen, above → darkred→red.
            if v < tmin:
                if tmin > 0:
                    frac_below = v / tmin  # 0.0 (far below) → 1.0 (just below)
                else:
                    frac_below = 0.0

                if frac_below < 1 / 3:
                    color = "orange"
                elif frac_below < 2 / 3:
                    color = "orangeyellow"
                else:
                    color = "yellow"

            elif v > tmax:
                over_span = max(4095 - tmax, 1)
                frac_above = (v - tmax) / over_span  # 0.0 just over → 1.0 far over

                if frac_above < 0.5:
                    color = "darkred"
                else:
                    color = "red"

            else:
                span = max(tmax - tmin, 1)
                frac_in = (v - tmin) / span  # 0.0 at min → 1.0 at max

                if frac_in < 1 / 3:
                    color = "yellowgreen"
                elif frac_in < 2 / 3:
                    color = "green"
                else:
                    color = "darkgreen"

            self._set_bar_color(self.bar_widgets[c], color)

        # Target band feedback based on channel 0
        ch0 = self.values[0][-1]
        if tmin <= ch0 <= tmax:
            self.status_label.setText("Status: ✅ – In target zone")
        elif ch0 < tmin:
            self.status_label.setText("Status: 👆 – Squeeze a bit harder")
        else:
            self.status_label.setText("Status: 👇 – Ease off slightly")

        # Update plot
        t_list = list(self.times)
        for c in range(NUM_CHANNELS):
            self.curves[c].setData(t_list, list(self.values[c]))

    # ==== SIM BACKEND / KEYBOARD INPUT HOOK (comment out for real hardware) ====
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

    # ---------- BAR COLOR HELPER ----------

    def _set_bar_color(self, bar: QProgressBar, color: str):
        palette = {
            "orange": "#FF9800",
            "orangeyellow": "#FFC107",
            "yellow": "#FFEB3B",
            "yellowgreen": "#CDDC39",
            "green": "#4CAF50",
            "darkgreen": "#2E7D32",
            "darkred": "#C62828",
            "red": "#F44336",
        }
        chunk_color = palette.get(color, "#FF9800")

        bar.setStyleSheet(
            "QProgressBar {"
            "  border: 1px solid #999;"
            "  border-radius: 3px;"
            "  background: #eee;"
            "}"
            f"QProgressBar::chunk {{ background-color: {chunk_color}; }}"
        )


def main():
    app = QApplication(sys.argv)
    win = PatientWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
