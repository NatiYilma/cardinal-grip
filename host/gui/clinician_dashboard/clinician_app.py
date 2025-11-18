## host/gui/clinician_app.py #version 7


## Clinician viewer for offline analysis.
## - Loads CSVs produced by patient_app.py (time_s, ch0_adc, ..., ch3_adc)
## - "Load latest" button finds the newest CSV in data/logs
## - Plots up to 4 channels over time with toggles
## - Shows basic stats (min, max, mean) per channel
## - Adds Min/Max ADC controls with dashed horizontal lines on the plot
##
## NOTE: Thresholds are set manually in this app (CSV currently does not store them).

import os
import sys
import csv
from glob import glob
from statistics import mean

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

# ------------ PATH SETUP ------------
GUI_DIR = os.path.dirname(__file__)          # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

NUM_CHANNELS = 4
CHANNEL_NAMES = ["Digitus Indicis", "Digitus Medius", "Digitus Annularis", "Digitus Minimus"]


class ClinicianWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Clinician Viewer")
        self.resize(1200, 800)

        self.time: list[float] = []
        self.channel_data: list[list[int]] = [[] for _ in range(NUM_CHANNELS)]
        self.loaded_path: str | None = None

        # Logical thresholds for overlay
        self.tmin = 1200
        self.tmax = 2000

        # ---------- MAIN LAYOUT ----------
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

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
        stats_group = QGroupBox("Basic statistics (per channel, all samples)")
        stats_layout = QVBoxLayout()
        stats_group.setLayout(stats_layout)

        self.stats_labels: list[QLabel] = []
        for c in range(NUM_CHANNELS):
            lbl = QLabel(f"Ch{c}: min –  max –  mean –")
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
        self._load_csv(latest_path)

    def _load_csv(self, path: str):
        """
        Load a CSV produced by patient_app.py:
            time_s, ch0_adc, ch1_adc, ch2_adc, ch3_adc
        """
        try:
            with open(path, "r", newline="") as f:
                reader = csv.reader(f)
                header = next(reader, None)

                if header is None:
                    raise ValueError("CSV file is empty")

                name_to_idx = {name: i for i, name in enumerate(header)}

                def col_index(name, default):
                    return name_to_idx.get(name, default)

                t_idx = col_index("time_s", 0)
                ch_idx = [
                    col_index("ch0_adc", 1),
                    col_index("ch1_adc", 2),
                    col_index("ch2_adc", 3),
                    col_index("ch3_adc", 4),
                ]

                times: list[float] = []
                channels: list[list[int]] = [[] for _ in range(NUM_CHANNELS)]

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
                            v = int(float(row[ch_idx[c]]))
                        except (ValueError, IndexError):
                            v = 0
                        channels[c].append(v)

            self.time = times
            self.channel_data = channels
            self.loaded_path = path

            base = os.path.basename(path)
            self.file_label.setText(f"Loaded: {base}")
            self.file_label.setStyleSheet("color: black;")

            self.update_plot()
            self.update_stats()

        except Exception as e:
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
        if not self.time:
            for curve in self.curves:
                curve.setData([], [])
            return

        visible_any = False
        for c in range(NUM_CHANNELS):
            if self.channel_checkboxes[c].isChecked():
                self.curves[c].setData(self.time, self.channel_data[c])
                visible_any = True
            else:
                self.curves[c].setData([], [])

        if visible_any:
            self.plot_widget.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)

        self.update_stats()

    def update_stats(self):
        """
        Compute min / max / mean for each channel and update labels.
        """
        if not self.time or not self.channel_data:
            for c in range(NUM_CHANNELS):
                self.stats_labels[c].setText(f"Ch{c}: min –  max –  mean –")
            return

        for c in range(NUM_CHANNELS):
            data = self.channel_data[c]
            if not data:
                self.stats_labels[c].setText(f"Ch{c}: min –  max –  mean –")
                continue

            mn = min(data)
            mx = max(data)
            avg = mean(data)
            self.stats_labels[c].setText(
                f"Ch{c}: min {mn:.0f}   max {mx:.0f}   mean {avg:.1f}"
            )


def main():
    app = QApplication(sys.argv)
    win = ClinicianWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
