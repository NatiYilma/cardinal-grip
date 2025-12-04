# host/gui.py

import os
import sys
from typing import List, Sequence

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QComboBox,
    QGroupBox,
    QFormLayout,
)

# This file is *pure UI*. No backend imports here.


class FSRMainWindow(QWidget):
    """
    UI-only window.

    Exposes signals that a controller (e.g. host/app.py) connects to:
      - serial_connect_requested(port: str)
      - wifi_connect_requested()
      - bluetooth_connect_requested()
      - wifi_scan_requested()
      - wifi_config_requested(ssid: str, password: str)
      - wifi_forget_requested()

    And provides UI update methods:
      - update_fsr(values, source)
      - set_backend_status(backend, state, message)
      - set_serial_port_placeholder(port)
      - set_wifi_networks(ssids)
    """

    # -----------------------
    # Signals
    # -----------------------
    serial_connect_requested = pyqtSignal(str)
    wifi_connect_requested = pyqtSignal()
    bluetooth_connect_requested = pyqtSignal()

    wifi_scan_requested = pyqtSignal()
    wifi_config_requested = pyqtSignal(str, str)
    wifi_forget_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Cardinal Grip – FSR Monitor")
        self.resize(680, 420)

        # ------------------------------------------------------------------
        # Top: backend status + FSR readout
        # ------------------------------------------------------------------
        self.label_fsr = QLabel("FSR: -, -, -, -", self)
        self.label_fsr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_fsr.setStyleSheet("font-size: 20px;")

        self.label_backend_summary = QLabel("No backend active", self)
        self.label_backend_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_backend_summary.setStyleSheet("font-size: 13px;")

        # ------------------------------------------------------------------
        # Status indicators for Serial / Wi-Fi / Bluetooth
        # ------------------------------------------------------------------
        self.serial_indicator = QLabel()
        self.wifi_indicator = QLabel()
        self.bt_indicator = QLabel()
        for lbl in (self.serial_indicator, self.wifi_indicator, self.bt_indicator):
            lbl.setFixedSize(14, 14)
            lbl.setStyleSheet(self._indicator_style("#888888"))  # idle grey

        self.serial_status_label = QLabel("Serial: idle")
        self.wifi_status_label = QLabel("Wi-Fi: idle")
        self.bt_status_label = QLabel("Bluetooth: idle")

        serial_row = QHBoxLayout()
        serial_row.addWidget(self.serial_indicator)
        serial_row.addWidget(self.serial_status_label)
        serial_row.addStretch()

        wifi_row = QHBoxLayout()
        wifi_row.addWidget(self.wifi_indicator)
        wifi_row.addWidget(self.wifi_status_label)
        wifi_row.addStretch()

        bt_row = QHBoxLayout()
        bt_row.addWidget(self.bt_indicator)
        bt_row.addWidget(self.bt_status_label)
        bt_row.addStretch()

        status_box = QGroupBox("Connection Status")
        status_layout = QVBoxLayout()
        status_layout.addLayout(serial_row)
        status_layout.addLayout(wifi_row)
        status_layout.addLayout(bt_row)
        status_box.setLayout(status_layout)

        # ------------------------------------------------------------------
        # Serial controls
        # ------------------------------------------------------------------
        self.serial_port_input = QLineEdit(self)
        self.serial_port_input.setPlaceholderText(
            "Auto-detect or enter port"
        )

        self.btn_serial_connect = QPushButton("Use Serial", self)
        self.btn_serial_connect.clicked.connect(self._emit_serial_connect)

        serial_controls_layout = QFormLayout()
        serial_controls_layout.addRow("Serial port:", self.serial_port_input)
        serial_controls_layout.addRow(self.btn_serial_connect)

        serial_box = QGroupBox("Serial (USB)")
        serial_box.setLayout(serial_controls_layout)

        # ------------------------------------------------------------------
        # Wi-Fi controls (STA config + AP hint)
        # ------------------------------------------------------------------
        self.label_ap_hint = QLabel(
            'AP: <b>CardinalGrip_AP</b>, password <code>SqueezyPeasy1</code><br>'
            'Connect your computer to this AP in your OS Wi-Fi menu for initial setup.'
        )
        self.label_ap_hint.setWordWrap(True)

        self.btn_wifi_backend = QPushButton("Use Wi-Fi Backend", self)
        self.btn_wifi_backend.clicked.connect(self._emit_wifi_connect)

        self.btn_wifi_scan = QPushButton("Scan STA Networks (via AP)", self)
        self.btn_wifi_scan.clicked.connect(self._emit_wifi_scan)

        self.wifi_ssid_combo = QComboBox(self)
        self.wifi_ssid_combo.setPlaceholderText("No scan yet – click 'Scan STA Networks'")

        self.wifi_password_input = QLineEdit(self)
        self.wifi_password_input.setPlaceholderText("Network password")
        self.wifi_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.btn_wifi_save = QPushButton("Save STA Credentials to Device", self)
        self.btn_wifi_save.clicked.connect(self._emit_wifi_config)

        self.btn_wifi_forget = QPushButton("Forget Wi-Fi on Device", self)
        self.btn_wifi_forget.clicked.connect(self._emit_wifi_forget)

        wifi_form = QFormLayout()
        wifi_form.addRow("Wi-Fi backend:", self.btn_wifi_backend)
        wifi_form.addRow("Scan networks:", self.btn_wifi_scan)
        wifi_form.addRow("STA SSID:", self.wifi_ssid_combo)
        wifi_form.addRow("STA password:", self.wifi_password_input)
        wifi_form.addRow(self.btn_wifi_save)
        wifi_form.addRow(self.btn_wifi_forget)

        wifi_box = QGroupBox("Wi-Fi (STA / AP)")
        wifi_layout = QVBoxLayout()
        wifi_layout.addWidget(self.label_ap_hint)
        wifi_layout.addLayout(wifi_form)
        wifi_box.setLayout(wifi_layout)

        # ------------------------------------------------------------------
        # Bluetooth controls
        # ------------------------------------------------------------------
        self.btn_bt_connect = QPushButton("Use Bluetooth (BLE)", self)
        self.btn_bt_connect.clicked.connect(self._emit_bt_connect)

        bt_box = QGroupBox("Bluetooth (BLE)")
        bt_layout = QVBoxLayout()
        bt_layout.addWidget(self.btn_bt_connect)
        bt_box.setLayout(bt_layout)

        # ------------------------------------------------------------------
        # Quit button
        # ------------------------------------------------------------------
        self.button_quit = QPushButton("Quit", self)
        self.button_quit.clicked.connect(self.close)

        # ------------------------------------------------------------------
        # Layout composition
        # ------------------------------------------------------------------
        top_layout = QVBoxLayout()
        top_layout.addWidget(self.label_fsr)
        top_layout.addWidget(self.label_backend_summary)
        top_layout.addWidget(status_box)

        lower_layout = QHBoxLayout()
        lower_layout.addWidget(serial_box, 1)
        lower_layout.addWidget(wifi_box, 2)
        lower_layout.addWidget(bt_box, 1)

        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)
        main_layout.addLayout(lower_layout)
        main_layout.addWidget(self.button_quit, alignment=Qt.AlignmentFlag.AlignRight)

        self.setLayout(main_layout)

        # Heartbeat timer (optional for future use)
        self._ticks = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    # ------------------------------------------------------------------
    # Internal helpers (UI only)
    # ------------------------------------------------------------------

    def _indicator_style(self, color: str) -> str:
        """Return stylesheet for a colored circular indicator."""
        return (
            "background-color: " + color + ";"
            "border-radius: 7px;"
            "border: 1px solid #444;"
        )

    def _tick(self) -> None:
        self._ticks += 1
        # Reserved if you later want a blinking heartbeat somewhere.

    # ------------------------------------------------------------------
    # Signal emitters (called on button clicks)
    # ------------------------------------------------------------------

    def _emit_serial_connect(self) -> None:
        port = self.serial_port_input.text().strip()
        self.serial_connect_requested.emit(port)

    def _emit_wifi_connect(self) -> None:
        self.wifi_connect_requested.emit()

    def _emit_bt_connect(self) -> None:
        self.bluetooth_connect_requested.emit()

    def _emit_wifi_scan(self) -> None:
        self.wifi_scan_requested.emit()

    def _emit_wifi_config(self) -> None:
        ssid = self.wifi_ssid_combo.currentText().strip()
        password = self.wifi_password_input.text().strip()
        if not ssid:
            QMessageBox.warning(self, "Wi-Fi", "Please select an SSID before saving.")
            return
        self.wifi_config_requested.emit(ssid, password)

    def _emit_wifi_forget(self) -> None:
        self.wifi_forget_requested.emit()

    # ------------------------------------------------------------------
    # Methods called by controller
    # ------------------------------------------------------------------

    def update_fsr(self, values: Sequence[int], source: str) -> None:
        v = (list(values) + [0, 0, 0, 0])[:4]
        v0, v1, v2, v3 = v
        self.label_fsr.setText(f"FSR: {v0}, {v1}, {v2}, {v3}  ({source})")

    def set_backend_status(self, backend: str, state: str, message: str) -> None:
        """
        backend: "serial" | "wifi" | "bluetooth"
        state:   "idle" | "connecting" | "connected" | "error"
        message: human-readable status string
        """
        # Color logic: per your preference
        #   Serial:     connected = yellow
        #   Wi-Fi:      connected = green
        #   Bluetooth:  connected = blue
        #   connecting: orange
        #   idle:       grey
        #   error:      red

        if state == "idle":
            color = "#888888"
        elif state == "connecting":
            color = "#f39c12"  # orange-ish
        elif state == "connected":
            if backend == "serial":
                color = "#f1c40f"  # yellow
            elif backend == "wifi":
                color = "#27ae60"  # green
            elif backend == "bluetooth":
                color = "#2980b9"  # blue
            else:
                color = "#2ecc71"
        elif state == "error":
            color = "#e74c3c"      # red
        else:
            color = "#888888"

        if backend == "serial":
            self.serial_indicator.setStyleSheet(self._indicator_style(color))
            self.serial_status_label.setText(f"Serial: {message}")
        elif backend == "wifi":
            self.wifi_indicator.setStyleSheet(self._indicator_style(color))
            self.wifi_status_label.setText(f"Wi-Fi: {message}")
        elif backend == "bluetooth":
            self.bt_indicator.setStyleSheet(self._indicator_style(color))
            self.bt_status_label.setText(f"Bluetooth: {message}")

        # Backend summary line – simple best-effort description
        self.label_backend_summary.setText(
            f"Serial: {self.serial_status_label.text().split(': ', 1)[-1]} | "
            f"Wi-Fi: {self.wifi_status_label.text().split(': ', 1)[-1]} | "
            f"Bluetooth: {self.bt_status_label.text().split(': ', 1)[-1]}"
        )

    def set_serial_port_placeholder(self, port: str | None) -> None:
        if port:
            self.serial_port_input.setPlaceholderText(
                f"Auto-detected: {port} (or override here)"
            )

    def set_wifi_networks(self, ssids: List[str]) -> None:
        self.wifi_ssid_combo.clear()
        if not ssids:
            self.wifi_ssid_combo.setPlaceholderText(
                "No networks found – check AP connection and rescan"
            )
            return
        self.wifi_ssid_combo.addItems(ssids)
        self.wifi_ssid_combo.setCurrentIndex(0)


def main() -> None:
    app = QApplication(sys.argv)
    window = FSRMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
