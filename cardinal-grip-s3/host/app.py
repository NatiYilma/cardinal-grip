# host/app.py

import logging
import os
import sys
from typing import Sequence, List

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from comms.backend_manager import BackendManager, BackendName

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)


class FSRBridge(QObject):
    """
    Thread-safe bridge from BackendManager callbacks (background threads)
    into the Qt main thread.

    Backends call:   backend_listener(values, source)
    → emit fsr_frame(list(values), source)
    → Qt delivers _on_fsr_signal(...) on the GUI thread.
    """
    fsr_frame = pyqtSignal(list, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)


class FSRMainWindow(QWidget):
    """
    Simple dashboard showing:

    - current backend (serial / wifi / bluetooth)
    - latest FSR values [v0, v1, v2, v3]

    GUI is pure UI:
      - BackendManager owns all transports.
      - GUI only listens via FSRBridge signals and calls high-level
        use_serial/use_wifi/use_bluetooth/stop() helpers.
    """

    def __init__(self, initial_backend: BackendName = "wifi") -> None:
        super().__init__()

        self.setWindowTitle("Cardinal Grip – FSR Monitor")
        self.resize(520, 260)

        # ------------------------------------------------------------------
        # Labels
        # ------------------------------------------------------------------
        self.label_backend = QLabel(self)
        self.label_backend.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_backend.setStyleSheet("font-size: 14px;")

        self.label_fsr = QLabel("FSR: -, -, -, -", self)
        self.label_fsr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_fsr.setStyleSheet("font-size: 18px;")

        # ------------------------------------------------------------------
        # Serial config (optional override)
        # ------------------------------------------------------------------
        self.serial_port_input = QLineEdit(self)
        self.serial_port_input.setPlaceholderText(
            "Serial port override (optional, e.g. /dev/cu.usbmodem14201 or COM3)"
        )

        # ------------------------------------------------------------------
        # Buttons
        # ------------------------------------------------------------------
        self.btn_serial = QPushButton("Use Serial", self)
        self.btn_wifi = QPushButton("Use Wi-Fi", self)
        self.btn_bt = QPushButton("Use Bluetooth (BLE)", self)
        self.button_quit = QPushButton("Quit", self)

        self.btn_serial.clicked.connect(self._on_click_serial)
        self.btn_wifi.clicked.connect(self._on_click_wifi)
        self.btn_bt.clicked.connect(self._on_click_bluetooth)
        self.button_quit.clicked.connect(QApplication.instance().quit)

        backend_buttons_layout = QHBoxLayout()
        backend_buttons_layout.addWidget(self.btn_serial)
        backend_buttons_layout.addWidget(self.btn_wifi)
        backend_buttons_layout.addWidget(self.btn_bt)

        layout = QVBoxLayout()
        layout.addWidget(self.label_backend)
        layout.addLayout(backend_buttons_layout)
        layout.addWidget(self.serial_port_input)
        layout.addWidget(self.label_fsr)
        layout.addWidget(self.button_quit)
        self.setLayout(layout)

        # ------------------------------------------------------------------
        # BackendManager + bridge wiring
        # ------------------------------------------------------------------
        self.backend = BackendManager(default_backend=initial_backend)

        # Bridge to keep Qt updates on the GUI thread only
        self._bridge = FSRBridge(self)
        self._bridge.fsr_frame.connect(self._on_fsr_signal)

        # Register a single backend listener that *only* emits the Qt signal.
        # This listener will be invoked from backend worker threads.
        self.backend.add_listener(self._backend_listener)

        self._update_backend_label()

        # Optional heartbeat
        self._ticks = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    # ------------------------------------------------------------------
    # BackendManager → Qt bridge
    # ------------------------------------------------------------------

    def _backend_listener(self, values: Sequence[int], source: BackendName) -> None:
        """
        This is called from backend worker threads.

        DO NOT touch Qt widgets here. Just emit the signal so Qt
        can deliver it on the GUI/main thread.
        """
        # Convert to plain list so it is safely serializable across threads.
        vals_list: List[int] = list(values)
        self._bridge.fsr_frame.emit(vals_list, source)

    def _on_fsr_signal(self, values: list, source: str) -> None:
        """
        Runs on the Qt GUI thread. Safe to touch widgets here.
        """
        # Normalize to 4 ints
        v0, v1, v2, v3 = (list(values) + [0, 0, 0, 0])[:4]
        self.label_fsr.setText(f"FSR: {v0}, {v1}, {v2}, {v3}  ({source})")
        logging.info("GUI: FSR frame from %s via Qt signal: %s", source, [v0, v1, v2, v3])

    # ------------------------------------------------------------------
    # Heartbeat (optional)
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        self._ticks += 1
        # Could be used later for status updates

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_click_serial(self) -> None:
        """
        Use Serial backend.

        - If user typed a port in the text field, use that.
        - Otherwise rely on BackendManager auto-detection.
        """
        port_override = self.serial_port_input.text().strip() or None

        try:
            self.backend.use_serial(port=port_override)
            self._update_backend_label()
        except Exception as e:
            logging.exception("GUI: failed to start serial backend")
            QMessageBox.critical(
                self,
                "Serial Error",
                f"Failed to start Serial backend:\n{e}",
            )

    def _on_click_wifi(self) -> None:
        """
        Use Wi-Fi backend.

        From the PC side we just connect to:
            ws://cardinal-grip.local:81/
        by default (or a custom URI later if you expose that in the UI).
        """
        try:
            self.backend.use_wifi()
            self._update_backend_label()
        except Exception as e:
            logging.exception("GUI: failed to start Wi-Fi backend")
            QMessageBox.critical(
                self,
                "Wi-Fi Error",
                f"Failed to start Wi-Fi backend:\n{e}",
            )

    def _on_click_bluetooth(self) -> None:
        """
        Use Bluetooth (BLE) backend.

        Requires `bleak` and OS BLE support.
        """
        try:
            self.backend.use_bluetooth()
            self._update_backend_label()
        except Exception as e:
            logging.exception("GUI: failed to start Bluetooth backend")
            QMessageBox.critical(
                self,
                "Bluetooth Error",
                f"Failed to start Bluetooth backend:\n{e}",
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_backend_label(self) -> None:
        self.label_backend.setText(
            f"Active backend: {self.backend.active_backend}"
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # type: ignore
        try:
            self.backend.stop()
        except Exception:
            pass
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)

    # Initial label only; no auto-connect.
    window = FSRMainWindow(initial_backend="wifi")
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()