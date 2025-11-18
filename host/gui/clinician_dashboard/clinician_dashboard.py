# host/gui/clinician_dashboard/clinician_dashboard.py

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QSpacerItem,
    QSizePolicy,
)
from PyQt6.QtGui import QFont

# ---------- PATH SETUP ----------
# This file lives at: .../cardinal-grip/host/gui/clinician_dashboard/clinician_dashboard.py
THIS_DIR = os.path.dirname(__file__)                 # .../host/gui/clinician_dashboard
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", "..", ".."))  # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# ---------- IMPORT EXISTING WINDOWS ----------
# File tree:
#   host/gui/clinician_dashboard/clinician_app.py
#   host/gui/patient_dashboard/patient_dual_launcher.py
#   host/gui/dashboard_calendar.py

from host.gui.clinician_dashboard.clinician_app import ClinicianWindow
from host.gui.patient_dashboard.patient_dual_launcher import DualPatientGameWindow
from host.gui.dashboard_calendar import DashboardWindow


class ClinicianDashboardWindow(QWidget):
    """
    Home screen for clinician:
      - Launch clinician analysis viewer
      - Launch dual view (live session)
      - Open adherence calendar
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Cardinal Grip – Clinician Dashboard")
        self.resize(800, 500)
        self.setMinimumSize(700, 420)

        # Child windows
        self.clinician_window: ClinicianWindow | None = None
        self.dual_window: DualPatientGameWindow | None = None
        self.calendar_window: DashboardWindow | None = None

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # ----- Title -----
        title = QLabel("Clinician Home")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        main_layout.addWidget(title)

        subtitle = QLabel("Select a tool for review or live supervision:")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: gray;")
        main_layout.addWidget(subtitle)

        main_layout.addSpacerItem(
            QSpacerItem(0, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )

        # ----- Main buttons -----
        buttons_group = QGroupBox()
        buttons_layout = QVBoxLayout()
        buttons_group.setLayout(buttons_layout)

        btn_clinician = QPushButton("📊 Clinician Viewer (CSV / Graphs / Stats)")
        btn_clinician.setMinimumHeight(50)
        btn_clinician.setStyleSheet("font-size: 14pt;")
        btn_clinician.clicked.connect(self.open_clinician_viewer)
        buttons_layout.addWidget(btn_clinician)

        btn_dual = QPushButton("🖥️ Live Session: Game + Monitor (Dual View)")
        btn_dual.setMinimumHeight(50)
        btn_dual.setStyleSheet("font-size: 14pt;")
        btn_dual.clicked.connect(self.open_dual)
        buttons_layout.addWidget(btn_dual)

        btn_calendar = QPushButton("📅 Exercise Calendar / Adherence")
        btn_calendar.setMinimumHeight(50)
        btn_calendar.setStyleSheet("font-size: 14pt;")
        btn_calendar.clicked.connect(self.open_calendar)
        buttons_layout.addWidget(btn_calendar)

        main_layout.addWidget(buttons_group)
        main_layout.addStretch(1)

        # Footer
        footer = QLabel(
            "Tip: use the Clinician Viewer for offline CSV analysis,\n"
            "and the Dual View during live sessions with the patient."
        )
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: gray;")
        main_layout.addWidget(footer)

    # ----- Launch helpers -----

    def _show_window(self, attr_name, cls):
        win = getattr(self, attr_name)
        if win is None:
            win = cls()
            setattr(self, attr_name, win)
        win.show()
        win.raise_()
        win.activateWindow()

    def open_clinician_viewer(self):
        self._show_window("clinician_window", ClinicianWindow)

    def open_dual(self):
        self._show_window("dual_window", DualPatientGameWindow)

    def open_calendar(self):
        self._show_window("calendar_window", DashboardWindow)


def main():
    app = QApplication(sys.argv)
    win = ClinicianDashboardWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
