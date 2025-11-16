# host/gui/patient_dual_launcher.py

import sys
from PyQt6.QtWidgets import QApplication

from patient_app import PatientWindow
from patient_game_app import PatientGameWindow
from comms.sim_backend import SimBackend as SerialBackend
# For real hardware, you’d instead:
# from comms.serial_backend import SerialBackend

def main():
    app = QApplication(sys.argv)

    # Shared backend instance
    backend = SerialBackend(port="/dev/cu.usbmodem14101", baud=115200, timeout=0.01)
    backend.start()

    # Both windows share backend; they do NOT own it
    patient_win = PatientWindow(backend=backend, owns_backend=False)
    game_win = PatientGameWindow(backend=backend, owns_backend=False)

    patient_win.show()
    game_win.show()

    app.exec()

    # Clean shutdown
    backend.stop()

if __name__ == "__main__":
    main()
