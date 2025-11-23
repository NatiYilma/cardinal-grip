# host/gui/clinician_dashboard/clinician_dashboard.py

import os
import sys
import json
import sqlite3
from datetime import datetime
from collections import defaultdict

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QStackedWidget,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QMessageBox,
)

# ---------- PATH SETUP ----------
CLINICIAN_DASHBOARD_DIR = os.path.dirname(__file__)   # .../host/gui/clinician_dashboard
GUI_DIR = os.path.dirname(CLINICIAN_DASHBOARD_DIR)    # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)                   # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)              # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

SESSIONS_JSON_PATH = os.path.join(DATA_DIR, "sessions_log.json")
CLINICIAN_PROFILE_PATH = os.path.join(DATA_DIR, "clinician_profile.json")
CLINICIAN_SETTINGS_PATH = os.path.join(DATA_DIR, "clinician_settings.json")

# Re-use existing calendar + clinician monitor + dual view + patient multi-finger view
from host.gui.common.dashboard_calendar import DashboardWindow
from host.gui.clinician_dashboard.clinician_app import ClinicianWindow
from host.gui.patient_dashboard.patient_app import PatientWindow
from host.gui.patient_dashboard.patient_dual_launcher import DualPatientGameWindow


# ---------- Helpers for sessions ----------

def _load_sessions():
    if not os.path.isfile(SESSIONS_JSON_PATH):
        return []
    try:
        with open(SESSIONS_JSON_PATH, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception:
        return []


def _sessions_summary():
    """
    Returns (total_sessions, total_reps, last_timestamp_str).
    """
    sessions = _load_sessions()
    if not sessions:
        return 0, 0, "No sessions yet"

    total_sessions = len(sessions)
    total_reps = 0
    last_ts = None

    for s in sessions:
        total_reps += int(s.get("total_reps", 0))
        ts_str = s.get("timestamp")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str)
                if last_ts is None or ts > last_ts:
                    last_ts = ts
            except Exception:
                continue

    if last_ts is None:
        last_str = "Unknown"
    else:
        last_str = last_ts.strftime("%b %d, %Y %H:%M")

    return total_sessions, total_reps, last_str


# ---------- Dashboard Page (Clinician) ----------

class ClinicianDashboardPage(QWidget):
    """
    Main clinician dashboard:
      - High-level stats from sessions_log.json
      - Quick actions (monitor, multi-finger monitor, dual view, calendar)
    """

    def __init__(self, parent_shell):
        super().__init__()
        self.shell = parent_shell  # parent shell window so we can call its helpers

        layout = QVBoxLayout()
        self.setLayout(layout)

        title = QLabel("Clinician Dashboard")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18pt; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Overview of patient exercise sessions and quick access to tools."
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: gray;")
        layout.addWidget(subtitle)

        # Stats group
        stats_group = QGroupBox("Session Summary")
        stats_layout = QVBoxLayout()
        stats_group.setLayout(stats_layout)

        self.sessions_label = QLabel()
        self.total_reps_label = QLabel()
        self.last_session_label = QLabel()

        stats_layout.addWidget(self.sessions_label)
        stats_layout.addWidget(self.total_reps_label)
        stats_layout.addWidget(self.last_session_label)

        layout.addWidget(stats_group)

        # Quick actions
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QHBoxLayout()
        actions_group.setLayout(actions_layout)

        btn_monitor = QPushButton("Open Clinician Monitor")
        btn_monitor.clicked.connect(self.shell.open_monitor)
        actions_layout.addWidget(btn_monitor)

        # NEW: Multi-finger monitor (same view as patient multi-finger mode)
        btn_multi_monitor = QPushButton("Multi-Finger Monitor")
        btn_multi_monitor.clicked.connect(self.shell.open_multi_monitor)
        actions_layout.addWidget(btn_multi_monitor)

        btn_dual = QPushButton("Dual View (Patient Game + Monitor)")
        btn_dual.clicked.connect(self.shell.open_dual)
        actions_layout.addWidget(btn_dual)

        btn_calendar = QPushButton("Open Exercise Calendar")
        btn_calendar.clicked.connect(lambda: self.shell.switch_page("calendar"))
        actions_layout.addWidget(btn_calendar)

        btn_refresh = QPushButton("Refresh Stats")
        btn_refresh.clicked.connect(self.refresh_stats)
        actions_layout.addWidget(btn_refresh)

        layout.addWidget(actions_group)

        layout.addStretch(1)

        self.refresh_stats()

    def refresh_stats(self):
        total_sessions, total_reps, last_str = _sessions_summary()
        self.sessions_label.setText(f"Total sessions (all modes): {total_sessions}")
        self.total_reps_label.setText(f"Total reps recorded (all fingers): {total_reps}")
        self.last_session_label.setText(f"Most recent session: {last_str}")


# ---------- Clinician Profile Page ----------

class ClinicianProfilePage(QWidget):
    """
    Stores clinician's own info + a simple list of patients
    in clinician_profile.json.
    """

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        self.setLayout(layout)

        title = QLabel("Clinician Profile")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(title)

        # --- Clinician info group ---
        info_group = QGroupBox("Clinician Information")
        info_layout = QVBoxLayout()
        info_group.setLayout(info_layout)

        # Name
        row_name = QHBoxLayout()
        row_name.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        row_name.addWidget(self.name_edit)
        info_layout.addLayout(row_name)

        # Location
        row_loc = QHBoxLayout()
        row_loc.addWidget(QLabel("Location (City, State/Country):"))
        self.location_edit = QLineEdit()
        row_loc.addWidget(self.location_edit)
        info_layout.addLayout(row_loc)

        # Organization type
        row_org_type = QHBoxLayout()
        row_org_type.addWidget(QLabel("Organization type:"))
        self.org_type_combo = QComboBox()
        self.org_type_combo.addItems(
            ["Clinic", "Rehab Center", "Hospital", "Outpatient Center", "Private Practice", "Other"]
        )
        row_org_type.addWidget(self.org_type_combo)
        info_layout.addLayout(row_org_type)

        # Organization name
        row_org_name = QHBoxLayout()
        row_org_name.addWidget(QLabel("Organization name:"))
        self.org_name_edit = QLineEdit()
        row_org_name.addWidget(self.org_name_edit)
        info_layout.addLayout(row_org_name)

        # Specialty
        row_spec = QHBoxLayout()
        row_spec.addWidget(QLabel("Specialty (e.g., OT/PT, Neuro, Hand Therapy):"))
        self.specialty_edit = QLineEdit()
        row_spec.addWidget(self.specialty_edit)
        info_layout.addLayout(row_spec)

        # Notes
        notes_label = QLabel("Notes (schedule, clinic reminders, etc.):")
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Free-text notes about your practice...")
        info_layout.addWidget(notes_label)
        info_layout.addWidget(self.notes_edit)

        layout.addWidget(info_group)

        # --- Patient list group ---
        patients_group = QGroupBox("Patients")
        patients_layout = QVBoxLayout()
        patients_group.setLayout(patients_layout)

        patients_desc = QLabel(
            "Simple list of patient profiles you manage with Cardinal Grip.\n"
            "You can add/remove names here (this is clinician-side only)."
        )
        patients_layout.addWidget(patients_desc)

        self.patients_list = QListWidget()
        patients_layout.addWidget(self.patients_list)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("Add Patient")
        btn_add.clicked.connect(self.add_patient)
        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(self.remove_selected_patient)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        patients_layout.addLayout(btn_row)

        layout.addWidget(patients_group)

        # Save row
        save_row = QHBoxLayout()
        save_row.addStretch(1)
        btn_save = QPushButton("Save Profile")
        btn_save.clicked.connect(self.save_profile)
        save_row.addWidget(btn_save)
        layout.addLayout(save_row)

        layout.addStretch(1)

        self.load_profile()

    # ----- Patient list handlers -----

    def add_patient(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Add Patient", "Patient name:")
        if ok and name.strip():
            self.patients_list.addItem(QListWidgetItem(name.strip()))

    def remove_selected_patient(self):
        for item in self.patients_list.selectedItems():
            row = self.patients_list.row(item)
            self.patients_list.takeItem(row)

    # ----- File I/O -----

    def load_profile(self):
        if not os.path.isfile(CLINICIAN_PROFILE_PATH):
            return
        try:
            with open(CLINICIAN_PROFILE_PATH, "r") as f:
                data = json.load(f)
        except Exception:
            return

        self.name_edit.setText(data.get("name", ""))
        self.location_edit.setText(data.get("location", ""))
        org_type = data.get("org_type", "")
        idx = self.org_type_combo.findText(org_type)
        if idx >= 0:
            self.org_type_combo.setCurrentIndex(idx)
        self.org_name_edit.setText(data.get("org_name", ""))
        self.specialty_edit.setText(data.get("specialty", ""))
        self.notes_edit.setPlainText(data.get("notes", ""))

        self.patients_list.clear()
        for p in data.get("patients", []):
            if isinstance(p, str):
                self.patients_list.addItem(QListWidgetItem(p))

    def save_profile(self):
        patients = []
        for i in range(self.patients_list.count()):
            item = self.patients_list.item(i)
            patients.append(item.text())

        data = {
            "name": self.name_edit.text().strip(),
            "location": self.location_edit.text().strip(),
            "org_type": self.org_type_combo.currentText(),
            "org_name": self.org_name_edit.text().strip(),
            "specialty": self.specialty_edit.text().strip(),
            "notes": self.notes_edit.toPlainText(),
            "patients": patients,
        }

        try:
            with open(CLINICIAN_PROFILE_PATH, "w") as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, "Saved", "Clinician profile saved.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save profile:\n{e}")


# ---------- Notifications Page ----------

class ClinicianNotificationsPage(QWidget):
    """
    Lightweight notifications view:
      - Recent sessions displayed as a scrollable list
    """

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        self.setLayout(layout)

        title = QLabel("Notifications")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Recent patient activity (sessions) based on local logs."
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: gray;")
        layout.addWidget(subtitle)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll, stretch=1)

        container = QWidget()
        self.notifications_layout = QVBoxLayout()
        container.setLayout(self.notifications_layout)
        scroll.setWidget(container)

        refresh_row = QHBoxLayout()
        refresh_row.addStretch(1)
        btn_refresh = QPushButton("Refresh Notifications")
        btn_refresh.clicked.connect(self.populate_notifications)
        refresh_row.addWidget(btn_refresh)
        layout.addLayout(refresh_row)

        self.populate_notifications()

    def populate_notifications(self):
        # Clear old
        while self.notifications_layout.count():
            item = self.notifications_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        sessions = _load_sessions()
        # Show most recent first
        sessions = sorted(
            sessions,
            key=lambda s: s.get("timestamp", ""),
            reverse=True,
        )

        if not sessions:
            self.notifications_layout.addWidget(QLabel("No sessions logged yet."))
            self.notifications_layout.addStretch(1)
            return

        max_to_show = 30
        for i, s in enumerate(sessions[:max_to_show]):
            ts_str = s.get("timestamp", "")
            mode = s.get("mode", "unknown")
            source = s.get("source", "unknown")
            fingers_used = s.get("fingers_used", 0)
            total_reps = s.get("total_reps", 0)
            combo_reps = s.get("combo_reps", 0)

            text = (
                f"[{ts_str}] Mode: {mode}, Source: {source}\n"
                f"  Fingers used: {fingers_used}, Total reps: {total_reps}, Combo reps: {combo_reps}"
            )
            label = QLabel(text)
            label.setWordWrap(True)
            label.setStyleSheet("border: 1px solid #ccc; padding: 4px;")
            self.notifications_layout.addWidget(label)

        self.notifications_layout.addStretch(1)


# ---------- Settings Page ----------

class ClinicianSettingsPage(QWidget):
    """
    Basic settings for clinician side:
      - Theme
      - High contrast
      - Sound on/off
      - Units (imperial/metric)
      - Connection defaults (serial/Bluetooth/Wi-Fi, baud, port)
    """

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        self.setLayout(layout)

        title = QLabel("Settings")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(title)

        # Theme group
        theme_group = QGroupBox("Appearance")
        theme_layout = QVBoxLayout()
        theme_group.setLayout(theme_layout)

        row_theme = QHBoxLayout()
        row_theme.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        row_theme.addWidget(self.theme_combo)
        theme_layout.addLayout(row_theme)

        row_contrast = QHBoxLayout()
        row_contrast.addWidget(QLabel("High contrast mode:"))
        self.high_contrast_combo = QComboBox()
        self.high_contrast_combo.addItems(["Off", "On"])
        row_contrast.addWidget(self.high_contrast_combo)
        theme_layout.addLayout(row_contrast)

        layout.addWidget(theme_group)

        # Sound group
        sound_group = QGroupBox("Audio")
        sound_layout = QHBoxLayout()
        sound_group.setLayout(sound_layout)

        sound_layout.addWidget(QLabel("Sound effects:"))
        self.sound_combo = QComboBox()
        self.sound_combo.addItems(["On", "Off"])
        sound_layout.addWidget(self.sound_combo)

        layout.addWidget(sound_group)

        # Units & connection
        conn_group = QGroupBox("Units & Connection Defaults")
        conn_layout = QVBoxLayout()
        conn_group.setLayout(conn_layout)

        row_units = QHBoxLayout()
        row_units.addWidget(QLabel("Units:"))
        self.units_combo = QComboBox()
        self.units_combo.addItems(["Metric (kPa, N)", "Imperial (psi, lbf)"])
        row_units.addWidget(self.units_combo)
        conn_layout.addLayout(row_units)

        row_conn_type = QHBoxLayout()
        row_conn_type.addWidget(QLabel("Default connection:"))
        self.conn_type_combo = QComboBox()
        self.conn_type_combo.addItems(["Serial", "Bluetooth", "Wi-Fi"])
        row_conn_type.addWidget(self.conn_type_combo)
        conn_layout.addLayout(row_conn_type)

        row_port = QHBoxLayout()
        row_port.addWidget(QLabel("Default serial port:"))
        self.port_edit = QLineEdit("/dev/cu.usbmodem14101")
        row_port.addWidget(self.port_edit)
        conn_layout.addLayout(row_port)

        row_baud = QHBoxLayout()
        row_baud.addWidget(QLabel("Default baud rate:"))
        self.baud_edit = QLineEdit("115200")
        row_baud.addWidget(self.baud_edit)
        conn_layout.addLayout(row_baud)

        layout.addWidget(conn_group)

        # Save row
        save_row = QHBoxLayout()
        save_row.addStretch(1)
        btn_save = QPushButton("Save Settings")
        btn_save.clicked.connect(self.save_settings)
        save_row.addWidget(btn_save)
        layout.addLayout(save_row)

        layout.addStretch(1)

        self.load_settings()

    def load_settings(self):
        if not os.path.isfile(CLINICIAN_SETTINGS_PATH):
            return
        try:
            with open(CLINICIAN_SETTINGS_PATH, "r") as f:
                data = json.load(f)
        except Exception:
            return

        def set_combo_from_key(combo, key, default):
            val = data.get(key, default)
            idx = combo.findText(val)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        set_combo_from_key(self.theme_combo, "theme", "Light")
        set_combo_from_key(self.high_contrast_combo, "high_contrast", "Off")
        set_combo_from_key(self.sound_combo, "sound", "On")
        set_combo_from_key(self.units_combo, "units", "Metric (kPa, N)")
        set_combo_from_key(self.conn_type_combo, "connection_type", "Serial")

        self.port_edit.setText(data.get("default_port", "/dev/cu.usbmodem14101"))
        self.baud_edit.setText(str(data.get("default_baud", "115200")))

    def save_settings(self):
        data = {
            "theme": self.theme_combo.currentText(),
            "high_contrast": self.high_contrast_combo.currentText(),
            "sound": self.sound_combo.currentText(),
            "units": self.units_combo.currentText(),
            "connection_type": self.conn_type_combo.currentText(),
            "default_port": self.port_edit.text().strip(),
            "default_baud": self.baud_edit.text().strip(),
        }
        try:
            with open(CLINICIAN_SETTINGS_PATH, "w") as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, "Saved", "Clinician settings saved.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save settings:\n{e}")


# ---------- Shell Window with Collapsible Sidebar ----------

class ClinicianShellWindow(QWidget):
    """
    Main clinician window with collapsible sidebar:
      - Dashboard
      - Calendar
      - Clinician Profile
      - Notifications
      - Settings
      - Quick buttons on dashboard for:
          * Clinician monitor
          * Multi-finger monitor (patient-style)
          * Dual view (patient game + monitor)
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Clinician")
        self.resize(1100, 700)

        self.sidebar_expanded = True
        self._open_windows = []
        self.multi_monitor_win = None   # NEW: persistent multi-finger window

        root_layout = QHBoxLayout()
        self.setLayout(root_layout)

        # Sidebar (left)
        self.sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(8, 8, 8, 8)
        sidebar_layout.setSpacing(8)
        self.sidebar_widget.setLayout(sidebar_layout)

        # Top row: app label + collapse button
        top_row = QHBoxLayout()
        self.app_label = QLabel("Cardinal Grip\nClinician")
        self.app_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.app_label.setStyleSheet("font-size: 14pt; font-weight: bold;")

        self.toggle_btn = QPushButton("⏴")
        self.toggle_btn.setFixedWidth(30)
        self.toggle_btn.clicked.connect(self.toggle_sidebar)

        top_row.addWidget(self.app_label, stretch=1)
        top_row.addWidget(self.toggle_btn)
        sidebar_layout.addLayout(top_row)

        # Nav buttons
        self.nav_buttons = {}
        self.nav_full_text = {
            "dashboard": "Dashboard",
            "calendar": "Calendar",
            "profile": "Clinician Profile",
            "notifications": "Notifications",
            "settings": "Settings",
        }
        btn_specs = [
            ("dashboard", "Dashboard"),
            ("calendar", "Calendar"),
            ("profile", "Clinician Profile"),
            ("notifications", "Notifications"),
            ("settings", "Settings"),
        ]

        for key, text in btn_specs:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self.switch_page(k))
            btn.setStyleSheet(
                "QPushButton { text-align: left; padding: 6px 10px; }"
                "QPushButton:checked { background-color: #1976D2; color: white; }"
            )
            sidebar_layout.addWidget(btn)
            self.nav_buttons[key] = btn

        sidebar_layout.addStretch(1)
        root_layout.addWidget(self.sidebar_widget, stretch=0)

        # Main stacked pages (right)
        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack, stretch=1)

        # Instantiate pages
        self.pages = {}
        self.pages["dashboard"] = ClinicianDashboardPage(self)
        self.pages["calendar"] = DashboardWindow()
        self.pages["profile"] = ClinicianProfilePage()
        self.pages["notifications"] = ClinicianNotificationsPage()
        self.pages["settings"] = ClinicianSettingsPage()

        # Add to stack in a consistent order
        self.page_order = ["dashboard", "calendar", "profile", "notifications", "settings"]
        for key in self.page_order:
            self.stack.addWidget(self.pages[key])

        # Default page
        self.switch_page("dashboard")
        self._apply_sidebar_state()

    # ---- Sidebar expand / collapse ----

    def toggle_sidebar(self):
        self.sidebar_expanded = not self.sidebar_expanded
        self._apply_sidebar_state()

    def _apply_sidebar_state(self):
        if self.sidebar_expanded:
            # Expanded
            self.sidebar_widget.setFixedWidth(220)
            self.app_label.setVisible(True)
            self.toggle_btn.setText("⏴")
            for key, btn in self.nav_buttons.items():
                btn.setText(self.nav_full_text.get(key, key.title()))
                btn.setStyleSheet(
                    "QPushButton { text-align: left; padding: 6px 10px; }"
                    "QPushButton:checked { background-color: #1976D2; color: white; }"
                )
        else:
            # Collapsed
            self.sidebar_widget.setFixedWidth(60)
            self.app_label.setVisible(False)
            self.toggle_btn.setText("⏵")
            for key, btn in self.nav_buttons.items():
                # Use first letter as a crude "icon"
                full = self.nav_full_text.get(key, key.title())
                btn.setText(full[0])
                btn.setStyleSheet(
                    "QPushButton { text-align: center; padding: 6px 0px; }"
                    "QPushButton:checked { background-color: #1976D2; color: white; }"
                )

    # ---- Page switching ----

    def switch_page(self, key: str):
        if key not in self.pages:
            return
        index = self.page_order.index(key)
        self.stack.setCurrentIndex(index)

        # update button checked state
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)

    # ---- Actions used by pages ----

    def open_monitor(self):
        """
        Open the clinician monitor window (multi-channel view).
        """
        win = ClinicianWindow()
        win.show()
        self._open_windows.append(win)

    def open_multi_monitor(self):
        """
        Open the multi-finger monitor used on the patient side (PatientWindow).
        This lets the clinician see the same 4-channel view.
        """
        if self.multi_monitor_win is None:
            self.multi_monitor_win = PatientWindow()
            self.multi_monitor_win.setWindowTitle(
                "Cardinal Grip – Multi-Finger Monitor (Clinician View)"
            )
        self.multi_monitor_win.show()
        self.multi_monitor_win.raise_()
        self.multi_monitor_win.activateWindow()

    def open_dual(self):
        """
        Open the dual patient window (game + monitor side-by-side).
        """
        win = DualPatientGameWindow()
        win.show()
        self._open_windows.append(win)


def main():
    app = QApplication(sys.argv)
    win = ClinicianShellWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()