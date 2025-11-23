# host/gui/patient_dashboard/patient_dual_launcher.py

"""
Dual view launcher:
  - Left:  PatientGameWindow (game mode)
  - Right: PatientWindow     (monitor / graph)

Design:
  * PatientGameWindow owns the backend and handles connect()/disconnect().
  * Dual view reuses that backend for PatientWindow (monitor).
  * ONE shared Min/Max ADC slider pair lives in the dual view and
    drives both child windows' thresholds + visuals.
  * Session logging:
      - PatientGameWindow is constructed with log_to_json=False so it does NOT
        log a "game" session row on stop.
      - DualPatientGameWindow logs a single combined "dual" session row into
        sessions_log.json / sessions_index.db using the shared session_id.
"""

import os
import sys
import time
import logging
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

from logger.app_logging import configure_logging

# ------------ PATH SETUP  ------------
# This file is .../cardinal-grip/host/gui/patient_dashboard/patient_dual_launcher.py
PATIENT_DASHBOARD_DIR = os.path.dirname(__file__)   # .../host/gui/patient_dashboard
GUI_DIR = os.path.dirname(PATIENT_DASHBOARD_DIR)    # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)                 # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)            # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Logging setup constants (configure_logging is only called in main())
LOG_DIR = os.path.join(PROJECT_ROOT, "logger")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "cardinal_grip.log")

logger = logging.getLogger("cardinal_grip.gui.patient_dual")

# Import the existing GUIs (they already choose backend i.e. SimBackend vs SerialBackend)
from host.gui.patient_dashboard.patient_game_app import PatientGameWindow
from host.gui.patient_dashboard.patient_app import PatientWindow

from comms.serial_backend import auto_detect_port

# Shared JSON+SQLite session logging for the dual view
from host.gui.common.session_logging import log_session_completion
from host.gui.common.instance_tracker import InstanceTrackerMixin
# ================================================================


class DualPatientGameWindow(InstanceTrackerMixin, QWidget):
    """
    Embeds:
      - Left:  PatientGameWindow  (game mode)
      - Right: PatientWindow      (monitor + graph)

    Game window owns backend; dual view:
      * drives global connect / disconnect / start / stop
      * exposes one shared Min/Max ADC slider pair
      * pushes thresholds into both child windows.
      * logs a single combined "dual" session row on stop.
    """

    def __init__(self, parent=None):
        # InstanceTrackerMixin will call QWidget.__init__ via super()
        super().__init__(parent)

        self.setWindowTitle("Cardinal Grip – Dual Patient View")
        self.resize(1200, 750)
        self.setMinimumSize(1100, 700)

        logger.info(
            "PatientDualWindow #%d created (active=%d, lifetime=%d)",
            self.instance_id,
            type(self).active_count(),
            type(self).lifetime_count(),
        )

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
        self.port_edit = QLineEdit("")
        self.port_edit.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.port_edit.setFixedWidth(220)
        # --- Placeholder to auto-detected port, if any ---
        try:
            detected = auto_detect_port()
        except Exception:
            logger.exception("auto_detect_port failed in dual launcher")
            detected = None

        if detected:
            self.port_edit.setPlaceholderText(detected)
        else:
            self.port_edit.setPlaceholderText("Auto-detecting port...")
        shared_bar.addWidget(self.port_edit)

        shared_bar.addWidget(QLabel("Baud:"))
        self.baud_edit = QLineEdit("115200")
        self.baud_edit.setPlaceholderText("115200")
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

        # Construct game window with log_to_json=False so dual window controls logging
        self.game_window = PatientGameWindow(self, log_to_json=False)

        # Hide local connection/session controls: dual view owns them
        self.game_window.connect_button.hide()
        self.game_window.disconnect_button.hide()
        self.game_window.start_button.hide()
        self.game_window.stop_button.hide()

        # Hide the game window's own Min/Max sliders; they are driven by shared ones
        try:
            self.game_window.target_min_slider.hide()
            self.game_window.target_max_slider.hide()
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

        self.patient_window = PatientWindow(self)

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
            logger.warning(
                "PatientDualWindow #%d (active=%d, lifetime=%d) failed to connect: game_window.backend is None",
                self.instance_id,
                type(self).active_count(),
                type(self).lifetime_count(),
            )
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

        logger.info(
            "PatientDualWindow #%d is Connected (active=%d, lifetime=%d)",
            self.instance_id,
            type(self).active_count(),
            type(self).lifetime_count(),
        )

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

        logger.info(
            "PatientDualWindow #%d is Disconnected (active=%d, lifetime=%d)",
            self.instance_id,
            type(self).active_count(),
            type(self).lifetime_count(),
        )

    # ---------- SESSION CONTROL + JSON LOGGING ----------

    def _make_new_session_id(self) -> str:
        return datetime.now().strftime("dual_%Y%m%d_%H%M%S")

    def handle_start_session(self):
        if self.shared_backend is None:
            self.status_label.setText("Status: Cannot start – not connected.")
            logger.warning(
                "PatientDualWindow #%d (active=%d, lifetime=%d) tried to start session without backend",
                self.instance_id,
                type(self).active_count(),
                type(self).lifetime_count(),
            )
            return

        # Shared session id for dual view
        sid = self._make_new_session_id()
        self.current_session_id = sid

        # Push id into game window so its internal state knows about it
        self.game_window.current_session_id = sid

        if hasattr(self.game_window, "start_session"):
            self.game_window.start_session()

        if hasattr(self.patient_window, "reset_session"):
            self.patient_window.reset_session()

        self.session_label.setText(f"Current session: {sid}")

        self.status_label.setText(
            "Status: Session running (shared backend; shared target zone)."
        )
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        logger.info(
            "PatientDualWindow #%d Session Started (id=%s, active=%d, lifetime=%d)",
            self.instance_id,
            sid,
            type(self).active_count(),
            type(self).lifetime_count(),
        )

    def handle_stop_session(self):
        """
        Stop both views and log a single combined dual session row if we have data.
        """
        sid = self.current_session_id

        # Stop game window (this will NOT log JSON because log_to_json=False)
        if hasattr(self.game_window, "stop_session"):
            self.game_window.stop_session()

        # Stop patient monitor timer (if it's still running)
        if hasattr(self.patient_window, "timer") and self.patient_window.timer.isActive():
            self.patient_window.timer.stop()

        # Log a combined session if we have an id and game stats
        try:
            # Use the game's cumulative reps_per_channel and combo_reps
            reps = getattr(self.game_window, "reps_per_channel", None)
            combo_reps = getattr(self.game_window, "combo_reps", 0)

            # If no session id (e.g., someone hit stop without start), fabricate one
            if sid is None:
                sid = self._make_new_session_id()

            # Only log if we actually have reps list
            log_session_completion(
                mode="dual",
                source="patient_dual_launcher",
                reps_per_channel=reps,
                combo_reps=combo_reps,
                csv_path=None,
                timestamp=datetime.now(),
                session_id=sid,
            )
            logger.info(
                "PatientDualWindow #%d logged dual session (id=%s, reps=%s, combo=%s)",
                self.instance_id,
                sid,
                reps,
                combo_reps,
            )
        except Exception:
            logger.exception(
                "PatientDualWindow #%d failed to log dual session (id=%s)",
                self.instance_id,
                sid,
            )

        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(self.shared_backend is not None)
        self.status_label.setText("Status: Session stopped")
        self.session_label.setText("Current session: –")

        logger.info(
            "PatientDualWindow #%d Session Stopped (id=%s)",
            self.instance_id,
            self.current_session_id,
        )
        self.current_session_id = None

    # ---------- KEYBOARD EVENTS (FOR SIM BACKEND) START ----------

    def keyPressEvent(self, event):
        """Forward key events to the game window so SimBackend keyboard control works."""
        self.game_window.keyPressEvent(event)

    def keyReleaseEvent(self, event):
        self.game_window.keyReleaseEvent(event)

    # ---------- KEYBOARD EVENTS (FOR SIM BACKEND) END ----------

    # ---------- Patient Dual Window Instance Close ----------

    def closeEvent(self, event):
        # Ensure we cleanly disconnect backend/timer if still active; avoid zombie threads
        if self.shared_backend is not None:
            self.handle_shared_disconnect()

        logger.info(
            "PatientDualWindow #%d closeEvent called (active=%d)",
            self.instance_id,
            type(self).active_count(),
        )
        # Do NOT touch counters here; InstanceTrackerMixin will update on destroyed.
        super().closeEvent(event)


def main():
    configure_logging(LOG_FILE)
    logger.info("Dual Patient Qt App Launching")

    app = QApplication(sys.argv)
    win = DualPatientGameWindow()
    win.show()
    logger.info("Dual Patient Qt App Launched")

    exit_code = app.exec()

    logger.info("Dual Patient Qt App Closed with exit code %d", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
