
# host/gui/clinician_app.py

# import os
# import sys
# import csv
# import json
# from datetime import datetime

# from PyQt6.QtCore import Qt
# from PyQt6.QtWidgets import (
#     QApplication,
#     QWidget,
#     QVBoxLayout,
#     QHBoxLayout,
#     QLabel,
#     QPushButton,
#     QLineEdit,
#     QFileDialog,
#     QMessageBox,
#     QGroupBox,
#     QSlider,
# )
# import pyqtgraph as pg

# # ------------ PATH SETUP ------------
# # This file is .../cardinal-grip/host/gui/clinician_app.py
# GUI_DIR = os.path.dirname(__file__)          # .../host/gui
# HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
# PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

# if PROJECT_ROOT not in sys.path:
#     sys.path.append(PROJECT_ROOT)
# # ------------------------------------

# NUM_CHANNELS = 4
# CHANNEL_NAMES = ["Index", "Middle", "Ring", "Pinky"]



# ------------------------------------
# Single FSR PROTOTYPE GUI BELOW
# # ------------ PATH SETUP ------------
# # This file is .../cardinal-grip/host/gui/clinician_app.py
# GUI_DIR = os.path.dirname(__file__)          # .../host/gui
# HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
# PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

# if PROJECT_ROOT not in sys.path:
#     sys.path.append(PROJECT_ROOT)
# # ------------------------------------


# class ClinicianWindow(QWidget):
#     def __init__(self):
#         super().__init__()

#         self.setWindowTitle("Cardinal Grip – Clinician")
#         self.resize(1000, 650)

#         # Session data
#         self.times = []
#         self.values = []
#         self.session_path = None

#         # ---------- UI LAYOUT ----------

#         main_layout = QVBoxLayout()
#         self.setLayout(main_layout)

#         # Top row: load button + filename
#         top_row = QHBoxLayout()

#         self.load_button = QPushButton("Load Session CSV")
#         self.load_button.clicked.connect(self.load_csv)
#         top_row.addWidget(self.load_button)

#         self.filename_label = QLabel("No file loaded")
#         self.filename_label.setStyleSheet("color: gray;")
#         top_row.addWidget(self.filename_label, stretch=1)

#         main_layout.addLayout(top_row)

#         # Middle: plot + right-side stats + target band controls
#         middle_row = QHBoxLayout()
#         main_layout.addLayout(middle_row, stretch=1)

#         # Plot
#         self.plot_widget = pg.PlotWidget()
#         self.plot_widget.setLabel("left", "Force", units="ADC")
#         self.plot_widget.setLabel("bottom", "Time", units="s")
#         self.curve = self.plot_widget.plot([], [])
#         middle_row.addWidget(self.plot_widget, stretch=3)

#         # Right panel
#         right_panel = QVBoxLayout()
#         middle_row.addLayout(right_panel, stretch=2)

#         # Session info group
#         info_group = QGroupBox("Session Info")
#         info_layout = QVBoxLayout()
#         info_group.setLayout(info_layout)

#         self.samples_label = QLabel("Samples: —")
#         self.duration_label = QLabel("Duration: —")
#         self.min_label = QLabel("Min force: —")
#         self.max_label = QLabel("Max force: —")
#         self.mean_label = QLabel("Mean force: —")

#         info_layout.addWidget(self.samples_label)
#         info_layout.addWidget(self.duration_label)
#         info_layout.addWidget(self.min_label)
#         info_layout.addWidget(self.max_label)
#         info_layout.addWidget(self.mean_label)

#         right_panel.addWidget(info_group)

#         # Target band group
#         band_group = QGroupBox("Target Band Analysis")
#         band_layout = QVBoxLayout()
#         band_group.setLayout(band_layout)

#         band_row_top = QHBoxLayout()
#         band_row_bottom = QHBoxLayout()

#         band_row_top.addWidget(QLabel("Min (ADC):"))
#         self.target_min_edit = QLineEdit("1200")
#         band_row_top.addWidget(self.target_min_edit)

#         band_row_bottom.addWidget(QLabel("Max (ADC):"))
#         self.target_max_edit = QLineEdit("2000")
#         band_row_bottom.addWidget(self.target_max_edit)

#         band_layout.addLayout(band_row_top)
#         band_layout.addLayout(band_row_bottom)

#         self.band_slider = QSlider(Qt.Orientation.Horizontal)
#         self.band_slider.setRange(0, 4095)
#         self.band_slider.setValue(1600)
#         self.band_slider.valueChanged.connect(self._band_slider_hint)
#         band_layout.addWidget(QLabel("Slider (for quick rough threshold):"))
#         band_layout.addWidget(self.band_slider)

#         self.band_result_label = QLabel("In-target %: —")
#         band_layout.addWidget(self.band_result_label)

#         self.recalc_button = QPushButton("Recalculate with target band")
#         self.recalc_button.clicked.connect(self.update_band_stats)
#         band_layout.addWidget(self.recalc_button)

#         right_panel.addWidget(band_group)

#         # Bottom hint
#         hint = QLabel(
#             "Tip: Patient GUI saves files under data/logs/. "
#             "Use this window to review progress over sessions."
#         )
#         hint.setStyleSheet("color: gray;")
#         main_layout.addWidget(hint)

#     # ---------- FILE LOADING ----------

#     def load_csv(self):
#         """Open a CSV file and load time_s, force_adc columns."""
#         data_dir = os.path.join(PROJECT_ROOT, "data", "logs")
#         os.makedirs(data_dir, exist_ok=True)

#         path, _ = QFileDialog.getOpenFileName(
#             self,
#             "Open Session CSV",
#             data_dir,
#             "CSV Files (*.csv)",
#         )
#         if not path:
#             return

#         times = []
#         values = []

#         try:
#             with open(path, "r", newline="") as f:
#                 reader = csv.reader(f)
#                 header = next(reader, None)
#                 for row in reader:
#                     if len(row) < 2:
#                         continue
#                     try:
#                         t = float(row[0])
#                         v = float(row[1])
#                         times.append(t)
#                         values.append(v)
#                     except ValueError:
#                         continue
#         except Exception as e:
#             QMessageBox.critical(self, "Error", f"Failed to read CSV:\n{e}")
#             return

#         if not times:
#             QMessageBox.warning(self, "No data", "No valid samples in this file.")
#             return

#         self.times = times
#         self.values = values
#         self.session_path = path

#         self.filename_label.setText(os.path.basename(path))
#         self.filename_label.setStyleSheet("color: black;")

#         self.update_plot()
#         self.update_stats()
#         self.update_band_stats()

#     # ---------- STATS / PLOT ----------

#     def update_plot(self):
#         if not self.times or not self.values:
#             self.curve.setData([], [])
#             return

#         self.curve.setData(self.times, self.values)

#     def update_stats(self):
#         if not self.times or not self.values:
#             self.samples_label.setText("Samples: —")
#             self.duration_label.setText("Duration: —")
#             self.min_label.setText("Min force: —")
#             self.max_label.setText("Max force: —")
#             self.mean_label.setText("Mean force: —")
#             return

#         n = len(self.values)
#         duration = self.times[-1] - self.times[0]
#         vmin = min(self.values)
#         vmax = max(self.values)
#         vmean = sum(self.values) / n

#         self.samples_label.setText(f"Samples: {n}")
#         self.duration_label.setText(f"Duration: {duration:.2f} s")
#         self.min_label.setText(f"Min force: {vmin:.1f}")
#         self.max_label.setText(f"Max force: {vmax:.1f}")
#         self.mean_label.setText(f"Mean force: {vmean:.1f}")

#     def update_band_stats(self):
#         """Compute % of samples in the chosen target ADC range."""
#         if not self.values:
#             self.band_result_label.setText("In-target %: —")
#             return

#         try:
#             tmin = float(self.target_min_edit.text().strip())
#             tmax = float(self.target_max_edit.text().strip())
#         except ValueError:
#             QMessageBox.warning(self, "Error", "Invalid target min/max.")
#             return

#         if tmax < tmin:
#             QMessageBox.warning(self, "Error", "Max must be >= min.")
#             return

#         total = len(self.values)
#         in_band = sum(1 for v in self.values if tmin <= v <= tmax)

#         pct = 100.0 * in_band / total
#         self.band_result_label.setText(f"In-target %: {pct:.1f}%")

#     def _band_slider_hint(self, value: int):
#         """
#         Small helper: when clinician drags the slider, we show a quick hint
#         of that value in the target_max box (non-destructive suggestion).
#         """
#         if not self.target_max_edit.hasFocus():
#             self.target_max_edit.setText(str(value))


# def main():
#     app = QApplication(sys.argv)
#     win = ClinicianWindow()
#     win.show()
#     sys.exit(app.exec())


# if __name__ == "__main__":
#     main()

#========================  Four FSRs =========================================

# host/gui/clinician_app.py
# ------------ PATH SETUP ------------
# This file is .../cardinal-grip/host/gui/clinician_app.py
# GUI_DIR = os.path.dirname(__file__)          # .../host/gui
# HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
# PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

# if PROJECT_ROOT not in sys.path:
#     sys.path.append(PROJECT_ROOT)
# # ------------------------------------


# class ClinicianWindow(QWidget):
#     def __init__(self):
#         super().__init__()

#         self.setWindowTitle("Cardinal Grip – Clinician")
#         self.resize(1000, 650)

#         # Session data
#         self.times = []              # list[float]
#         self.values = []             # list[list[float]] – values[c][i]
#         self.num_channels = 0
#         self.selected_channel = 0
#         self.session_path = None

#         # For plotting
#         self.curves = []

#         # ---------- UI LAYOUT ----------

#         main_layout = QVBoxLayout()
#         self.setLayout(main_layout)

#         # Top row: load button + filename
#         top_row = QHBoxLayout()

#         self.load_button = QPushButton("Load Session CSV")
#         self.load_button.clicked.connect(self.load_csv)
#         top_row.addWidget(self.load_button)

#         self.filename_label = QLabel("No file loaded")
#         self.filename_label.setStyleSheet("color: gray;")
#         top_row.addWidget(self.filename_label, stretch=1)

#         main_layout.addLayout(top_row)

#         # Middle: plot + right-side stats + target band controls
#         middle_row = QHBoxLayout()
#         main_layout.addLayout(middle_row, stretch=1)

#         # Plot
#         self.plot_widget = pg.PlotWidget()
#         self.plot_widget.setLabel("left", "Force", units="ADC")
#         self.plot_widget.setLabel("bottom", "Time", units="s")
#         self.plot_widget.addLegend()
#         middle_row.addWidget(self.plot_widget, stretch=3)

#         # Right panel
#         right_panel = QVBoxLayout()
#         middle_row.addLayout(right_panel, stretch=2)

#         # Session info group
#         info_group = QGroupBox("Session Info")
#         info_layout = QVBoxLayout()
#         info_group.setLayout(info_layout)

#         self.samples_label = QLabel("Samples: —")
#         self.duration_label = QLabel("Duration: —")
#         self.min_label = QLabel("Min force: —")
#         self.max_label = QLabel("Max force: —")
#         self.mean_label = QLabel("Mean force: —")

#         # Channel selector for stats
#         chan_row = QHBoxLayout()
#         chan_row.addWidget(QLabel("Channel for stats:"))
#         self.channel_select = QComboBox()
#         self.channel_select.currentIndexChanged.connect(self._channel_changed)
#         self.channel_select.setEnabled(False)
#         chan_row.addWidget(self.channel_select)

#         info_layout.addLayout(chan_row)
#         info_layout.addWidget(self.samples_label)
#         info_layout.addWidget(self.duration_label)
#         info_layout.addWidget(self.min_label)
#         info_layout.addWidget(self.max_label)
#         info_layout.addWidget(self.mean_label)

#         right_panel.addWidget(info_group)

#         # Target band group
#         band_group = QGroupBox("Target Band Analysis (selected channel)")
#         band_layout = QVBoxLayout()
#         band_group.setLayout(band_layout)

#         band_row_top = QHBoxLayout()
#         band_row_bottom = QHBoxLayout()

#         band_row_top.addWidget(QLabel("Min (ADC):"))
#         self.target_min_edit = QLineEdit("1200")
#         band_row_top.addWidget(self.target_min_edit)

#         band_row_bottom.addWidget(QLabel("Max (ADC):"))
#         self.target_max_edit = QLineEdit("2000")
#         band_row_bottom.addWidget(self.target_max_edit)

#         band_layout.addLayout(band_row_top)
#         band_layout.addLayout(band_row_bottom)

#         self.band_slider = QSlider(Qt.Orientation.Horizontal)
#         self.band_slider.setRange(0, 4095)
#         self.band_slider.setValue(1600)
#         self.band_slider.valueChanged.connect(self._band_slider_hint)
#         band_layout.addWidget(QLabel("Slider (quick threshold suggestion):"))
#         band_layout.addWidget(self.band_slider)

#         self.band_result_label = QLabel("In-target %: —")
#         band_layout.addWidget(self.band_result_label)

#         self.recalc_button = QPushButton("Recalculate with target band")
#         self.recalc_button.clicked.connect(self.update_band_stats)
#         band_layout.addWidget(self.recalc_button)

#         right_panel.addWidget(band_group)

#         # Bottom hint
#         hint = QLabel(
#             "Tip: Patient GUI saves files under data/logs/. "
#             "Use this window to review progress over sessions."
#         )
#         hint.setStyleSheet("color: gray;")
#         main_layout.addWidget(hint)

#     # ---------- FILE LOADING ----------

#     def load_csv(self):
#         """
#         Open a CSV file and load:
#         - new format: time_s, ch0_adc, ch1_adc, ch2_adc, ch3_adc, ...
#         - OR legacy:  time_s, force_adc
#         """
#         data_dir = os.path.join(PROJECT_ROOT, "data", "logs")
#         os.makedirs(data_dir, exist_ok=True)

#         path, _ = QFileDialog.getOpenFileName(
#             self,
#             "Open Session CSV",
#             data_dir,
#             "CSV Files (*.csv)",
#         )
#         if not path:
#             return

#         try:
#             with open(path, "r", newline="") as f:
#                 reader = csv.reader(f)
#                 header = next(reader, None)

#                 if header is None:
#                     raise ValueError("CSV has no header row.")

#                 # Detect multi-channel vs single-channel
#                 # Our new patient GUI header: ["time_s", "ch0_adc", "ch1_adc", ...]
#                 if "ch0_adc" in header:
#                     time_idx = header.index("time_s") if "time_s" in header else 0
#                     channel_indices = [
#                         i for i, h in enumerate(header) if h.startswith("ch")
#                     ]
#                     num_channels = len(channel_indices)

#                     times = []
#                     values = [[] for _ in range(num_channels)]

#                     for row in reader:
#                         if len(row) <= max(channel_indices):
#                             continue
#                         try:
#                             t = float(row[time_idx])
#                         except ValueError:
#                             continue

#                         times.append(t)
#                         for j, col_idx in enumerate(channel_indices):
#                             try:
#                                 v = float(row[col_idx])
#                             except ValueError:
#                                 v = float("nan")
#                             values[j].append(v)

#                 else:
#                     # Legacy: assume time, force
#                     times = []
#                     values = [[]]  # single channel
#                     num_channels = 1

#                     for row in reader:
#                         if len(row) < 2:
#                             continue
#                         try:
#                             t = float(row[0])
#                             v = float(row[1])
#                         except ValueError:
#                             continue
#                         times.append(t)
#                         values[0].append(v)

#         except Exception as e:
#             QMessageBox.critical(self, "Error", f"Failed to read CSV:\n{e}")
#             return

#         if not times:
#             QMessageBox.warning(self, "No data", "No valid samples in this file.")
#             return

#         self.times = times
#         self.values = values
#         self.num_channels = num_channels
#         self.selected_channel = 0
#         self.session_path = path

#         # Update filename label
#         self.filename_label.setText(os.path.basename(path))
#         self.filename_label.setStyleSheet("color: black;")

#         # Rebuild curves for the plot
#         self._setup_curves()

#         # Configure channel selector
#         self.channel_select.clear()
#         for c in range(self.num_channels):
#             self.channel_select.addItem(f"Ch{c}")
#         self.channel_select.setEnabled(self.num_channels > 1)
#         self.channel_select.setCurrentIndex(0)

#         # Update views
#         self.update_plot()
#         self.update_stats()
#         self.update_band_stats()

#     # ---------- PLOTTING ----------

#     def _setup_curves(self):
#         """Create curves for each channel in the plot."""
#         self.plot_widget.clear()
#         self.plot_widget.setLabel("left", "Force", units="ADC")
#         self.plot_widget.setLabel("bottom", "Time", units="s")
#         self.plot_widget.addLegend()

#         self.curves = []
#         colors = ["r", "g", "b", "y", "m", "c", "w"]
#         for c in range(self.num_channels):
#             curve = self.plot_widget.plot(
#                 [], [],
#                 pen=pg.mkPen(colors[c % len(colors)], width=2),
#                 name=f"Ch{c}",
#             )
#             self.curves.append(curve)

#     def update_plot(self):
#         if not self.times or not self.values:
#             for curve in self.curves:
#                 curve.setData([], [])
#             return

#         t = self.times
#         for c, curve in enumerate(self.curves):
#             if c < len(self.values):
#                 curve.setData(t, self.values[c])
#             else:
#                 curve.setData([], [])

#     # ---------- STATS ----------

#     def _get_channel_values(self):
#         if (
#             self.num_channels == 0
#             or self.selected_channel < 0
#             or self.selected_channel >= self.num_channels
#         ):
#             return []
#         return self.values[self.selected_channel]

#     def update_stats(self):
#         vchan = self._get_channel_values()
#         if not self.times or not vchan:
#             self.samples_label.setText("Samples: —")
#             self.duration_label.setText("Duration: —")
#             self.min_label.setText("Min force: —")
#             self.max_label.setText("Max force: —")
#             self.mean_label.setText("Mean force: —")
#             return

#         n = len(vchan)
#         duration = self.times[-1] - self.times[0]
#         vmin = min(vchan)
#         vmax = max(vchan)
#         vmean = sum(v for v in vchan if not self._is_nan(v)) / max(
#             1, sum(0 if self._is_nan(v) else 1 for v in vchan)
#         )

#         self.samples_label.setText(f"Samples: {n}")
#         self.duration_label.setText(f"Duration: {duration:.2f} s")
#         self.min_label.setText(f"Min force (Ch{self.selected_channel}): {vmin:.1f}")
#         self.max_label.setText(f"Max force (Ch{self.selected_channel}): {vmax:.1f}")
#         self.mean_label.setText(
#             f"Mean force (Ch{self.selected_channel}): {vmean:.1f}"
#         )

#     # ---------- BAND STATS ----------

#     def update_band_stats(self):
#         """Compute % of samples in the chosen target ADC range on selected channel."""
#         vchan = self._get_channel_values()
#         if not vchan:
#             self.band_result_label.setText("In-target %: —")
#             return

#         try:
#             tmin = float(self.target_min_edit.text().strip())
#             tmax = float(self.target_max_edit.text().strip())
#         except ValueError:
#             QMessageBox.warning(self, "Error", "Invalid target min/max.")
#             return

#         if tmax < tmin:
#             QMessageBox.warning(self, "Error", "Max must be >= min.")
#             return

#         vals = [v for v in vchan if not self._is_nan(v)]
#         if not vals:
#             self.band_result_label.setText("In-target %: —")
#             return

#         total = len(vals)
#         in_band = sum(1 for v in vals if tmin <= v <= tmax)

#         pct = 100.0 * in_band / total
#         self.band_result_label.setText(
#             f"In-target % (Ch{self.selected_channel}): {pct:.1f}%"
#         )

#     def _band_slider_hint(self, value: int):
#         """
#         When clinician drags the slider, show a quick suggestion
#         in the target_max box (non-destructive).
#         """
#         if not self.target_max_edit.hasFocus():
#             self.target_max_edit.setText(str(value))

#     def _channel_changed(self, index: int):
#         self.selected_channel = index
#         self.update_stats()
#         self.update_band_stats()

#     @staticmethod
#     def _is_nan(x):
#         return x != x  # NaN is not equal to itself


# def main():
#     app = QApplication(sys.argv)
#     win = ClinicianWindow()
#     win.show()
#     sys.exit(app.exec())


# if __name__ == "__main__":
#     main()


#########===================== Clinician GUI V2 ==============================##########

# class ClinicianWindow(QWidget):
#     def __init__(self):
#         super().__init__()

#         self.setWindowTitle("Cardinal Grip – Clinician")
#         self.resize(1100, 700)

#         # Session data (for currently loaded CSV)
#         self.times = []
#         self.values = []
#         self.session_path = None

#         # Patient aggregated stats (from patient_stats.json)
#         self.patient_stats_path = os.path.join(PROJECT_ROOT, "data", "patient_stats.json")
#         self.reps_per_channel = []
#         self.sessions_completed = 0
#         self.combo_reps = 0
#         self.last_updated = None

#         # ---------- UI LAYOUT ----------

#         main_layout = QVBoxLayout()
#         self.setLayout(main_layout)

#         # Top row: load button + filename
#         top_row = QHBoxLayout()

#         self.load_button = QPushButton("Load Session CSV")
#         self.load_button.clicked.connect(self.load_csv)
#         top_row.addWidget(self.load_button)

#         self.filename_label = QLabel("No file loaded")
#         self.filename_label.setStyleSheet("color: gray;")
#         top_row.addWidget(self.filename_label, stretch=1)

#         main_layout.addLayout(top_row)

#         # Middle: plot + right-side panels (session stats + target band + patient history)
#         middle_row = QHBoxLayout()
#         main_layout.addLayout(middle_row, stretch=1)

#         # -------- LEFT: Plot --------
#         self.plot_widget = pg.PlotWidget()
#         self.plot_widget.setLabel("left", "Force", units="ADC")
#         self.plot_widget.setLabel("bottom", "Time", units="s")
#         self.curve = self.plot_widget.plot([], [])
#         middle_row.addWidget(self.plot_widget, stretch=3)

#         # -------- RIGHT: Panels --------
#         right_panel = QVBoxLayout()
#         middle_row.addLayout(right_panel, stretch=2)

#         # Session info group
#         info_group = QGroupBox("Session Info (Current CSV)")
#         info_layout = QVBoxLayout()
#         info_group.setLayout(info_layout)

#         self.samples_label = QLabel("Samples: —")
#         self.duration_label = QLabel("Duration: —")
#         self.min_label = QLabel("Min force: —")
#         self.max_label = QLabel("Max force: —")
#         self.mean_label = QLabel("Mean force: —")

#         info_layout.addWidget(self.samples_label)
#         info_layout.addWidget(self.duration_label)
#         info_layout.addWidget(self.min_label)
#         info_layout.addWidget(self.max_label)
#         info_layout.addWidget(self.mean_label)

#         right_panel.addWidget(info_group)

#         # Target band group (per-session)
#         band_group = QGroupBox("Target Band Analysis")
#         band_layout = QVBoxLayout()
#         band_group.setLayout(band_layout)

#         band_row_top = QHBoxLayout()
#         band_row_bottom = QHBoxLayout()

#         band_row_top.addWidget(QLabel("Min (ADC):"))
#         self.target_min_edit = QLineEdit("1200")
#         band_row_top.addWidget(self.target_min_edit)

#         band_row_bottom.addWidget(QLabel("Max (ADC):"))
#         self.target_max_edit = QLineEdit("2000")
#         band_row_bottom.addWidget(self.target_max_edit)

#         band_layout.addLayout(band_row_top)
#         band_layout.addLayout(band_row_bottom)

#         self.band_slider = QSlider(Qt.Orientation.Horizontal)
#         self.band_slider.setRange(0, 4095)
#         self.band_slider.setValue(1600)
#         self.band_slider.valueChanged.connect(self._band_slider_hint)
#         band_layout.addWidget(QLabel("Slider (quick rough threshold):"))
#         band_layout.addWidget(self.band_slider)

#         self.band_result_label = QLabel("In-target %: —")
#         band_layout.addWidget(self.band_result_label)

#         self.recalc_button = QPushButton("Recalculate with target band")
#         self.recalc_button.clicked.connect(self.update_band_stats)
#         band_layout.addWidget(self.recalc_button)

#         right_panel.addWidget(band_group)

#         # Patient history group (aggregated JSON stats)
#         history_group = QGroupBox("Patient History (Aggregated Game Stats)")
#         history_layout = QVBoxLayout()
#         history_group.setLayout(history_layout)

#         self.history_status_label = QLabel("patient_stats.json: not loaded yet")
#         self.history_status_label.setStyleSheet("color: gray;")
#         history_layout.addWidget(self.history_status_label)

#         self.reps_label = QLabel("Per-finger reps: —")
#         history_layout.addWidget(self.reps_label)

#         self.total_reps_label = QLabel("Total reps across fingers: —")
#         history_layout.addWidget(self.total_reps_label)

#         self.combo_reps_label = QLabel("All-fingers combo reps: —")
#         history_layout.addWidget(self.combo_reps_label)

#         self.sessions_completed_label = QLabel("Game sessions completed: —")
#         history_layout.addWidget(self.sessions_completed_label)

#         self.last_updated_label = QLabel("Last updated: —")
#         history_layout.addWidget(self.last_updated_label)

#         self.refresh_history_button = QPushButton("Refresh Patient History")
#         self.refresh_history_button.clicked.connect(self.load_patient_stats)
#         history_layout.addWidget(self.refresh_history_button)

#         right_panel.addWidget(history_group)

#         # Bottom hint
#         hint = QLabel(
#             "Tip: Patient GUI saves per-session CSV files under data/logs/.\n"
#             "      Game mode also maintains a patient_stats.json summary in data/."
#         )
#         hint.setStyleSheet("color: gray;")
#         main_layout.addWidget(hint)

#         # Load patient history once at startup
#         self.load_patient_stats()

#     # ---------- FILE LOADING (CSV) ----------

#     def load_csv(self):
#         """Open a CSV file and load time_s, force_adc columns."""
#         data_dir = os.path.join(PROJECT_ROOT, "data", "logs")
#         os.makedirs(data_dir, exist_ok=True)

#         path, _ = QFileDialog.getOpenFileName(
#             self,
#             "Open Session CSV",
#             data_dir,
#             "CSV Files (*.csv)",
#         )
#         if not path:
#             return

#         times = []
#         values = []

#         try:
#             with open(path, "r", newline="") as f:
#                 reader = csv.reader(f)
#                 header = next(reader, None)
#                 for row in reader:
#                     if len(row) < 2:
#                         continue
#                     try:
#                         t = float(row[0])
#                         v = float(row[1])
#                         times.append(t)
#                         values.append(v)
#                     except ValueError:
#                         continue
#         except Exception as e:
#             QMessageBox.critical(self, "Error", f"Failed to read CSV:\n{e}")
#             return

#         if not times:
#             QMessageBox.warning(self, "No data", "No valid samples in this file.")
#             return

#         self.times = times
#         self.values = values
#         self.session_path = path

#         self.filename_label.setText(os.path.basename(path))
#         self.filename_label.setStyleSheet("color: black;")

#         self.update_plot()
#         self.update_stats()
#         self.update_band_stats()

#     # ---------- CSV STATS / PLOT ----------

#     def update_plot(self):
#         if not self.times or not self.values:
#             self.curve.setData([], [])
#             return

#         self.curve.setData(self.times, self.values)

#     def update_stats(self):
#         if not self.times or not self.values:
#             self.samples_label.setText("Samples: —")
#             self.duration_label.setText("Duration: —")
#             self.min_label.setText("Min force: —")
#             self.max_label.setText("Max force: —")
#             self.mean_label.setText("Mean force: —")
#             return

#         n = len(self.values)
#         duration = self.times[-1] - self.times[0]
#         vmin = min(self.values)
#         vmax = max(self.values)
#         vmean = sum(self.values) / n

#         self.samples_label.setText(f"Samples: {n}")
#         self.duration_label.setText(f"Duration: {duration:.2f} s")
#         self.min_label.setText(f"Min force: {vmin:.1f}")
#         self.max_label.setText(f"Max force: {vmax:.1f}")
#         self.mean_label.setText(f"Mean force: {vmean:.1f}")

#     def update_band_stats(self):
#         """Compute % of samples in the chosen target ADC range."""
#         if not self.values:
#             self.band_result_label.setText("In-target %: —")
#             return

#         try:
#             tmin = float(self.target_min_edit.text().strip())
#             tmax = float(self.target_max_edit.text().strip())
#         except ValueError:
#             QMessageBox.warning(self, "Error", "Invalid target min/max.")
#             return

#         if tmax < tmin:
#             QMessageBox.warning(self, "Error", "Max must be >= min.")
#             return

#         total = len(self.values)
#         in_band = sum(1 for v in self.values if tmin <= v <= tmax)

#         pct = 100.0 * in_band / total
#         self.band_result_label.setText(f"In-target %: {pct:.1f}%")

#     def _band_slider_hint(self, value: int):
#         """
#         When clinician drags the slider, show that value as a quick suggestion
#         in the target_max box (non-destructive).
#         """
#         if not self.target_max_edit.hasFocus():
#             self.target_max_edit.setText(str(value))

#     # ---------- PATIENT HISTORY / JSON ----------

#     def load_patient_stats(self):
#         """
#         Load aggregated stats from data/patient_stats.json
#         (written by patient_game_app).
#         """
#         data_dir = os.path.join(PROJECT_ROOT, "data")
#         os.makedirs(data_dir, exist_ok=True)

#         if not os.path.isfile(self.patient_stats_path):
#             self.history_status_label.setText(
#                 "patient_stats.json not found yet (no game sessions saved)."
#             )
#             self.history_status_label.setStyleSheet("color: gray;")
#             self.reps_label.setText("Per-finger reps: —")
#             self.total_reps_label.setText("Total reps across fingers: —")
#             self.combo_reps_label.setText("All-fingers combo reps: —")
#             self.sessions_completed_label.setText("Game sessions completed: —")
#             self.last_updated_label.setText("Last updated: —")
#             return

#         try:
#             with open(self.patient_stats_path, "r") as f:
#                 data = json.load(f)
#         except Exception as e:
#             QMessageBox.critical(
#                 self,
#                 "Error",
#                 f"Failed to read patient_stats.json:\n{e}",
#             )
#             return

#         self.reps_per_channel = data.get("reps_per_channel", [])
#         self.sessions_completed = int(data.get("sessions_completed", 0))
#         self.combo_reps = int(data.get("combo_reps", 0))
#         self.last_updated = data.get("last_updated", None)

#         # ---- Update UI ----
#         self.history_status_label.setText(f"Loaded patient_stats.json")
#         self.history_status_label.setStyleSheet("color: green;")

#         if self.reps_per_channel and len(self.reps_per_channel) == 4:
#             finger_names = ["Index", "Middle", "Ring", "Pinky"]
#             parts = [
#                 f"{name}: {rep}"
#                 for name, rep in zip(finger_names, self.reps_per_channel)
#             ]
#             self.reps_label.setText("Per-finger reps: " + ", ".join(parts))
#             total = sum(self.reps_per_channel)
#             self.total_reps_label.setText(
#                 f"Total reps across fingers: {total}"
#             )
#         else:
#             self.reps_label.setText("Per-finger reps: —")
#             self.total_reps_label.setText("Total reps across fingers: —")

#         self.combo_reps_label.setText(
#             f"All-fingers combo reps: {self.combo_reps}"
#         )
#         self.sessions_completed_label.setText(
#             f"Game sessions completed: {self.sessions_completed}"
#         )
#         if self.last_updated:
#             self.last_updated_label.setText(f"Last updated: {self.last_updated}")
#         else:
#             self.last_updated_label.setText("Last updated: —")


# def main():
#     app = QApplication(sys.argv)
#     win = ClinicianWindow()
#     win.show()
#     sys.exit(app.exec())


# if __name__ == "__main__":
#     main()


#########===================== Clinician GUI V3 ==============================##########

# host/gui/clinician_app.py

# import os
# import sys
# import csv
# import json
# from datetime import datetime

# from PyQt6.QtCore import Qt
# from PyQt6.QtWidgets import (
#     QApplication,
#     QWidget,
#     QVBoxLayout,
#     QHBoxLayout,
#     QLabel,
#     QPushButton,
#     QLineEdit,
#     QFileDialog,
#     QMessageBox,
#     QGroupBox,
#     QSlider,
# )
# import pyqtgraph as pg

# # ------------ PATH SETUP ------------
# # This file is .../cardinal-grip/host/gui/clinician_app.py
# GUI_DIR = os.path.dirname(__file__)          # .../host/gui
# HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
# PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

# if PROJECT_ROOT not in sys.path:
#     sys.path.append(PROJECT_ROOT)
# # ------------------------------------

# NUM_CHANNELS = 4
# CHANNEL_NAMES = ["Index", "Middle", "Ring", "Pinky"]

# class ClinicianWindow(QWidget):
#     def __init__(self):
#         super().__init__()

#         self.setWindowTitle("Cardinal Grip – Clinician")
#         self.resize(1100, 700)

#         # Session data (CSV)
#         self.times = []
#         self.values = []   # flattened or per-channel depending on file
#         self.session_path = None

#         # Game stats (from patient_stats.json)
#         self.game_stats_path = os.path.join(PROJECT_ROOT, "data", "patient_stats.json")
#         self.reps_per_channel = [0] * NUM_CHANNELS
#         self.sessions_completed = 0
#         self.last_updated = None

#         # ---------- UI LAYOUT ----------

#         main_layout = QVBoxLayout()
#         self.setLayout(main_layout)

#         # Top row: load button + filename
#         top_row = QHBoxLayout()

#         self.load_button = QPushButton("Load Session CSV")
#         self.load_button.clicked.connect(self.load_csv)
#         top_row.addWidget(self.load_button)

#         self.filename_label = QLabel("No file loaded")
#         self.filename_label.setStyleSheet("color: gray;")
#         top_row.addWidget(self.filename_label, stretch=1)

#         main_layout.addLayout(top_row)

#         # Middle: plot + right-side panels
#         middle_row = QHBoxLayout()
#         main_layout.addLayout(middle_row, stretch=1)

#         # ---- Plot ----
#         self.plot_widget = pg.PlotWidget()
#         self.plot_widget.setLabel("left", "Force", units="ADC")
#         self.plot_widget.setLabel("bottom", "Time", units="s")
#         self.curve = self.plot_widget.plot([], [], pen=pg.mkPen("w", width=2))
#         middle_row.addWidget(self.plot_widget, stretch=3)

#         # ---- Right panel ----
#         right_panel = QVBoxLayout()
#         middle_row.addLayout(right_panel, stretch=2)

#         # ----- Session Info Group -----
#         info_group = QGroupBox("Session Info (from CSV)")
#         info_layout = QVBoxLayout()
#         info_group.setLayout(info_layout)

#         self.samples_label = QLabel("Samples: —")
#         self.duration_label = QLabel("Duration: —")
#         self.min_label = QLabel("Min force: —")
#         self.max_label = QLabel("Max force: —")
#         self.mean_label = QLabel("Mean force: —")

#         info_layout.addWidget(self.samples_label)
#         info_layout.addWidget(self.duration_label)
#         info_layout.addWidget(self.min_label)
#         info_layout.addWidget(self.max_label)
#         info_layout.addWidget(self.mean_label)

#         right_panel.addWidget(info_group)

#         # ----- Target Band Group (for CSV analysis) -----
#         band_group = QGroupBox("Target Band Analysis (CSV)")
#         band_layout = QVBoxLayout()
#         band_group.setLayout(band_layout)

#         band_row_top = QHBoxLayout()
#         band_row_bottom = QHBoxLayout()

#         band_row_top.addWidget(QLabel("Min (ADC):"))
#         self.target_min_edit = QLineEdit("1200")
#         band_row_top.addWidget(self.target_min_edit)

#         band_row_bottom.addWidget(QLabel("Max (ADC):"))
#         self.target_max_edit = QLineEdit("2000")
#         band_row_bottom.addWidget(self.target_max_edit)

#         band_layout.addLayout(band_row_top)
#         band_layout.addLayout(band_row_bottom)

#         self.band_slider = QSlider(Qt.Orientation.Horizontal)
#         self.band_slider.setRange(0, 4095)
#         self.band_slider.setValue(1600)
#         self.band_slider.valueChanged.connect(self._band_slider_hint)
#         band_layout.addWidget(QLabel("Quick threshold slider (suggests a max value):"))
#         band_layout.addWidget(self.band_slider)

#         self.band_result_label = QLabel("In-target %: —")
#         band_layout.addWidget(self.band_result_label)

#         self.recalc_button = QPushButton("Recalculate with target band")
#         self.recalc_button.clicked.connect(self.update_band_stats)
#         band_layout.addWidget(self.recalc_button)

#         right_panel.addWidget(band_group)

#         # ----- Game Mode Summary Group (from patient_stats.json) -----
#         game_group = QGroupBox("Game Mode Summary (from patient_stats.json)")
#         game_layout = QVBoxLayout()
#         game_group.setLayout(game_layout)

#         self.game_status_label = QLabel("No game stats loaded yet.")
#         self.game_status_label.setStyleSheet("color: gray;")
#         game_layout.addWidget(self.game_status_label)

#         # Per-channel reps labels
#         self.channel_rep_labels = []
#         for i, name in enumerate(CHANNEL_NAMES):
#             lbl = QLabel(f"{name}: 0 reps")
#             self.channel_rep_labels.append(lbl)
#             game_layout.addWidget(lbl)

#         self.total_reps_label = QLabel("Total reps across fingers: 0")
#         self.sessions_completed_label = QLabel("Game-mode sessions completed: 0")
#         self.last_updated_label = QLabel("Last updated: —")

#         game_layout.addWidget(self.total_reps_label)
#         game_layout.addWidget(self.sessions_completed_label)
#         game_layout.addWidget(self.last_updated_label)

#         self.refresh_game_button = QPushButton("Refresh game stats")
#         self.refresh_game_button.clicked.connect(self.load_game_stats)
#         game_layout.addWidget(self.refresh_game_button)

#         right_panel.addWidget(game_group)

#         # ---- Bottom hint ----
#         hint = QLabel(
#             "Tip: Patient GUI (4-channel) saves CSVs under data/logs/, "
#             "and the game-mode patient GUI saves cumulative stats to data/patient_stats.json."
#         )
#         hint.setStyleSheet("color: gray;")
#         main_layout.addWidget(hint)

#         # Initial load of patient_stats.json (if it exists)
#         self.load_game_stats()

#     # ---------- FILE LOADING (CSV) ----------

#     def load_csv(self):
#         """Open a CSV file and load time + force columns."""
#         data_dir = os.path.join(PROJECT_ROOT, "data", "logs")
#         os.makedirs(data_dir, exist_ok=True)

#         path, _ = QFileDialog.getOpenFileName(
#             self,
#             "Open Session CSV",
#             data_dir,
#             "CSV Files (*.csv)",
#         )
#         if not path:
#             return

#         times = []
#         values = []

#         try:
#             with open(path, "r", newline="") as f:
#                 reader = csv.reader(f)
#                 header = next(reader, None)

#                 # We support both:
#                 #  - Single-column force ("force_adc")
#                 #  - Multi-channel: time_s, ch0_adc, ch1_adc, ch2_adc, ch3_adc
#                 # For simplicity, we convert to a single magnitude:
#                 #   - if multiple channels, we use ch0_adc, or average.
#                 ch_indices = []

#                 if header:
#                     # identify time & channel columns
#                     # time assumed at col 0
#                     # channels: columns named ch0_adc, ch1_adc, etc.
#                     for idx, name in enumerate(header):
#                         if name.strip().lower().startswith("ch"):
#                             ch_indices.append(idx)
#                 for row in reader:
#                     if len(row) < 2:
#                         continue
#                     try:
#                         t = float(row[0])
#                     except ValueError:
#                         continue

#                     # 1) multi-channel CSV
#                     if ch_indices:
#                         chan_vals = []
#                         for idx in ch_indices:
#                             if idx < len(row):
#                                 try:
#                                     chan_vals.append(float(row[idx]))
#                                 except ValueError:
#                                     chan_vals.append(0.0)
#                         if not chan_vals:
#                             continue
#                         v = sum(chan_vals) / len(chan_vals)  # average as aggregate
#                     else:
#                         # 2) simple two-column CSV: time_s, force_adc
#                         try:
#                             v = float(row[1])
#                         except ValueError:
#                             continue

#                     times.append(t)
#                     values.append(v)

#         except Exception as e:
#             QMessageBox.critical(self, "Error", f"Failed to read CSV:\n{e}")
#             return

#         if not times:
#             QMessageBox.warning(self, "No data", "No valid samples in this file.")
#             return

#         self.times = times
#         self.values = values
#         self.session_path = path

#         self.filename_label.setText(os.path.basename(path))
#         self.filename_label.setStyleSheet("color: black;")

#         self.update_plot()
#         self.update_stats()
#         self.update_band_stats()

#     # ---------- STATS / PLOT (CSV) ----------

#     def update_plot(self):
#         if not self.times or not self.values:
#             self.curve.setData([], [])
#             return
#         self.curve.setData(self.times, self.values)

#     def update_stats(self):
#         if not self.times or not self.values:
#             self.samples_label.setText("Samples: —")
#             self.duration_label.setText("Duration: —")
#             self.min_label.setText("Min force: —")
#             self.max_label.setText("Max force: —")
#             self.mean_label.setText("Mean force: —")
#             return

#         n = len(self.values)
#         duration = self.times[-1] - self.times[0]
#         vmin = min(self.values)
#         vmax = max(self.values)
#         vmean = sum(self.values) / n

#         self.samples_label.setText(f"Samples: {n}")
#         self.duration_label.setText(f"Duration: {duration:.2f} s")
#         self.min_label.setText(f"Min force: {vmin:.1f}")
#         self.max_label.setText(f"Max force: {vmax:.1f}")
#         self.mean_label.setText(f"Mean force: {vmean:.1f}")

#     def update_band_stats(self):
#         """Compute % of samples in the chosen target ADC range."""
#         if not self.values:
#             self.band_result_label.setText("In-target %: —")
#             return

#         try:
#             tmin = float(self.target_min_edit.text().strip())
#             tmax = float(self.target_max_edit.text().strip())
#         except ValueError:
#             QMessageBox.warning(self, "Error", "Invalid target min/max.")
#             return

#         if tmax < tmin:
#             QMessageBox.warning(self, "Error", "Max must be >= min.")
#             return

#         total = len(self.values)
#         in_band = sum(1 for v in self.values if tmin <= v <= tmax)

#         pct = 100.0 * in_band / total
#         self.band_result_label.setText(f"In-target %: {pct:.1f}%")

#     def _band_slider_hint(self, value: int):
#         """
#         When clinician drags the slider, suggest a max value (non-destructive)
#         by reflecting it in the target_max box.
#         """
#         if not self.target_max_edit.hasFocus():
#             self.target_max_edit.setText(str(value))

#     # ---------- GAME STATS (patient_stats.json) ----------

#     def load_game_stats(self):
#         """
#         Load cumulative game-mode stats written by patient_game_app.py
#         from data/patient_stats.json, if it exists.
#         """
#         # Default/reset
#         self.reps_per_channel = [0] * NUM_CHANNELS
#         self.sessions_completed = 0
#         self.last_updated = None

#         if not os.path.isfile(self.game_stats_path):
#             self.game_status_label.setText("Game stats: no patient_stats.json found yet.")
#             self.game_status_label.setStyleSheet("color: gray;")
#             self._update_game_labels()
#             return

#         try:
#             with open(self.game_stats_path, "r") as f:
#                 data = json.load(f)

#             reps = data.get("reps_per_channel", [0] * NUM_CHANNELS)
#             if not isinstance(reps, list) or len(reps) != NUM_CHANNELS:
#                 reps = [0] * NUM_CHANNELS

#             self.reps_per_channel = [int(x) for x in reps]
#             self.sessions_completed = int(data.get("sessions_completed", 0))
#             self.last_updated = data.get("last_updated", None)

#             self.game_status_label.setText("Game stats loaded successfully.")
#             self.game_status_label.setStyleSheet("color: green;")

#         except Exception as e:
#             self.game_status_label.setText(f"Error reading game stats: {e}")
#             self.game_status_label.setStyleSheet("color: red;")
#             # Leave defaults in place

#         self._update_game_labels()

#     def _update_game_labels(self):
#         total_reps = sum(self.reps_per_channel)

#         # Per-channel
#         for i, name in enumerate(CHANNEL_NAMES):
#             reps = self.reps_per_channel[i]
#             self.channel_rep_labels[i].setText(f"{name}: {reps} reps")

#         self.total_reps_label.setText(f"Total reps across fingers: {total_reps}")
#         self.sessions_completed_label.setText(
#             f"Game-mode sessions completed: {self.sessions_completed}"
#         )

#         if self.last_updated:
#             self.last_updated_label.setText(f"Last updated: {self.last_updated}")
#         else:
#             self.last_updated_label.setText("Last updated: —")


# def main():
#     app = QApplication(sys.argv)
#     win = ClinicianWindow()
#     win.show()
#     sys.exit(app.exec())


# if __name__ == "__main__":
#     main()

#########===================== Clinician GUI V4 ==============================##########

# host/gui/clinician_app.py

# import os
# import sys
# import csv
# import json
# from datetime import datetime
# from statistics import mean

# from PyQt6.QtCore import Qt
# from PyQt6.QtWidgets import (
#     QApplication,
#     QWidget,
#     QVBoxLayout,
#     QHBoxLayout,
#     QLabel,
#     QPushButton,
#     QLineEdit,
#     QFileDialog,
#     QMessageBox,
#     QGroupBox,
#     QCheckBox,
# )
# import pyqtgraph as pg

# # ------------ PATH SETUP ------------
# GUI_DIR = os.path.dirname(__file__)          # .../host/gui
# HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
# PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

# if PROJECT_ROOT not in sys.path:
#     sys.path.append(PROJECT_ROOT)

# NUM_CHANNELS = 4
# CHANNEL_NAMES = ["Index", "Middle", "Ring", "Pinky"]


# class ClinicianWindow(QWidget):
#     def __init__(self):
#         super().__init__()

#         self.setWindowTitle("Cardinal Grip – Clinician Viewer")
#         self.resize(1100, 700)

#         # Loaded session data
#         self.times: list[float] = []
#         # values[c] = list of samples for channel c
#         self.values: list[list[int]] = [[] for _ in range(NUM_CHANNELS)]
#         self.session_path: str | None = None

#         # Game stats (from patient_stats.json)
#         self.game_stats_path = os.path.join(PROJECT_ROOT, "data", "patient_stats.json")
#         self.reps_per_channel = [0] * NUM_CHANNELS
#         self.sessions_completed = 0
#         self.combo_reps = 0
#         self.last_updated: str | None = None

#         # Target band lines for plot
#         self.target_min_line = None
#         self.target_max_line = None

#         # ---------- UI LAYOUT ----------
#         main_layout = QVBoxLayout()
#         self.setLayout(main_layout)

#         # ===== TOP: load controls =====
#         top_row = QHBoxLayout()

#         self.load_button = QPushButton("Load Session CSV")
#         self.load_button.clicked.connect(self.load_csv)
#         top_row.addWidget(self.load_button)

#         self.load_latest_button = QPushButton("Load Latest from /data/logs")
#         self.load_latest_button.clicked.connect(self.load_latest_csv)
#         top_row.addWidget(self.load_latest_button)

#         self.filename_label = QLabel("No file loaded")
#         self.filename_label.setStyleSheet("color: gray;")
#         top_row.addWidget(self.filename_label, stretch=1)

#         main_layout.addLayout(top_row)

#         # ===== MIDDLE: plot + right-side panels =====
#         middle_row = QHBoxLayout()
#         main_layout.addLayout(middle_row, stretch=1)

#         # ---- Plot ----
#         self.plot_widget = pg.PlotWidget()
#         self.plot_widget.setLabel("left", "Force", units="ADC")
#         self.plot_widget.setLabel("bottom", "Time", units="s")
#         self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
#         middle_row.addWidget(self.plot_widget, stretch=3)

#         # 4 channel curves
#         colors = ["r", "g", "b", "y"]
#         self.curves = []
#         for c in range(NUM_CHANNELS):
#             curve = self.plot_widget.plot(
#                 [],
#                 [],
#                 pen=pg.mkPen(colors[c % len(colors)], width=2),
#                 name=f"Ch{c} ({CHANNEL_NAMES[c]})",
#             )
#             self.curves.append(curve)

#         # ---- Right panel ----
#         right_panel = QVBoxLayout()
#         middle_row.addLayout(right_panel, stretch=2)

#         # === Channel visibility group ===
#         vis_group = QGroupBox("Channels")
#         vis_layout = QVBoxLayout()
#         vis_group.setLayout(vis_layout)

#         self.channel_checkboxes: list[QCheckBox] = []
#         for i in range(NUM_CHANNELS):
#             cb = QCheckBox(f"Ch{i} – {CHANNEL_NAMES[i]}")
#             cb.setChecked(True)
#             cb.stateChanged.connect(self.update_visibility)
#             self.channel_checkboxes.append(cb)
#             vis_layout.addWidget(cb)

#         right_panel.addWidget(vis_group)

#         # === Target band group (for analysis only) ===
#         band_group = QGroupBox("Target Band (Analysis)")
#         band_layout = QVBoxLayout()
#         band_group.setLayout(band_layout)

#         row_min = QHBoxLayout()
#         row_min.addWidget(QLabel("Min (ADC):"))
#         self.target_min_edit = QLineEdit("1200")
#         row_min.addWidget(self.target_min_edit)
#         band_layout.addLayout(row_min)

#         row_max = QHBoxLayout()
#         row_max.addWidget(QLabel("Max (ADC):"))
#         self.target_max_edit = QLineEdit("2000")
#         row_max.addWidget(self.target_max_edit)
#         band_layout.addLayout(row_max)

#         self.apply_band_button = QPushButton("Apply target band")
#         self.apply_band_button.clicked.connect(self.apply_target_band)
#         band_layout.addWidget(self.apply_band_button)

#         self.band_info_label = QLabel("Target band lines will overlay on the plot.")
#         self.band_info_label.setStyleSheet("color: gray;")
#         band_layout.addWidget(self.band_info_label)

#         right_panel.addWidget(band_group)

#         # === Session statistics group ===
#         stats_group = QGroupBox("Session Statistics (Loaded CSV)")
#         stats_layout = QVBoxLayout()
#         stats_group.setLayout(stats_layout)

#         self.stats_labels_per_channel: list[QLabel] = []
#         for i, name in enumerate(CHANNEL_NAMES):
#             lbl = QLabel(f"{name}: —")
#             stats_layout.addWidget(lbl)
#             self.stats_labels_per_channel.append(lbl)

#         self.session_summary_label = QLabel("Session summary: —")
#         stats_layout.addWidget(self.session_summary_label)

#         right_panel.addWidget(stats_group)

#         # === Game stats group (patient_stats.json) ===
#         game_group = QGroupBox("Game Mode Aggregate Stats")
#         game_layout = QVBoxLayout()
#         game_group.setLayout(game_layout)

#         self.channel_rep_labels: list[QLabel] = []
#         for i, name in enumerate(CHANNEL_NAMES):
#             lbl = QLabel(f"{name}: — reps")
#             game_layout.addWidget(lbl)
#             self.channel_rep_labels.append(lbl)

#         self.total_reps_label = QLabel("Total reps across fingers: —")
#         game_layout.addWidget(self.total_reps_label)

#         self.sessions_completed_label = QLabel("Game-mode sessions completed: —")
#         game_layout.addWidget(self.sessions_completed_label)

#         self.combo_reps_label = QLabel("All-fingers combo reps: —")
#         game_layout.addWidget(self.combo_reps_label)

#         self.last_updated_label = QLabel("Last updated: —")
#         self.last_updated_label.setStyleSheet("color: gray;")
#         game_layout.addWidget(self.last_updated_label)

#         right_panel.addWidget(game_group)

#         # Spacer stretch on right panel
#         right_panel.addStretch(1)

#         # At startup, try to load game stats (if file exists)
#         self.load_game_stats()

#     # ================= CSV LOADING =================

#     def load_csv(self):
#         """
#         Open a file dialog and load a CSV of format:
#             time_s, ch0_adc, ch1_adc, ch2_adc, ch3_adc
#         as written by patient_app.py.
#         """
#         data_dir = os.path.join(PROJECT_ROOT, "data", "logs")
#         os.makedirs(data_dir, exist_ok=True)

#         path, _ = QFileDialog.getOpenFileName(
#             self,
#             "Open session CSV",
#             data_dir,
#             "CSV Files (*.csv)",
#         )
#         if not path:
#             return

#         self._load_csv_from_path(path)

#     def load_latest_csv(self):
#         """
#         Convenience: load the newest CSV in data/logs (by filename time stamp).
#         """
#         data_dir = os.path.join(PROJECT_ROOT, "data", "logs")
#         if not os.path.isdir(data_dir):
#             QMessageBox.warning(self, "No logs", f"No directory:\n{data_dir}")
#             return

#         files = [
#             os.path.join(data_dir, f)
#             for f in os.listdir(data_dir)
#             if f.lower().endswith(".csv")
#         ]
#         if not files:
#             QMessageBox.information(self, "No CSV files", "No session logs found.")
#             return

#         files.sort()  # your filenames are time-stamped, so lexical sort works
#         latest = files[-1]
#         self._load_csv_from_path(latest)

#     def _load_csv_from_path(self, path: str):
#         times: list[float] = []
#         values = [[] for _ in range(NUM_CHANNELS)]

#         try:
#             with open(path, "r") as f:
#                 reader = csv.reader(f)
#                 header = next(reader, None)

#                 # Determine column indices
#                 if header is not None and "time_s" in header:
#                     t_idx = header.index("time_s")
#                     ch_idx = []
#                     for c in range(NUM_CHANNELS):
#                         col_name = f"ch{c}_adc"
#                         if col_name in header:
#                             ch_idx.append(header.index(col_name))
#                         else:
#                             ch_idx.append(None)
#                     # Read rows
#                     for row in reader:
#                         try:
#                             t = float(row[t_idx])
#                         except (ValueError, TypeError, IndexError):
#                             continue
#                             # skip bad row
#                         times.append(t)
#                         for c in range(NUM_CHANNELS):
#                             idx = ch_idx[c]
#                             if idx is None or idx >= len(row):
#                                 values[c].append(0)
#                             else:
#                                 try:
#                                     v = int(row[idx])
#                                 except ValueError:
#                                     v = 0
#                                 values[c].append(v)
#                 else:
#                     # Fallback assumption: time in col 0, then 4 channels
#                     for row in reader:
#                         if len(row) < 5:
#                             continue
#                         try:
#                             t = float(row[0])
#                             ch_vals = [int(x) for x in row[1:1+NUM_CHANNELS]]
#                         except ValueError:
#                             continue
#                         times.append(t)
#                         for c in range(NUM_CHANNELS):
#                             values[c].append(ch_vals[c])
#         except Exception as e:
#             QMessageBox.critical(self, "Error", f"Failed to read CSV:\n{e}")
#             return

#         if not times:
#             QMessageBox.warning(self, "No data", "No valid samples in this file.")
#             return

#         self.times = times
#         self.values = values
#         self.session_path = path

#         self.filename_label.setText(os.path.basename(path))
#         self.update_plot()
#         self.update_session_stats()

#     # ================= PLOT & STATS =================

#     def update_plot(self):
#         if not self.times or not any(self.values):
#             # clear
#             for curve in self.curves:
#                 curve.setData([], [])
#             return

#         for c in range(NUM_CHANNELS):
#             if c < len(self.values):
#                 self.curves[c].setData(self.times, self.values[c])
#             else:
#                 self.curves[c].setData([], [])

#         self.update_visibility()

#     def update_visibility(self):
#         for i, cb in enumerate(self.channel_checkboxes):
#             visible = cb.isChecked()
#             self.curves[i].setVisible(visible)

#     def update_session_stats(self):
#         if not self.times:
#             for lbl in self.stats_labels_per_channel:
#                 lbl.setText("—")
#             self.session_summary_label.setText("Session summary: —")
#             return

#         duration = self.times[-1] - self.times[0] if len(self.times) > 1 else 0.0

#         for c in range(NUM_CHANNELS):
#             vals = self.values[c]
#             if not vals:
#                 self.stats_labels_per_channel[c].setText(
#                     f"{CHANNEL_NAMES[c]}: no data"
#                 )
#                 continue

#             v_min = min(vals)
#             v_max = max(vals)
#             v_mean = mean(vals)

#             self.stats_labels_per_channel[c].setText(
#                 f"{CHANNEL_NAMES[c]} – min: {v_min:.0f}, max: {v_max:.0f}, mean: {v_mean:.1f}"
#             )

#         self.session_summary_label.setText(
#             f"Session summary: {len(self.times)} samples over {duration:.1f} s"
#         )

#     # ================= TARGET BAND LINES =================

#     def apply_target_band(self):
#         try:
#             tmin = int(self.target_min_edit.text().strip())
#             tmax = int(self.target_max_edit.text().strip())
#         except ValueError:
#             QMessageBox.warning(self, "Error", "Min/Max must be integers.")
#             return

#         if tmin >= tmax:
#             QMessageBox.warning(
#                 self,
#                 "Error",
#                 "Min ADC must be less than Max ADC.",
#             )
#             return

#         # Remove old lines if present
#         if self.target_min_line is not None:
#             self.plot_widget.removeItem(self.target_min_line)
#         if self.target_max_line is not None:
#             self.plot_widget.removeItem(self.target_max_line)

#         # Add new horizontal lines
#         self.target_min_line = pg.InfiniteLine(
#             pos=tmin, angle=0, pen=pg.mkPen("#FF9800", style=Qt.PenStyle.DashLine)
#         )  # orange dashed
#         self.target_max_line = pg.InfiniteLine(
#             pos=tmax, angle=0, pen=pg.mkPen("#4CAF50", style=Qt.PenStyle.DashLine)
#         )  # green dashed

#         self.plot_widget.addItem(self.target_min_line)
#         self.plot_widget.addItem(self.target_max_line)

#     # ================= GAME STATS (patient_stats.json) =================

#     def load_game_stats(self):
#         if not os.path.isfile(self.game_stats_path):
#             # No stats yet; leave as default
#             self.update_game_stats_labels()
#             return

#         try:
#             with open(self.game_stats_path, "r") as f:
#                 data = json.load(f)
#         except Exception:
#             # If corrupted, ignore but don't crash
#             self.update_game_stats_labels()
#             return

#         self.reps_per_channel = data.get("reps_per_channel", [0] * NUM_CHANNELS)
#         if len(self.reps_per_channel) != NUM_CHANNELS:
#             self.reps_per_channel = [0] * NUM_CHANNELS

#         self.sessions_completed = int(data.get("sessions_completed", 0))
#         self.combo_reps = int(data.get("combo_reps", 0))
#         self.last_updated = data.get("last_updated", None)

#         self.update_game_stats_labels()

#     def update_game_stats_labels(self):
#         total_reps = sum(self.reps_per_channel)

#         for i, name in enumerate(CHANNEL_NAMES):
#             reps = self.reps_per_channel[i]
#             self.channel_rep_labels[i].setText(f"{name}: {reps} reps")

#         self.total_reps_label.setText(f"Total reps across fingers: {total_reps}")
#         self.sessions_completed_label.setText(
#             f"Game-mode sessions completed: {self.sessions_completed}"
#         )
#         self.combo_reps_label.setText(
#             f"All-fingers combo reps: {self.combo_reps}"
#         )

#         if self.last_updated:
#             self.last_updated_label.setText(f"Last updated: {self.last_updated}")
#         else:
#             self.last_updated_label.setText("Last updated: —")


# def main():
#     app = QApplication(sys.argv)
#     win = ClinicianWindow()
#     win.show()
#     sys.exit(app.exec())


# if __name__ == "__main__":
#     main()


#########===================== Clinician GUI V5 ==============================##########

# host/gui/clinician_app.py

import os
import sys
import csv
import json
import math
from datetime import datetime
from statistics import mean, pstdev

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QMessageBox,
    QGroupBox,
    QCheckBox,
    QComboBox,
)
import pyqtgraph as pg

# ------------ PATH SETUP ------------
GUI_DIR = os.path.dirname(__file__)          # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

NUM_CHANNELS = 4
CHANNEL_NAMES = ["Index", "Middle", "Ring", "Pinky"]


class ClinicianWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Clinician Viewer")
        self.resize(1200, 750)

        # Loaded session data (current CSV)
        self.times: list[float] = []
        self.values: list[list[int]] = [[] for _ in range(NUM_CHANNELS)]
        self.session_path: str | None = None

        # Target band for analysis (optional)
        self.band_min: int | None = None
        self.band_max: int | None = None
        self.target_min_line = None
        self.target_max_line = None

        # Multi-session summary list
        # Each summary: {
        #   "basename": str,
        #   "means": [float]*4,
        #   "band_percent": [float|None]*4,
        #   "duration": float,
        #   "samples": int,
        #   "mtime": float|None,
        # }
        self.session_summaries: list[dict] = []

        # Game stats (from patient_game_app)
        self.game_stats_path = os.path.join(PROJECT_ROOT, "data", "patient_stats.json")
        self.reps_per_channel = [0] * NUM_CHANNELS
        self.sessions_completed = 0
        self.combo_reps = 0
        self.last_updated: str | None = None

        # ---------- UI LAYOUT ----------
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # ===== TOP: Load controls =====
        top_row = QHBoxLayout()

        self.load_button = QPushButton("Load Session CSV")
        self.load_button.setToolTip(
            "Open a saved patient session CSV (time_s, ch0..ch3)."
        )
        self.load_button.clicked.connect(self.load_csv)
        top_row.addWidget(self.load_button)

        self.load_latest_button = QPushButton("Load Latest from /data/logs")
        self.load_latest_button.setToolTip(
            "Automatically load the most recent session CSV in data/logs."
        )
        self.load_latest_button.clicked.connect(self.load_latest_csv)
        top_row.addWidget(self.load_latest_button)

        self.filename_label = QLabel("No file loaded")
        self.filename_label.setStyleSheet("color: gray;")
        top_row.addWidget(self.filename_label, stretch=1)

        main_layout.addLayout(top_row)

        # ===== MIDDLE: plot + right-side analysis panels =====
        middle_row = QHBoxLayout()
        main_layout.addLayout(middle_row, stretch=3)

        # ---- MAIN TIME-SERIES PLOT ----
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel("left", "Force (ADC)")
        self.plot_widget.setLabel("bottom", "Time (s)")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        middle_row.addWidget(self.plot_widget, stretch=3)

        colors = ["r", "g", "b", "y"]
        self.curves = []
        for c in range(NUM_CHANNELS):
            curve = self.plot_widget.plot(
                [],
                [],
                pen=pg.mkPen(colors[c % len(colors)], width=2),
                name=f"Ch{c} ({CHANNEL_NAMES[c]})",
            )
            self.curves.append(curve)

        # ---- RIGHT PANEL ----
        right_panel = QVBoxLayout()
        middle_row.addLayout(right_panel, stretch=2)

        # === Channel visibility ===
        vis_group = QGroupBox("Channels (visibility)")
        vis_layout = QVBoxLayout()
        vis_group.setLayout(vis_layout)

        self.channel_checkboxes: list[QCheckBox] = []
        for i in range(NUM_CHANNELS):
            cb = QCheckBox(f"Ch{i} – {CHANNEL_NAMES[i]}")
            cb.setChecked(True)
            cb.stateChanged.connect(self.update_visibility)
            self.channel_checkboxes.append(cb)
            vis_layout.addWidget(cb)

        right_panel.addWidget(vis_group)

        # === Target band (analysis-only; does not affect patient app) ===
        band_group = QGroupBox("Target Band (Analysis Only)")
        band_layout = QVBoxLayout()
        band_group.setLayout(band_layout)

        row_min = QHBoxLayout()
        row_min.addWidget(QLabel("Min (ADC):"))
        self.target_min_edit = QLineEdit("1200")
        self.target_min_edit.setToolTip("Lower bound of desired force band.")
        row_min.addWidget(self.target_min_edit)
        band_layout.addLayout(row_min)

        row_max = QHBoxLayout()
        row_max.addWidget(QLabel("Max (ADC):"))
        self.target_max_edit = QLineEdit("2000")
        self.target_max_edit.setToolTip("Upper bound of desired force band.")
        row_max.addWidget(self.target_max_edit)
        band_layout.addLayout(row_max)

        self.apply_band_button = QPushButton("Apply Target Band to Plot + Stats")
        self.apply_band_button.clicked.connect(self.apply_target_band)
        band_layout.addWidget(self.apply_band_button)

        self.band_info_label = QLabel(
            "Dashed lines show Min/Max. Time-in-band & reaction time use this range."
        )
        self.band_info_label.setStyleSheet("color: gray;")
        band_layout.addWidget(self.band_info_label)

        right_panel.addWidget(band_group)

        # === Session statistics (current CSV) ===
        stats_group = QGroupBox("Current Session Statistics (Loaded CSV)")
        stats_layout = QVBoxLayout()
        stats_group.setLayout(stats_layout)

        self.stats_labels_per_channel: list[QLabel] = []
        for i, name in enumerate(CHANNEL_NAMES):
            lbl = QLabel(f"{name}: —")
            lbl.setToolTip(
                "Per-finger min, max, mean, RMS, variability, and time in band."
            )
            stats_layout.addWidget(lbl)
            self.stats_labels_per_channel.append(lbl)

        self.session_summary_label = QLabel("Session summary: —")
        stats_layout.addWidget(self.session_summary_label)

        self.reaction_time_label = QLabel("Reaction time (Index): —")
        self.reaction_time_label.setToolTip(
            "Time from start until Index finger first enters the target band."
        )
        stats_layout.addWidget(self.reaction_time_label)

        right_panel.addWidget(stats_group)

        # === Game mode aggregate stats from patient_game_app ===
        game_group = QGroupBox("Game Mode Aggregate Stats (patient_game_app)")
        game_layout = QVBoxLayout()
        game_group.setLayout(game_layout)

        self.channel_rep_labels: list[QLabel] = []
        for i, name in enumerate(CHANNEL_NAMES):
            lbl = QLabel(f"{name}: — reps")
            lbl.setToolTip("Total successful 5-second holds for this finger.")
            game_layout.addWidget(lbl)
            self.channel_rep_labels.append(lbl)

        self.total_reps_label = QLabel("Total reps across fingers: —")
        game_layout.addWidget(self.total_reps_label)

        self.sessions_completed_label = QLabel(
            "Game-mode sessions completed: —"
        )
        game_layout.addWidget(self.sessions_completed_label)

        self.combo_reps_label = QLabel("All-fingers combo reps: —")
        self.combo_reps_label.setToolTip(
            "Successful all-finger 5-second holds in patient_game_app."
        )
        game_layout.addWidget(self.combo_reps_label)

        self.last_updated_label = QLabel("Last updated: —")
        self.last_updated_label.setStyleSheet("color: gray;")
        game_layout.addWidget(self.last_updated_label)

        right_panel.addWidget(game_group)

        # === Multi-session comparison dashboard ===
        comp_group = QGroupBox("Session Comparison (Multi-Session Dashboard)")
        comp_layout = QVBoxLayout()
        comp_group.setLayout(comp_layout)

        metric_row = QHBoxLayout()
        metric_row.addWidget(QLabel("Metric:"))
        self.metric_combo = QComboBox()
        self.metric_combo.addItems([
            "Mean ADC – Index",
            "Mean ADC – Middle",
            "Mean ADC – Ring",
            "Mean ADC – Pinky",
            "Percent time in band – Index",
            "Percent time in band – Middle",
            "Percent time in band – Ring",
            "Percent time in band – Pinky",
        ])
        self.metric_combo.currentIndexChanged.connect(self.update_comparison_plot)
        metric_row.addWidget(self.metric_combo)
        comp_layout.addLayout(metric_row)

        self.comparison_plot = pg.PlotWidget()
        self.comparison_plot.setLabel("left", "Metric value")
        self.comparison_plot.setLabel("bottom", "Session index (1 = first loaded)")
        self.comparison_plot.showGrid(x=True, y=True, alpha=0.3)
        comp_layout.addWidget(self.comparison_plot, stretch=1)

        self.comparison_info_label = QLabel(
            "No sessions loaded yet. Load CSVs to build the comparison dashboard."
        )
        self.comparison_info_label.setStyleSheet("color: gray;")
        comp_layout.addWidget(self.comparison_info_label)

        right_panel.addWidget(comp_group)

        # Spacer
        right_panel.addStretch(1)

        # At startup, try to load game stats from patient_game_app
        self.load_game_stats()
        # Initial comparison plot (empty)
        self.update_comparison_plot()

    # ================= CSV LOADING =================

    def load_csv(self):
        """
        Open a file dialog and load a CSV of format:
            time_s, ch0_adc, ch1_adc, ch2_adc, ch3_adc
        as written by patient_app.py.
        """
        data_dir = os.path.join(PROJECT_ROOT, "data", "logs")
        os.makedirs(data_dir, exist_ok=True)

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open session CSV",
            data_dir,
            "CSV Files (*.csv)",
        )
        if not path:
            return

        self._load_csv_from_path(path)

    def load_latest_csv(self):
        """
        Convenience: load the newest CSV in data/logs (by filename).
        """
        data_dir = os.path.join(PROJECT_ROOT, "data", "logs")
        if not os.path.isdir(data_dir):
            QMessageBox.warning(self, "No logs", f"No directory:\n{data_dir}")
            return

        files = [
            os.path.join(data_dir, f)
            for f in os.listdir(data_dir)
            if f.lower().endswith(".csv")
        ]
        if not files:
            QMessageBox.information(self, "No CSV files", "No session logs found.")
            return

        files.sort()  # filenames are time-stamped, so lexical sort works
        latest = files[-1]
        self._load_csv_from_path(latest)

    def _load_csv_from_path(self, path: str):
        times: list[float] = []
        values = [[] for _ in range(NUM_CHANNELS)]

        try:
            with open(path, "r") as f:
                reader = csv.reader(f)
                header = next(reader, None)

                if header is not None and "time_s" in header:
                    # Use headers if available
                    t_idx = header.index("time_s")
                    ch_idx = []
                    for c in range(NUM_CHANNELS):
                        col_name = f"ch{c}_adc"
                        if col_name in header:
                            ch_idx.append(header.index(col_name))
                        else:
                            ch_idx.append(None)

                    for row in reader:
                        try:
                            t = float(row[t_idx])
                        except (ValueError, TypeError, IndexError):
                            continue
                        times.append(t)
                        for c in range(NUM_CHANNELS):
                            idx = ch_idx[c]
                            if idx is None or idx >= len(row):
                                values[c].append(0)
                            else:
                                try:
                                    v = int(row[idx])
                                except ValueError:
                                    v = 0
                                values[c].append(v)
                else:
                    # Fallback assumption: col0 = time, col1..4 = channels
                    for row in reader:
                        if len(row) < 5:
                            continue
                        try:
                            t = float(row[0])
                            ch_vals = [int(x) for x in row[1:1+NUM_CHANNELS]]
                        except ValueError:
                            continue
                        times.append(t)
                        for c in range(NUM_CHANNELS):
                            values[c].append(ch_vals[c])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read CSV:\n{e}")
            return

        if not times:
            QMessageBox.warning(self, "No data", "No valid samples in this file.")
            return

        self.times = times
        self.values = values
        self.session_path = path
        self.filename_label.setText(os.path.basename(path))

        # Update main plot & stats for this session
        self.update_plot()
        self.update_session_stats()

        # Compute summary for multi-session dashboard and append
        summary = self._compute_current_session_summary()
        self.session_summaries.append(summary)
        self.update_comparison_plot()

    # ================= PLOT & PER-SESSION STATS =================

    def update_plot(self):
        if not self.times or not any(self.values):
            for curve in self.curves:
                curve.setData([], [])
            return

        for c in range(NUM_CHANNELS):
            self.curves[c].setData(self.times, self.values[c])

        self.update_visibility()

    def update_visibility(self):
        for i, cb in enumerate(self.channel_checkboxes):
            visible = cb.isChecked()
            self.curves[i].setVisible(visible)

    def update_session_stats(self):
        """
        Compute per-channel and per-session statistics for the currently loaded CSV.
        Includes: min, max, mean, RMS, std dev, time in band, % in band, reaction time.
        """
        if not self.times:
            for lbl in self.stats_labels_per_channel:
                lbl.setText("—")
            self.session_summary_label.setText("Session summary: —")
            self.reaction_time_label.setText("Reaction time (Index): —")
            return

        total_samples = len(self.times)
        duration = (
            self.times[-1] - self.times[0] if total_samples > 1 else 0.0
        )

        # Reaction time for Index finger (Ch0)
        rt_text = "Reaction time (Index): —"
        if (
            self.band_min is not None
            and self.band_max is not None
            and self.values[0]
        ):
            rt = None
            t0 = self.times[0]
            for t, v0 in zip(self.times, self.values[0]):
                if self.band_min <= v0 <= self.band_max:
                    rt = t - t0
                    break
            if rt is not None:
                rt_text = f"Reaction time (Index): {rt:.2f} s from start"
        self.reaction_time_label.setText(rt_text)

        for c in range(NUM_CHANNELS):
            vals = self.values[c]
            if not vals:
                self.stats_labels_per_channel[c].setText(
                    f"{CHANNEL_NAMES[c]}: no data"
                )
                continue

            v_min = min(vals)
            v_max = max(vals)
            v_mean = mean(vals)
            v_rms = math.sqrt(mean([v * v for v in vals]))
            v_std = pstdev(vals) if len(vals) > 1 else 0.0

            time_in_band = None
            percent_in_band = None
            if (
                self.band_min is not None
                and self.band_max is not None
                and total_samples > 1
            ):
                in_band_count = sum(
                    1 for v in vals if self.band_min <= v <= self.band_max
                )
                dt = duration / (total_samples - 1) if total_samples > 1 else 0.0
                time_in_band = in_band_count * dt
                percent_in_band = (
                    100.0 * in_band_count / total_samples if total_samples > 0 else 0.0
                )

            if time_in_band is not None:
                tib_str = f", in-band: {time_in_band:.1f} s ({percent_in_band:.1f}%)"
            else:
                tib_str = ""
            self.stats_labels_per_channel[c].setText(
                f"{CHANNEL_NAMES[c]} – "
                f"min: {v_min:.0f}, max: {v_max:.0f}, "
                f"mean: {v_mean:.1f}, RMS: {v_rms:.1f}, "
                f"σ: {v_std:.1f}{tib_str}"
            )

        self.session_summary_label.setText(
            f"Session summary: {total_samples} samples over {duration:.1f} s"
        )

    # ================= TARGET BAND LINES =================

    def apply_target_band(self):
        """
        Apply target Min/Max ADC to:
          - overlay dashed horizontal lines on the plot
          - recompute time-in-band and reaction-time stats
          - update multi-session comparison if band metrics selected
        """
        try:
            tmin = int(self.target_min_edit.text().strip())
            tmax = int(self.target_max_edit.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Error", "Min/Max must be integers.")
            return

        if tmin >= tmax:
            QMessageBox.warning(
                self,
                "Error",
                "Min ADC must be less than Max ADC.",
            )
            return

        self.band_min = tmin
        self.band_max = tmax

        # Remove old lines
        if self.target_min_line is not None:
            self.plot_widget.removeItem(self.target_min_line)
        if self.target_max_line is not None:
            self.plot_widget.removeItem(self.target_max_line)

        # Add new horizontal lines
        self.target_min_line = pg.InfiniteLine(
            pos=tmin,
            angle=0,
            pen=pg.mkPen("#FF9800", style=Qt.PenStyle.DashLine),  # orange
        )
        self.target_max_line = pg.InfiniteLine(
            pos=tmax,
            angle=0,
            pen=pg.mkPen("#4CAF50", style=Qt.PenStyle.DashLine),  # green
        )
        self.plot_widget.addItem(self.target_min_line)
        self.plot_widget.addItem(self.target_max_line)

        # Recompute stats for current session with band info
        self.update_session_stats()

        # NOTE: band-based metrics in the multi-session dashboard
        # use the band as it existed when each CSV was loaded.
        # You can clear and re-load sessions after adjusting band
        # if you want a consistent band across them.
        self.update_comparison_plot()

    # ================= PER-SESSION SUMMARY (FOR MULTI-SESSION DASHBOARD) =================

    def _compute_current_session_summary(self) -> dict:
        """
        Build a compact summary for the currently loaded session.
        Used for multi-session comparison dashboard.
        """
        summary = {
            "basename": os.path.basename(self.session_path)
            if self.session_path
            else "—",
            "means": [0.0] * NUM_CHANNELS,
            "band_percent": [None] * NUM_CHANNELS,
            "duration": 0.0,
            "samples": len(self.times),
            "mtime": None,
        }

        if not self.times:
            return summary

        total_samples = len(self.times)
        duration = (
            self.times[-1] - self.times[0] if total_samples > 1 else 0.0
        )
        summary["duration"] = duration

        for c in range(NUM_CHANNELS):
            vals = self.values[c]
            if vals:
                v_mean = mean(vals)
            else:
                v_mean = 0.0
            summary["means"][c] = v_mean

            if (
                self.band_min is not None
                and self.band_max is not None
                and vals
                and total_samples > 0
            ):
                in_band_count = sum(
                    1 for v in vals if self.band_min <= v <= self.band_max
                )
                percent_in_band = 100.0 * in_band_count / total_samples
            else:
                percent_in_band = None

            summary["band_percent"][c] = percent_in_band

        try:
            if self.session_path:
                summary["mtime"] = os.path.getmtime(self.session_path)
        except Exception:
            summary["mtime"] = None

        return summary

    # ================= MULTI-SESSION COMPARISON DASHBOARD =================

    def update_comparison_plot(self):
        """
        Plot a summary metric (mean ADC or % time in band) across all loaded sessions.
        X-axis: session index in load order (1,2,3,...).
        """
        self.comparison_plot.clear()

        if not self.session_summaries:
            self.comparison_info_label.setText(
                "No sessions loaded yet. Load CSVs to build the comparison dashboard."
            )
            return

        metric = self.metric_combo.currentText()
        x = list(range(1, len(self.session_summaries) + 1))
        y: list[float] = []

        # Determine metric type and channel index
        channel_index = 0
        if "Index" in metric:
            channel_index = 0
        elif "Middle" in metric:
            channel_index = 1
        elif "Ring" in metric:
            channel_index = 2
        elif "Pinky" in metric:
            channel_index = 3

        if metric.startswith("Mean ADC"):
            self.comparison_plot.setLabel("left", "Mean ADC")
            for s in self.session_summaries:
                y.append(s["means"][channel_index])

        elif metric.startswith("Percent time in band"):
            self.comparison_plot.setLabel("left", "Percent in band (%)")
            for s in self.session_summaries:
                p = s["band_percent"][channel_index]
                # If band wasn't defined when this session was loaded, treat as 0
                y.append(p if p is not None else 0.0)

        # Plot as line with points
        self.comparison_plot.plot(
            x,
            y,
            pen=pg.mkPen("#2196F3", width=2),
            symbol="o",
            symbolBrush="#FFFFFF",
        )

        # Label x-axis with indices
        ax = self.comparison_plot.getAxis("bottom")
        ax.setTicks([[(i, str(i)) for i in x]])

        # Text mapping index → filename
        names = [s["basename"] for s in self.session_summaries]
        info = "Sessions (index → file): " + ", ".join(
            f"{i+1}: {name}" for i, name in enumerate(names)
        )
        self.comparison_info_label.setText(info)

    # ================= GAME STATS (patient_game_app JSON) =================

    def load_game_stats(self):
        """
        Read aggregate game-mode stats from data/patient_stats.json
        written by patient_game_app (reps per finger, combo reps, etc.).
        """
        if not os.path.isfile(self.game_stats_path):
            self.update_game_stats_labels()
            return

        try:
            with open(self.game_stats_path, "r") as f:
                data = json.load(f)
        except Exception:
            self.update_game_stats_labels()
            return

        self.reps_per_channel = data.get("reps_per_channel", [0] * NUM_CHANNELS)
        if len(self.reps_per_channel) != NUM_CHANNELS:
            self.reps_per_channel = [0] * NUM_CHANNELS

        self.sessions_completed = int(data.get("sessions_completed", 0))
        self.combo_reps = int(data.get("combo_reps", 0))
        self.last_updated = data.get("last_updated", None)

        self.update_game_stats_labels()

    def update_game_stats_labels(self):
        total_reps = sum(self.reps_per_channel)

        for i, name in enumerate(CHANNEL_NAMES):
            reps = self.reps_per_channel[i]
            self.channel_rep_labels[i].setText(f"{name}: {reps} reps")

        self.total_reps_label.setText(f"Total reps across fingers: {total_reps}")
        self.sessions_completed_label.setText(
            f"Game-mode sessions completed: {self.sessions_completed}"
        )
        self.combo_reps_label.setText(
            f"All-fingers combo reps: {self.combo_reps}"
        )

        if self.last_updated:
            self.last_updated_label.setText(f"Last updated: {self.last_updated}")
        else:
            self.last_updated_label.setText("Last updated: —")


def main():
    app = QApplication(sys.argv)
    win = ClinicianWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

#########===================== Clinician GUI V6 ==============================##########