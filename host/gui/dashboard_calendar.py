# host/gui/dashboard_calendar.py #version 2

"""
Dashboard calendar file gets information from /data/sessions_log.json
and /data/patient_profile.json (for rehab start date).
"""

import os
import sys
import json
from collections import defaultdict
from datetime import datetime, date, timedelta

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QTextCharFormat, QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLabel,
    QCalendarWidget,
    QHBoxLayout,
    QGroupBox,
)

# ---------- PATH SETUP ----------
GUI_DIR = os.path.dirname(__file__)          # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
SESSIONS_LOG_PATH = os.path.join(DATA_DIR, "sessions_log.json")
PATIENT_PROFILE_PATH = os.path.join(DATA_DIR, "patient_profile.json")


class AdherenceCalendar(QCalendarWidget):
    """
    Calendar that colors each day according to session adherence:
      - pre-start days (before rehab start): dark gray
      - rehab start date: brown
      - future days (after today): light gray "upcoming"
      - past days with no session: solid bright red
      - past days with sessions: color by how many fingers used + combo reps
      - today: translucent bright blue (same hue as "current selection", but transparent)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setGridVisible(True)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)

        # Rehab start date from patient_profile.json (may be None)
        self.start_date: date | None = self._load_start_date()

        # Map: date -> {"fingers_used": int, "has_combo": bool}
        self.day_summary = self._load_day_summary()

        # Make weekday headers (Sun..Sat) all white text instead of red weekends
        self._configure_weekday_formats()

        self._apply_colors()

    # ----- Data loading -----

    def _load_start_date(self) -> date | None:
        """
        Reads patient_profile.json and returns start_date as a date object,
        or None if missing / invalid.
        """
        if not os.path.isfile(PATIENT_PROFILE_PATH):
            return None
        try:
            with open(PATIENT_PROFILE_PATH, "r") as f:
                profile = json.load(f)
        except Exception:
            return None

        s = profile.get("start_date")
        if not s:
            return None
        try:
            return date.fromisoformat(s)
        except Exception:
            return None

    def _load_day_summary(self):
        """
        Read sessions_log.json and compute a daily summary:
          { date(): {"fingers_used": N, "has_combo": bool} }
        """
        summary = defaultdict(lambda: {"fingers_used": 0, "has_combo": False})

        if not os.path.isfile(SESSIONS_LOG_PATH):
            return summary

        try:
            with open(SESSIONS_LOG_PATH, "r") as f:
                sessions = json.load(f)
        except Exception:
            return summary

        for sess in sessions:
            ts_str = sess.get("timestamp")
            reps = sess.get("reps_per_channel", [])
            combo_reps = int(sess.get("combo_reps", 0))

            if not ts_str:
                continue

            try:
                ts = datetime.fromisoformat(ts_str)
            except Exception:
                continue

            d = ts.date()
            fingers_used = sum(1 for r in reps if isinstance(r, (int, float)) and r > 0)
            has_combo = combo_reps > 0

            # If multiple sessions in same day, keep the "max" usage
            prev = summary[d]
            summary[d] = {
                "fingers_used": max(prev["fingers_used"], fingers_used),
                "has_combo": prev["has_combo"] or has_combo,
            }

        return summary

    # ----- Visual configuration -----

    def _configure_weekday_formats(self):
        """
        Make weekday headers & date text all white (no red weekends).
        """
        base_fmt = QTextCharFormat()
        base_fmt.setForeground(QBrush(QColor("#FFFFFF"))) # white
        base_fmt.setFontWeight(QFont.Weight.ExtraBold)

        for dow in (
            Qt.DayOfWeek.Monday,
            Qt.DayOfWeek.Tuesday,
            Qt.DayOfWeek.Wednesday,
            Qt.DayOfWeek.Thursday,
            Qt.DayOfWeek.Friday,
            Qt.DayOfWeek.Saturday,
            Qt.DayOfWeek.Sunday,
        ):
            self.setWeekdayTextFormat(dow, base_fmt)

    def _format_for_status(self, status: str) -> QTextCharFormat:
        """
        Map logical status -> QTextCharFormat (background color).
        Foreground stays white from _configure_weekday_formats().
        """
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold)

        if status == "pre_start":
            # Before rehab start date
            fmt.setBackground(QBrush(QColor("#424242")))  # dark gray
        elif status == "start_date":
            # Rehab start date itself (brown tile)
            fmt.setBackground(QBrush(QColor("#6D4C41")))
        elif status == "upcoming":
            # Future from "today"
            fmt.setBackground(QBrush(QColor("#BDBDBD")))  # light gray
        elif status == "today":
            # Current day – translucent bright blue
            c = QColor(0, 0, 255, 127)
            c.setAlpha(250)  # bright transparent
            fmt.setBackground(QBrush(c))
        elif status == "missed":
            # Solid bright red for missed
            fmt.setBackground(QBrush(QColor("#F44336")))
        elif status == "level_1":
            fmt.setBackground(QBrush(QColor("#FFEB3B")))  # yellow
        elif status == "level_2":
            fmt.setBackground(QBrush(QColor("#CDDC39")))  # yellow-green
        elif status == "level_3":
            fmt.setBackground(QBrush(QColor("#8BC34A")))  # medium green
        elif status == "level_4":
            fmt.setBackground(QBrush(QColor("#4CAF50")))  # strong green
        elif status == "level_4_combo":
            fmt.setBackground(QBrush(QColor("#2E7D32")))  # darkest green

        return fmt

    def _status_for_date(self, d: date) -> str:
        today = date.today()

        # Handle rehab start date, if present
        if self.start_date is not None:
            if d < self.start_date:
                return "pre_start"
            if d == self.start_date:
                return "start_date"

        # Today gets its own translucent-blue highlight
        if d == today:
            return "today"

        # Pure future days (after today) are "upcoming"
        if d > today:
            return "upcoming"

        # Past days: look at adherence
        day_info = self.day_summary.get(d)

        if day_info is None or day_info["fingers_used"] == 0:
            # past day, no session
            return "missed"

        fingers = day_info["fingers_used"]
        has_combo = day_info["has_combo"]

        if fingers <= 1:
            return "level_1"
        elif fingers == 2:
            return "level_2"
        elif fingers == 3:
            return "level_3"
        else:
            # 4 fingers used
            return "level_4_combo" if has_combo else "level_4"

    def _apply_colors(self):
        """
        Color a multi-year window so that trailing/leading days
        in adjacent months are not left in the default dark theme.
        """
        # Clear any previous formats
        self.setDateTextFormat(QDate(), QTextCharFormat())

        today = date.today()
        years = [today.year]
        if self.start_date is not None:
            years.append(self.start_date.year)

        year_min = min(years) - 1
        year_max = max(years) + 1

        start = date(year_min, 1, 1)
        end = date(year_max, 12, 31)

        cur = start
        while cur <= end:
            status = self._status_for_date(cur)
            fmt = self._format_for_status(status)
            self.setDateTextFormat(QDate(cur.year, cur.month, cur.day), fmt)
            cur = cur + timedelta(days=1)


class DashboardWindow(QWidget):
    """
    Simple dashboard window that shows:
      - Title & legend
      - Adherence calendar
    Can be used as the patient dashboard or clinician dashboard.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Cardinal Grip – Adherence Dashboard")
        self.resize(600, 450)

        layout = QVBoxLayout()
        self.setLayout(layout)

        title = QLabel("Exercise Calendar")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(title)

        # Calendar
        self.calendar = AdherenceCalendar()
        layout.addWidget(self.calendar, stretch=1)

        # Legend
        legend_group = QGroupBox("Legend")
        legend_layout = QHBoxLayout()
        legend_group.setLayout(legend_layout)

        def legend_item(text, status_key):
            swatch = QLabel("   ")
            swatch.setFixedSize(24, 16)
            fmt = self.calendar._format_for_status(status_key)
            brush = fmt.background()
            color = brush.color()
            swatch.setStyleSheet(
                f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});"
                "border: 1px solid #555;"
            )
            label = QLabel(text)
            label.setStyleSheet("color: white;")
            box = QVBoxLayout()
            w = QWidget()
            box.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignCenter)
            box.addWidget(label, alignment=Qt.AlignmentFlag.AlignCenter)
            w.setLayout(box)
            return w

        # Replace "Pre-start period" with explicit brown start date in legend
        legend_layout.addWidget(legend_item("Start date", "start_date"))
        legend_layout.addWidget(legend_item("Upcoming", "upcoming"))
        legend_layout.addWidget(legend_item("Missed", "missed"))
        legend_layout.addWidget(legend_item("1 finger", "level_1"))
        legend_layout.addWidget(legend_item("2 fingers", "level_2"))
        legend_layout.addWidget(legend_item("3 fingers", "level_3"))
        legend_layout.addWidget(legend_item("4 fingers", "level_4"))
        legend_layout.addWidget(legend_item("4 + combo", "level_4_combo"))

        layout.addWidget(legend_group)


def main():
    app = QApplication(sys.argv)
    win = DashboardWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
