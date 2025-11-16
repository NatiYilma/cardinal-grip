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

import sys
from PyQt6.QtWidgets import QApplication

from patient_app import PatientWindow
from patient_game_app import PatientGameWindow
from comms.sim_backend import SimBackend as SerialBackend
# For real hardware, you’d instead use:
# from comms.serial_backend import SerialBackend


def main():
    app = QApplication(sys.argv)

    # Shared backend instance
    backend = SerialBackend(port="/dev/cu.usbmodem14101", baud=115200, timeout=0.01)
    backend.start()

    # Both windows share backend; they do NOT own it
    patient_win = PatientWindow(backend=backend, owns_backend=False)
    game_win = PatientGameWindow(backend=backend, owns_backend=False)

    # --- Sync Min/Max ADC sliders between the two windows ---

    def sync_min_from_patient(val: int):
        # Update game slider if different, without triggering its signal again
        if game_win.target_min_slider.value() != val:
            game_win.target_min_slider.blockSignals(True)
            game_win.target_min_slider.setValue(val)
            game_win.target_min_slider.blockSignals(False)

    def sync_min_from_game(val: int):
        if patient_win.target_min_slider.value() != val:
            patient_win.target_min_slider.blockSignals(True)
            patient_win.target_min_slider.setValue(val)
            patient_win.target_min_slider.blockSignals(False)

    def sync_max_from_patient(val: int):
        if game_win.target_max_slider.value() != val:
            game_win.target_max_slider.blockSignals(True)
            game_win.target_max_slider.setValue(val)
            game_win.target_max_slider.blockSignals(False)

    def sync_max_from_game(val: int):
        if patient_win.target_max_slider.value() != val:
            patient_win.target_max_slider.blockSignals(True)
            patient_win.target_max_slider.setValue(val)
            patient_win.target_max_slider.blockSignals(False)

    # Connect signals both ways
    patient_win.target_min_slider.valueChanged.connect(sync_min_from_patient)
    game_win.target_min_slider.valueChanged.connect(sync_min_from_game)

    patient_win.target_max_slider.valueChanged.connect(sync_max_from_patient)
    game_win.target_max_slider.valueChanged.connect(sync_max_from_game)

    # Optional: start them with the same initial values (take patient as source)
    game_win.target_min_slider.setValue(patient_win.target_min_slider.value())
    game_win.target_max_slider.setValue(patient_win.target_max_slider.value())

    patient_win.show()
    game_win.show()

    app.exec()

    # Clean shutdown
    backend.stop()


if __name__ == "__main__":
    main()
