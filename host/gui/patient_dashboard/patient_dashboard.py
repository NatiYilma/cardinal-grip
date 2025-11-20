import os
import sys
import json
from datetime import datetime, date

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QStackedWidget,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QDateEdit,
    QListWidget,
    QGroupBox,
    QComboBox,
    QCheckBox,
)

# ---------- PATH SETUP ----------
# This file is .../cardinal-grip/host/gui/patient_dashboard/patient_dashboard.py
PATIENT_DASHBOARD_DIR = os.path.dirname(__file__)   # .../host/gui/patient_dashboard
GUI_DIR = os.path.dirname(PATIENT_DASHBOARD_DIR)    # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)                 # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)            # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

PROFILE_PATH = os.path.join(DATA_DIR, "patient_profile.json")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
SESSIONS_JSON_PATH = os.path.join(DATA_DIR, "sessions_log.json")

# Existing windows
from host.gui.patient_dashboard.patient_game_app import PatientGameWindow
from host.gui.patient_dashboard.patient_app import PatientWindow
from host.gui.patient_dashboard.patient_dual_launcher import DualPatientGameWindow
from host.gui.dashboard_calendar import DashboardWindow


# =====================================================================
#  Helper: sessions summary
# =====================================================================

def _load_sessions():
    if not os.path.isfile(SESSIONS_JSON_PATH):
        return []
    try:
        with open(SESSIONS_JSON_PATH, "r") as f:
            sessions = json.load(f)
        if not isinstance(sessions, list):
            return []
        return sessions
    except Exception:
        return []


def _latest_session_summary():
    sessions = _load_sessions()
    if not sessions:
        return "No sessions logged yet."

    # Sort by timestamp, newest first
    def parse_ts(s):
        try:
            return datetime.fromisoformat(s.get("timestamp", ""))
        except Exception:
            return datetime.min

    sessions_sorted = sorted(sessions, key=parse_ts, reverse=True)
    s = sessions_sorted[0]

    ts_str = s.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts_str)
        date_str = ts.strftime("%b %d, %Y %H:%M")
    except Exception:
        date_str = ts_str or "Unknown time"

    mode = s.get("mode", "unknown")
    fingers = s.get("fingers_used", 0)
    total_reps = s.get("total_reps", 0)
    combo_reps = s.get("combo_reps", 0)

    return (
        f"Last session: {date_str}  "
        f"(mode: {mode}, fingers used: {fingers}, "
        f"total reps: {total_reps}, combos: {combo_reps})"
    )


# =====================================================================
#  Dashboard page
# =====================================================================

class DashboardPage(QWidget):
    """
    Main home dashboard:
      - Quick welcome text
      - Buttons to open game / monitor / dual / calendar
      - Lightweight summary using sessions_log.json
    """

    def __init__(self, shell_window: "PatientShellWindow"):
        super().__init__()
        self.shell = shell_window

        layout = QVBoxLayout()
        self.setLayout(layout)

        title = QLabel("Patient Dashboard")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18pt; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Welcome to Cardinal Grip.\n\n"
            "Use this dashboard to start a session, monitor your grip, or "
            "review your progress."
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: gray;")
        layout.addWidget(subtitle)

        # Quick actions
        btn_group = QGroupBox("Quick Actions")
        btn_layout = QVBoxLayout()
        btn_group.setLayout(btn_layout)

        btn_game = QPushButton("Play Game")
        btn_game.clicked.connect(self.shell.open_game)
        btn_layout.addWidget(btn_game)

        btn_monitor = QPushButton("Open Monitor (multi-finger view)")
        btn_monitor.clicked.connect(self.shell.open_monitor)
        btn_layout.addWidget(btn_monitor)

        btn_dual = QPushButton("Dual View (game + monitor side-by-side)")
        btn_dual.clicked.connect(self.shell.open_dual)
        btn_layout.addWidget(btn_dual)

        btn_calendar = QPushButton("Open Exercise Calendar")
        btn_calendar.clicked.connect(lambda: self.shell.switch_page("calendar"))
        btn_layout.addWidget(btn_calendar)

        layout.addWidget(btn_group)

        # Stats summary from sessions_log.json
        stats_group = QGroupBox("Recent Activity")
        stats_layout = QVBoxLayout()
        stats_group.setLayout(stats_layout)

        self.last_session_label = QLabel(_latest_session_summary())
        self.last_session_label.setWordWrap(True)
        stats_layout.addWidget(self.last_session_label)

        layout.addWidget(stats_group)
        layout.addStretch(1)

    def refresh(self):
        """Called when page is re-shown, to update last session text."""
        self.last_session_label.setText(_latest_session_summary())


# =====================================================================
#  Calendar page (wraps your existing DashboardWindow)
# =====================================================================

class CalendarPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout()
        self.setLayout(layout)

        header = QLabel("Exercise Calendar")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(header)

        info = QLabel(
            "Each day is color-coded based on how many fingers you exercised\n"
            "and whether you completed combo reps."
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet("color: gray;")
        layout.addWidget(info)

        # Wrap the existing DashboardWindow widget
        self.calendar_widget = DashboardWindow()
        layout.addWidget(self.calendar_widget, stretch=1)


# =====================================================================
#  Profile page
# =====================================================================

class ProfilePage(QWidget):
    """
    Stores simple patient meta:
      - name, age, location
      - handedness
      - treatment start date
      - finger injury profile
      - free-text notes
    """

    FINGERS = ["Thumb", "Index", "Middle", "Ring", "Pinky"]
    STATUS_OPTIONS = [
        "Unaffected",
        "Mildly impaired",
        "Moderately impaired",
        "Severely impaired",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self._profile = {}

        layout = QVBoxLayout()
        self.setLayout(layout)

        title = QLabel("Patient Profile")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(title)

        form = QFormLayout()

        self.name_edit = QLineEdit()
        form.addRow("Name:", self.name_edit)

        self.age_spin = QSpinBox()
        self.age_spin.setRange(0, 120)
        form.addRow("Age:", self.age_spin)

        self.location_edit = QLineEdit()
        form.addRow("Location (city, country):", self.location_edit)

        self.handedness_combo = QComboBox()
        self.handedness_combo.addItems(["Right-handed", "Left-handed", "Ambidextrous"])
        form.addRow("Handedness:", self.handedness_combo)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate())
        form.addRow("Start date of treatment:", self.start_date_edit)

        # Finger injury profile
        finger_group = QGroupBox("Hand/Finger Injury Profile")
        finger_layout = QFormLayout()
        self.finger_status_widgets = {}

        for finger in self.FINGERS:
            combo = QComboBox()
            combo.addItems(self.STATUS_OPTIONS)
            finger_layout.addRow(f"{finger}:", combo)
            self.finger_status_widgets[finger] = combo

        finger_group.setLayout(finger_layout)
        form.addRow(finger_group)

        layout.addLayout(form)

        notes_label = QLabel("Notes (free text):")
        layout.addWidget(notes_label)
        self.notes_edit = QTextEdit()
        layout.addWidget(self.notes_edit, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.save_btn = QPushButton("Save Profile")
        self.save_btn.clicked.connect(self.save_profile)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.load_profile()

    # ----- Persistence -----

    def load_profile(self):
        if not os.path.isfile(PROFILE_PATH):
            return
        try:
            with open(PROFILE_PATH, "r") as f:
                data = json.load(f)
        except Exception:
            return

        self._profile = data

        self.name_edit.setText(data.get("name", ""))
        self.age_spin.setValue(int(data.get("age", 0)))
        self.location_edit.setText(data.get("location", ""))

        handed = data.get("handedness", "Right-handed")
        idx = self.handedness_combo.findText(handed)
        if idx >= 0:
            self.handedness_combo.setCurrentIndex(idx)

        start_date_str = data.get("start_date")
        if start_date_str:
            try:
                dt = datetime.fromisoformat(start_date_str).date()
                self.start_date_edit.setDate(QDate(dt.year, dt.month, dt.day))
            except Exception:
                pass

        injury_profile = data.get("injury_profile", {})
        for finger, combo in self.finger_status_widgets.items():
            status = injury_profile.get(finger, "Unaffected")
            j = combo.findText(status)
            if j >= 0:
                combo.setCurrentIndex(j)

        self.notes_edit.setPlainText(data.get("notes", ""))

    def save_profile(self):
        dt = self.start_date_edit.date()
        start_date = date(dt.year(), dt.month(), dt.day())

        injury_profile = {}
        for finger, combo in self.finger_status_widgets.items():
            injury_profile[finger] = combo.currentText()

        data = {
            "name": self.name_edit.text().strip(),
            "age": int(self.age_spin.value()),
            "location": self.location_edit.text().strip(),
            "handedness": self.handedness_combo.currentText(),
            "start_date": start_date.isoformat(),
            "injury_profile": injury_profile,
            "notes": self.notes_edit.toPlainText(),
        }

        try:
            with open(PROFILE_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            # Fail silently for now; could show a QMessageBox if you want
            print("Failed to save profile:", e)


# =====================================================================
#  Notifications page
# =====================================================================

class NotificationsPage(QWidget):
    """
    Lightweight scrollable list of notifications inferred from sessions_log.json.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout()
        self.setLayout(layout)

        title = QLabel("Notifications")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(title)

        hint = QLabel(
            "This is a simple activity feed based on your recent sessions.\n"
            "In a future version, this could include reminders, streak alerts, "
            "and clinician messages."
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: gray;")
        layout.addWidget(hint)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, stretch=1)

        self.refresh()

    def refresh(self):
        self.list_widget.clear()
        sessions = _load_sessions()
        if not sessions:
            self.list_widget.addItem("No activity yet.")
            return

        # Sort newest first
        def parse_ts(s):
            try:
                return datetime.fromisoformat(s.get("timestamp", ""))
            except Exception:
                return datetime.min

        sessions_sorted = sorted(sessions, key=parse_ts, reverse=True)

        for s in sessions_sorted[:50]:  # cap to last 50 items
            ts_str = s.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str)
                date_str = ts.strftime("%b %d, %Y %H:%M")
            except Exception:
                date_str = ts_str or "Unknown time"

            mode = s.get("mode", "unknown")
            total_reps = s.get("total_reps", 0)
            fingers = s.get("fingers_used", 0)
            combo_reps = s.get("combo_reps", 0)

            msg = (
                f"{date_str} – {mode} session: "
                f"{total_reps} total reps, {fingers} fingers used"
            )
            if combo_reps:
                msg += f", {combo_reps} combo reps 🎉"

            self.list_widget.addItem(msg)


# =====================================================================
#  Settings page
# =====================================================================

class SettingsPage(QWidget):
    """
    App behavior:
      - language
      - theme (light / dark / high contrast)
      - sound on/off
      - units (imperial / metric)
      - connection defaults (serial / baud / bluetooth / wifi)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._settings = {}

        layout = QVBoxLayout()
        self.setLayout(layout)

        title = QLabel("Settings")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(title)

        form = QFormLayout()

        # Language (future-proof, even if only English now)
        self.language_combo = QComboBox()
        self.language_combo.addItems(["English"])
        form.addRow("Language:", self.language_combo)

        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark", "High contrast"])
        form.addRow("Theme:", self.theme_combo)

        # Sound effects
        self.sound_checkbox = QCheckBox("Enable sound effects")
        self.sound_checkbox.setChecked(True)
        form.addRow(self.sound_checkbox)

        # Units
        self.units_combo = QComboBox()
        self.units_combo.addItems(["Imperial", "Metric"])
        form.addRow("Units:", self.units_combo)

        # Connection defaults
        conn_group = QGroupBox("Connection Defaults")
        conn_layout = QFormLayout()

        self.serial_port_edit = QLineEdit("/dev/cu.usbmodem14101")
        conn_layout.addRow("Serial port:", self.serial_port_edit)

        self.baud_edit = QLineEdit("115200")
        conn_layout.addRow("Baud rate:", self.baud_edit)

        self.bluetooth_edit = QLineEdit()
        conn_layout.addRow("Bluetooth device ID:", self.bluetooth_edit)

        self.wifi_host_edit = QLineEdit()
        conn_layout.addRow("WiFi host (IP/hostname):", self.wifi_host_edit)

        conn_group.setLayout(conn_layout)
        form.addRow(conn_group)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self.save_settings)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        layout.addStretch(1)

        self.load_settings()

    # ----- Persistence -----

    def load_settings(self):
        if not os.path.isfile(SETTINGS_PATH):
            return
        try:
            with open(SETTINGS_PATH, "r") as f:
                data = json.load(f)
        except Exception:
            return

        self._settings = data

        lang = data.get("language", "English")
        i = self.language_combo.findText(lang)
        if i >= 0:
            self.language_combo.setCurrentIndex(i)

        theme = data.get("theme", "Light")
        j = self.theme_combo.findText(theme)
        if j >= 0:
            self.theme_combo.setCurrentIndex(j)

        self.sound_checkbox.setChecked(bool(data.get("sound_enabled", True)))

        units = data.get("units", "Imperial")
        k = self.units_combo.findText(units)
        if k >= 0:
            self.units_combo.setCurrentIndex(k)

        self.serial_port_edit.setText(data.get("serial_port", "/dev/cu.usbmodem14101"))
        self.baud_edit.setText(str(data.get("baud_rate", "115200")))
        self.bluetooth_edit.setText(data.get("bluetooth_id", ""))
        self.wifi_host_edit.setText(data.get("wifi_host", ""))

    def save_settings(self):
        data = {
            "language": self.language_combo.currentText(),
            "theme": self.theme_combo.currentText(),
            "sound_enabled": self.sound_checkbox.isChecked(),
            "units": self.units_combo.currentText(),
            "serial_port": self.serial_port_edit.text().strip(),
            "baud_rate": self.baud_edit.text().strip(),
            "bluetooth_id": self.bluetooth_edit.text().strip(),
            "wifi_host": self.wifi_host_edit.text().strip(),
        }

        try:
            with open(SETTINGS_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print("Failed to save settings:", e)


# =====================================================================
#  Shell window with *expandable* sidebar + stacked pages
# =====================================================================

class PatientShellWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Patient")
        self.resize(900, 600)

        self.game_win = None
        self.patient_win = None
        self.dual_win = None
        self.calendar_popup = None  # if you still ever want a stand-alone calendar

        self.sidebar_expanded = True
        self.expanded_sidebar_width = 220
        self.collapsed_sidebar_width = 60

        root_layout = QHBoxLayout()
        self.setLayout(root_layout)

        # Sidebar (left)
        self.sidebar_layout = QVBoxLayout()
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setLayout(self.sidebar_layout)
        self.sidebar_widget.setFixedWidth(self.expanded_sidebar_width)

        # Top row: hamburger button + app label
        top_row = QHBoxLayout()
        self.toggle_btn = QPushButton("☰")
        self.toggle_btn.setFixedWidth(30)
        self.toggle_btn.clicked.connect(self.toggle_sidebar)
        top_row.addWidget(self.toggle_btn)

        self.app_label = QLabel("Cardinal Grip")
        self.app_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.app_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        top_row.addWidget(self.app_label, stretch=1)

        self.sidebar_layout.addLayout(top_row)
        self.sidebar_layout.addSpacing(10)

        self.nav_buttons = {}
        self.nav_button_labels = {}  # full text labels

        self.stack = QStackedWidget()

        # Create pages
        self.dashboard_page = DashboardPage(self)
        self.calendar_page = CalendarPage(self)
        self.profile_page = ProfilePage(self)
        self.notifications_page = NotificationsPage(self)
        self.settings_page = SettingsPage(self)

        self.page_order = {
            "dashboard": 0,
            "calendar": 1,
            "profile": 2,
            "notifications": 3,
            "settings": 4,
        }

        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.calendar_page)
        self.stack.addWidget(self.profile_page)
        self.stack.addWidget(self.notifications_page)
        self.stack.addWidget(self.settings_page)

        # Nav buttons
        def make_nav_button(text, key):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda: self.switch_page(key))
            self.sidebar_layout.addWidget(btn)
            self.nav_buttons[key] = btn
            self.nav_button_labels[key] = text

        make_nav_button("Dashboard", "dashboard")
        make_nav_button("Calendar", "calendar")
        make_nav_button("Profile", "profile")
        make_nav_button("Notifications", "notifications")
        make_nav_button("Settings", "settings")

        self.sidebar_layout.addStretch(1)

        root_layout.addWidget(self.sidebar_widget)
        root_layout.addWidget(self.stack, stretch=1)

        # Start on Dashboard
        self.switch_page("dashboard")

    # ----- Sidebar expand/collapse -----

    def toggle_sidebar(self):
        self.sidebar_expanded = not self.sidebar_expanded

        if self.sidebar_expanded:
            # Expanded: full width, full labels
            self.sidebar_widget.setFixedWidth(self.expanded_sidebar_width)
            self.app_label.setText("Cardinal Grip")
            self.app_label.setVisible(True)

            for key, btn in self.nav_buttons.items():
                full_text = self.nav_button_labels.get(key, key.title())
                btn.setText(full_text)
                btn.setToolTip("")  # no need, label is visible
        else:
            # Collapsed: narrow, minimal text
            self.sidebar_widget.setFixedWidth(self.collapsed_sidebar_width)
            self.app_label.setText("CG")

            for key, btn in self.nav_buttons.items():
                full_text = self.nav_button_labels.get(key, key.title())
                btn.setText("•")  # minimal mark
                btn.setToolTip(full_text)

    # ----- Nav helpers -----

    def switch_page(self, key: str):
        idx = self.page_order.get(key, 0)
        self.stack.setCurrentIndex(idx)

        # Update button checked state
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)

        # Trigger refresh hooks where needed
        if key == "dashboard":
            self.dashboard_page.refresh()
        elif key == "notifications":
            self.notifications_page.refresh()

    # ----- Open external windows (reuse existing logic) -----

    def open_game(self):
        if self.game_win is None:
            self.game_win = PatientGameWindow()
        self.game_win.show()
        self.game_win.raise_()
        self.game_win.activateWindow()

    def open_monitor(self):
        if self.patient_win is None:
            self.patient_win = PatientWindow()
        self.patient_win.show()
        self.patient_win.raise_()
        self.patient_win.activateWindow()

    def open_dual(self):
        if self.dual_win is None:
            self.dual_win = DualPatientGameWindow()
        self.dual_win.show()
        self.dual_win.raise_()
        self.dual_win.activateWindow()

    def open_calendar_popup(self):
        """
        Optional: if you ever still want a separate, stand-alone calendar window.
        Not currently used, but kept for flexibility.
        """
        if self.calendar_popup is None:
            self.calendar_popup = DashboardWindow()
        self.calendar_popup.show()
        self.calendar_popup.raise_()
        self.calendar_popup.activateWindow()


# =====================================================================
#  Entry point
# =====================================================================

def main():
    app = QApplication(sys.argv)
    win = PatientShellWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
