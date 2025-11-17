# # host/gui/patient_dual_launcher.py

# import sys
# from PyQt6.QtWidgets import QApplication

# from patient_app import PatientWindow
# from patient_game_app import PatientGameWindow
# from comms.sim_backend import SimBackend as SerialBackend
# # For real hardware, you’d instead:
# # from comms.serial_backend import SerialBackend

# def main():
#     app = QApplication(sys.argv)

#     # Shared backend instance
#     backend = SerialBackend(port="/dev/cu.usbmodem14101", baud=115200, timeout=0.01)
#     backend.start()

#     # Both windows share backend; they do NOT own it
#     patient_win = PatientWindow(backend=backend, owns_backend=False)
#     game_win = PatientGameWindow(backend=backend, owns_backend=False)

#     patient_win.show()
#     game_win.show()

#     app.exec()

#     # Clean shutdown
#     backend.stop()

# if __name__ == "__main__":
#     main()


#########===================== PATIENT DUAL GUI V2 ==============================##########

# host/gui/patient_dual_launcher.py

# import sys
# from PyQt6.QtWidgets import QApplication

# from patient_app import PatientWindow
# from patient_game_app import PatientGameWindow
# from comms.sim_backend import SimBackend as SerialBackend
# # For real hardware, you’d instead use:
# # from comms.serial_backend import SerialBackend


# def main():
#     app = QApplication(sys.argv)

#     # ---------- Shared backend for BOTH windows ----------
#     # One SimBackend instance so keyboard input drives both UIs.
#     backend = SerialBackend(port="/dev/cu.usbmodem14101", baud=115200, timeout=0.01)
#     backend.start()

#     # Both windows share the backend; they do NOT own/stop it.
#     patient_win = PatientWindow(backend=backend, owns_backend=False)
#     game_win = PatientGameWindow(backend=backend, owns_backend=False)

#     # ---------- Sync Min/Max ADC sliders between the two GUIs ----------

#     def sync_min_from_patient(val: int):
#         # Update game slider if different, without re-triggering its signals
#         if game_win.target_min_slider.value() != val:
#             game_win.target_min_slider.blockSignals(True)
#             game_win.target_min_slider.setValue(val)
#             game_win.target_min_slider.blockSignals(False)

#     def sync_min_from_game(val: int):
#         if patient_win.target_min_slider.value() != val:
#             patient_win.target_min_slider.blockSignals(True)
#             patient_win.target_min_slider.setValue(val)
#             patient_win.target_min_slider.blockSignals(False)

#     def sync_max_from_patient(val: int):
#         if game_win.target_max_slider.value() != val:
#             game_win.target_max_slider.blockSignals(True)
#             game_win.target_max_slider.setValue(val)
#             game_win.target_max_slider.blockSignals(False)

#     def sync_max_from_game(val: int):
#         if patient_win.target_max_slider.value() != val:
#             patient_win.target_max_slider.blockSignals(True)
#             patient_win.target_max_slider.setValue(val)
#             patient_win.target_max_slider.blockSignals(False)

#     # Connect signals both ways
#     patient_win.target_min_slider.valueChanged.connect(sync_min_from_patient)
#     game_win.target_min_slider.valueChanged.connect(sync_min_from_game)

#     patient_win.target_max_slider.valueChanged.connect(sync_max_from_patient)
#     game_win.target_max_slider.valueChanged.connect(sync_max_from_game)

#     # Start with the same values (take patient as canonical initial source)
#     game_win.target_min_slider.setValue(patient_win.target_min_slider.value())
#     game_win.target_max_slider.setValue(patient_win.target_max_slider.value())

#     # ---------- Sync "connection" when Game Session starts ----------

#     def ensure_both_running():
#         """
#         When the game session is started:
#         - Mirror port/baud settings from game window into patient window (for consistency).
#         - Call handle_connect() on both windows so they start their timers using the shared backend.
#         """
#         # Mirror serial settings visually
#         patient_win.port_edit.setText(game_win.port_edit.text())
#         patient_win.baud_edit.setText(game_win.baud_edit.text())

#         # For shared backend: handle_connect() should treat existing backend as "already open"
#         # and just start timers / update status, because owns_backend=False.
#         if game_win.backend is not None:
#             game_win.handle_connect()
#         if patient_win.backend is not None:
#             patient_win.handle_connect()

#     # Hook into the game window's Start Session button, *before* its own slot runs.
#     game_win.start_button.clicked.connect(ensure_both_running)

#     # ---------- Show both windows ----------
#     patient_win.show()
#     game_win.show()

#     app.exec()

#     # Clean shutdown: the launcher owns the backend instance
#     backend.stop()


# if __name__ == "__main__":
#     main()

#########===================== PATIENT DUAL GUI V3 ==============================##########
# host/gui/patient_dual_launcher.py

# import sys
# from PyQt6.QtWidgets import QApplication

# from patient_app import PatientWindow
# from patient_game_app import PatientGameWindow
# from comms.sim_backend import SimBackend as SerialBackend
# # For real hardware, you’d instead use:
# # from comms.serial_backend import SerialBackend


# def main():
#     app = QApplication(sys.argv)

#     # ---------- Shared backend for BOTH windows ----------
#     # Single backend instance so keyboard input + data are shared.
#     backend = SerialBackend(port="/dev/cu.usbmodem14101", baud=115200, timeout=0.01)
#     backend.start()

#     # Both windows share backend; they do NOT own/stop it themselves.
#     # (Assumes PatientWindow / PatientGameWindow accept backend, owns_backend)
#     patient_win = PatientWindow(backend=backend, owns_backend=False)
#     game_win = PatientGameWindow(backend=backend, owns_backend=False)

#     # ---------- Min/Max ADC slider sync (both directions) ----------

#     def sync_min_from_patient(val: int):
#         # Patient → Game
#         if game_win.target_min_slider.value() != val:
#             game_win.target_min_slider.blockSignals(True)
#             game_win.target_min_slider.setValue(val)
#             game_win.target_min_slider.blockSignals(False)
#             game_win.target_min_slider.update()
#             # Update any game-side band visuals / labels
#             if hasattr(game_win, "_update_band_labels"):
#                 game_win._update_band_labels()

#     def sync_min_from_game(val: int):
#         # Game → Patient
#         if patient_win.target_min_slider.value() != val:
#             patient_win.target_min_slider.blockSignals(True)
#             patient_win.target_min_slider.setValue(val)
#             patient_win.target_min_slider.blockSignals(False)
#             patient_win.target_min_slider.update()
#             # If you later add a similar helper in patient_app, this will call it
#             if hasattr(patient_win, "_update_band_labels"):
#                 patient_win._update_band_labels()

#     def sync_max_from_patient(val: int):
#         # Patient → Game
#         if game_win.target_max_slider.value() != val:
#             game_win.target_max_slider.blockSignals(True)
#             game_win.target_max_slider.setValue(val)
#             game_win.target_max_slider.blockSignals(False)
#             game_win.target_max_slider.update()
#             if hasattr(game_win, "_update_band_labels"):
#                 game_win._update_band_labels()

#     def sync_max_from_game(val: int):
#         # Game → Patient
#         if patient_win.target_max_slider.value() != val:
#             patient_win.target_max_slider.blockSignals(True)
#             patient_win.target_max_slider.setValue(val)
#             patient_win.target_max_slider.blockSignals(False)
#             patient_win.target_max_slider.update()
#             if hasattr(patient_win, "_update_band_labels"):
#                 patient_win._update_band_labels()

#     # Wire signals BOTH ways
#     # patient → game
#     patient_win.target_min_slider.valueChanged.connect(sync_min_from_patient)
#     patient_win.target_max_slider.valueChanged.connect(sync_max_from_patient)

#     # game → patient
#     game_win.target_min_slider.valueChanged.connect(sync_min_from_game)
#     game_win.target_max_slider.valueChanged.connect(sync_max_from_game)

#     # Start with the same values (take game or patient as canonical; here: game)
#     patient_win.target_min_slider.setValue(game_win.target_min_slider.value())
#     patient_win.target_max_slider.setValue(game_win.target_max_slider.value())

#     # ---------- Sync connection when Game Session starts ----------

#     def ensure_both_connected():
#         """
#         When the game session is started:
#         - Copy port/baud from game → patient for consistency.
#         - Call handle_connect() on both windows so they start their timers
#           with the shared backend.
#         """
#         patient_win.port_edit.setText(game_win.port_edit.text())
#         patient_win.baud_edit.setText(game_win.baud_edit.text())

#         # In shared-backend mode, handle_connect() should just start timers
#         # / update status when backend is already present.
#         if game_win.backend is not None:
#             game_win.handle_connect()
#         if patient_win.backend is not None:
#             patient_win.handle_connect()

#     # Hook this into the game window's Start Session button
#     game_win.start_button.clicked.connect(ensure_both_connected)

#     # ---------- Show both windows ----------
#     patient_win.show()
#     game_win.show()

#     app.exec()

#     # Clean shutdown: launcher owns the backend
#     backend.stop()


# if __name__ == "__main__":
#     main()


#########===================== PATIENT DUAL GUI V4 ==============================##########

# host/gui/dual_patient_game_app.py

import os
import sys
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
)

GUI_DIR = os.path.dirname(__file__)
HOST_DIR = os.path.dirname(GUI_DIR)
PROJECT_ROOT = os.path.dirname(HOST_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from comms.sim_backend import SimBackend as SerialBackend
from host.gui.patient_game_app import PatientGameWindow
from host.gui.patient_app import PatientWindow

class DualPatientGameWindow(QWidget):
    """
    Dual view:
      - Left: PatientGameWindow (game)
      - Right: PatientWindow (multi-channel graph)
    Uses one shared backend and one shared session_id for logging.
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Dual (Game + Patient)")
        self.resize(1800, 900)

        self.backend: SerialBackend | None = None

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # ===== TOP CONTROL BAR =====
        control_row = QHBoxLayout()

        control_row.addWidget(QLabel("Serial port:"))
        self.port_edit = QLineEdit("/dev/cu.usbmodem14101")
        self.port_edit.setFixedWidth(220)
        control_row.addWidget(self.port_edit)

        control_row.addWidget(QLabel("Baud:"))
        self.baud_edit = QLineEdit("115200")
        self.baud_edit.setFixedWidth(80)
        control_row.addWidget(self.baud_edit)

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.handle_connect)
        control_row.addWidget(self.connect_button)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.handle_disconnect)
        self.disconnect_button.setEnabled(False)
        control_row.addWidget(self.disconnect_button)

        self.start_button = QPushButton("Start Session")
        self.start_button.clicked.connect(self.handle_start_session)
        self.start_button.setEnabled(False)
        control_row.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Session")
        self.stop_button.clicked.connect(self.handle_stop_session)
        self.stop_button.setEnabled(False)
        control_row.addWidget(self.stop_button)

        main_layout.addLayout(control_row)

        # ===== CENTER: two sub-windows side by side =====
        center_row = QHBoxLayout()

        # Game window (does NOT own backend in dual mode)
        self.game_window = PatientGameWindow(
            backend=None,
            owns_backend=False,
        )
        # Hide its own connection buttons (we control from top bar)
        self.game_window.connect_button.hide()
        self.game_window.disconnect_button.hide()
        self.game_window.start_button.hide()
        self.game_window.stop_button.hide()

        # Patient window (also non-owning backend)
        self.patient_window = PatientWindow(
            backend=None,
            owns_backend=False,
        )
        self.patient_window.connect_button.hide()
        self.patient_window.disconnect_button.hide()

        center_row.addWidget(self.game_window, stretch=1)
        center_row.addWidget(self.patient_window, stretch=1)

        main_layout.addLayout(center_row)

        # Simple status label (optional)
        self.dual_status = QLabel("Dual status: Not connected")
        self.dual_status.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(self.dual_status)

        # Capture keyboard for sim backend
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ===== CONNECTION HANDLERS =====

    def handle_connect(self):
        if self.backend is not None:
            return

        port = self.port_edit.text().strip()
        try:
            baud = int(self.baud_edit.text().strip())
        except ValueError:
            baud = 115200

        try:
            self.backend = SerialBackend(port=port, baud=baud, timeout=0.01)
            self.backend.start()
        except Exception as e:
            self.dual_status.setText(f"Dual status: Serial error – {e}")
            self.backend = None
            return

        # Share backend with both windows
        self.game_window.backend = self.backend
        self.game_window.owns_backend = False
        self.patient_window.backend = self.backend
        self.patient_window.owns_backend = False

        # Let each window know about shared connection
        self.game_window.handle_connect()
        self.patient_window.handle_connect()

        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        self.start_button.setEnabled(True)
        self.dual_status.setText(
            f"Dual status: Connected to {port} @ {baud}"
        )

    def handle_disconnect(self):
        # Stop any running session
        self.handle_stop_session()

        if self.backend is not None:
            self.backend.stop()
            self.backend = None

        self.game_window.backend = None
        self.patient_window.backend = None

        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)

        self.dual_status.setText("Dual status: Disconnected")

    # ===== SESSION CONTROL (shared session_id) =====

    def handle_start_session(self):
        if self.backend is None:
            return

        # Shared session id for game+patient logs
        shared_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Push shared id into both windows
        self.game_window.set_external_session_id(shared_id)
        self.patient_window.set_external_session_id(shared_id)

        # Begin logging in patient window
        self.patient_window.begin_session_logging()
        # Start game session (this also sets up its own per-session logging)
        self.game_window.start_session()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.dual_status.setText(f"Dual status: Session running (id={shared_id})")

    def handle_stop_session(self):
        # Stop game session (this also flushes its logs)
        self.game_window.stop_session()
        # End patient logging (flush patient logs)
        self.patient_window.end_session_logging()

        self.start_button.setEnabled(self.backend is not None)
        self.stop_button.setEnabled(False)
        if self.backend is not None:
            self.dual_status.setText("Dual status: Connected – session stopped")

    # ===== KEYBOARD FOR SIM BACKEND =====

    def keyPressEvent(self, event):
        # Forward keyboard events to game window (so its SimBackend mapping works)
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

########===================== PATIENT DUAL GUI V5 ==============================##########