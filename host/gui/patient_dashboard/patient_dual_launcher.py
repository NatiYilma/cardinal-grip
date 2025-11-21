# host/gui/patient_dual_launcher.py  #version 7

"""
Dual view launcher:
  - Left:  PatientGameWindow (game mode)
  - Right: PatientWindow     (monitor / graph)

Design:
  * PatientGameWindow owns the backend and handles connect()/disconnect().
  * Dual view reuses that backend for PatientWindow (monitor).
  * ONE shared Min/Max ADC slider pair lives in the dual view and
    drives both child windows' thresholds + visuals.
"""

import os
import sys
import time
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
    QGroupBox,
    QSlider,
)

# ------------ PATH SETUP  ------------
# This file is .../cardinal-grip/host/gui/patient_dashboard/patient_dual_launcher.py
PATIENT_DASHBOARD_DIR = os.path.dirname(__file__)   # .../host/gui/patient_dashboard
GUI_DIR = os.path.dirname(PATIENT_DASHBOARD_DIR)    # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)    # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Import the existing GUIs (they already choose backend i.e. SimBackend vs SerialBackend)
from host.gui.patient_dashboard.patient_game_app import PatientGameWindow
from host.gui.patient_dashboard.patient_app import PatientWindow

from comms.serial_backend import auto_detect_port
# Optional: print available ports for debugging
# print(SerialBackend.list_ports())
# ================================================================

class DualPatientGameWindow(QWidget):
    """
    Embeds:
      - Left:  PatientGameWindow  (game mode)
      - Right: PatientWindow      (monitor + graph)

    Game window owns backend; dual view:
      * drives global connect / disconnect / start / stop
      * exposes one shared Min/Max ADC slider pair
      * pushes thresholds into both child windows.
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Dual Patient View")
        self.resize(1200, 750)
        self.setMinimumSize(1100, 700)
        print("Patient Dual Window Launched and Running")

        self.shared_backend = None
        self.current_session_id: str | None = None

        # ---------- TOP-LEVEL LAYOUT ----------
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # ===== HEADER TEXT =====
        header = QLabel(
            "Dual view – shared backend:\n"
            "Left: Patient Game | Right: Patient Monitor.\n"
            "Use these controls for connection/session (individual connect buttons are disabled)."
        )
        header.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(header)

        # ===== SHARED CONNECTION BAR =====
        # (Shared Backend)
        shared_bar = QHBoxLayout()

        shared_bar.addWidget(QLabel("Port:"))
        self.port_edit = QLineEdit("") #"/dev/cu.usbmodem14101" #"/dev/cu.usbmodem14201" #"/dev/cu.usbserial-0001"
        self.port_edit.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.port_edit.setFixedWidth(220)
        # --- Placeholder to auto-detected port, if any ---
        try:
            detected = auto_detect_port()
        except Exception:
            detected = None

        if detected:
            # This will appear as light/transparent text until user types
            self.port_edit.setPlaceholderText(detected)
        else:
            # Fallback hint if nothing is detected
            self.port_edit.setPlaceholderText("Auto-detecting port...")
        shared_bar.addWidget(self.port_edit)

        shared_bar.addWidget(QLabel("Baud:"))
        self.baud_edit = QLineEdit("115200")
        self.baud_edit.setPlaceholderText("115200") # Set BAUD rate default 115200
        self.baud_edit.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.baud_edit.setFixedWidth(80)
        self.baud_edit.setReadOnly(False)
        shared_bar.addWidget(self.baud_edit)

        self.connect_button = QPushButton("Connect (shared)")
        self.connect_button.clicked.connect(self.handle_shared_connect)
        shared_bar.addWidget(self.connect_button)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.handle_shared_disconnect)
        self.disconnect_button.setEnabled(False)
        shared_bar.addWidget(self.disconnect_button)

        self.start_button = QPushButton("Start Session")
        self.start_button.clicked.connect(self.handle_start_session)
        self.start_button.setEnabled(False)
        shared_bar.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Session")
        self.stop_button.clicked.connect(self.handle_stop_session)
        self.stop_button.setEnabled(False)
        shared_bar.addWidget(self.stop_button)

        shared_bar.addStretch(1)
        main_layout.addLayout(shared_bar)

        # ===== SHARED TARGET ZONE CONTROLS (ONE PAIR OF SLIDERS) =====
        band_group = QGroupBox("Shared Target Zone (applies to ALL fingers in BOTH views)")
        band_layout = QHBoxLayout()
        band_group.setLayout(band_layout)

        # Min slider + numeric label
        band_layout.addWidget(QLabel("Min (ADC):"))
        self.shared_min_slider = QSlider(Qt.Orientation.Horizontal)
        self.shared_min_slider.setRange(0, 4095)
        self.shared_min_slider.setValue(1200)
        self.shared_min_slider.setMinimumWidth(260)
        band_layout.addWidget(self.shared_min_slider)

        self.shared_min_label = QLabel("1200")
        self.shared_min_label.setFixedWidth(60)
        self.shared_min_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        band_layout.addWidget(self.shared_min_label)

        # Max slider + numeric label
        band_layout.addWidget(QLabel("Max (ADC):"))
        self.shared_max_slider = QSlider(Qt.Orientation.Horizontal)
        self.shared_max_slider.setRange(0, 4095)
        self.shared_max_slider.setValue(2000)
        self.shared_max_slider.setMinimumWidth(260)
        band_layout.addWidget(self.shared_max_slider)

        self.shared_max_label = QLabel("2000")
        self.shared_max_label.setFixedWidth(60)
        self.shared_max_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        band_layout.addWidget(self.shared_max_label)

        band_hint = QLabel("Stay in the green zone for 5 s to earn a rep (game view).")
        band_layout.addWidget(band_hint)

        main_layout.addWidget(band_group)

        # ===== STATUS LINE =====
        self.status_label = QLabel("Status: Not connected")
        self.status_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(self.status_label)

        # ===== CENTER: TWO CHILD WINDOWS SIDE-BY-SIDE =====
        center_row = QHBoxLayout()
        main_layout.addLayout(center_row, stretch=1)

        # ----- Left group: Patient Game -----
        left_group = QGroupBox("Patient Game View")
        left_layout = QVBoxLayout()
        left_group.setLayout(left_layout)

        self.game_window = PatientGameWindow()
        self.game_window.setParent(self)

        # Hide local connection/session controls: dual view owns them
        self.game_window.connect_button.hide()
        self.game_window.disconnect_button.hide()
        self.game_window.start_button.hide()
        self.game_window.stop_button.hide()

        # Hide the game window's own Min/Max sliders; they are driven by shared ones
        try:
            self.game_window.target_min_slider.hide()
            self.game_window.target_max_slider.hide()
            # optional numeric labels if present
            if hasattr(self.game_window, "target_min_value_label"):
                self.game_window.target_min_value_label.hide()
            if hasattr(self.game_window, "target_max_value_label"):
                self.game_window.target_max_value_label.hide()
        except Exception:
            pass

        left_layout.addWidget(self.game_window)
        center_row.addWidget(left_group, stretch=1)

        # ----- Right group: Patient Monitor -----
        right_group = QGroupBox("Patient Monitor View")
        right_layout = QVBoxLayout()
        right_group.setLayout(right_layout)

        self.patient_window = PatientWindow()
        self.patient_window.setParent(self)

        self.patient_window.connect_button.hide()
        self.patient_window.disconnect_button.hide()

        # Hide the patient window's own Min/Max sliders; driven by shared ones
        try:
            self.patient_window.target_min_slider.hide()
            self.patient_window.target_max_slider.hide()
        except Exception:
            pass

        right_layout.addWidget(self.patient_window)
        center_row.addWidget(right_group, stretch=1)

        # Now that children exist, initialize them from shared sliders
        self._push_shared_thresholds_to_children()

        # Wire shared slider callbacks
        self.shared_min_slider.valueChanged.connect(self._on_shared_min_changed)
        self.shared_max_slider.valueChanged.connect(self._on_shared_max_changed)

        # ===== BOTTOM: SESSION INFO =====
        bottom_row = QHBoxLayout()
        self.session_label = QLabel("Current session: –")
        bottom_row.addWidget(self.session_label)
        bottom_row.addStretch(1)
        main_layout.addLayout(bottom_row)

    # ---------- SHARED THRESHOLD HELPERS ----------

    def _push_shared_thresholds_to_children(self):
        """Push shared Min/Max slider values into both child windows + visuals."""
        tmin = self.shared_min_slider.value()
        tmax = self.shared_max_slider.value()

        # update labels
        self.shared_min_label.setText(str(tmin))
        self.shared_max_label.setText(str(tmax))

        # Game window thresholds
        try:
            self.game_window.target_min_slider.blockSignals(True)
            self.game_window.target_max_slider.blockSignals(True)
            self.game_window.target_min_slider.setValue(tmin)
            self.game_window.target_max_slider.setValue(tmax)
            self.game_window.target_min_slider.blockSignals(False)
            self.game_window.target_max_slider.blockSignals(False)
            if hasattr(self.game_window, "_update_band_labels"):
                self.game_window._update_band_labels()
        except Exception:
            pass

        # Patient window thresholds
        try:
            self.patient_window.target_min_slider.blockSignals(True)
            self.patient_window.target_max_slider.blockSignals(True)
            self.patient_window.target_min_slider.setValue(tmin)
            self.patient_window.target_max_slider.setValue(tmax)
            self.patient_window.target_min_slider.blockSignals(False)
            self.patient_window.target_max_slider.blockSignals(False)
            if hasattr(self.patient_window, "_update_band_visuals"):
                self.patient_window._update_band_visuals()
        except Exception:
            pass

    def _on_shared_min_changed(self, value: int):
        # Enforce Min <= Max
        if value > self.shared_max_slider.value():
            self.shared_max_slider.blockSignals(True)
            self.shared_max_slider.setValue(value)
            self.shared_max_slider.blockSignals(False)
        self._push_shared_thresholds_to_children()

    def _on_shared_max_changed(self, value: int):
        # Enforce Min <= Max
        if value < self.shared_min_slider.value():
            self.shared_min_slider.blockSignals(True)
            self.shared_min_slider.setValue(value)
            self.shared_min_slider.blockSignals(False)
        self._push_shared_thresholds_to_children()

    # ---------- SHARED CONNECTION HANDLERS ----------

    def handle_shared_connect(self):
        """
        Let the game window perform its normal connect()
        and then share its backend with the patient monitor.
        """
        
        if self.shared_backend is not None:
            return

        # Push our port/baud into the game window fields, then call its connect.
        self.game_window.port_edit.setText(self.port_edit.text())
        self.game_window.baud_edit.setText(self.baud_edit.text())

        if hasattr(self.game_window, "handle_connect"):
            self.game_window.handle_connect()

        backend = getattr(self.game_window, "backend", None)
        if backend is None:
            self.status_label.setText("Status: Failed to connect (see game view).")
            return

        self.shared_backend = backend

        # Share backend with patient monitor
        self.patient_window.backend = backend
        if hasattr(self.patient_window, "reset_session"):
            self.patient_window.reset_session()
        if hasattr(self.patient_window, "timer"):
            if hasattr(self.patient_window, "start_time"):
                self.patient_window.start_time = time.time()
            self.patient_window.timer.start()

        self.status_label.setText(
            f"Status: Connected to {self.port_edit.text().strip()} @ "
            f"{self.baud_edit.text().strip()}"
        )
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        self.start_button.setEnabled(True)

    def handle_shared_disconnect(self):
        """Stop session and disconnect both child windows."""
        self.handle_stop_session()

        if hasattr(self.game_window, "handle_disconnect"):
            self.game_window.handle_disconnect()
        if hasattr(self.patient_window, "handle_disconnect"):
            self.patient_window.handle_disconnect()

        self.shared_backend = None
        self.status_label.setText("Status: Disconnected")
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.start_button.setEnabled(False)

    # ---------- SESSION CONTROL + OPTIONAL JSON LOGGING ----------

    def _make_new_session_id(self) -> str:
        return datetime.now().strftime("session_%Y%m%d_%H%M%S")

    def handle_start_session(self):
        if self.shared_backend is None:
            self.status_label.setText("Status: Cannot start – not connected.")
            return

        if hasattr(self.game_window, "start_session"):
            self.game_window.start_session()

        if hasattr(self.patient_window, "reset_session"):
            self.patient_window.reset_session()

        sid = self._make_new_session_id()
        self.current_session_id = sid
        self.session_label.setText(f"Current session: {sid}")

        if hasattr(self.game_window, "set_external_session_id"):
            self.game_window.set_external_session_id(sid)
        if hasattr(self.patient_window, "set_external_session_id"):
            self.patient_window.set_external_session_id(sid)

        if hasattr(self.game_window, "begin_session_logging"):
            self.game_window.begin_session_logging(sid, source="dual_view")
        if hasattr(self.patient_window, "begin_session_logging"):
            self.patient_window.begin_session_logging(sid, source="dual_view")

        self.status_label.setText(
            "Status: Session running (shared backend; shared target zone)."
        )
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def handle_stop_session(self):
        if hasattr(self.game_window, "stop_session"):
            self.game_window.stop_session()

        if hasattr(self.patient_window, "end_session_logging"):
            self.patient_window.end_session_logging()
        if hasattr(self.game_window, "end_session_logging"):
            self.game_window.end_session_logging()

        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(self.shared_backend is not None)
        self.status_label.setText("Status: Session stopped")
        self.session_label.setText("Current session: –")
        self.current_session_id = None

    # ---------- KEYBOARD EVENTS (FOR SIM BACKEND) ----------

    def keyPressEvent(self, event):
        """Forward key events to the game window so SimBackend keyboard control works."""
        self.game_window.keyPressEvent(event)

    def keyReleaseEvent(self, event):
        self.game_window.keyReleaseEvent(event)


def main():
    app = QApplication(sys.argv)
    win = DualPatientGameWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
