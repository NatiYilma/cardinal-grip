# host/gui/clinician_dashboard/clinician_app.py 

""" 
Clinician viewer for offline analysis.
- Loads CSVs produced by patient_app.py:
      time_s, ch0_adc, ..., ch3_adc, tmin_adc, tmax_adc   (thresholds optional)
- "Load latest" button finds the newest CSV in data/logs
- Plots up to 4 channels over time with toggles
- Shows rich stats (min, max, mean, std, percentiles, % in-band) per channel
- Reads Min/Max ADC thresholds from CSV when present and syncs the controls
- Grid + hover crosshair for detailed inspection

NOTE: If CSV has no tmin/tmax columns, thresholds fall back to current spinbox values.
"""

import os
import sys
import csv
import statistics
from glob import glob
import logging
import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QCheckBox,
    QMessageBox,
    QGroupBox,
    QSpinBox,
)
from PyQt6.QtGui import QFont

import pyqtgraph as pg
import numpy as np

# ------------ PATH SETUP ------------
# This file is .../cardinal-grip/host/gui/clinician_dashboard/clinician_app.py
CLINICIAN_DASHBOARD_DIR = os.path.dirname(__file__)   # .../host/gui/clinician_dashboard
GUI_DIR = os.path.dirname(CLINICIAN_DASHBOARD_DIR)    # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)                   # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)              # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from logger.app_logging import configure_logging  # safe after sys.path tweak

NUM_CHANNELS = 4
CHANNEL_NAMES = ["Digitus Indicis", "Digitus Medius", "Digitus Annularis", "Digitus Minimus"]

# Optional patient profile shown in the header (single local patient for now)
PATIENT_PROFILE_PATH = os.path.join(PROJECT_ROOT, "data", "patient_profile.json")

# Logging: reuse same log directory + file
LOG_DIR = os.path.join(PROJECT_ROOT, "logger")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "cardinal_grip.log")

logger = logging.getLogger("cardinal_grip.gui.clinician_viewer")


def load_patient_profile() -> dict:
    """
    Load a simple patient_profile.json if present.

    Example schema:
    {
        "name": "Patient Name",
        "age":  67,
        "diagnosis": "Post-stroke right hand weakness",
        "injury_profile": ["Digitus Medius", "Digitus Annularis"]
    }
    """
    if not os.path.isfile(PATIENT_PROFILE_PATH):
        return {}
    try:
        with open(PATIENT_PROFILE_PATH, "r") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        logger.exception("Failed to load patient profile from %s", PATIENT_PROFILE_PATH)
    return {}


class ClinicianWindow(QWidget):
    def __init__(self):
        super().__init__()

        logger.info("ClinicianWindow created")

        self.setWindowTitle("Cardinal Grip – Clinician Viewer")
        self.resize(1200, 800)

        # Numeric data arrays
        self.time: np.ndarray | None = None          # shape (N,)
        self.channel_data: np.ndarray | None = None  # shape (4, N)
        self.loaded_path: str | None = None

        # Logical thresholds for overlay
        self.tmin = 1200
        self.tmax = 2000

        # ---------- MAIN LAYOUT ----------
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # ===== PATIENT INFO HEADER =====
        self.patient_label = QLabel("Patient: (no profile loaded)")
        self.patient_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.patient_label.setStyleSheet("font-weight: bold; padding: 4px;")
        main_layout.addWidget(self.patient_label)

        # Try to load profile once at startup (will be refreshed on CSV load)
        self._refresh_patient_label()

        # ===== TOP BAR: load controls =====
        top_row = QHBoxLayout()

        self.load_button = QPushButton("Load CSV…")
        self.load_button.clicked.connect(self.handle_load_csv)
        top_row.addWidget(self.load_button)

        self.load_latest_button = QPushButton("Load latest from data/logs")
        self.load_latest_button.clicked.connect(self.handle_load_latest)
        top_row.addWidget(self.load_latest_button)

        self.file_label = QLabel("No file loaded")
        self.file_label.setStyleSheet("color: gray;")
        top_row.addWidget(self.file_label, stretch=1)

        main_layout.addLayout(top_row)

        # ===== CENTER: plot + right panel =====
        center_row = QHBoxLayout()
        main_layout.addLayout(center_row, stretch=1)

        # --- Plot ---
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel("left", "Force", units="ADC")
        self.plot_widget.setLabel("bottom", "Time", units="s")
        self.plot_widget.addLegend()
        center_row.addWidget(self.plot_widget, stretch=3)

        colors = ["r", "g", "b", "y"]
        self.curves = []
        for c in range(NUM_CHANNELS):
            curve = self.plot_widget.plot(
                [], [],
                pen=pg.mkPen(colors[c % len(colors)], width=2),
                name=f"Ch{c} ({CHANNEL_NAMES[c]})",
            )
            self.curves.append(curve)

        # Threshold overlay lines (horizontal)
        self.min_line = pg.InfiniteLine(
            angle=0,
            pos=self.tmin,
            pen=pg.mkPen((150, 0, 150), width=1, style=Qt.PenStyle.DashLine),
        )
        self.max_line = pg.InfiniteLine(
            angle=0,
            pos=self.tmax,
            pen=pg.mkPen((0, 150, 150), width=1, style=Qt.PenStyle.DashLine),
        )
        self.plot_widget.addItem(self.min_line)
        self.plot_widget.addItem(self.max_line)

        # ===== PLOT ENHANCEMENTS: grid + hover crosshair =====
        self.plot_item = self.plot_widget.getPlotItem()
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)

        self.v_line = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen((150, 150, 150), width=1),
        )
        self.h_line = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen((150, 150, 150), width=1),
        )
        self.plot_item.addItem(self.v_line, ignoreBounds=True)
        self.plot_item.addItem(self.h_line, ignoreBounds=True)

        self.hover_label = QLabel("t = – s, Force = – ADC")
        self.hover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hover_label.setStyleSheet("color: gray;")
        main_layout.addWidget(self.hover_label)

        self.plot_widget.scene().sigMouseMoved.connect(self._on_plot_mouse_moved)

        # --- Right side: toggles + thresholds + stats ---
        right_panel = QVBoxLayout()
        center_row.addLayout(right_panel, stretch=1)

        # Channel visibility
        vis_group = QGroupBox("Channels")
        vis_layout = QVBoxLayout()
        vis_group.setLayout(vis_layout)

        self.channel_checkboxes: list[QCheckBox] = []
        for c in range(NUM_CHANNELS):
            cb = QCheckBox(f"Ch{c} – {CHANNEL_NAMES[c]}")
            cb.setChecked(True)
            cb.stateChanged.connect(self.update_plot)
            self.channel_checkboxes.append(cb)
            vis_layout.addWidget(cb)

        right_panel.addWidget(vis_group)

        # Threshold controls
        thresh_group = QGroupBox("Thresholds (ADC)")
        thresh_layout = QHBoxLayout()
        thresh_group.setLayout(thresh_layout)

        thresh_layout.addWidget(QLabel("Min:"))
        self.min_spin = QSpinBox()
        self.min_spin.setRange(0, 4095)
        self.min_spin.setValue(self.tmin)
        self.min_spin.valueChanged.connect(self._on_min_changed)
        thresh_layout.addWidget(self.min_spin)

        thresh_layout.addWidget(QLabel("Max:"))
        self.max_spin = QSpinBox()
        self.max_spin.setRange(0, 4095)
        self.max_spin.setValue(self.tmax)
        self.max_spin.valueChanged.connect(self._on_max_changed)
        thresh_layout.addWidget(self.max_spin)

        right_panel.addWidget(thresh_group)

        # Stats panel
        stats_group = QGroupBox("Statistics (per channel, all samples)")
        stats_layout = QVBoxLayout()
        stats_group.setLayout(stats_layout)

        self.stats_labels: list[QLabel] = []
        for c in range(NUM_CHANNELS):
            lbl = QLabel(
                f"Ch{c}: min –  max –  mean –  std –  "
                f"p25–p50–p75 –  in-band –"
            )
            lbl.setFont(QFont("Arial", 10))
            self.stats_labels.append(lbl)
            stats_layout.addWidget(lbl)

        right_panel.addWidget(stats_group)
        right_panel.addStretch(1)

        # Footer
        self.footer_label = QLabel(
            "Tip: use the Patient app to record sessions (Save CSV),\n"
            "then open them here for offline analysis."
        )
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_label.setStyleSheet("color: gray; padding-top: 6px;")
        main_layout.addWidget(self.footer_label)

    # ---------- PATIENT LABEL ----------

    def _refresh_patient_label(self):
        profile = load_patient_profile()
        if not profile:
            self.patient_label.setText("Patient: (no profile loaded)")
            return

        name = profile.get("name", "Unknown")
        age = profile.get("age", "–")
        dx = profile.get("diagnosis", "")
        problems = profile.get("injury_profile", [])

        if isinstance(problems, list):
            problems_str = ", ".join(str(p) for p in problems)
        else:
            problems_str = str(problems)

        if dx:
            text = (
                f"Patient: {name}  |  Age: {age}  |  Dx/Notes: {dx}  "
                f"|  Problem areas: {problems_str}"
            )
        else:
            text = (
                f"Patient: {name}  |  Age: {age}  "
                f"|  Problem areas: {problems_str}"
            )

        self.patient_label.setText(text)

    # ---------- HOVER HANDLER ----------

    def _on_plot_mouse_moved(self, pos):
        """
        Update crosshair + label when the mouse moves over the plot.
        """
        if self.time is None or self.time.size == 0:
            return

        if not self.plot_widget.sceneBoundingRect().contains(pos):
            return

        vb = self.plot_item.vb
        mouse_point = vb.mapSceneToView(pos)
        t = mouse_point.x()
        y = mouse_point.y()

        self.v_line.setPos(t)
        self.h_line.setPos(y)
        self.hover_label.setText(f"t = {t:0.2f} s, Force = {y:0.1f} ADC")

    # ---------- Threshold handlers ----------

    def _on_min_changed(self, value: int):
        self.tmin = value
        # Enforce tmin <= tmax
        if self.tmin > self.tmax:
            self.tmax = self.tmin
            self.max_spin.blockSignals(True)
            self.max_spin.setValue(self.tmax)
            self.max_spin.blockSignals(False)
        self.min_line.setPos(self.tmin)
        self.max_line.setPos(self.tmax)
        self.update_stats()

    def _on_max_changed(self, value: int):
        self.tmax = value
        # Enforce tmin <= tmax
        if self.tmax < self.tmin:
            self.tmin = self.tmax
            self.min_spin.blockSignals(True)
            self.min_spin.setValue(self.tmin)
            self.min_spin.blockSignals(False)
        self.min_line.setPos(self.tmin)
        self.max_line.setPos(self.tmax)
        self.update_stats()

    # ---------- CSV LOADING ----------

    def handle_load_csv(self):
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

        self._load_csv(path)

    def handle_load_latest(self):
        """
        Find the most recently modified CSV in data/logs and load it.
        """
        data_dir = os.path.join(PROJECT_ROOT, "data", "logs")
        os.makedirs(data_dir, exist_ok=True)

        csv_paths = glob(os.path.join(data_dir, "*.csv"))
        if not csv_paths:
            QMessageBox.information(
                self,
                "No logs",
                f"No CSV files found in:\n{data_dir}",
            )
            return

        latest_path = max(csv_paths, key=os.path.getmtime)
        logger.info("Loading latest CSV: %s", latest_path)
        self._load_csv(latest_path)

    def _load_csv(self, path: str):
        """
        Load a CSV produced by patient_app.py:
            time_s, ch0_adc, ch1_adc, ch2_adc, ch3_adc, [tmin_adc, tmax_adc]
        Threshold columns are optional.
        """
        logger.info("Attempting to load CSV: %s", path)
        try:
            with open(path, "r", newline="") as f:
                reader = csv.reader(f)
                header = next(reader, None)

                if header is None:
                    raise ValueError("CSV file is empty")

                name_to_idx = {name: i for i, name in enumerate(header)}

                def col_index(name, default=None):
                    return name_to_idx.get(name, default)

                t_idx = col_index("time_s", 0)
                ch_idx = [
                    col_index("ch0_adc", 1),
                    col_index("ch1_adc", 2),
                    col_index("ch2_adc", 3),
                    col_index("ch3_adc", 4),
                ]

                tmin_idx = col_index("tmin_adc", None)
                tmax_idx = col_index("tmax_adc", None)

                times: list[float] = []
                channels: list[list[float]] = [[] for _ in range(NUM_CHANNELS)]

                first_tmin = None
                first_tmax = None

                for row in reader:
                    if not row:
                        continue
                    try:
                        t = float(row[t_idx])
                    except (ValueError, IndexError):
                        continue
                    times.append(t)

                    for c in range(NUM_CHANNELS):
                        try:
                            v = float(row[ch_idx[c]])
                        except (ValueError, IndexError, TypeError):
                            v = 0.0
                        channels[c].append(v)

                    # Capture thresholds from the first row that has them
                    if first_tmin is None and tmin_idx is not None and tmin_idx < len(row):
                        try:
                            first_tmin = float(row[tmin_idx])
                        except (ValueError, TypeError):
                            pass
                    if first_tmax is None and tmax_idx is not None and tmax_idx < len(row):
                        try:
                            first_tmax = float(row[tmax_idx])
                        except (ValueError, TypeError):
                            pass

            # Convert to NumPy
            self.time = np.array(times, dtype=float)
            self.channel_data = np.array(channels, dtype=float)  # shape (4, N)
            self.loaded_path = path

            base = os.path.basename(path)
            self.file_label.setText(f"Loaded: {base}")
            self.file_label.setStyleSheet("color: black;")

            logger.info(
                "Loaded CSV %s with %d samples",
                base,
                self.time.size if self.time is not None else 0,
            )

            # If CSV contained thresholds, sync to spinboxes
            if first_tmin is not None and first_tmax is not None:
                self.min_spin.blockSignals(True)
                self.max_spin.blockSignals(True)
                self.min_spin.setValue(int(first_tmin))
                self.max_spin.setValue(int(first_tmax))
                self.min_spin.blockSignals(False)
                self.max_spin.blockSignals(False)
                # This will indirectly update tmin/tmax + overlay via _on_*_changed
                self._on_min_changed(self.min_spin.value())
                self._on_max_changed(self.max_spin.value())

            # Refresh patient label (in case profile changed while running)
            self._refresh_patient_label()

            self.update_plot()
            self.update_stats()

        except Exception as e:
            logger.exception("Failed to load CSV from %s", path)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load CSV:\n{path}\n\n{e}",
            )

    # ---------- PLOTTING & STATS ----------

    def update_plot(self):
        """
        Update the plot curves based on loaded data and channel checkboxes.
        """
        if self.time is None or self.time.size == 0 or self.channel_data is None:
            for curve in self.curves:
                curve.setData([], [])
            return

        visible_any = False
        for c in range(NUM_CHANNELS):
            if self.channel_checkboxes[c].isChecked():
                self.curves[c].setData(self.time, self.channel_data[c, :])
                visible_any = True
            else:
                self.curves[c].setData([], [])

        if visible_any:
            self.plot_widget.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)

        self.update_stats()

    def update_stats(self):
        """
        Compute min / max / mean / std / percentiles and
        % time in threshold band for each channel and update labels.
        """
        if self.time is None or self.time.size == 0 or self.channel_data is None:
            for c in range(NUM_CHANNELS):
                self.stats_labels[c].setText(
                    f"Ch{c}: min –  max –  mean –  std –  p25–p50–p75 –  in-band –"
                )
            return

        data = self.channel_data  # shape (4, N)

        for c in range(NUM_CHANNELS):
            ch = data[c, :]  # (N,)
            if ch.size == 0:
                self.stats_labels[c].setText(
                    f"Ch{c}: min –  max –  mean –  std –  p25–p50–p75 –  in-band –"
                )
                continue

            mn = float(np.min(ch))
            mx = float(np.max(ch))
            avg = float(np.mean(ch))
            std = float(np.std(ch, ddof=0))

            p25, p50, p75 = np.percentile(ch, [25, 50, 75])

            # % of samples inside threshold band
            in_band_mask = (ch >= self.tmin) & (ch <= self.tmax)
            pct_in_band = float(in_band_mask.mean() * 100.0)

            self.stats_labels[c].setText(
                f"Ch{c}: "
                f"min {mn:.0f}   max {mx:.0f}   mean {avg:.1f}   std {std:.1f}   "
                f"p25 {p25:.0f}   p50 {p50:.0f}   p75 {p75:.0f}   "
                f"in-band {pct_in_band:5.1f}%"
            )


def main():
    configure_logging(LOG_FILE)
    logger.info("Clinician Viewer Qt App Launching")

    app = QApplication(sys.argv)
    win = ClinicianWindow()
    win.show()
    logger.info("Clinician Viewer Qt App Launched")

    exit_code = app.exec()
    logger.info("Clinician Viewer Qt App Closed with exit code %d", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
