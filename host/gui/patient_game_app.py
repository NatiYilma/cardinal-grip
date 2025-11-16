# # host/gui/patient_game_app.py

# import os
# import sys
# import json
# import time
# from datetime import datetime

# from PyQt6.QtCore import QTimer, Qt, QUrl
# from PyQt6.QtWidgets import (
#     QApplication,
#     QWidget,
#     QVBoxLayout,
#     QHBoxLayout,
#     QLabel,
#     QPushButton,
#     QLineEdit,
#     QSlider,
#     QProgressBar,
#     QMessageBox,
#     QGroupBox,
# )
# from PyQt6.QtGui import QFont
# from PyQt6.QtMultimedia import QSoundEffect

# # -------- PATH SETUP (same pattern as other GUIs) --------
# GUI_DIR = os.path.dirname(__file__)          # .../host/gui
# HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
# PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

# if PROJECT_ROOT not in sys.path:
#     sys.path.append(PROJECT_ROOT)

# from comms.serial_backend import SerialBackend  # noqa: E402
# # --------------------------------------------------------


# NUM_CHANNELS = 4
# CHANNEL_NAMES = ["Index", "Middle", "Ring", "Pinky"]

# # Seconds the finger must stay in target band to count a rep
# HOLD_SECONDS = 5.0


# class PatientGameWindow(QWidget):
#     def __init__(self):
#         super().__init__()

#         self.setWindowTitle("Cardinal Grip – Patient Game Mode")
#         self.resize(1100, 700)

#         # --- Serial + data state ---
#         self.backend: SerialBackend | None = None
#         self.last_time = None  # for dt calculation in timer

#         # One hold timer per channel (seconds spent continuously in band)
#         self.hold_time = [0.0] * NUM_CHANNELS
#         self.in_band_prev = [False] * NUM_CHANNELS

#         # All-fingers simultaneous hold
#         self.combo_hold_time = 0.0    # seconds all fingers are in band
#         self.combo_reps = 0           # all-finger reps
#         self.last_all_in_band = False

#         # Persistent reps per channel, loaded/saved from JSON
#         self.reps_per_channel = [0] * NUM_CHANNELS
#         self.sessions_completed = 0
#         self.stats_path = os.path.join(PROJECT_ROOT, "data", "patient_stats.json")
#         self._load_stats()

#         # Emoji sequence for success feedback
#         self.emoji_cycle = ["👍", "👏", "🙌", "👌"]
#         self.emoji_index = 0

#         # --- Audio setup ---
#         self.sounds = {}
#         self._init_sounds()

#         # Fail / success cycles for combo
#         self.combo_fail_sounds = [
#             self.sounds.get("oof"),
#             self.sounds.get("spongebob"),
#             self.sounds.get("bruh"),
#         ]
#         self.combo_success_sounds = [
#             self.sounds.get("rizz"),
#             self.sounds.get("wow"),
#             self.sounds.get("yay"),
#         ]
#         self.combo_fail_index = 0
#         self.combo_success_index = 0

#         # --- UI ---
#         main_layout = QVBoxLayout()
#         self.setLayout(main_layout)

#         # ===== TOP: serial + control bar =====
#         top_row = QHBoxLayout()

#         top_row.addWidget(QLabel("Serial port:"))
#         # Use your current default Feather ESP32-S3 port
#         self.port_edit = QLineEdit("/dev/cu.usbmodem14101")
#         self.port_edit.setFixedWidth(220)
#         top_row.addWidget(self.port_edit)

#         top_row.addWidget(QLabel("Baud:"))
#         self.baud_edit = QLineEdit("115200")
#         self.baud_edit.setFixedWidth(80)
#         top_row.addWidget(self.baud_edit)

#         self.connect_button = QPushButton("Connect")
#         self.connect_button.clicked.connect(self.handle_connect)
#         top_row.addWidget(self.connect_button)

#         self.disconnect_button = QPushButton("Disconnect")
#         self.disconnect_button.clicked.connect(self.handle_disconnect)
#         self.disconnect_button.setEnabled(False)
#         top_row.addWidget(self.disconnect_button)

#         self.start_button = QPushButton("Start Session")
#         self.start_button.clicked.connect(self.start_session)
#         self.start_button.setEnabled(False)
#         top_row.addWidget(self.start_button)

#         self.stop_button = QPushButton("Stop Session")
#         self.stop_button.clicked.connect(self.stop_session)
#         self.stop_button.setEnabled(False)
#         top_row.addWidget(self.stop_button)

#         main_layout.addLayout(top_row)

#         # Status line
#         self.status_label = QLabel("Status: Not connected")
#         self.status_label.setStyleSheet("font-weight: bold;")
#         main_layout.addWidget(self.status_label)

#         # ===== TARGET BAND CONTROLS =====
#         band_group = QGroupBox("Target Zone (applies to all fingers)")
#         band_layout = QHBoxLayout()
#         band_group.setLayout(band_layout)

#         band_layout.addWidget(QLabel("Min (ADC):"))
#         self.target_min_slider = QSlider(Qt.Orientation.Horizontal)
#         self.target_min_slider.setRange(0, 4095)
#         self.target_min_slider.setValue(1200)
#         band_layout.addWidget(self.target_min_slider)

#         band_layout.addWidget(QLabel("Max (ADC):"))
#         self.target_max_slider = QSlider(Qt.Orientation.Horizontal)
#         self.target_max_slider.setRange(0, 4095)
#         self.target_max_slider.setValue(2000)
#         band_layout.addWidget(self.target_max_slider)

#         self.band_hint_label = QLabel(
#             f"Stay in the green zone for {HOLD_SECONDS:.0f} seconds to earn a rep."
#         )
#         band_layout.addWidget(self.band_hint_label)

#         main_layout.addWidget(band_group)

#         # ===== CENTER: per-finger game bars =====
#         center_row = QHBoxLayout()
#         main_layout.addLayout(center_row, stretch=1)

#         self.bar_widgets = []
#         self.value_labels = []
#         self.countdown_labels = []
#         self.rep_labels = []

#         for i in range(NUM_CHANNELS):
#             col = QVBoxLayout()

#             # Finger name
#             name_label = QLabel(CHANNEL_NAMES[i])
#             name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#             name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
#             col.addWidget(name_label)

#             # Vertical bar (force)
#             bar = QProgressBar()
#             bar.setOrientation(Qt.Orientation.Vertical)
#             bar.setRange(0, 4095)
#             bar.setValue(0)
#             bar.setFixedWidth(60)
#             bar.setStyleSheet("QProgressBar::chunk { background-color: orange; }")
#             col.addWidget(bar, stretch=1, alignment=Qt.AlignmentFlag.AlignHCenter)
#             self.bar_widgets.append(bar)

#             # Current value label
#             val_label = QLabel("Force: 0")
#             val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#             col.addWidget(val_label)
#             self.value_labels.append(val_label)

#             # Countdown label
#             cd_label = QLabel("Hold: –")
#             cd_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#             cd_label.setStyleSheet("font-size: 11pt;")
#             col.addWidget(cd_label)
#             self.countdown_labels.append(cd_label)

#             # Rep count label (persistent over runs)
#             rep_label = QLabel(f"Reps: {self.reps_per_channel[i]}")
#             rep_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#             rep_label.setStyleSheet("font-size: 11pt; font-weight: bold;")
#             col.addWidget(rep_label)
#             self.rep_labels.append(rep_label)

#             center_row.addLayout(col)

#         # ===== ALL-FINGERS COMBO GROUP =====
#         combo_group = QGroupBox("All-Fingers Challenge")
#         combo_layout = QVBoxLayout()
#         combo_group.setLayout(combo_layout)

#         self.combo_info_label = QLabel(
#             f"When ALL fingers are in the green zone for {HOLD_SECONDS:.0f} seconds, "
#             "you earn a combo rep!"
#         )
#         combo_layout.addWidget(self.combo_info_label)

#         # Horizontal progress bar for all-fingers hold
#         self.combo_bar = QProgressBar()
#         self.combo_bar.setRange(0, 100)  # percent of HOLD_SECONDS
#         self.combo_bar.setValue(0)
#         self.combo_bar.setTextVisible(True)
#         self.combo_bar.setFormat("All-fingers hold: %p%")
#         combo_layout.addWidget(self.combo_bar)

#         # All-fingers countdown label
#         self.combo_countdown_label = QLabel("All-fingers hold: –")
#         self.combo_countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#         self.combo_countdown_label.setStyleSheet("font-size: 11pt;")
#         combo_layout.addWidget(self.combo_countdown_label)

#         # Combo reps label
#         self.combo_reps_label = QLabel(f"All-fingers reps: {self.combo_reps}")
#         self.combo_reps_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#         self.combo_reps_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
#         combo_layout.addWidget(self.combo_reps_label)

#         # Emoji label
#         self.emoji_label = QLabel("")
#         self.emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#         emoji_font = QFont("Arial", 32)
#         self.emoji_label.setFont(emoji_font)
#         combo_layout.addWidget(self.emoji_label)

#         main_layout.addWidget(combo_group)

#         # ===== BOTTOM: overall stats =====
#         bottom_row = QHBoxLayout()
#         self.total_reps_label = QLabel(self._total_reps_text())
#         self.total_reps_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
#         bottom_row.addWidget(self.total_reps_label)

#         self.session_count_label = QLabel(
#             f"Sessions completed (game mode): {self.sessions_completed}"
#         )
#         bottom_row.addWidget(self.session_count_label)

#         main_layout.addLayout(bottom_row)

#         # ===== TIMER =====
#         self.timer = QTimer()
#         self.timer.setInterval(50)  # 20 Hz
#         self.timer.timeout.connect(self.game_tick)

#     # ------------- AUDIO HELPERS -------------

#     def _init_sounds(self):
#         """Load all .wav files from PROJECT_ROOT/audio into QSoundEffect objects."""
#         audio_dir = os.path.join(PROJECT_ROOT, "audio")

#         def make_sound(name: str, filename: str) -> QSoundEffect | None:
#             path = os.path.join(audio_dir, filename)
#             if not os.path.isfile(path):
#                 # Don't crash if file is missing; just skip it.
#                 return None
#             s = QSoundEffect()
#             s.setSource(QUrl.fromLocalFile(path))
#             s.setVolume(0.9)  # 0.0–1.0
#             return s

#         self.sounds["applepay"] = make_sound("applepay", "applepay.wav")
#         self.sounds["bruh"] = make_sound("bruh", "bruh.wav")
#         self.sounds["yay"] = make_sound("yay", "yay.wav")
#         self.sounds["mario"] = make_sound("mario", "mario.wav")
#         self.sounds["oof"] = make_sound("oof", "oof.wav")
#         self.sounds["rizz"] = make_sound("rizz", "rizz.wav")
#         self.sounds["spongebob"] = make_sound("spongebob", "spongebob.wav")
#         self.sounds["wow"] = make_sound("wow", "wow.wav")
#         self.sounds["duolingo"] = make_sound("duolingo", "duolingo.wav")

#     def _play_sound(self, sound: QSoundEffect | None):
#         """Safely play a sound if it exists."""
#         if sound is None:
#             return
#         # Restart from beginning each time
#         sound.stop()
#         sound.play()

#     # ------------- STATS PERSISTENCE (JSON) -------------

#     def _load_stats(self):
#         os.makedirs(os.path.join(PROJECT_ROOT, "data"), exist_ok=True)
#         if not os.path.isfile(self.stats_path):
#             # default structure
#             self.reps_per_channel = [0] * NUM_CHANNELS
#             self.sessions_completed = 0
#             self.combo_reps = 0
#             return
#         try:
#             with open(self.stats_path, "r") as f:
#                 data = json.load(f)
#             self.reps_per_channel = data.get("reps_per_channel", [0] * NUM_CHANNELS)
#             if len(self.reps_per_channel) != NUM_CHANNELS:
#                 self.reps_per_channel = [0] * NUM_CHANNELS
#             self.sessions_completed = int(data.get("sessions_completed", 0))
#             self.combo_reps = int(data.get("combo_reps", 0))
#         except Exception:
#             # If corrupted, reset
#             self.reps_per_channel = [0] * NUM_CHANNELS
#             self.sessions_completed = 0
#             self.combo_reps = 0

#     def _save_stats(self):
#         data = {
#             "reps_per_channel": self.reps_per_channel,
#             "sessions_completed": self.sessions_completed,
#             "combo_reps": self.combo_reps,
#             "last_updated": datetime.now().isoformat(timespec="seconds"),
#         }
#         try:
#             with open(self.stats_path, "w") as f:
#                 json.dump(data, f, indent=2)
#         except Exception:
#             # Don't crash GUI if writing fails
#             pass

#     def _total_reps_text(self):
#         total = sum(self.reps_per_channel)
#         return f"Total reps across fingers: {total}"

#     # ------------- CONNECTION / SESSION CONTROL -------------

#     def handle_connect(self):
#         if self.backend is not None:
#             return
#         port = self.port_edit.text().strip()
#         try:
#             baud = int(self.baud_edit.text().strip())
#         except ValueError:
#             QMessageBox.warning(self, "Error", "Invalid baud rate.")
#             return

#         try:
#             self.backend = SerialBackend(port=port, baud=baud, timeout=0.01)
#             self.backend.start()
#         except Exception as e:
#             QMessageBox.critical(self, "Serial error", f"Failed to open {port}:\n{e}")
#             self.backend = None
#             return

#         self.status_label.setText(f"Status: Connected to {port} @ {baud}")
#         self.connect_button.setEnabled(False)
#         self.disconnect_button.setEnabled(True)
#         self.start_button.setEnabled(True)

#     def handle_disconnect(self):
#         self.stop_session()
#         if self.backend is not None:
#             self.backend.stop()
#             self.backend = None
#         self.status_label.setText("Status: Disconnected")
#         self.connect_button.setEnabled(True)
#         self.disconnect_button.setEnabled(False)
#         self.start_button.setEnabled(False)

#     def start_session(self):
#         # Reset per-session hold timers ONLY (not reps)
#         self.hold_time = [0.0] * NUM_CHANNELS
#         self.in_band_prev = [False] * NUM_CHANNELS
#         self.combo_hold_time = 0.0
#         self.last_time = time.time()
#         self.last_all_in_band = False
#         self.combo_bar.setValue(0)
#         self.combo_countdown_label.setText("All-fingers hold: –")
#         self.emoji_label.setText("")

#         self.timer.start()
#         self.start_button.setEnabled(False)
#         self.stop_button.setEnabled(True)
#         self.status_label.setText(
#             "Status: Session running – squeeze to hit the green zone!"
#         )

#     def stop_session(self):
#         if self.timer.isActive():
#             self.timer.stop()
#             self.sessions_completed += 1
#             self._save_stats()
#             self.session_count_label.setText(
#                 f"Sessions completed (game mode): {self.sessions_completed}"
#             )
#         self.start_button.setEnabled(self.backend is not None)
#         self.stop_button.setEnabled(False)

#         # Reset combo bar visuals
#         self.combo_hold_time = 0.0
#         self.combo_bar.setValue(0)
#         self.combo_countdown_label.setText("All-fingers hold: –")
#         self.last_all_in_band = False

#     # ------------- GAME LOOP -------------

#     def game_tick(self):
#         if self.backend is None:
#             return

#         vals = self.backend.get_latest()
#         if vals is None:
#             return

#         # Ensure vals is a list/tuple of length NUM_CHANNELS
#         if isinstance(vals, (int, float)):
#             vals = [vals] * NUM_CHANNELS
#         elif isinstance(vals, (list, tuple)):
#             if len(vals) < NUM_CHANNELS:
#                 vals = list(vals) + [0] * (NUM_CHANNELS - len(vals))
#         else:
#             return

#         now = time.time()
#         if self.last_time is None:
#             dt = 0.0
#         else:
#             dt = now - self.last_time
#         self.last_time = now

#         tmin = self.target_min_slider.value()
#         tmax = self.target_max_slider.value()

#         # Track which channels are in-band for combo logic
#         in_band_flags = [False] * NUM_CHANNELS

#         for i in range(NUM_CHANNELS):
#             val = int(vals[i])
#             val = max(0, min(4095, val))

#             # Update bar & numeric text
#             self.bar_widgets[i].setValue(val)
#             self.value_labels[i].setText(f"Force: {val}")

#             # Determine zone and color
#             if val < tmin:
#                 zone = "low"
#                 color = "orange"
#             elif val > tmax:
#                 zone = "high"
#                 color = "red"
#             else:
#                 zone = "in_band"
#                 color = "green"

#             in_band_flags[i] = (zone == "in_band")
#             self._set_bar_color(self.bar_widgets[i], color)

#             # --- Single-finger target zone ENTER: play applepay.wav ---
#             if zone == "in_band" and not self.in_band_prev[i] and self.timer.isActive():
#                 self._play_sound(self.sounds.get("applepay"))

#             # ---- Per-channel countdown logic ----
#             if self.timer.isActive() and zone == "in_band":
#                 self.hold_time[i] += dt
#                 remaining = max(0.0, HOLD_SECONDS - self.hold_time[i])
#                 if remaining > 0:
#                     self.countdown_labels[i].setText(f"Hold: {remaining:0.1f} s")
#                 else:
#                     # Rep achieved for this finger
#                     self.reps_per_channel[i] += 1
#                     self.rep_labels[i].setText(f"Reps: {self.reps_per_channel[i]}")
#                     self.total_reps_label.setText(self._total_reps_text())
#                     self.countdown_labels[i].setText("Nice! ✅")
#                     # Play duolingo.wav on successful single-finger rep
#                     self._play_sound(self.sounds.get("duolingo"))

#                     # Reset hold timer so they must do another full 5 s
#                     self.hold_time[i] = 0.0
#                     # Save to disk on each successful rep
#                     self._save_stats()
#             else:
#                 # Not in band or session not running → reset hold timer
#                 self.hold_time[i] = 0.0
#                 self.countdown_labels[i].setText("Hold: –")

#             # Update previous in-band state
#             self.in_band_prev[i] = (zone == "in_band")

#         # ---- All-fingers combo logic ----
#         all_in_band = self.timer.isActive() and all(in_band_flags)

#         if all_in_band:
#             # Combo just started: play mario.wav
#             if not self.last_all_in_band:
#                 self._play_sound(self.sounds.get("mario"))

#             self.combo_hold_time += dt
#             combo_remaining = max(0.0, HOLD_SECONDS - self.combo_hold_time)
#             pct = int(
#                 max(0.0, min(1.0, self.combo_hold_time / HOLD_SECONDS)) * 100.0
#             )
#             self.combo_bar.setValue(pct)

#             if combo_remaining > 0:
#                 self.combo_countdown_label.setText(
#                     f"All-fingers hold: {combo_remaining:0.1f} s"
#                 )
#             else:
#                 # Combo rep achieved
#                 self.combo_reps += 1
#                 self.combo_reps_label.setText(
#                     f"All-fingers reps: {self.combo_reps}"
#                 )

#                 # Cycle emoji
#                 emoji = self.emoji_cycle[self.emoji_index]
#                 self.emoji_index = (self.emoji_index + 1) % len(self.emoji_cycle)
#                 self.emoji_label.setText(emoji)

#                 # Play success sound: cycle among rizz/wow/yay
#                 if self.combo_success_sounds:
#                     s = self.combo_success_sounds[self.combo_success_index]
#                     self.combo_success_index = (
#                         self.combo_success_index + 1
#                     ) % len(self.combo_success_sounds)
#                     self._play_sound(s)

#                 # Reset combo timer for next rep
#                 self.combo_hold_time = 0.0
#                 self.combo_bar.setValue(0)
#                 self.combo_countdown_label.setText("Great job! 🎉")

#                 # Persist stats
#                 self._save_stats()
#         else:
#             # If we *just* broke combo while counting, it's a fail
#             if (
#                 self.last_all_in_band
#                 and self.timer.isActive()
#                 and self.combo_hold_time > 0.0
#             ):
#                 # Play fail sound: cycle among oof/spongebob/bruh
#                 if self.combo_fail_sounds:
#                     s = self.combo_fail_sounds[self.combo_fail_index]
#                     self.combo_fail_index = (
#                         self.combo_fail_index + 1
#                     ) % len(self.combo_fail_sounds)
#                     self._play_sound(s)

#             self.combo_hold_time = 0.0
#             self.combo_bar.setValue(0)
#             self.combo_countdown_label.setText("All-fingers hold: –")

#         self.last_all_in_band = all_in_band

#     def _set_bar_color(self, bar: QProgressBar, color: str):
#         if color == "green":
#             chunk_color = "#4CAF50"
#         elif color == "red":
#             chunk_color = "#F44336"
#         else:  # orange / default
#             chunk_color = "#FF9800"
#         bar.setStyleSheet(
#             "QProgressBar {"
#             "border: 1px solid #999;"
#             "border-radius: 3px;"
#             "background: #eee;"
#             "}"
#             f"QProgressBar::chunk {{ background-color: {chunk_color}; }}"
#         )


# def main():
#     app = QApplication(sys.argv)
#     win = PatientGameWindow()
#     win.show()
#     sys.exit(app.exec())


# if __name__ == "__main__":
#     main()



#########===================== PATIENT GAME GUI V2 ==============================##########
# host/gui/patient_game_app.py

# import os
# import sys
# import json
# import time
# from datetime import datetime

# from PyQt6.QtCore import QTimer, Qt, QUrl
# from PyQt6.QtWidgets import (
#     QApplication,
#     QWidget,
#     QVBoxLayout,
#     QHBoxLayout,
#     QLabel,
#     QPushButton,
#     QLineEdit,
#     QSlider,
#     QProgressBar,
#     QMessageBox,
#     QGroupBox,
# )
# from PyQt6.QtGui import QFont
# from PyQt6.QtMultimedia import QSoundEffect

# # -------- PATH SETUP (same pattern as other GUIs) --------
# GUI_DIR = os.path.dirname(__file__)          # .../host/gui
# HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
# PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

# if PROJECT_ROOT not in sys.path:
#     sys.path.append(PROJECT_ROOT)

# # from comms.serial_backend import SerialBackend  # noqa: E402
# from comms.sim_backend import SimBackend as SerialBackend # Simulated inputs from ESP32-S3
# # --------------------------------------------------------


# NUM_CHANNELS = 4
# CHANNEL_NAMES = ["Index", "Middle", "Ring", "Pinky"]

# # Seconds the finger must stay in target band to count a rep
# HOLD_SECONDS = 5.0


# class PatientGameWindow(QWidget):
#     def __init__(self):
#         super().__init__()

#         self.setWindowTitle("Cardinal Grip – Patient Game Mode")
#         self.resize(1100, 700)

#         # --- Serial + data state ---
#         self.backend: SerialBackend | None = None
#         self.last_time = None  # for dt calculation in timer

#         # One hold timer per channel (seconds spent continuously in band)
#         self.hold_time = [0.0] * NUM_CHANNELS
#         self.in_band_prev = [False] * NUM_CHANNELS

#         # All-fingers simultaneous hold
#         self.combo_hold_time = 0.0    # seconds all fingers are in band
#         self.combo_reps = 0           # all-finger reps
#         self.last_all_in_band = False

#         # Persistent reps per channel, loaded/saved from JSON
#         self.reps_per_channel = [0] * NUM_CHANNELS
#         self.sessions_completed = 0
#         self.stats_path = os.path.join(PROJECT_ROOT, "data", "patient_stats.json")
#         self._load_stats()

#         # Emoji sequence for success feedback
#         self.emoji_cycle = ["👍", "👏", "🙌", "👌"]
#         self.emoji_index = 0

#         # --- Audio setup ---
#         self.sounds: dict[str, QSoundEffect | None] = {}
#         self._init_sounds()

#         # Fail / success cycles for combo
#         self.combo_fail_sounds = [
#             self.sounds.get("oof"),
#             self.sounds.get("spongebob"),
#             self.sounds.get("bruh"),
#         ]
#         self.combo_success_sounds = [
#             self.sounds.get("rizz"),
#             self.sounds.get("wow"),
#             self.sounds.get("yay"),
#         ]
#         self.combo_fail_index = 0
#         self.combo_success_index = 0

#         # --- UI ---
#         main_layout = QVBoxLayout()
#         self.setLayout(main_layout)

#         # ===== TOP: serial + control bar =====
#         top_row = QHBoxLayout()

#         top_row.addWidget(QLabel("Serial port:"))
#         # Default port; you can edit this in the GUI each run
#         self.port_edit = QLineEdit("/dev/cu.usbmodem14101")
#         self.port_edit.setFixedWidth(220)
#         top_row.addWidget(self.port_edit)

#         top_row.addWidget(QLabel("Baud:"))
#         self.baud_edit = QLineEdit("115200")
#         self.baud_edit.setFixedWidth(80)
#         top_row.addWidget(self.baud_edit)

#         self.connect_button = QPushButton("Connect")
#         self.connect_button.clicked.connect(self.handle_connect)
#         top_row.addWidget(self.connect_button)

#         self.disconnect_button = QPushButton("Disconnect")
#         self.disconnect_button.clicked.connect(self.handle_disconnect)
#         self.disconnect_button.setEnabled(False)
#         top_row.addWidget(self.disconnect_button)

#         self.start_button = QPushButton("Start Session")
#         self.start_button.clicked.connect(self.start_session)
#         self.start_button.setEnabled(False)
#         top_row.addWidget(self.start_button)

#         self.stop_button = QPushButton("Stop Session")
#         self.stop_button.clicked.connect(self.stop_session)
#         self.stop_button.setEnabled(False)
#         top_row.addWidget(self.stop_button)

#         main_layout.addLayout(top_row)

#         # Status line
#         self.status_label = QLabel("Status: Not connected")
#         self.status_label.setStyleSheet("font-weight: bold;")
#         main_layout.addWidget(self.status_label)

#         # ===== TARGET BAND CONTROLS =====
#         band_group = QGroupBox("Target Zone (applies to all fingers)")
#         band_layout = QHBoxLayout()
#         band_group.setLayout(band_layout)

#         band_layout.addWidget(QLabel("Min (ADC):"))
#         self.target_min_slider = QSlider(Qt.Orientation.Horizontal)
#         self.target_min_slider.setRange(0, 4095)
#         self.target_min_slider.setValue(1200)
#         band_layout.addWidget(self.target_min_slider)

#         band_layout.addWidget(QLabel("Max (ADC):"))
#         self.target_max_slider = QSlider(Qt.Orientation.Horizontal)
#         self.target_max_slider.setRange(0, 4095)
#         self.target_max_slider.setValue(2000)
#         band_layout.addWidget(self.target_max_slider)

#         self.band_hint_label = QLabel(
#             f"Stay in the green zone for {HOLD_SECONDS:.0f} seconds to earn a rep."
#         )
#         band_layout.addWidget(self.band_hint_label)

#         main_layout.addWidget(band_group)

#         # ===== CENTER: per-finger game bars =====
#         center_row = QHBoxLayout()
#         main_layout.addLayout(center_row, stretch=1)

#         self.bar_widgets: list[QProgressBar] = []
#         self.value_labels: list[QLabel] = []
#         self.countdown_labels: list[QLabel] = []
#         self.rep_labels: list[QLabel] = []

#         for i in range(NUM_CHANNELS):
#             col = QVBoxLayout()

#             # Finger name
#             name_label = QLabel(CHANNEL_NAMES[i])
#             name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#             name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
#             col.addWidget(name_label)

#             # Vertical bar (force)
#             bar = QProgressBar()
#             bar.setOrientation(Qt.Orientation.Vertical)
#             bar.setRange(0, 4095)
#             bar.setValue(0)
#             bar.setFixedWidth(60)
#             bar.setStyleSheet("QProgressBar::chunk { background-color: orange; }")
#             col.addWidget(bar, stretch=1, alignment=Qt.AlignmentFlag.AlignHCenter)
#             self.bar_widgets.append(bar)

#             # Current value label
#             val_label = QLabel("Force: 0")
#             val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#             col.addWidget(val_label)
#             self.value_labels.append(val_label)

#             # Countdown label
#             cd_label = QLabel("Hold: –")
#             cd_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#             cd_label.setStyleSheet("font-size: 11pt;")
#             col.addWidget(cd_label)
#             self.countdown_labels.append(cd_label)

#             # Rep count label (persistent over runs)
#             rep_label = QLabel(f"Reps: {self.reps_per_channel[i]}")
#             rep_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#             rep_label.setStyleSheet("font-size: 11pt; font-weight: bold;")
#             col.addWidget(rep_label)
#             self.rep_labels.append(rep_label)

#             center_row.addLayout(col)

#         # ===== ALL-FINGERS COMBO GROUP =====
#         combo_group = QGroupBox("All-Fingers Challenge")
#         combo_layout = QVBoxLayout()
#         combo_group.setLayout(combo_layout)

#         self.combo_info_label = QLabel(
#             f"When ALL fingers are in the green zone for {HOLD_SECONDS:.0f} seconds, "
#             "you earn a combo rep!"
#         )
#         combo_layout.addWidget(self.combo_info_label)

#         # Horizontal progress bar for all-fingers hold
#         self.combo_bar = QProgressBar()
#         self.combo_bar.setRange(0, 100)  # percent of HOLD_SECONDS
#         self.combo_bar.setValue(0)
#         self.combo_bar.setTextVisible(True)
#         self.combo_bar.setFormat("All-fingers hold: %p%")
#         combo_layout.addWidget(self.combo_bar)

#         # All-fingers countdown label
#         self.combo_countdown_label = QLabel("All-fingers hold: –")
#         self.combo_countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#         self.combo_countdown_label.setStyleSheet("font-size: 11pt;")
#         combo_layout.addWidget(self.combo_countdown_label)

#         # Combo reps label
#         self.combo_reps_label = QLabel(f"All-fingers reps: {self.combo_reps}")
#         self.combo_reps_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#         self.combo_reps_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
#         combo_layout.addWidget(self.combo_reps_label)

#         # Emoji label
#         self.emoji_label = QLabel("")
#         self.emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#         emoji_font = QFont("Arial", 32)
#         self.emoji_label.setFont(emoji_font)
#         combo_layout.addWidget(self.emoji_label)

#         main_layout.addWidget(combo_group)

#         # ===== BOTTOM: overall stats =====
#         bottom_row = QHBoxLayout()
#         self.total_reps_label = QLabel(self._total_reps_text())
#         self.total_reps_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
#         bottom_row.addWidget(self.total_reps_label)

#         self.session_count_label = QLabel(
#             f"Sessions completed (game mode): {self.sessions_completed}"
#         )
#         bottom_row.addWidget(self.session_count_label)

#         main_layout.addLayout(bottom_row)

#         # ===== TIMER =====
#         self.timer = QTimer()
#         self.timer.setInterval(50)  # 20 Hz
#         self.timer.timeout.connect(self.game_tick)

#     # ------------- AUDIO HELPERS -------------

#     def _init_sounds(self):
#         """Load all .wav files from PROJECT_ROOT/audio into QSoundEffect objects."""
#         audio_dir = os.path.join(PROJECT_ROOT, "audio")

#         def make_sound(filename: str) -> QSoundEffect | None:
#             path = os.path.join(audio_dir, filename)
#             if not os.path.isfile(path):
#                 # Don't crash if file is missing; just skip it.
#                 return None
#             s = QSoundEffect()
#             s.setSource(QUrl.fromLocalFile(path))
#             s.setVolume(0.9)  # 0.0–1.0
#             return s

#         self.sounds["applepay"] = make_sound("applepay.wav")
#         self.sounds["bruh"] = make_sound("bruh.wav")
#         self.sounds["duolingo"] = make_sound("duolingo.wav")
#         self.sounds["mario"] = make_sound("mario.wav")
#         self.sounds["oof"] = make_sound("oof.wav")
#         self.sounds["rizz"] = make_sound("rizz.wav")
#         self.sounds["spongebob"] = make_sound("spongebob.wav")
#         self.sounds["wow"] = make_sound("wow.wav")
#         self.sounds["yay"] = make_sound("yay.wav")

#     def _play_sound(self, sound: QSoundEffect | None):
#         """Safely play a sound if it exists."""
#         if sound is None:
#             return
#         sound.stop()
#         sound.play()

#     # ------------- STATS PERSISTENCE (JSON) -------------

#     def _load_stats(self):
#         os.makedirs(os.path.join(PROJECT_ROOT, "data"), exist_ok=True)
#         if not os.path.isfile(self.stats_path):
#             # default structure
#             self.reps_per_channel = [0] * NUM_CHANNELS
#             self.sessions_completed = 0
#             self.combo_reps = 0
#             return
#         try:
#             with open(self.stats_path, "r") as f:
#                 data = json.load(f)
#             self.reps_per_channel = data.get("reps_per_channel", [0] * NUM_CHANNELS)
#             if len(self.reps_per_channel) != NUM_CHANNELS:
#                 self.reps_per_channel = [0] * NUM_CHANNELS
#             self.sessions_completed = int(data.get("sessions_completed", 0))
#             self.combo_reps = int(data.get("combo_reps", 0))
#         except Exception:
#             # If corrupted, reset
#             self.reps_per_channel = [0] * NUM_CHANNELS
#             self.sessions_completed = 0
#             self.combo_reps = 0

#     def _save_stats(self):
#         data = {
#             "reps_per_channel": self.reps_per_channel,
#             "sessions_completed": self.sessions_completed,
#             "combo_reps": self.combo_reps,
#             "last_updated": datetime.now().isoformat(timespec="seconds"),
#         }
#         try:
#             with open(self.stats_path, "w") as f:
#                 json.dump(data, f, indent=2)
#         except Exception:
#             # Don't crash GUI if writing fails
#             pass

#     def _total_reps_text(self):
#         total = sum(self.reps_per_channel)
#         return f"Total reps across fingers: {total}"

#     # ------------- CONNECTION / SESSION CONTROL -------------

#     def handle_connect(self):
#         if self.backend is not None:
#             return
#         port = self.port_edit.text().strip()
#         try:
#             baud = int(self.baud_edit.text().strip())
#         except ValueError:
#             QMessageBox.warning(self, "Error", "Invalid baud rate.")
#             return

#         try:
#             self.backend = SerialBackend(port=port, baud=baud, timeout=0.01)
#             self.backend.start()
#         except Exception as e:
#             QMessageBox.critical(self, "Serial error", f"Failed to open {port}:\n{e}")
#             self.backend = None
#             return

#         self.status_label.setText(f"Status: Connected to {port} @ {baud}")
#         self.connect_button.setEnabled(False)
#         self.disconnect_button.setEnabled(True)
#         self.start_button.setEnabled(True)

#     def handle_disconnect(self):
#         self.stop_session()
#         if self.backend is not None:
#             self.backend.stop()
#             self.backend = None
#         self.status_label.setText("Status: Disconnected")
#         self.connect_button.setEnabled(True)
#         self.disconnect_button.setEnabled(False)
#         self.start_button.setEnabled(False)

#     def start_session(self):
#         # Reset per-session hold timers ONLY (not reps)
#         self.hold_time = [0.0] * NUM_CHANNELS
#         self.in_band_prev = [False] * NUM_CHANNELS
#         self.combo_hold_time = 0.0
#         self.last_time = time.time()
#         self.last_all_in_band = False
#         self.combo_bar.setValue(0)
#         self.combo_countdown_label.setText("All-fingers hold: –")
#         self.emoji_label.setText("")

#         self.timer.start()
#         self.start_button.setEnabled(False)
#         self.stop_button.setEnabled(True)
#         self.status_label.setText(
#             "Status: Session running – squeeze to hit the green zone!"
#         )

#     def stop_session(self):
#         if self.timer.isActive():
#             self.timer.stop()
#             self.sessions_completed += 1
#             self._save_stats()
#             self.session_count_label.setText(
#                 f"Sessions completed (game mode): {self.sessions_completed}"
#             )
#         self.start_button.setEnabled(self.backend is not None)
#         self.stop_button.setEnabled(False)

#         # Reset combo bar visuals
#         self.combo_hold_time = 0.0
#         self.combo_bar.setValue(0)
#         self.combo_countdown_label.setText("All-fingers hold: –")
#         self.last_all_in_band = False

#     # ------------- GAME LOOP -------------

#     def game_tick(self):
#         if self.backend is None:
#             return

#         vals = self.backend.get_latest()
#         if vals is None:
#             return

#         # Ensure vals is a list/tuple of length NUM_CHANNELS
#         if isinstance(vals, (int, float)):
#             vals = [vals] * NUM_CHANNELS
#         elif isinstance(vals, (list, tuple)):
#             if len(vals) < NUM_CHANNELS:
#                 vals = list(vals) + [0] * (NUM_CHANNELS - len(vals))
#         else:
#             return

#         now = time.time()
#         if self.last_time is None:
#             dt = 0.0
#         else:
#             dt = now - self.last_time
#         self.last_time = now

#         tmin = self.target_min_slider.value()
#         tmax = self.target_max_slider.value()

#         # Track which channels are in-band for combo logic
#         in_band_flags = [False] * NUM_CHANNELS

#         for i in range(NUM_CHANNELS):
#             val = int(vals[i])
#             val = max(0, min(4095, val))

#             # Update bar & numeric text
#             self.bar_widgets[i].setValue(val)
#             self.value_labels[i].setText(f"Force: {val}")

#             # Determine zone and color
#             if val < tmin:
#                 zone = "low"
#                 color = "orange"
#             elif val > tmax:
#                 zone = "high"
#                 color = "red"
#             else:
#                 zone = "in_band"
#                 color = "green"

#             in_band_flags[i] = (zone == "in_band")
#             self._set_bar_color(self.bar_widgets[i], color)

#             # --- Single-finger target zone ENTER: play applepay.wav ---
#             if zone == "in_band" and not self.in_band_prev[i] and self.timer.isActive():
#                 self._play_sound(self.sounds.get("applepay"))

#             # ---- Per-channel countdown logic ----
#             if self.timer.isActive() and zone == "in_band":
#                 self.hold_time[i] += dt
#                 remaining = max(0.0, HOLD_SECONDS - self.hold_time[i])
#                 if remaining > 0:
#                     self.countdown_labels[i].setText(f"Hold: {remaining:0.1f} s")
#                 else:
#                     # Rep achieved for this finger
#                     self.reps_per_channel[i] += 1
#                     self.rep_labels[i].setText(f"Reps: {self.reps_per_channel[i]}")
#                     self.total_reps_label.setText(self._total_reps_text())
#                     self.countdown_labels[i].setText("Nice! ✅")
#                     # Play duolingo.wav on successful single-finger rep
#                     self._play_sound(self.sounds.get("duolingo"))

#                     # Reset hold timer so they must do another full 5 s
#                     self.hold_time[i] = 0.0
#                     # Save to disk on each successful rep
#                     self._save_stats()
#             else:
#                 # Not in band or session not running → reset hold timer
#                 self.hold_time[i] = 0.0
#                 self.countdown_labels[i].setText("Hold: –")

#             # Update previous in-band state
#             self.in_band_prev[i] = (zone == "in_band")

#         # ---- All-fingers combo logic ----
#         all_in_band = self.timer.isActive() and all(in_band_flags)

#         if all_in_band:
#             # Combo just started: play mario.wav
#             if not self.last_all_in_band:
#                 self._play_sound(self.sounds.get("mario"))

#             self.combo_hold_time += dt
#             combo_remaining = max(0.0, HOLD_SECONDS - self.combo_hold_time)
#             pct = int(
#                 max(0.0, min(1.0, self.combo_hold_time / HOLD_SECONDS)) * 100.0
#             )
#             self.combo_bar.setValue(pct)

#             if combo_remaining > 0:
#                 self.combo_countdown_label.setText(
#                     f"All-fingers hold: {combo_remaining:0.1f} s"
#                 )
#             else:
#                 # Combo rep achieved
#                 self.combo_reps += 1
#                 self.combo_reps_label.setText(
#                     f"All-fingers reps: {self.combo_reps}"
#                 )

#                 # Cycle emoji
#                 emoji = self.emoji_cycle[self.emoji_index]
#                 self.emoji_index = (self.emoji_index + 1) % len(self.emoji_cycle)
#                 self.emoji_label.setText(emoji)

#                 # Play success sound: cycle among rizz/wow/yay
#                 if self.combo_success_sounds:
#                     s = self.combo_success_sounds[self.combo_success_index]
#                     self.combo_success_index = (
#                         self.combo_success_index + 1
#                     ) % len(self.combo_success_sounds)
#                     self._play_sound(s)

#                 # Reset combo timer for next rep
#                 self.combo_hold_time = 0.0
#                 self.combo_bar.setValue(0)
#                 self.combo_countdown_label.setText("Great job! 🎉")

#                 # Persist stats
#                 self._save_stats()
#         else:
#             # If we *just* broke combo while counting, it's a fail
#             if (
#                 self.last_all_in_band
#                 and self.timer.isActive()
#                 and self.combo_hold_time > 0.0
#             ):
#                 # Play fail sound: cycle among oof/spongebob/bruh
#                 if self.combo_fail_sounds:
#                     s = self.combo_fail_sounds[self.combo_fail_index]
#                     self.combo_fail_index = (
#                         self.combo_fail_index + 1
#                     ) % len(self.combo_fail_sounds)
#                     self._play_sound(s)

#             self.combo_hold_time = 0.0
#             self.combo_bar.setValue(0)
#             self.combo_countdown_label.setText("All-fingers hold: –")

#         self.last_all_in_band = all_in_band

#     def _set_bar_color(self, bar: QProgressBar, color: str):
#         if color == "green":
#             chunk_color = "#4CAF50"
#         elif color == "red":
#             chunk_color = "#F44336"
#         else:  # orange / default
#             chunk_color = "#FF9800"
#         bar.setStyleSheet(
#             "QProgressBar {"
#             "border: 1px solid #999;"
#             "border-radius: 3px;"
#             "background: #eee;"
#             "}"
#             f"QProgressBar::chunk {{ background-color: {chunk_color}; }}"
#         )


# def main():
#     app = QApplication(sys.argv)
#     win = PatientGameWindow()
#     win.show()
#     sys.exit(app.exec())


# if __name__ == "__main__":
#     main()


#########===================== PATIENT GAME GUI V3 ==============================##########
########===================== PATIENT GAME GUI V2 ==============================##########
# host/gui/patient_game_app.py

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
from PyQt6.QtGui import QFont
from PyQt6.QtMultimedia import QSoundEffect

# -------- PATH SETUP (same pattern as other GUIs) --------
GUI_DIR = os.path.dirname(__file__)          # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)          # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)     # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# from comms.serial_backend import SerialBackend  # noqa: E402
from comms.sim_backend import SimBackend as SerialBackend # Simulated inputs from ESP32-S3
# --------------------------------------------------------


NUM_CHANNELS = 4
CHANNEL_NAMES = ["Index", "Middle", "Ring", "Pinky"]

# Seconds the finger must stay in target band to count a rep
HOLD_SECONDS = 5.0


class PatientGameWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cardinal Grip – Patient Game Mode")
        self.resize(1100, 700)

        # ==== SIM BACKEND / KEYBOARD INPUT HOOK (comment out for real hardware) ====
        # Allow this window to receive key events so a simulated backend
        # (e.g., SimBackend with keyboard control) can be driven directly.
        # For real Serial/WiFi/Bluetooth backends, you can safely comment this out.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # ==== END SIM BACKEND HOOK ====

        # --- Serial + data state ---
        self.backend: SerialBackend | None = None
        self.last_time = None  # for dt calculation in timer

        # One hold timer per channel (seconds spent continuously in band)
        self.hold_time = [0.0] * NUM_CHANNELS
        self.in_band_prev = [False] * NUM_CHANNELS

        # All-fingers simultaneous hold
        self.combo_hold_time = 0.0    # seconds all fingers are in band
        self.combo_reps = 0           # all-finger reps
        self.last_all_in_band = False

        # Persistent reps per channel, loaded/saved from JSON
        self.reps_per_channel = [0] * NUM_CHANNELS
        self.sessions_completed = 0
        self.stats_path = os.path.join(PROJECT_ROOT, "data", "patient_stats.json")
        self._load_stats()

        # Emoji sequence for success feedback
        self.emoji_cycle = ["👍", "👏", "🙌", "👌"]
        self.emoji_index = 0

        # --- Audio setup ---
        self.sounds: dict[str, QSoundEffect | None] = {}
        self._init_sounds()

        # Fail / success cycles for combo
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

        # --- UI ---
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # ===== TOP: serial + control bar =====
        top_row = QHBoxLayout()

        top_row.addWidget(QLabel("Serial port:"))
        # Default port; you can edit this in the GUI each run
        self.port_edit = QLineEdit("/dev/cu.usbmodem14101")
        self.port_edit.setFixedWidth(220)
        top_row.addWidget(self.port_edit)

        top_row.addWidget(QLabel("Baud:"))
        self.baud_edit = QLineEdit("115200")
        self.baud_edit.setFixedWidth(80)
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

        # Status line
        self.status_label = QLabel("Status: Not connected")
        self.status_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(self.status_label)

        # ===== TARGET BAND CONTROLS =====
        band_group = QGroupBox("Target Zone (applies to all fingers)")
        band_layout = QHBoxLayout()
        band_group.setLayout(band_layout)

        band_layout.addWidget(QLabel("Min (ADC):"))
        self.target_min_slider = QSlider(Qt.Orientation.Horizontal)
        self.target_min_slider.setRange(0, 4095)
        self.target_min_slider.setValue(1200)
        band_layout.addWidget(self.target_min_slider)

        band_layout.addWidget(QLabel("Max (ADC):"))
        self.target_max_slider = QSlider(Qt.Orientation.Horizontal)
        self.target_max_slider.setRange(0, 4095)
        self.target_max_slider.setValue(2000)
        band_layout.addWidget(self.target_max_slider)

        self.band_hint_label = QLabel(
            f"Stay in the green zone for {HOLD_SECONDS:.0f} seconds to earn a rep."
        )
        band_layout.addWidget(self.band_hint_label)

        main_layout.addWidget(band_group)

        # ===== CENTER: per-finger game bars =====
        center_row = QHBoxLayout()
        main_layout.addLayout(center_row, stretch=1)

        self.bar_widgets: list[QProgressBar] = []
        self.value_labels: list[QLabel] = []
        self.countdown_labels: list[QLabel] = []
        self.rep_labels: list[QLabel] = []

        for i in range(NUM_CHANNELS):
            col = QVBoxLayout()

            # Finger name
            name_label = QLabel(CHANNEL_NAMES[i])
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            col.addWidget(name_label)

            # Vertical bar (force)
            bar = QProgressBar()
            bar.setOrientation(Qt.Orientation.Vertical)
            bar.setRange(0, 4095)
            bar.setValue(0)
            bar.setFixedWidth(60)
            bar.setStyleSheet("QProgressBar::chunk { background-color: orange; }")
            col.addWidget(bar, stretch=1, alignment=Qt.AlignmentFlag.AlignHCenter)
            self.bar_widgets.append(bar)

            # Current value label
            val_label = QLabel("Force: 0")
            val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(val_label)
            self.value_labels.append(val_label)

            # Countdown label
            cd_label = QLabel("Hold: –")
            cd_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cd_label.setStyleSheet("font-size: 11pt;")
            col.addWidget(cd_label)
            self.countdown_labels.append(cd_label)

            # Rep count label (persistent over runs)
            rep_label = QLabel(f"Reps: {self.reps_per_channel[i]}")
            rep_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rep_label.setStyleSheet("font-size: 11pt; font-weight: bold;")
            col.addWidget(rep_label)
            self.rep_labels.append(rep_label)

            center_row.addLayout(col)

        # ===== ALL-FINGERS COMBO GROUP =====
        combo_group = QGroupBox("All-Fingers Challenge")
        combo_layout = QVBoxLayout()
        combo_group.setLayout(combo_layout)

        self.combo_info_label = QLabel(
            f"When ALL fingers are in the green zone for {HOLD_SECONDS:.0f} seconds, "
            "you earn a combo rep!"
        )
        combo_layout.addWidget(self.combo_info_label)

        # Horizontal progress bar for all-fingers hold
        self.combo_bar = QProgressBar()
        self.combo_bar.setRange(0, 100)  # percent of HOLD_SECONDS
        self.combo_bar.setValue(0)
        self.combo_bar.setTextVisible(True)
        self.combo_bar.setFormat("All-fingers hold: %p%")
        combo_layout.addWidget(self.combo_bar)

        # All-fingers countdown label
        self.combo_countdown_label = QLabel("All-fingers hold: –")
        self.combo_countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.combo_countdown_label.setStyleSheet("font-size: 11pt;")
        combo_layout.addWidget(self.combo_countdown_label)

        # Combo reps label
        self.combo_reps_label = QLabel(f"All-fingers reps: {self.combo_reps}")
        self.combo_reps_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.combo_reps_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        combo_layout.addWidget(self.combo_reps_label)

        # Emoji label
        self.emoji_label = QLabel("")
        self.emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emoji_font = QFont("Arial", 32)
        self.emoji_label.setFont(emoji_font)
        combo_layout.addWidget(self.emoji_label)

        main_layout.addWidget(combo_group)

        # ===== BOTTOM: overall stats =====
        bottom_row = QHBoxLayout()
        self.total_reps_label = QLabel(self._total_reps_text())
        self.total_reps_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        bottom_row.addWidget(self.total_reps_label)

        self.session_count_label = QLabel(
            f"Sessions completed (game mode): {self.sessions_completed}"
        )
        bottom_row.addWidget(self.session_count_label)

        main_layout.addLayout(bottom_row)

        # ===== TIMER =====
        self.timer = QTimer()
        self.timer.setInterval(50)  # 20 Hz
        self.timer.timeout.connect(self.game_tick)

    # ------------- AUDIO HELPERS -------------

    def _init_sounds(self):
        """Load all .wav files from PROJECT_ROOT/audio into QSoundEffect objects."""
        audio_dir = os.path.join(PROJECT_ROOT, "audio")

        def make_sound(filename: str) -> QSoundEffect | None:
            path = os.path.join(audio_dir, filename)
            if not os.path.isfile(path):
                # Don't crash if file is missing; just skip it.
                return None
            s = QSoundEffect()
            s.setSource(QUrl.fromLocalFile(path))
            s.setVolume(0.9)  # 0.0–1.0
            return s

        self.sounds["applepay"] = make_sound("applepay.wav")
        self.sounds["bruh"] = make_sound("bruh.wav")
        self.sounds["duolingo"] = make_sound("duolingo.wav")
        self.sounds["mario"] = make_sound("mario.wav")
        self.sounds["oof"] = make_sound("oof.wav")
        self.sounds["rizz"] = make_sound("rizz.wav")
        self.sounds["spongebob"] = make_sound("spongebob.wav")
        self.sounds["wow"] = make_sound("wow.wav")
        self.sounds["yay"] = make_sound("yay.wav")

    def _play_sound(self, sound: QSoundEffect | None):
        """Safely play a sound if it exists."""
        if sound is None:
            return
        sound.stop()
        sound.play()

    # ------------- STATS PERSISTENCE (JSON) -------------

    def _load_stats(self):
        os.makedirs(os.path.join(PROJECT_ROOT, "data"), exist_ok=True)
        if not os.path.isfile(self.stats_path):
            # default structure
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
            # If corrupted, reset
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
            # Don't crash GUI if writing fails
            pass

    def _total_reps_text(self):
        total = sum(self.reps_per_channel)
        return f"Total reps across fingers: {total}"

    # ------------- CONNECTION / SESSION CONTROL -------------

    def handle_connect(self):
        if self.backend is not None:
            return
        port = self.port_edit.text().strip()
        try:
            baud = int(self.baud_edit.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid baud rate.")
            return

        try:
            self.backend = SerialBackend(port=port, baud=baud, timeout=0.01)
            self.backend.start()
        except Exception as e:
            QMessageBox.critical(self, "Serial error", f"Failed to open {port}:\n{e}")
            self.backend = None
            return

        self.status_label.setText(f"Status: Connected to {port} @ {baud}")
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        self.start_button.setEnabled(True)

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
        # Reset per-session hold timers ONLY (not reps)
        self.hold_time = [0.0] * NUM_CHANNELS
        self.in_band_prev = [False] * NUM_CHANNELS
        self.combo_hold_time = 0.0
        self.last_time = time.time()
        self.last_all_in_band = False
        self.combo_bar.setValue(0)
        self.combo_countdown_label.setText("All-fingers hold: –")
        self.emoji_label.setText("")

        self.timer.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText(
            "Status: Session running – squeeze to hit the green zone!"
        )

        # ==== SIM BACKEND / KEYBOARD INPUT HOOK (comment out for real hardware) ====
        # When simulating via keyboard, make sure this window has focus so
        # key presses reach keyPressEvent / keyReleaseEvent.
        # For real hardware backends, you can safely comment this out.
        self.setFocus()
        # ==== END SIM BACKEND HOOK ====

    def stop_session(self):
        if self.timer.isActive():
            self.timer.stop()
            self.sessions_completed += 1
            self._save_stats()
            self.session_count_label.setText(
                f"Sessions completed (game mode): {self.sessions_completed}"
            )
        self.start_button.setEnabled(self.backend is not None)
        self.stop_button.setEnabled(False)

        # Reset combo bar visuals
        self.combo_hold_time = 0.0
        self.combo_bar.setValue(0)
        self.combo_countdown_label.setText("All-fingers hold: –")
        self.last_all_in_band = False

    # ------------- GAME LOOP -------------

    def game_tick(self):
        if self.backend is None:
            return

        vals = self.backend.get_latest()
        if vals is None:
            return

        # Ensure vals is a list/tuple of length NUM_CHANNELS
        if isinstance(vals, (int, float)):
            vals = [vals] * NUM_CHANNELS
        elif isinstance(vals, (list, tuple)):
            if len(vals) < NUM_CHANNELS:
                vals = list(vals) + [0] * (NUM_CHANNELS - len(vals))
        else:
            return

        now = time.time()
        if self.last_time is None:
            dt = 0.0
        else:
            dt = now - self.last_time
        self.last_time = now

        tmin = self.target_min_slider.value()
        tmax = self.target_max_slider.value()

        # Track which channels are in-band for combo logic
        in_band_flags = [False] * NUM_CHANNELS

        for i in range(NUM_CHANNELS):
            val = int(vals[i])
            val = max(0, min(4095, val))

            # Update bar & numeric text
            self.bar_widgets[i].setValue(val)
            self.value_labels[i].setText(f"Force: {val}")

            # Determine zone and color
            if val < tmin:
                zone = "low"
                color = "orange"
            elif val > tmax:
                zone = "high"
                color = "red"
            else:
                zone = "in_band"
                color = "green"

            in_band_flags[i] = (zone == "in_band")
            self._set_bar_color(self.bar_widgets[i], color)

            # --- Single-finger target zone ENTER: play applepay.wav ---
            if zone == "in_band" and not self.in_band_prev[i] and self.timer.isActive():
                self._play_sound(self.sounds.get("applepay"))

            # ---- Per-channel countdown logic ----
            if self.timer.isActive() and zone == "in_band":
                self.hold_time[i] += dt
                remaining = max(0.0, HOLD_SECONDS - self.hold_time[i])
                if remaining > 0:
                    self.countdown_labels[i].setText(f"Hold: {remaining:0.1f} s")
                else:
                    # Rep achieved for this finger
                    self.reps_per_channel[i] += 1
                    self.rep_labels[i].setText(f"Reps: {self.reps_per_channel[i]}")
                    self.total_reps_label.setText(self._total_reps_text())
                    self.countdown_labels[i].setText("Nice! ✅")
                    # Play duolingo.wav on successful single-finger rep
                    self._play_sound(self.sounds.get("duolingo"))

                    # Reset hold timer so they must do another full 5 s
                    self.hold_time[i] = 0.0
                    # Save to disk on each successful rep
                    self._save_stats()
            else:
                # Not in band or session not running → reset hold timer
                self.hold_time[i] = 0.0
                self.countdown_labels[i].setText("Hold: –")

            # Update previous in-band state
            self.in_band_prev[i] = (zone == "in_band")

        # ---- All-fingers combo logic ----
        all_in_band = self.timer.isActive() and all(in_band_flags)

        if all_in_band:
            # Combo just started: play mario.wav
            if not self.last_all_in_band:
                self._play_sound(self.sounds.get("mario"))

            self.combo_hold_time += dt
            combo_remaining = max(0.0, HOLD_SECONDS - self.combo_hold_time)
            pct = int(
                max(0.0, min(1.0, self.combo_hold_time / HOLD_SECONDS)) * 100.0
            )
            self.combo_bar.setValue(pct)

            if combo_remaining > 0:
                self.combo_countdown_label.setText(
                    f"All-fingers hold: {combo_remaining:0.1f} s"
                )
            else:
                # Combo rep achieved
                self.combo_reps += 1
                self.combo_reps_label.setText(
                    f"All-fingers reps: {self.combo_reps}"
                )

                # Cycle emoji
                emoji = self.emoji_cycle[self.emoji_index]
                self.emoji_index = (self.emoji_index + 1) % len(self.emoji_cycle)
                self.emoji_label.setText(emoji)

                # Play success sound: cycle among rizz/wow/yay
                if self.combo_success_sounds:
                    s = self.combo_success_sounds[self.combo_success_index]
                    self.combo_success_index = (
                        self.combo_success_index + 1
                    ) % len(self.combo_success_sounds)
                    self._play_sound(s)

                # Reset combo timer for next rep
                self.combo_hold_time = 0.0
                self.combo_bar.setValue(0)
                self.combo_countdown_label.setText("Great job! 🎉")

                # Persist stats
                self._save_stats()
        else:
            # If we *just* broke combo while counting, it's a fail
            if (
                self.last_all_in_band
                and self.timer.isActive()
                and self.combo_hold_time > 0.0
            ):
                # Play fail sound: cycle among oof/spongebob/bruh
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

    # ==== SIM BACKEND / KEYBOARD INPUT HOOK (comment out for real hardware) ====
    # Generic key forwarding: sends raw characters to any backend that
    # exposes a `handle_char(ch: str, is_press: bool)` method.
    # For real Serial/WiFi/BLE backends, you can safely comment out this
    # entire block and the rest of the GUI stays backend-agnostic.
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
    # ==== END SIM BACKEND HOOK ====

    def _set_bar_color(self, bar: QProgressBar, color: str):
        if color == "green":
            chunk_color = "#4CAF50"
        elif color == "red":
            chunk_color = "#F44336"
        else:  # orange / default
            chunk_color = "#FF9800"
        bar.setStyleSheet(
            "QProgressBar {"
            "border: 1px solid #999;"
            "border-radius: 3px;"
            "background: #eee;"
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
