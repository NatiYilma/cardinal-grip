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

import sys
from PyQt6.QtWidgets import QApplication

from patient_app import PatientWindow
from patient_game_app import PatientGameWindow
from comms.sim_backend import SimBackend as SerialBackend
# For real hardware, you’d instead use:
# from comms.serial_backend import SerialBackend


def main():
    app = QApplication(sys.argv)

    # ---------- Shared backend for BOTH windows ----------
    # Single backend instance so keyboard input + data are shared.
    backend = SerialBackend(port="/dev/cu.usbmodem14101", baud=115200, timeout=0.01)
    backend.start()

    # Both windows share backend; they do NOT own/stop it themselves.
    # (Assumes PatientWindow / PatientGameWindow accept backend, owns_backend)
    patient_win = PatientWindow(backend=backend, owns_backend=False)
    game_win = PatientGameWindow(backend=backend, owns_backend=False)

    # ---------- Min/Max ADC slider sync (both directions) ----------

    def sync_min_from_patient(val: int):
        # Patient → Game
        if game_win.target_min_slider.value() != val:
            game_win.target_min_slider.blockSignals(True)
            game_win.target_min_slider.setValue(val)
            game_win.target_min_slider.blockSignals(False)
            game_win.target_min_slider.update()
            # Update any game-side band visuals / labels
            if hasattr(game_win, "_update_band_labels"):
                game_win._update_band_labels()

    def sync_min_from_game(val: int):
        # Game → Patient
        if patient_win.target_min_slider.value() != val:
            patient_win.target_min_slider.blockSignals(True)
            patient_win.target_min_slider.setValue(val)
            patient_win.target_min_slider.blockSignals(False)
            patient_win.target_min_slider.update()
            # If you later add a similar helper in patient_app, this will call it
            if hasattr(patient_win, "_update_band_labels"):
                patient_win._update_band_labels()

    def sync_max_from_patient(val: int):
        # Patient → Game
        if game_win.target_max_slider.value() != val:
            game_win.target_max_slider.blockSignals(True)
            game_win.target_max_slider.setValue(val)
            game_win.target_max_slider.blockSignals(False)
            game_win.target_max_slider.update()
            if hasattr(game_win, "_update_band_labels"):
                game_win._update_band_labels()

    def sync_max_from_game(val: int):
        # Game → Patient
        if patient_win.target_max_slider.value() != val:
            patient_win.target_max_slider.blockSignals(True)
            patient_win.target_max_slider.setValue(val)
            patient_win.target_max_slider.blockSignals(False)
            patient_win.target_max_slider.update()
            if hasattr(patient_win, "_update_band_labels"):
                patient_win._update_band_labels()

    # Wire signals BOTH ways
    # patient → game
    patient_win.target_min_slider.valueChanged.connect(sync_min_from_patient)
    patient_win.target_max_slider.valueChanged.connect(sync_max_from_patient)

    # game → patient
    game_win.target_min_slider.valueChanged.connect(sync_min_from_game)
    game_win.target_max_slider.valueChanged.connect(sync_max_from_game)

    # Start with the same values (take game or patient as canonical; here: game)
    patient_win.target_min_slider.setValue(game_win.target_min_slider.value())
    patient_win.target_max_slider.setValue(game_win.target_max_slider.value())

    # ---------- Sync connection when Game Session starts ----------

    def ensure_both_connected():
        """
        When the game session is started:
        - Copy port/baud from game → patient for consistency.
        - Call handle_connect() on both windows so they start their timers
          with the shared backend.
        """
        patient_win.port_edit.setText(game_win.port_edit.text())
        patient_win.baud_edit.setText(game_win.baud_edit.text())

        # In shared-backend mode, handle_connect() should just start timers
        # / update status when backend is already present.
        if game_win.backend is not None:
            game_win.handle_connect()
        if patient_win.backend is not None:
            patient_win.handle_connect()

    # Hook this into the game window's Start Session button
    game_win.start_button.clicked.connect(ensure_both_connected)

    # ---------- Show both windows ----------
    patient_win.show()
    game_win.show()

    app.exec()

    # Clean shutdown: launcher owns the backend
    backend.stop()


if __name__ == "__main__":
    main()
