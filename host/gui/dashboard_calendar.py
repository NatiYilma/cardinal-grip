# host/gui/dashboard_calendar.py

import os
import sys
import json
from collections import defaultdict
from datetime import datetime, date

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


SESSIONS_LOG_PATH = os.path.join(PROJECT_ROOT, "data", "sessions_log.json")


class AdherenceCalendar(QCalendarWidget):
    """
    Calendar that colors each day according to session adherence:
      - future days: gray (upcoming)
      - past days with no session: translucent red
      - past days with sessions: color by how many fingers used + combo reps.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setGridVisible(True)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)

        # Map: date -> {"fingers_used": int, "has_combo": bool}
        self.day_summary = self._load_day_summary()

        self._apply_colors()

    # ----- Data loading / summarizing -----

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

            # If multiple sessions in same day, we keep the "max" usage
            prev = summary[d]
            summary[d] = {
                "fingers_used": max(prev["fingers_used"], fingers_used),
                "has_combo": prev["has_combo"] or has_combo,
            }

        return summary

    # ----- Coloring logic -----

    def _format_for_status(self, status: str) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Normal)

        if status == "upcoming":
            fmt.setBackground(QBrush(QColor("#BDBDBD")))  # gray
        elif status == "missed":
            fmt.setBackground(QBrush(QColor(244, 67, 54, 80)))  # translucent red
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

        if d > today:
            return "upcoming"

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
        Walk over the visible month ±1 and apply formats.
        (For performance, you could limit the range, but this is fine for a calendar.)
        """
        # Clear any previous formats
        self.setDateTextFormat(QDate(), QTextCharFormat())

        # We’ll color from Jan 1 of this year to Dec 31 of this year for now
        year = date.today().year
        start = date(year, 1, 1)
        end = date(year, 12, 31)

        cur = start
        while cur <= end:
            status = self._status_for_date(cur)
            fmt = self._format_for_status(status)
            self.setDateTextFormat(QDate(cur.year, cur.month, cur.day), fmt)
            cur = date.fromordinal(cur.toordinal() + 1)


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
            box = QVBoxLayout()
            w = QWidget()
            box.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignCenter)
            box.addWidget(label, alignment=Qt.AlignmentFlag.AlignCenter)
            w.setLayout(box)
            return w

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
