# host/gui/clinician_dashboard.py

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
)

# PATHS
# This file is .../cardinal-grip/host/gui/clinician_dashboard/clinician_dashboard.py
CLINICIAN_DASHBOARD_DIR = os.path.dirname(__file__)   # .../host/gui/clinician_dashboard
GUI_DIR = os.path.dirname(CLINICIAN_DASHBOARD_DIR)    # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)    # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# SQLite3 database
from model.db import init_db

from host.gui.clinician_dashboard.clinician_app import ClinicianWindow
from host.gui.patient_dashboard.patient_app import PatientWindow
from host.gui.dashboard_calendar import DashboardWindow


class ClinicianDashboard(QWidget):
    def __init__(self):
        super().__init__()

        init_db()  # Confirms instantiation of DB + table exists before anything else

        self.setWindowTitle("Cardinal Grip – Clinician Dashboard")
        self.resize(600, 400)

        self.clinician_win = None
        self.patient_monitor_win = None
        self.calendar_win = None

        layout = QVBoxLayout()
        self.setLayout(layout)

        title = QLabel("Clinician Dashboard")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18pt; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Open recorded sessions, monitor live grips, or review adherence."
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: gray;")
        layout.addWidget(subtitle)

        btn_clinician = QPushButton("Open Clinician Viewer (CSV analysis)")
        btn_clinician.clicked.connect(self.open_clinician)
        layout.addWidget(btn_clinician)

        btn_monitor = QPushButton("Live Patient Monitor (multi-finger)")
        btn_monitor.clicked.connect(self.open_monitor)
        layout.addWidget(btn_monitor)

        btn_calendar = QPushButton("Exercise Calendar (adherence)")
        btn_calendar.clicked.connect(self.open_calendar)
        layout.addWidget(btn_calendar)

        layout.addStretch(1)

    def open_clinician(self):
        if self.clinician_win is None:
            self.clinician_win = ClinicianWindow()
        self.clinician_win.show()
        self.clinician_win.raise_()
        self.clinician_win.activateWindow()

    def open_monitor(self):
        if self.patient_monitor_win is None:
            self.patient_monitor_win = PatientWindow()
        self.patient_monitor_win.show()
        self.patient_monitor_win.raise_()
        self.patient_monitor_win.activateWindow()

    def open_calendar(self):
        if self.calendar_win is None:
            self.calendar_win = DashboardWindow()
        self.calendar_win.show()
        self.calendar_win.raise_()
        self.calendar_win.activateWindow()


def main():
    app = QApplication(sys.argv)
    win = ClinicianDashboard()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
