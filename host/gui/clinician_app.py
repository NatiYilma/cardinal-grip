
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

import os
import sys
import csv
import json
from datetime import datetime

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
    QSlider,
)
import pyqtgraph as pg

# ------------ PATH SETUP ------------
# This file is .../cardinal-grip/host/gui/clinician_app.py
GUI_DIR = os.path.dirname(__file__)          # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
# ------------------------------------

NUM_CHANNELS = 4
CHANNEL_NAMES = ["Index", "Middle", "Ring", "Pinky"]

class ClinicianWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Clinician")
        self.resize(1100, 700)

        # Session data (CSV)
        self.times = []
        self.values = []   # flattened or per-channel depending on file
        self.session_path = None

        # Game stats (from patient_stats.json)
        self.game_stats_path = os.path.join(PROJECT_ROOT, "data", "patient_stats.json")
        self.reps_per_channel = [0] * NUM_CHANNELS
        self.sessions_completed = 0
        self.last_updated = None

        # ---------- UI LAYOUT ----------

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Top row: load button + filename
        top_row = QHBoxLayout()

        self.load_button = QPushButton("Load Session CSV")
        self.load_button.clicked.connect(self.load_csv)
        top_row.addWidget(self.load_button)

        self.filename_label = QLabel("No file loaded")
        self.filename_label.setStyleSheet("color: gray;")
        top_row.addWidget(self.filename_label, stretch=1)

        main_layout.addLayout(top_row)

        # Middle: plot + right-side panels
        middle_row = QHBoxLayout()
        main_layout.addLayout(middle_row, stretch=1)

        # ---- Plot ----
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel("left", "Force", units="ADC")
        self.plot_widget.setLabel("bottom", "Time", units="s")
        self.curve = self.plot_widget.plot([], [], pen=pg.mkPen("w", width=2))
        middle_row.addWidget(self.plot_widget, stretch=3)

        # ---- Right panel ----
        right_panel = QVBoxLayout()
        middle_row.addLayout(right_panel, stretch=2)

        # ----- Session Info Group -----
        info_group = QGroupBox("Session Info (from CSV)")
        info_layout = QVBoxLayout()
        info_group.setLayout(info_layout)

        self.samples_label = QLabel("Samples: —")
        self.duration_label = QLabel("Duration: —")
        self.min_label = QLabel("Min force: —")
        self.max_label = QLabel("Max force: —")
        self.mean_label = QLabel("Mean force: —")

        info_layout.addWidget(self.samples_label)
        info_layout.addWidget(self.duration_label)
        info_layout.addWidget(self.min_label)
        info_layout.addWidget(self.max_label)
        info_layout.addWidget(self.mean_label)

        right_panel.addWidget(info_group)

        # ----- Target Band Group (for CSV analysis) -----
        band_group = QGroupBox("Target Band Analysis (CSV)")
        band_layout = QVBoxLayout()
        band_group.setLayout(band_layout)

        band_row_top = QHBoxLayout()
        band_row_bottom = QHBoxLayout()

        band_row_top.addWidget(QLabel("Min (ADC):"))
        self.target_min_edit = QLineEdit("1200")
        band_row_top.addWidget(self.target_min_edit)

        band_row_bottom.addWidget(QLabel("Max (ADC):"))
        self.target_max_edit = QLineEdit("2000")
        band_row_bottom.addWidget(self.target_max_edit)

        band_layout.addLayout(band_row_top)
        band_layout.addLayout(band_row_bottom)

        self.band_slider = QSlider(Qt.Orientation.Horizontal)
        self.band_slider.setRange(0, 4095)
        self.band_slider.setValue(1600)
        self.band_slider.valueChanged.connect(self._band_slider_hint)
        band_layout.addWidget(QLabel("Quick threshold slider (suggests a max value):"))
        band_layout.addWidget(self.band_slider)

        self.band_result_label = QLabel("In-target %: —")
        band_layout.addWidget(self.band_result_label)

        self.recalc_button = QPushButton("Recalculate with target band")
        self.recalc_button.clicked.connect(self.update_band_stats)
        band_layout.addWidget(self.recalc_button)

        right_panel.addWidget(band_group)

        # ----- Game Mode Summary Group (from patient_stats.json) -----
        game_group = QGroupBox("Game Mode Summary (from patient_stats.json)")
        game_layout = QVBoxLayout()
        game_group.setLayout(game_layout)

        self.game_status_label = QLabel("No game stats loaded yet.")
        self.game_status_label.setStyleSheet("color: gray;")
        game_layout.addWidget(self.game_status_label)

        # Per-channel reps labels
        self.channel_rep_labels = []
        for i, name in enumerate(CHANNEL_NAMES):
            lbl = QLabel(f"{name}: 0 reps")
            self.channel_rep_labels.append(lbl)
            game_layout.addWidget(lbl)

        self.total_reps_label = QLabel("Total reps across fingers: 0")
        self.sessions_completed_label = QLabel("Game-mode sessions completed: 0")
        self.last_updated_label = QLabel("Last updated: —")

        game_layout.addWidget(self.total_reps_label)
        game_layout.addWidget(self.sessions_completed_label)
        game_layout.addWidget(self.last_updated_label)

        self.refresh_game_button = QPushButton("Refresh game stats")
        self.refresh_game_button.clicked.connect(self.load_game_stats)
        game_layout.addWidget(self.refresh_game_button)

        right_panel.addWidget(game_group)

        # ---- Bottom hint ----
        hint = QLabel(
            "Tip: Patient GUI (4-channel) saves CSVs under data/logs/, "
            "and the game-mode patient GUI saves cumulative stats to data/patient_stats.json."
        )
        hint.setStyleSheet("color: gray;")
        main_layout.addWidget(hint)

        # Initial load of patient_stats.json (if it exists)
        self.load_game_stats()

    # ---------- FILE LOADING (CSV) ----------

    def load_csv(self):
        """Open a CSV file and load time + force columns."""
        data_dir = os.path.join(PROJECT_ROOT, "data", "logs")
        os.makedirs(data_dir, exist_ok=True)

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Session CSV",
            data_dir,
            "CSV Files (*.csv)",
        )
        if not path:
            return

        times = []
        values = []

        try:
            with open(path, "r", newline="") as f:
                reader = csv.reader(f)
                header = next(reader, None)

                # We support both:
                #  - Single-column force ("force_adc")
                #  - Multi-channel: time_s, ch0_adc, ch1_adc, ch2_adc, ch3_adc
                # For simplicity, we convert to a single magnitude:
                #   - if multiple channels, we use ch0_adc, or average.
                ch_indices = []

                if header:
                    # identify time & channel columns
                    # time assumed at col 0
                    # channels: columns named ch0_adc, ch1_adc, etc.
                    for idx, name in enumerate(header):
                        if name.strip().lower().startswith("ch"):
                            ch_indices.append(idx)
                for row in reader:
                    if len(row) < 2:
                        continue
                    try:
                        t = float(row[0])
                    except ValueError:
                        continue

                    # 1) multi-channel CSV
                    if ch_indices:
                        chan_vals = []
                        for idx in ch_indices:
                            if idx < len(row):
                                try:
                                    chan_vals.append(float(row[idx]))
                                except ValueError:
                                    chan_vals.append(0.0)
                        if not chan_vals:
                            continue
                        v = sum(chan_vals) / len(chan_vals)  # average as aggregate
                    else:
                        # 2) simple two-column CSV: time_s, force_adc
                        try:
                            v = float(row[1])
                        except ValueError:
                            continue

                    times.append(t)
                    values.append(v)

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
        self.filename_label.setStyleSheet("color: black;")

        self.update_plot()
        self.update_stats()
        self.update_band_stats()

    # ---------- STATS / PLOT (CSV) ----------

    def update_plot(self):
        if not self.times or not self.values:
            self.curve.setData([], [])
            return
        self.curve.setData(self.times, self.values)

    def update_stats(self):
        if not self.times or not self.values:
            self.samples_label.setText("Samples: —")
            self.duration_label.setText("Duration: —")
            self.min_label.setText("Min force: —")
            self.max_label.setText("Max force: —")
            self.mean_label.setText("Mean force: —")
            return

        n = len(self.values)
        duration = self.times[-1] - self.times[0]
        vmin = min(self.values)
        vmax = max(self.values)
        vmean = sum(self.values) / n

        self.samples_label.setText(f"Samples: {n}")
        self.duration_label.setText(f"Duration: {duration:.2f} s")
        self.min_label.setText(f"Min force: {vmin:.1f}")
        self.max_label.setText(f"Max force: {vmax:.1f}")
        self.mean_label.setText(f"Mean force: {vmean:.1f}")

    def update_band_stats(self):
        """Compute % of samples in the chosen target ADC range."""
        if not self.values:
            self.band_result_label.setText("In-target %: —")
            return

        try:
            tmin = float(self.target_min_edit.text().strip())
            tmax = float(self.target_max_edit.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid target min/max.")
            return

        if tmax < tmin:
            QMessageBox.warning(self, "Error", "Max must be >= min.")
            return

        total = len(self.values)
        in_band = sum(1 for v in self.values if tmin <= v <= tmax)

        pct = 100.0 * in_band / total
        self.band_result_label.setText(f"In-target %: {pct:.1f}%")

    def _band_slider_hint(self, value: int):
        """
        When clinician drags the slider, suggest a max value (non-destructive)
        by reflecting it in the target_max box.
        """
        if not self.target_max_edit.hasFocus():
            self.target_max_edit.setText(str(value))

    # ---------- GAME STATS (patient_stats.json) ----------

    def load_game_stats(self):
        """
        Load cumulative game-mode stats written by patient_game_app.py
        from data/patient_stats.json, if it exists.
        """
        # Default/reset
        self.reps_per_channel = [0] * NUM_CHANNELS
        self.sessions_completed = 0
        self.last_updated = None

        if not os.path.isfile(self.game_stats_path):
            self.game_status_label.setText("Game stats: no patient_stats.json found yet.")
            self.game_status_label.setStyleSheet("color: gray;")
            self._update_game_labels()
            return

        try:
            with open(self.game_stats_path, "r") as f:
                data = json.load(f)

            reps = data.get("reps_per_channel", [0] * NUM_CHANNELS)
            if not isinstance(reps, list) or len(reps) != NUM_CHANNELS:
                reps = [0] * NUM_CHANNELS

            self.reps_per_channel = [int(x) for x in reps]
            self.sessions_completed = int(data.get("sessions_completed", 0))
            self.last_updated = data.get("last_updated", None)

            self.game_status_label.setText("Game stats loaded successfully.")
            self.game_status_label.setStyleSheet("color: green;")

        except Exception as e:
            self.game_status_label.setText(f"Error reading game stats: {e}")
            self.game_status_label.setStyleSheet("color: red;")
            # Leave defaults in place

        self._update_game_labels()

    def _update_game_labels(self):
        total_reps = sum(self.reps_per_channel)

        # Per-channel
        for i, name in enumerate(CHANNEL_NAMES):
            reps = self.reps_per_channel[i]
            self.channel_rep_labels[i].setText(f"{name}: {reps} reps")

        self.total_reps_label.setText(f"Total reps across fingers: {total_reps}")
        self.sessions_completed_label.setText(
            f"Game-mode sessions completed: {self.sessions_completed}"
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