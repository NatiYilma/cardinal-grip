# host/gui/patient_dashboard/patient_game_app.py  # version 9 – with latency via BaseBackend

import os
import sys
import json
import time
from datetime import datetime

from PyQt6.QtCore import QTimer, Qt, QUrl
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QSlider,
    QProgressBar,
    QMessageBox,
    QGroupBox,
)
from PyQt6.QtGui import QFont, QPainter, QPen, QColor
from PyQt6.QtMultimedia import QSoundEffect

# -------- PATH SETUP --------
PATIENT_DASHBOARD_DIR = os.path.dirname(__file__)   # .../host/gui/patient_dashboard
GUI_DIR = os.path.dirname(PATIENT_DASHBOARD_DIR)    # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)                 # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)            # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from host.gui.session_logging import log_session_completion

from comms.serial_backend import SerialBackend, auto_detect_port
# ================================================================


NUM_CHANNELS = 4
CHANNEL_NAMES = ["Index", "Middle", "Ring", "Pinky"]

HOLD_SECONDS = 5.0  # seconds in-band to count a rep


class ThresholdProgressBar(QProgressBar):
    """Vertical progress bar with faint dashed lines for min/max thresholds."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._min_thresh: int | None = None
        self._max_thresh: int | None = None

    def set_thresholds(self, min_val: int, max_val: int):
        self._min_thresh = min_val
        self._max_thresh = max_val
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        if self._min_thresh is None or self._max_thresh is None:
            return

        rect = self.contentsRect()
        if rect.height() <= 0:
            return

        minimum = self.minimum()
        maximum = self.maximum()
        span = maximum - minimum
        if span <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(0, 0, 0, 120))  # faint gray
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setWidth(1)
        painter.setPen(pen)

        def draw_for_value(v):
            v_clamped = max(minimum, min(maximum, v))
            frac = (v_clamped - minimum) / span
            y = rect.bottom() - frac * rect.height()
            painter.drawLine(rect.left() + 2, int(y), rect.right() - 2, int(y))

        draw_for_value(self._min_thresh)
        draw_for_value(self._max_thresh)

        painter.end()


class PatientGameWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Patient Game Mode")
        self.resize(1100, 700)
        print("Patient Game Window Launched and Running")

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # --- Backend and state ---
        self.backend: SerialBackend | None = None
        self.last_time = None

        self.hold_time = [0.0] * NUM_CHANNELS
        self.in_band_prev = [False] * NUM_CHANNELS

        self.combo_hold_time = 0.0
        self.combo_reps = 0
        self.last_all_in_band = False

        self.session_start_time: float | None = None
        self.current_session_id: str | None = None

        # Persistent stats
        self.reps_per_channel = [0] * NUM_CHANNELS
        self.sessions_completed = 0
        self.stats_path = os.path.join(PROJECT_ROOT, "data", "patient_stats.json")
        self._load_stats()

        self.emoji_cycle = ["👍", "👏", "🙌", "👌"]
        self.emoji_index = 0

        # Audio
        self.sounds: dict[str, QSoundEffect | None] = {}
        self._init_sounds()
        self.combo_fail_sounds = [
            self.sounds.get("oof"),
            self.sounds.get("spongebob"),
            self.sounds.get("bruh"),
        ]
        self.combo_success_sounds = [
            self.sounds.get("rizz"),
            self.sounds.get("wow"),
            self.sounds.get("yay"),
        ]
        self.combo_fail_index = 0
        self.combo_success_index = 0

        # === UI ===
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # ----- Top: serial controls -----
        top_row = QHBoxLayout()

        top_row.addWidget(QLabel("Serial port:"))
        self.port_edit = QLineEdit("")
        self.port_edit.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.port_edit.setFixedWidth(220)

        try:
            detected = auto_detect_port()
        except Exception:
            detected = None

        if detected:
            self.port_edit.setPlaceholderText(detected)
        else:
            self.port_edit.setPlaceholderText("Auto-detecting port...")
        top_row.addWidget(self.port_edit)

        top_row.addWidget(QLabel("Baud:"))
        self.baud_edit = QLineEdit("115200")
        self.baud_edit.setPlaceholderText("115200")
        self.baud_edit.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.baud_edit.setFixedWidth(80)
        self.baud_edit.setReadOnly(False)
        top_row.addWidget(self.baud_edit)

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.handle_connect)
        top_row.addWidget(self.connect_button)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.handle_disconnect)
        self.disconnect_button.setEnabled(False)
        top_row.addWidget(self.disconnect_button)

        self.start_button = QPushButton("Start Session")
        self.start_button.clicked.connect(self.start_session)
        self.start_button.setEnabled(False)
        top_row.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Session")
        self.stop_button.clicked.connect(self.stop_session)
        self.stop_button.setEnabled(False)
        top_row.addWidget(self.stop_button)

        main_layout.addLayout(top_row)

        self.status_label = QLabel("Status: Not connected")
        self.status_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(self.status_label)

        # ----- Target band controls -----
        band_group = QGroupBox("Target Zone (applies to all fingers)")
        band_layout = QHBoxLayout()
        band_group.setLayout(band_layout)

        band_layout.addWidget(QLabel("Min (ADC):"))
        self.target_min_slider = QSlider(Qt.Orientation.Horizontal)
        self.target_min_slider.setRange(0, 4095)
        self.target_min_slider.setValue(1200)
        band_layout.addWidget(self.target_min_slider)

        self.target_min_value_label = QLabel(str(self.target_min_slider.value()))
        self.target_min_value_label.setFixedWidth(60)
        self.target_min_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        band_layout.addWidget(self.target_min_value_label)

        band_layout.addWidget(QLabel("Max (ADC):"))
        self.target_max_slider = QSlider(Qt.Orientation.Horizontal)
        self.target_max_slider.setRange(0, 4095)
        self.target_max_slider.setValue(2000)
        band_layout.addWidget(self.target_max_slider)

        self.target_max_value_label = QLabel(str(self.target_max_slider.value()))
        self.target_max_value_label.setFixedWidth(60)
        self.target_max_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        band_layout.addWidget(self.target_max_value_label)

        band_hint = QLabel(
            f"Stay in the green zone for {HOLD_SECONDS:.0f} s to earn a rep."
        )
        band_layout.addWidget(band_hint)

        main_layout.addWidget(band_group)

        self.target_min_slider.valueChanged.connect(self._on_min_slider_changed)
        self.target_max_slider.valueChanged.connect(self._on_max_slider_changed)

        # ----- Center: per-finger bars -----
        center_row = QHBoxLayout()
        main_layout.addLayout(center_row, stretch=1)

        self.bar_widgets: list[ThresholdProgressBar] = []
        self.value_labels: list[QLabel] = []
        self.countdown_labels: list[QLabel] = []
        self.rep_labels: list[QLabel] = []

        for i in range(NUM_CHANNELS):
            col = QVBoxLayout()

            name_label = QLabel(CHANNEL_NAMES[i])
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            col.addWidget(name_label)

            bar = ThresholdProgressBar()
            bar.setOrientation(Qt.Orientation.Vertical)
            bar.setRange(0, 4095)
            bar.setValue(0)
            bar.setFixedWidth(60)
            bar.setStyleSheet("QProgressBar::chunk { background-color: orange; }")
            col.addWidget(bar, stretch=1, alignment=Qt.AlignmentFlag.AlignHCenter)
            self.bar_widgets.append(bar)

            val_label = QLabel("Force: 0")
            val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(val_label)
            self.value_labels.append(val_label)

            cd_label = QLabel("Hold: –")
            cd_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cd_label.setStyleSheet("font-size: 11pt;")
            col.addWidget(cd_label)
            self.countdown_labels.append(cd_label)

            rep_label = QLabel(f"Reps: {self.reps_per_channel[i]}")
            rep_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rep_label.setStyleSheet("font-size: 11pt; font-weight: bold;")
            col.addWidget(rep_label)
            self.rep_labels.append(rep_label)

            center_row.addLayout(col)

        self._update_band_labels()

        # ----- All-fingers combo group -----
        combo_group = QGroupBox("All-Fingers Challenge")
        combo_layout = QVBoxLayout()
        combo_group.setLayout(combo_layout)

        self.combo_info_label = QLabel(
            f"When ALL fingers are in the green zone for {HOLD_SECONDS:.0f} seconds, "
            "you earn a combo rep!"
        )
        combo_layout.addWidget(self.combo_info_label)

        self.combo_bar = QProgressBar()
        self.combo_bar.setRange(0, 100)
        self.combo_bar.setValue(0)
        self.combo_bar.setTextVisible(True)
        self.combo_bar.setFormat("All-fingers hold: %p%")
        combo_layout.addWidget(self.combo_bar)

        self.combo_countdown_label = QLabel("All-fingers hold: –")
        self.combo_countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.combo_countdown_label.setStyleSheet("font-size: 11pt;")
        combo_layout.addWidget(self.combo_countdown_label)

        self.combo_reps_label = QLabel(f"All-fingers reps: {self.combo_reps}")
        self.combo_reps_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.combo_reps_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        combo_layout.addWidget(self.combo_reps_label)

        self.emoji_label = QLabel("")
        self.emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emoji_font = QFont("Arial", 32)
        self.emoji_label.setFont(emoji_font)
        combo_layout.addWidget(self.emoji_label)

        main_layout.addWidget(combo_group)

        # ----- Bottom: stats -----
        bottom_row = QHBoxLayout()
        self.total_reps_label = QLabel(self._total_reps_text())
        self.total_reps_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        bottom_row.addWidget(self.total_reps_label)

        self.session_count_label = QLabel(
            f"Sessions completed (game mode): {self.sessions_completed}"
        )
        bottom_row.addWidget(self.session_count_label)

        main_layout.addLayout(bottom_row)

        # Timer
        self.timer = QTimer()
        self.timer.setInterval(20)  # 20 ms -> ~50 Hz
        self.timer.timeout.connect(self.game_tick)

    # -------- Audio helpers --------

    def _init_sounds(self):
        audio_dir = os.path.join(PROJECT_ROOT, "audio")

        def make_sound(filename: str) -> QSoundEffect | None:
            path = os.path.join(audio_dir, filename)
            if not os.path.isfile(path):
                return None
            s = QSoundEffect()
            s.setSource(QUrl.fromLocalFile(path))
            s.setVolume(0.9)
            return s

        self.sounds["applepay"] = make_sound("applepay_mono.wav")
        self.sounds["bruh"] = make_sound("bruh_mono.wav")
        self.sounds["duolingo"] = make_sound("duolingo_mono.wav")
        self.sounds["mario"] = make_sound("mario_mono.wav")
        self.sounds["oof"] = make_sound("oof_mono.wav")
        self.sounds["rizz"] = make_sound("rizz_mono.wav")
        self.sounds["spongebob"] = make_sound("spongebob_mono.wav")
        self.sounds["wow"] = make_sound("wow_mono.wav")
        self.sounds["yay"] = make_sound("yay_mono.wav")

    def _play_sound(self, sound: QSoundEffect | None):
        if sound is None:
            return
        sound.stop()
        sound.play()

    # -------- JSON stats --------

    def _load_stats(self):
        os.makedirs(os.path.join(PROJECT_ROOT, "data"), exist_ok=True)
        if not os.path.isfile(self.stats_path):
            self.reps_per_channel = [0] * NUM_CHANNELS
            self.sessions_completed = 0
            self.combo_reps = 0
            return
        try:
            with open(self.stats_path, "r") as f:
                data = json.load(f)
            self.reps_per_channel = data.get("reps_per_channel", [0] * NUM_CHANNELS)
            if len(self.reps_per_channel) != NUM_CHANNELS:
                self.reps_per_channel = [0] * NUM_CHANNELS
            self.sessions_completed = int(data.get("sessions_completed", 0))
            self.combo_reps = int(data.get("combo_reps", 0))
        except Exception:
            self.reps_per_channel = [0] * NUM_CHANNELS
            self.sessions_completed = 0
            self.combo_reps = 0

    def _save_stats(self):
        data = {
            "reps_per_channel": self.reps_per_channel,
            "sessions_completed": self.sessions_completed,
            "combo_reps": self.combo_reps,
            "last_updated": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            with open(self.stats_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _total_reps_text(self):
        total = sum(self.reps_per_channel)
        return f"Total reps across fingers: {total}"

    def _update_band_labels(self):
        tmin = self.target_min_slider.value()
        tmax = self.target_max_slider.value()
        self.target_min_value_label.setText(str(tmin))
        self.target_max_value_label.setText(str(tmax))
        for bar in self.bar_widgets:
            bar.set_thresholds(tmin, tmax)

    def _on_min_slider_changed(self, value: int):
        if value > self.target_max_slider.value():
            self.target_max_slider.blockSignals(True)
            self.target_max_slider.setValue(value)
            self.target_max_slider.blockSignals(False)
        self._update_band_labels()

    def _on_max_slider_changed(self, value: int):
        if value < self.target_min_slider.value():
            self.target_min_slider.blockSignals(True)
            self.target_min_slider.setValue(value)
            self.target_min_slider.blockSignals(False)
        self._update_band_labels()

    # -------- Connection / session --------

    def handle_connect(self):
        if self.backend is not None:
            return

        port_text = self.port_edit.text().strip()
        baud_text = self.baud_edit.text().strip()

        if not baud_text:
            baud = 115200
        else:
            try:
                baud = int(baud_text)
            except ValueError:
                QMessageBox.warning(self, "Error", "Invalid baud rate.")
                return
        if baud <= 0:
            QMessageBox.warning(self, "Error", "Baud rate must be positive.")
            return

        if not port_text or port_text.lower() == "auto":
            port_arg = None
            port_label = "auto-detect"
        else:
            port_arg = port_text
            port_label = port_text

        try:
            self.backend = SerialBackend(port=port_arg, baud=baud, timeout=0.01, num_channels=1)
            self.backend.start()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Serial error",
                f"Failed to open {port_arg or '(auto-detect)'}:\n{e}",
            )
            self.backend = None
            return

        actual_port = getattr(self.backend, "port", None) or "(auto)"
        self.status_label.setText(f"Status: Connected to {actual_port} @ {baud}")
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)

        self.start_session()
        self.start_time = time.time()
        self.timer.start()

    def handle_disconnect(self):
        self.stop_session()
        if self.backend is not None:
            self.backend.stop()
            self.backend = None
        self.status_label.setText("Status: Disconnected")
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.start_button.setEnabled(False)

    def start_session(self):
        self.hold_time = [0.0] * NUM_CHANNELS
        self.in_band_prev = [False] * NUM_CHANNELS
        self.combo_hold_time = 0.0
        self.last_time = time.time()
        self.last_all_in_band = False
        self.combo_bar.setValue(0)
        self.combo_countdown_label.setText("All-fingers hold: –")
        self.emoji_label.setText("")

        self.session_start_time = time.time()
        self.current_session_id = datetime.now().strftime("game_%Y%m%d_%H%M%S")

        self.timer.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText(
            "Status: Session running – squeeze to hit the green zone!"
        )

        self.setFocus()

    def stop_session(self):
        if self.timer.isActive():
            self.timer.stop()
            self.sessions_completed += 1
            self._save_stats()

            try:
                log_session_completion(
                    mode="game",
                    source="patient_game_app",
                    reps_per_channel=self.reps_per_channel,
                    combo_reps=self.combo_reps,
                    csv_path=None,
                    timestamp=datetime.now(),
                    session_id=self.current_session_id,
                )
            except Exception as e:
                print("Warning: failed to log session:", e)

            self.session_count_label.setText(
                f"Sessions completed (game mode): {self.sessions_completed}"
            )

        self.start_button.setEnabled(self.backend is not None)
        self.stop_button.setEnabled(False)

        self.combo_hold_time = 0.0
        self.combo_bar.setValue(0)
        self.combo_countdown_label.setText("All-fingers hold: –")
        self.last_all_in_band = False

    # -------- Game loop --------

    def game_tick(self):
        if self.backend is None:
            return

        now_gui = time.time()

        vals = self.backend.get_latest()
        if vals is None:
            return

        # Latency measurement via BaseBackend API
        last_ts = None
        if hasattr(self.backend, "get_last_timestamp"):
            last_ts = self.backend.get_last_timestamp()

        if last_ts is not None:
            age_ms = (now_gui - last_ts) * 1000.0
            if int(now_gui * 50) % 10 == 0:
                print(f"[Game: latency] age={age_ms:5.1f} ms, vals={vals}")
                # ~5–25 ms → fast pipeline
                # 100–300+ ms → delayed pipeline

        if isinstance(vals, (int, float)):
            vals = [vals] * NUM_CHANNELS
        elif isinstance(vals, (list, tuple)):
            if len(vals) < NUM_CHANNELS:
                vals = list(vals) + [0] * (NUM_CHANNELS - len(vals))
        else:
            return

        now = time.time()
        dt = 0.0 if self.last_time is None else (now - self.last_time)
        self.last_time = now

        tmin = self.target_min_slider.value()
        tmax = self.target_max_slider.value()

        in_band_flags = [False] * NUM_CHANNELS

        for i in range(NUM_CHANNELS):
            val = int(vals[i])
            val = max(0, min(4095, val))

            self.bar_widgets[i].setValue(val)
            self.value_labels[i].setText(f"Force: {val}")

            if val < tmin:
                zone = "low"
                frac_below = (val / tmin) if tmin > 0 else 0.0
                color = "orange" if frac_below < 0.5 else "yellow"
            elif val > tmax:
                zone = "high"
                span_high = max(1, 4095 - tmax)
                frac_above = (val - tmax) / span_high
                color = "darkred" if frac_above < 0.5 else "red"
            else:
                zone = "in_band"
                span = max(tmax - tmin, 1)
                frac_in = (val - tmin) / span
                if frac_in < 1 / 3:
                    color = "yellowgreen"
                elif frac_in < 2 / 3:
                    color = "green"
                else:
                    color = "darkgreen"

            in_band_flags[i] = (zone == "in_band")
            self._set_bar_color(self.bar_widgets[i], color)

            if zone == "in_band" and not self.in_band_prev[i] and self.timer.isActive():
                self._play_sound(self.sounds.get("applepay"))

            if self.timer.isActive() and zone == "in_band":
                self.hold_time[i] += dt
                remaining = max(0.0, HOLD_SECONDS - self.hold_time[i])
                if remaining > 0:
                    self.countdown_labels[i].setText(f"Hold: {remaining:0.1f} s")
                else:
                    self.reps_per_channel[i] += 1
                    self.rep_labels[i].setText(f"Reps: {self.reps_per_channel[i]}")
                    self.total_reps_label.setText(self._total_reps_text())
                    self.countdown_labels[i].setText("Nice! ✅")
                    self._play_sound(self.sounds.get("duolingo"))
                    self.hold_time[i] = 0.0
                    self._save_stats()
            else:
                self.hold_time[i] = 0.0
                self.countdown_labels[i].setText("Hold: –")

            self.in_band_prev[i] = (zone == "in_band")

        all_in_band = self.timer.isActive() and all(in_band_flags)

        if all_in_band:
            if not self.last_all_in_band:
                self._play_sound(self.sounds.get("mario"))

            self.combo_hold_time += dt
            combo_remaining = max(0.0, HOLD_SECONDS - self.combo_hold_time)
            pct = int(max(0.0, min(1.0, self.combo_hold_time / HOLD_SECONDS)) * 100.0)
            self.combo_bar.setValue(pct)

            if combo_remaining > 0:
                self.combo_countdown_label.setText(
                    f"All-fingers hold: {combo_remaining:0.1f} s"
                )
            else:
                self.combo_reps += 1
                self.combo_reps_label.setText(
                    f"All-fingers reps: {self.combo_reps}"
                )

                emoji = self.emoji_cycle[self.emoji_index]
                self.emoji_index = (self.emoji_index + 1) % len(self.emoji_cycle)
                self.emoji_label.setText(emoji)

                if self.combo_success_sounds:
                    s = self.combo_success_sounds[self.combo_success_index]
                    self.combo_success_index = (
                        self.combo_success_index + 1
                    ) % len(self.combo_success_sounds)
                    self._play_sound(s)

                self.combo_hold_time = 0.0
                self.combo_bar.setValue(0)
                self.combo_countdown_label.setText("Great job! 🎉")
                self._save_stats()
        else:
            if (
                self.last_all_in_band
                and self.timer.isActive()
                and self.combo_hold_time > 0.0
            ):
                if self.combo_fail_sounds:
                    s = self.combo_fail_sounds[self.combo_fail_index]
                    self.combo_fail_index = (
                        self.combo_fail_index + 1
                    ) % len(self.combo_fail_sounds)
                    self._play_sound(s)

            self.combo_hold_time = 0.0
            self.combo_bar.setValue(0)
            self.combo_countdown_label.setText("All-fingers hold: –")

        self.last_all_in_band = all_in_band

    # ---- Keyboard → backend passthrough (SimBackend) ----
    def keyPressEvent(self, event):
        if self.backend is not None and hasattr(self.backend, "handle_char"):
            ch = event.text()
            if ch:
                self.backend.handle_char(ch, True)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if self.backend is not None and hasattr(self.backend, "handle_char"):
            ch = event.text()
            if ch:
                self.backend.handle_char(ch, False)
        super().keyReleaseEvent(event)

    # ---- Color helper ----
    def _set_bar_color(self, bar: QProgressBar, color: str):
        palette = {
            "orange": "#FF9800",
            "yellow": "#FFEB3B",
            "yellowgreen": "#CDDC39",
            "green": "#4CAF50",
            "darkgreen": "#2E7D32",
            "darkred": "#B71C1C",
            "red": "#F44336",
        }
        chunk_color = palette.get(color, "#FF9800")

        bar.setStyleSheet(
            "QProgressBar {"
            "  border: 1px solid #999;"
            "  border-radius: 3px;"
            "  background: #eee;"
            "}"
            f"QProgressBar::chunk {{ background-color: {chunk_color}; }}"
        )


def main():
    app = QApplication(sys.argv)
    win = PatientGameWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
