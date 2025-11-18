# host/gui/patient_dashboard/patient_dashboard.py

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
# This file lives at: .../cardinal-grip/host/gui/patient_dashboard/patient_dashboard.py
THIS_DIR = os.path.dirname(__file__)                 # .../host/gui/patient_dashboard
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", "..", ".."))  # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# ---------- IMPORT EXISTING WINDOWS ----------
# File tree:
#   host/gui/patient_dashboard/patient_game.py
#   host/gui/patient_dashboard/patient_app.py
#   host/gui/patient_dashboard/patient_dual_launcher.py
#   host/gui/dashboard_calendar.py

from host.gui.patient_dashboard.patient_game_app import PatientGameWindow
from host.gui.patient_dashboard.patient_app import PatientWindow
from host.gui.patient_dashboard.patient_dual_launcher import DualPatientGameWindow
from host.gui.dashboard_calendar import DashboardWindow


class PatientDashboardWindow(QWidget):
    """
    Home screen for the patient side:
      - Launch game
      - Launch monitor
      - Launch dual view
      - Open exercise calendar
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Cardinal Grip – Patient Dashboard")
        self.resize(800, 500)
        self.setMinimumSize(700, 420)

        # Child windows (lazy-created when first opened)
        self.game_window: PatientGameWindow | None = None
        self.monitor_window: PatientWindow | None = None
        self.dual_window: DualPatientGameWindow | None = None
        self.calendar_window: DashboardWindow | None = None

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # ----- Title -----
        title = QLabel("Patient Home")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        main_layout.addWidget(title)

        subtitle = QLabel("Choose what you’d like to do today:")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: gray;")
        main_layout.addWidget(subtitle)

        main_layout.addSpacerItem(
            QSpacerItem(0, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )

        # ----- Main button grid -----
        buttons_group = QGroupBox()
        buttons_layout = QHBoxLayout()
        buttons_group.setLayout(buttons_layout)

        # Left column (exercise-related)
        left_col = QVBoxLayout()

        btn_game = QPushButton("▶ Play Exercise Game")
        btn_game.setMinimumHeight(50)
        btn_game.setStyleSheet("font-size: 14pt;")
        btn_game.clicked.connect(self.open_game)
        left_col.addWidget(btn_game)

        btn_monitor = QPushButton("📈 Live Finger Monitor")
        btn_monitor.setMinimumHeight(50)
        btn_monitor.setStyleSheet("font-size: 14pt;")
        btn_monitor.clicked.connect(self.open_monitor)
        left_col.addWidget(btn_monitor)

        buttons_layout.addLayout(left_col)

        # Right column (overview & advanced)
        right_col = QVBoxLayout()

        btn_dual = QPushButton("🖥️ Game + Monitor (Dual View)")
        btn_dual.setMinimumHeight(50)
        btn_dual.setStyleSheet("font-size: 14pt;")
        btn_dual.clicked.connect(self.open_dual)
        right_col.addWidget(btn_dual)

        btn_calendar = QPushButton("📅 Exercise Calendar")
        btn_calendar.setMinimumHeight(50)
        btn_calendar.setStyleSheet("font-size: 14pt;")
        btn_calendar.clicked.connect(self.open_calendar)
        right_col.addWidget(btn_calendar)

        buttons_layout.addLayout(right_col)

        main_layout.addWidget(buttons_group)
        main_layout.addStretch(1)

        # Footer
        footer = QLabel("Tip: use the Exercise Calendar to see streaks and missed days.")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: gray;")
        main_layout.addWidget(footer)

    # ----- Launchers -----

    def _show_window(self, attr_name, cls):
        """Utility: lazily create & show a child window."""
        win = getattr(self, attr_name)
        if win is None:
            win = cls()
            setattr(self, attr_name, win)
        win.show()
        win.raise_()
        win.activateWindow()

    def open_game(self):
        self._show_window("game_window", PatientGameWindow)

    def open_monitor(self):
        self._show_window("monitor_window", PatientWindow)

    def open_dual(self):
        self._show_window("dual_window", DualPatientGameWindow)

    def open_calendar(self):
        self._show_window("calendar_window", DashboardWindow)


def main():
    app = QApplication(sys.argv)
    win = PatientDashboardWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
