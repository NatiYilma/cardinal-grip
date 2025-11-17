# host/gui/patient_dual_launcher.py #version 7

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
    QLineEdit,
)

# ---------- PATH SETUP ----------
GUI_DIR = os.path.dirname(__file__)          # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Import the two GUIs from the same folder
from patient_game_app import PatientGameWindow
from patient_app import PatientWindow

# Use the same backend type both apps expect
from comms.sim_backend import SimBackend as SerialBackend  # swap to real serial if needed


class DualPatientGameWindow(QWidget):
    """
    Side-by-side view embedding:
      - Left:  PatientGameWindow
      - Right: PatientWindow

    Features:
      - Shared SerialBackend for both (one connection).
      - Top-level Connect/Disconnect/Start/Stop controls.
      - Min/Max ADC sliders stay in sync between both windows.
      - Global invariant: Min <= Max always.
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Dual Patient View (Shared Backend)")
        self.resize(1500, 850)

        self.backend: SerialBackend | None = None
        self._current_min = None
        self._current_max = None

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # ===== TOP: Shared connection + thresholds info =====
        top_row = QHBoxLayout()
        main_layout.addLayout(top_row)

        caption = QLabel(
            "Dual view – shared backend:\n"
            "Left: Patient Game | Right: Patient Monitor.\n"
            "Use these controls for connection/session (individual connect buttons are disabled)."
        )
        caption.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        caption.setStyleSheet("font-weight: bold; padding: 4px;")
        top_row.addWidget(caption, stretch=2)

        # Shared serial controls
        self.port_edit = QLineEdit("/dev/cu.usbmodem14101")
        self.port_edit.setFixedWidth(220)
        top_row.addWidget(QLabel("Port:"))
        top_row.addWidget(self.port_edit)

        self.baud_edit = QLineEdit("115200")
        self.baud_edit.setFixedWidth(80)
        top_row.addWidget(QLabel("Baud:"))
        top_row.addWidget(self.baud_edit)

        self.connect_button = QPushButton("Connect (shared)")
        self.connect_button.clicked.connect(self.handle_connect)
        top_row.addWidget(self.connect_button)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.handle_disconnect)
        self.disconnect_button.setEnabled(False)
        top_row.addWidget(self.disconnect_button)

        self.start_button = QPushButton("Start Session")
        self.start_button.clicked.connect(self.handle_start_session)
        self.start_button.setEnabled(False)
        top_row.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Session")
        self.stop_button.clicked.connect(self.handle_stop_session)
        self.stop_button.setEnabled(False)
        top_row.addWidget(self.stop_button)

        # ===== CENTER: embedded game + patient windows =====
        center_row = QHBoxLayout()
        main_layout.addLayout(center_row, stretch=1)

        self.game_window = PatientGameWindow()
        self.patient_window = PatientWindow()

        # Embed as child widgets
        center_row.addWidget(self.game_window, stretch=1)
        center_row.addWidget(self.patient_window, stretch=1)

        # Disable individual connect buttons (we manage shared backend)
        self._disable_internal_connect_controls()

        # Threshold sync wiring (Min/Max sliders)
        self._wire_threshold_sync()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _disable_internal_connect_controls(self):
        """Disable the built-in connect/disconnect in the embedded windows."""
        for w in (self.game_window, self.patient_window):
            if hasattr(w, "connect_button"):
                w.connect_button.setEnabled(False)
            if hasattr(w, "disconnect_button"):
                w.disconnect_button.setEnabled(False)

    def _wire_threshold_sync(self):
        """
        Keep Min / Max ADC thresholds synced between both views.
        Uses a global state (self._current_min/_current_max) to enforce Min <= Max.
        """

        gw = self.game_window
        pw = self.patient_window

        have_game_min = hasattr(gw, "target_min_slider")
        have_game_max = hasattr(gw, "target_max_slider")
        have_patient_min = hasattr(pw, "target_min_slider")
        have_patient_max = hasattr(pw, "target_max_slider")

        if not (have_game_min and have_game_max and have_patient_min and have_patient_max):
            return

        # Initialize global min/max from game window
        self._current_min = gw.target_min_slider.value()
        self._current_max = gw.target_max_slider.value()
        if self._current_max < self._current_min:
            self._current_max = self._current_min
            gw.target_max_slider.setValue(self._current_max)

        # Push to patient window as initial sync
        self._set_sliders_without_feedback(self._current_min, self._current_max)

        # Hook BOTH directions
        gw.target_min_slider.valueChanged.connect(
            lambda v: self._on_slider_changed(v, source="game_min")
        )
        gw.target_max_slider.valueChanged.connect(
            lambda v: self._on_slider_changed(v, source="game_max")
        )

        pw.target_min_slider.valueChanged.connect(
            lambda v: self._on_slider_changed(v, source="patient_min")
        )
        pw.target_max_slider.valueChanged.connect(
            lambda v: self._on_slider_changed(v, source="patient_max")
        )

        # Let game window update its dashed thresholds once
        updater = getattr(gw, "_update_band_labels", None)
        if callable(updater):
            updater()

    def _on_slider_changed(self, value: int, source: str):
        """
        Handle min/max moves from either window, enforce Min <= Max,
        and push the final pair of values back to both windows.
        """
        if self._current_min is None or self._current_max is None:
            # Should not happen, but guard anyway.
            self._current_min = value
            self._current_max = value

        # Update global state
        if "min" in source:
            self._current_min = value
        else:
            self._current_max = value

        # Enforce Min <= Max
        if self._current_max < self._current_min:
            if "min" in source:
                self._current_max = self._current_min
            else:
                self._current_min = self._current_max

        # Apply back to both windows without re-triggering signals
        self._set_sliders_without_feedback(self._current_min, self._current_max)

        # Ask game window to refresh dashed lines & numeric labels if available
        updater = getattr(self.game_window, "_update_band_labels", None)
        if callable(updater):
            updater()

        # If patient window later gets its own band-label helper, call it too
        updater_p = getattr(self.patient_window, "_update_band_labels", None)
        if callable(updater_p):
            updater_p()

    def _set_sliders_without_feedback(self, tmin: int, tmax: int):
        """Set both windows' sliders while blocking valueChanged signals."""
        gw = self.game_window
        pw = self.patient_window

        for w, kind in ((gw, "game"), (pw, "patient")):
            if hasattr(w, "target_min_slider") and hasattr(w, "target_max_slider"):
                # Min
                smin = w.target_min_slider
                old1 = smin.blockSignals(True)
                smin.setValue(tmin)
                smin.blockSignals(old1)

                # Max
                smax = w.target_max_slider
                old2 = smax.blockSignals(True)
                smax.setValue(tmax)
                smax.blockSignals(old2)

    # ------------------------------------------------------------------
    # Shared connection / session control
    # ------------------------------------------------------------------
    def handle_connect(self):
        """Create a single backend and assign it to both embedded windows."""
        if self.backend is not None:
            return

        port = self.port_edit.text().strip()
        try:
            baud = int(self.baud_edit.text().strip())
        except ValueError:
            # Fall back to 115200
            baud = 115200
            self.baud_edit.setText("115200")

        try:
            self.backend = SerialBackend(port=port, baud=baud, timeout=0.01)
            self.backend.start()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Serial error", f"Failed to open {port}:\n{e}")
            self.backend = None
            return

        # Inject shared backend into both windows
        self.game_window.backend = self.backend
        self.patient_window.backend = self.backend

        # Update their status labels and buttons
        if hasattr(self.game_window, "status_label"):
            self.game_window.status_label.setText(f"Status: Connected (shared) {port} @ {baud}")
        if hasattr(self.patient_window, "status_label"):
            self.patient_window.status_label.setText(f"Status: Connected (shared) {port} @ {baud}")

        # Dual-level controls
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def handle_disconnect(self):
        """Stop session in both windows and tear down shared backend."""
        # Stop sessions first
        self.handle_stop_session()

        if self.backend is not None:
            try:
                self.backend.stop()
            except Exception:
                pass
            self.backend = None

        # Reset both windows
        if hasattr(self.game_window, "backend"):
            self.game_window.backend = None
        if hasattr(self.patient_window, "backend"):
            self.patient_window.backend = None

        if hasattr(self.game_window, "status_label"):
            self.game_window.status_label.setText("Status: Disconnected")
        if hasattr(self.patient_window, "status_label"):
            self.patient_window.status_label.setText("Status: Disconnected")

        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)

    def handle_start_session(self):
        """
        Start a session:
          - Game side: call its start_session()
          - Patient side: reset session + start its timer
        (Backend must already be connected.)
        """
        if self.backend is None:
            return

        # Game side
        if hasattr(self.game_window, "start_session"):
            self.game_window.start_session()

        # Patient side: mimic what its handle_connect does regarding timer
        if hasattr(self.patient_window, "reset_session"):
            self.patient_window.reset_session()
        if hasattr(self.patient_window, "timer"):
            self.patient_window.timer.start()
        if hasattr(self.patient_window, "status_label"):
            self.patient_window.status_label.setText("Status: Monitoring (shared backend)")

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def handle_stop_session(self):
        """
        Stop a session on both views but keep the backend alive.
        """
        # Game side
        if hasattr(self.game_window, "stop_session"):
            self.game_window.stop_session()

        # Patient side
        if hasattr(self.patient_window, "timer") and self.patient_window.timer.isActive():
            self.patient_window.timer.stop()
        if hasattr(self.patient_window, "status_label") and self.backend is not None:
            self.patient_window.status_label.setText("Status: Connected (idle)")

        self.start_button.setEnabled(self.backend is not None)
        self.stop_button.setEnabled(False)


def main():
    app = QApplication(sys.argv)
    win = DualPatientGameWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
