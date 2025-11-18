# host/gui/patient_dashboard.py

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
)

# This file is .../cardinal-grip/host/gui/patient_dashboard/patient_dashboard.py
PATIENT_DASHBOARD_DIR = os.path.dirname(__file__)   # .../host/gui/patient_dashboard
GUI_DIR = os.path.dirname(PATIENT_DASHBOARD_DIR)    # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)    # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Import existing windows
from host.gui.patient_dashboard.patient_game_app import PatientGameWindow
from host.gui.patient_dashboard.patient_app import PatientWindow
from host.gui.patient_dashboard.patient_dual_launcher import DualPatientGameWindow
from host.gui.dashboard_calendar import DashboardWindow


class PatientDashboard(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Patient Dashboard")
        self.resize(600, 400)

        self.game_win = None
        self.patient_win = None
        self.dual_win = None
        self.calendar_win = None

        layout = QVBoxLayout()
        self.setLayout(layout)

        title = QLabel("Patient Dashboard")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18pt; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Choose what you want to do today:\n"
            "Play the game, monitor your grip, or review your exercise calendar."
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: gray;")
        layout.addWidget(subtitle)

        btn_row = QVBoxLayout()
        layout.addLayout(btn_row)

        btn_game = QPushButton("Play Game")
        btn_game.clicked.connect(self.open_game)
        btn_row.addWidget(btn_game)

        btn_monitor = QPushButton("Open Monitor (multi-finger view)")
        btn_monitor.clicked.connect(self.open_monitor)
        btn_row.addWidget(btn_monitor)

        btn_dual = QPushButton("Dual View (game + monitor side-by-side)")
        btn_dual.clicked.connect(self.open_dual)
        btn_row.addWidget(btn_dual)

        btn_calendar = QPushButton("Exercise Calendar")
        btn_calendar.clicked.connect(self.open_calendar)
        btn_row.addWidget(btn_calendar)

        layout.addStretch(1)

    # ---- Button handlers ----

    def open_game(self):
        if self.game_win is None:
            self.game_win = PatientGameWindow()
        self.game_win.show()
        self.game_win.raise_()
        self.game_win.activateWindow()

    def open_monitor(self):
        if self.patient_win is None:
            self.patient_win = PatientWindow()
        self.patient_win.show()
        self.patient_win.raise_()
        self.patient_win.activateWindow()

    def open_dual(self):
        if self.dual_win is None:
            self.dual_win = DualPatientGameWindow()
        self.dual_win.show()
        self.dual_win.raise_()
        self.dual_win.activateWindow()

    def open_calendar(self):
        if self.calendar_win is None:
            self.calendar_win = DashboardWindow()
        self.calendar_win.show()
        self.calendar_win.raise_()
        self.calendar_win.activateWindow()


def main():
    app = QApplication(sys.argv)
    win = PatientDashboard()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
