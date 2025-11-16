# # comms/sim_backend.py

# """
# SimBackend

# A drop-in replacement for SerialBackend that *pretends* to be the ESP32-S3
# streaming 4 FSR channels. It is designed to work directly with
# host/gui/patient_game_app.py without any changes.

# It supports:
#   1. Single-finger hold patterns (one channel in band).
#   2. Finger combinations (two or three channels in band).
#   3. All-fingers combo (all four in band long enough to trigger combo reps).
#   4. Chaos mode (random-ish forces on each channel) to stress-test the GUI.

# The constructor intentionally accepts (port, baud, timeout) so that
# patient_game_app.py can call:

#     SerialBackend(port=..., baud=..., timeout=0.01)

# even though this simulator does not actually use a serial port.
# """

# import threading
# import time
# import random

# NUM_CHANNELS = 4

# # These are "ADC" levels relative to your default target (1200–2000)
# LOW_LEVEL = 400       # definitely below target
# IN_BAND_LEVEL = 1600  # comfortably inside target band
# HIGH_LEVEL = 3000     # definitely above target


# class SimBackend:
#     """
#     A drop-in replacement for SerialBackend that generates scripted 4-channel
#     FSR values. patient_game_app.game_tick() does not need to change.
#     """

#     def __init__(self, port=None, baud=115200, timeout=0.01, update_interval=None):
#         """
#         Parameters are kept compatible with SerialBackend:

#           port: ignored (for API compatibility)
#           baud: ignored
#           timeout: used as a default update interval if update_interval is None
#           update_interval: seconds between updates (default ≈ timeout or 0.05)
#         """
#         self.port = port
#         self.baud = baud
#         self.timeout = timeout

#         # How often we update the simulated values
#         self.update_interval = (
#             update_interval if update_interval is not None else (timeout or 0.05)
#         )

#         self._running = False
#         self._thread: threading.Thread | None = None
#         self._lock = threading.Lock()
#         self._latest = [0] * NUM_CHANNELS  # last generated values

#         # Phase state for scripted patterns
#         self.phase_index = 0
#         self.phase_start_time = time.time()

#         # Define a sequence of phases to cycle through
#         # Each phase is a dict: { "name": str, "duration": float, "func": callable }
#         self.phases = [
#             {
#                 "name": "idle_all_low",
#                 "duration": 2.0,
#                 "func": self._phase_all_low,
#             },
#             {
#                 "name": "index_only",
#                 "duration": 5.5,  # long enough to trigger HOLD_SECONDS with defaults
#                 "func": self._phase_index_only,
#             },
#             {
#                 "name": "middle_only",
#                 "duration": 5.5,
#                 "func": self._phase_middle_only,
#             },
#             {
#                 "name": "ring_only",
#                 "duration": 5.5,
#                 "func": self._phase_ring_only,
#             },
#             {
#                 "name": "pinky_only",
#                 "duration": 5.5,
#                 "func": self._phase_pinky_only,
#             },
#             {
#                 "name": "index_middle_combo",
#                 "duration": 6.0,
#                 "func": self._phase_index_middle,
#             },
#             {
#                 "name": "ring_pinky_combo",
#                 "duration": 6.0,
#                 "func": self._phase_ring_pinky,
#             },
#             {
#                 "name": "all_fingers_combo",
#                 "duration": 7.0,  # enough for at least one combo rep
#                 "func": self._phase_all_in_band,
#             },
#             {
#                 "name": "chaos_mode",
#                 "duration": 6.0,
#                 "func": self._phase_chaos,
#             },
#         ]

#     # ------------------------------------------------------------------
#     # Public API – same shape as SerialBackend
#     # ------------------------------------------------------------------

#     def start(self):
#         """Start the background simulation thread."""
#         if self._running:
#             return
#         self._running = True
#         self._thread = threading.Thread(target=self._run_loop, daemon=True)
#         self._thread.start()

#     def stop(self):
#         """Stop the background simulation thread."""
#         self._running = False
#         if self._thread is not None:
#             self._thread.join(timeout=1.0)
#             self._thread = None

#     def get_latest(self):
#         """
#         Return the latest 4-channel values as a list of ints.
#         patient_game_app.game_tick() calls this frequently.
#         """
#         with self._lock:
#             return list(self._latest)

#     # ------------------------------------------------------------------
#     # Internal main loop
#     # ------------------------------------------------------------------

#     def _run_loop(self):
#         """Main simulation loop; runs in a background thread."""
#         while self._running:
#             now = time.time()
#             elapsed = now - self.phase_start_time

#             phase = self.phases[self.phase_index]
#             if elapsed > phase["duration"]:
#                 # move to next phase
#                 self.phase_index = (self.phase_index + 1) % len(self.phases)
#                 self.phase_start_time = now
#                 phase = self.phases[self.phase_index]
#                 elapsed = 0.0

#             # Generate values for current phase
#             vals = phase["func"](elapsed)

#             # Clamp and store
#             vals = [int(max(0, min(4095, v))) for v in vals]
#             if len(vals) < NUM_CHANNELS:
#                 vals = vals + [0] * (NUM_CHANNELS - len(vals))
#             vals = vals[:NUM_CHANNELS]

#             with self._lock:
#                 self._latest = vals

#             time.sleep(self.update_interval)

#     # ------------------------------------------------------------------
#     # Phase patterns
#     # Each pattern takes elapsed time (seconds) and returns a list of 4 ints
#     # ------------------------------------------------------------------

#     def _jitter(self, base, amount=60):
#         """Small random jitter to make values less robotically constant."""
#         return base + random.randint(-amount, amount)

#     def _phase_all_low(self, t: float):
#         # All fingers relaxed, well below target band.
#         return [self._jitter(LOW_LEVEL) for _ in range(NUM_CHANNELS)]

#     def _phase_index_only(self, t: float):
#         # Index (channel 0) in band; others low.
#         return [
#             self._jitter(IN_BAND_LEVEL),      # Index
#             self._jitter(LOW_LEVEL),          # Middle
#             self._jitter(LOW_LEVEL),          # Ring
#             self._jitter(LOW_LEVEL),          # Pinky
#         ]

#     def _phase_middle_only(self, t: float):
#         # Middle (channel 1) in band.
#         return [
#             self._jitter(LOW_LEVEL),
#             self._jitter(IN_BAND_LEVEL),
#             self._jitter(LOW_LEVEL),
#             self._jitter(LOW_LEVEL),
#         ]

#     def _phase_ring_only(self, t: float):
#         # Ring (channel 2) in band.
#         return [
#             self._jitter(LOW_LEVEL),
#             self._jitter(LOW_LEVEL),
#             self._jitter(IN_BAND_LEVEL),
#             self._jitter(LOW_LEVEL),
#         ]

#     def _phase_pinky_only(self, t: float):
#         # Pinky (channel 3) in band.
#         return [
#             self._jitter(LOW_LEVEL),
#             self._jitter(LOW_LEVEL),
#             self._jitter(LOW_LEVEL),
#             self._jitter(IN_BAND_LEVEL),
#         ]

#     def _phase_index_middle(self, t: float):
#         # Index + Middle in band, others low.
#         return [
#             self._jitter(IN_BAND_LEVEL),
#             self._jitter(IN_BAND_LEVEL),
#             self._jitter(LOW_LEVEL),
#             self._jitter(LOW_LEVEL),
#         ]

#     def _phase_ring_pinky(self, t: float):
#         # Ring + Pinky in band, others low.
#         return [
#             self._jitter(LOW_LEVEL),
#             self._jitter(LOW_LEVEL),
#             self._jitter(IN_BAND_LEVEL),
#             self._jitter(IN_BAND_LEVEL),
#         ]

#     def _phase_all_in_band(self, t: float):
#         # All four fingers in band — ideal for testing combo reps.
#         return [self._jitter(IN_BAND_LEVEL) for _ in range(NUM_CHANNELS)]

#     def _phase_chaos(self, t: float):
#         # Random-ish values per channel: some low, some in band, some high.
#         vals = []
#         for _ in range(NUM_CHANNELS):
#             base = random.choice([LOW_LEVEL, IN_BAND_LEVEL, HIGH_LEVEL])
#             vals.append(self._jitter(base, amount=120))
#         return vals
    
#########===================== SIMULATED BACKEND V2 ==============================##########

# comms/sim_backend.py

# """
# SimBackend

# A drop-in replacement for SerialBackend that pretends to be the ESP32-S3
# streaming 4 FSR channels. It is designed to integrate directly with
# host/gui/patient_game_app.py, where it is imported as:

#     from comms.sim_backend import SimBackend as SerialBackend

# API compatibility with SerialBackend:
#     SimBackend(port=None, baud=115200, timeout=0.01, update_interval=None)
#     start()
#     stop()
#     get_latest() -> list[4 ints]

# Extra API for keyboard/manual control (used by the GUI only in sim mode):
#     enable_manual(enabled: bool = True)
#     set_manual_state(channel: int, state: "low" | "in_band" | "high")

# Conceptual behavior:
#     - In normal scripted mode (manual_mode = False), the backend cycles through
#       a set of phases:
#         * all fingers low
#         * one finger in band at a time
#         * a few 2-finger combos
#         * all four in band (for combo rep testing)
#         * chaos/random mode

#     - In manual mode (manual_mode = True), the GUI tells the backend which
#       fingers are "low", "in_band", or "high". The backend translates that
#       into ADC-like values (~400, ~1600, ~3000 with jitter). The GUI still
#       only ever calls get_latest() and never fabricates sensor values itself.
# """

# import threading
# import time
# import random

# NUM_CHANNELS = 4

# # Approximate "ADC" levels relative to your default target band (1200–2000)
# LOW_LEVEL = 400        # clearly below target
# IN_BAND_LEVEL = 1600   # comfortably inside target band
# HIGH_LEVEL = 3000      # clearly above target


# class SimBackend:
#     """
#     Software stand-in for the ESP32-S3 + FSR grid.

#     This class is intentionally backend-only: it just produces numeric
#     readings. The GUI is responsible for handling user input (including
#     keyboard events) and forwarding high-level commands like
#     set_manual_state(...).
#     """

#     def __init__(self, port=None, baud=115200, timeout=0.01, update_interval=None):
#         """
#         Parameters:
#             port:          ignored (kept for API compatibility)
#             baud:          ignored
#             timeout:       used as default update interval if update_interval is None
#             update_interval:
#                 seconds between simulated updates. If None, falls back to
#                 `timeout` or 0.05 seconds.
#         """
#         self.port = port
#         self.baud = baud
#         self.timeout = timeout

#         # How often we update the simulated values
#         self.update_interval = (
#             update_interval if update_interval is not None else (timeout or 0.05)
#         )

#         # Threading / state
#         self._running = False
#         self._thread: threading.Thread | None = None
#         self._lock = threading.Lock()
#         self._latest = [0] * NUM_CHANNELS  # last generated values

#         # ---- Scripted phase state (when not in manual mode) ----
#         self.phase_index = 0
#         self.phase_start_time = time.time()

#         # Define a sequence of phases for automated testing.
#         # Each phase is a dict: { "name": str, "duration": float, "func": callable }
#         self.phases = [
#             {
#                 "name": "idle_all_low",
#                 "duration": 2.0,
#                 "func": self._phase_all_low,
#             },
#             {
#                 "name": "index_only",
#                 "duration": 5.5,  # long enough to trigger HOLD_SECONDS (5s)
#                 "func": self._phase_index_only,
#             },
#             {
#                 "name": "middle_only",
#                 "duration": 5.5,
#                 "func": self._phase_middle_only,
#             },
#             {
#                 "name": "ring_only",
#                 "duration": 5.5,
#                 "func": self._phase_ring_only,
#             },
#             {
#                 "name": "pinky_only",
#                 "duration": 5.5,
#                 "func": self._phase_pinky_only,
#             },
#             {
#                 "name": "index_middle_combo",
#                 "duration": 6.0,
#                 "func": self._phase_index_middle,
#             },
#             {
#                 "name": "ring_pinky_combo",
#                 "duration": 6.0,
#                 "func": self._phase_ring_pinky,
#             },
#             {
#                 "name": "all_fingers_combo",
#                 "duration": 7.0,  # enough for at least one combo rep
#                 "func": self._phase_all_in_band,
#             },
#             {
#                 "name": "chaos_mode",
#                 "duration": 6.0,
#                 "func": self._phase_chaos,
#             },
#         ]

#         # ---- Manual (keyboard-driven) mode state ----
#         # When manual_mode is True, we ignore scripted phases and instead
#         # use per-channel "manual levels" set by the GUI.
#         """
#         """
#         self.manual_mode = True # True or False
#         self._manual_levels = [LOW_LEVEL] * NUM_CHANNELS

#     # ------------------------------------------------------------------
#     # Public API – compatible with SerialBackend
#     # ------------------------------------------------------------------

#     def start(self):
#         """Start the background simulation thread."""
#         if self._running:
#             return
#         self._running = True
#         self._thread = threading.Thread(target=self._run_loop, daemon=True)
#         self._thread.start()

#     def stop(self):
#         """Stop the background simulation thread."""
#         self._running = False
#         if self._thread is not None:
#             self._thread.join(timeout=1.0)
#             self._thread = None

#     def get_latest(self):
#         """
#         Return the latest 4-channel values as a list of ints.
#         patient_game_app.game_tick() calls this frequently.
#         """
#         with self._lock:
#             return list(self._latest)

#     # ------------------------------------------------------------------
#     # Extra API – used only by the GUI in sim mode
#     # ------------------------------------------------------------------

#     def enable_manual(self, enabled: bool = True):
#         """
#         Toggle manual (keyboard-driven) mode.

#         When enabled:
#             - Scripted phases are ignored.
#             - set_manual_state() determines each channel's force level.
#         """
#         self.manual_mode = bool(enabled)

#     def set_manual_state(self, channel: int, state: str):
#         """
#         Set the logical state for a given channel when manual_mode is True.

#         channel: 0–3 (Index, Middle, Ring, Pinky)
#         state:   "low" | "in_band" | "high"
#         """
#         if not (0 <= channel < NUM_CHANNELS):
#             return

#         state = state.lower()
#         if state == "low":
#             level = LOW_LEVEL
#         elif state == "in_band":
#             level = IN_BAND_LEVEL
#         elif state == "high":
#             level = HIGH_LEVEL
#         else:
#             # Ignore unknown states
#             return

#         with self._lock:
#             self._manual_levels[channel] = level

#     # ------------------------------------------------------------------
#     # Internal main loop
#     # ------------------------------------------------------------------

#     def _run_loop(self):
#         """Main simulation loop; runs in a background thread."""
#         while self._running:
#             if self.manual_mode:
#                 # Manual/keyboard-driven: just use _manual_levels with a bit of jitter
#                 with self._lock:
#                     base_levels = list(self._manual_levels)
#                 vals = [self._jitter(v, amount=60) for v in base_levels]
#             else:
#                 # Scripted phase logic
#                 now = time.time()
#                 elapsed = now - self.phase_start_time

#                 phase = self.phases[self.phase_index]
#                 if elapsed > phase["duration"]:
#                     # Move to next phase
#                     self.phase_index = (self.phase_index + 1) % len(self.phases)
#                     self.phase_start_time = now
#                     phase = self.phases[self.phase_index]
#                     elapsed = 0.0

#                 vals = phase["func"](elapsed)

#             # Clamp and normalize
#             vals = [int(max(0, min(4095, v))) for v in vals]
#             if len(vals) < NUM_CHANNELS:
#                 vals = vals + [0] * (NUM_CHANNELS - len(vals))
#             vals = vals[:NUM_CHANNELS]

#             with self._lock:
#                 self._latest = vals

#             time.sleep(self.update_interval)

#     # ------------------------------------------------------------------
#     # Phase patterns
#     # Each pattern takes elapsed time (seconds) and returns a list of 4 ints.
#     # ------------------------------------------------------------------

#     def _jitter(self, base: int, amount: int = 60) -> int:
#         """Small random jitter to make values less robotically constant."""
#         return base + random.randint(-amount, amount)

#     def _phase_all_low(self, t: float):
#         # All fingers relaxed, well below target band.
#         return [self._jitter(LOW_LEVEL) for _ in range(NUM_CHANNELS)]

#     def _phase_index_only(self, t: float):
#         # Index (channel 0) in band; others low.
#         return [
#             self._jitter(IN_BAND_LEVEL),      # Index
#             self._jitter(LOW_LEVEL),          # Middle
#             self._jitter(LOW_LEVEL),          # Ring
#             self._jitter(LOW_LEVEL),          # Pinky
#         ]

#     def _phase_middle_only(self, t: float):
#         # Middle (channel 1) in band.
#         return [
#             self._jitter(LOW_LEVEL),
#             self._jitter(IN_BAND_LEVEL),
#             self._jitter(LOW_LEVEL),
#             self._jitter(LOW_LEVEL),
#         ]

#     def _phase_ring_only(self, t: float):
#         # Ring (channel 2) in band.
#         return [
#             self._jitter(LOW_LEVEL),
#             self._jitter(LOW_LEVEL),
#             self._jitter(IN_BAND_LEVEL),
#             self._jitter(LOW_LEVEL),
#         ]

#     def _phase_pinky_only(self, t: float):
#         # Pinky (channel 3) in band.
#         return [
#             self._jitter(LOW_LEVEL),
#             self._jitter(LOW_LEVEL),
#             self._jitter(LOW_LEVEL),
#             self._jitter(IN_BAND_LEVEL),
#         ]

#     def _phase_index_middle(self, t: float):
#         # Index + Middle in band, others low.
#         return [
#             self._jitter(IN_BAND_LEVEL),
#             self._jitter(IN_BAND_LEVEL),
#             self._jitter(LOW_LEVEL),
#             self._jitter(LOW_LEVEL),
#         ]

#     def _phase_ring_pinky(self, t: float):
#         # Ring + Pinky in band, others low.
#         return [
#             self._jitter(LOW_LEVEL),
#             self._jitter(LOW_LEVEL),
#             self._jitter(IN_BAND_LEVEL),
#             self._jitter(IN_BAND_LEVEL),
#         ]

#     def _phase_all_in_band(self, t: float):
#         # All four fingers in band — ideal for testing combo reps.
#         return [self._jitter(IN_BAND_LEVEL) for _ in range(NUM_CHANNELS)]

#     def _phase_chaos(self, t: float):
#         # Random-ish values per channel: some low, some in band, some high.
#         vals = []
#         for _ in range(NUM_CHANNELS):
#             base = random.choice([LOW_LEVEL, IN_BAND_LEVEL, HIGH_LEVEL])
#             vals.append(self._jitter(base, amount=120))
#         return vals

# comms/sim_backend.py

# """
# SimBackend (manual-only)

# A drop-in replacement for SerialBackend that pretends to be the ESP32-S3
# streaming 4 FSR channels — but values are controlled *exclusively* by
# the GUI via keyboard.

# Used in host/gui/patient_game_app.py as:

#     from comms.sim_backend import SimBackend as SerialBackend

# API:
#     SimBackend(port=None, baud=115200, timeout=0.01, update_interval=None)
#     start()
#     stop()
#     get_latest() -> list[4 ints]

# Extra API (called by the GUI):
#     set_manual_state(channel: int, state: "low" | "in_band" | "high")
# """

# import threading
# import time
# import random

# NUM_CHANNELS = 4

# # Approximate "ADC" levels relative to your default target band (1200–2000)
# LOW_LEVEL = 400        # clearly below target
# IN_BAND_LEVEL = 1600   # comfortably inside target band
# HIGH_LEVEL = 3000      # clearly above target


# class SimBackend:
#     """
#     Software stand-in for the ESP32-S3 + FSR grid.

#     - It does NOT read hardware.
#     - It does NOT have scripted patterns.
#     - It ONLY outputs values based on _manual_levels, which the GUI sets
#       via set_manual_state(...).
#     """

#     def __init__(self, port=None, baud=115200, timeout=0.01, update_interval=None):
#         """
#         Parameters kept for compatibility with SerialBackend:
#             port:          ignored
#             baud:          ignored
#             timeout:       used as default update interval if update_interval is None
#             update_interval:
#                 seconds between simulated updates. If None, falls back to
#                 `timeout` or 0.05 seconds.
#         """
#         self.port = port
#         self.baud = baud
#         self.timeout = timeout

#         # How often we update the simulated values
#         self.update_interval = (
#             update_interval if update_interval is not None else (timeout or 0.05)
#         )

#         # Threading / state
#         self._running = False
#         self._thread: threading.Thread | None = None
#         self._lock = threading.Lock()
#         self._latest = [0] * NUM_CHANNELS  # last generated values

#         # Manual levels for each channel (Index, Middle, Ring, Pinky)
#         self._manual_levels = [LOW_LEVEL] * NUM_CHANNELS

#     # ------------------------------------------------------------------
#     # Public API – compatible with SerialBackend
#     # ------------------------------------------------------------------

#     def start(self):
#         """Start the background simulation thread."""
#         if self._running:
#             return
#         self._running = True
#         self._thread = threading.Thread(target=self._run_loop, daemon=True)
#         self._thread.start()

#     def stop(self):
#         """Stop the background simulation thread."""
#         self._running = False
#         if self._thread is not None:
#             self._thread.join(timeout=1.0)
#             self._thread = None

#     def get_latest(self):
#         """
#         Return the latest 4-channel values as a list of ints.
#         patient_game_app.game_tick() calls this frequently.
#         """
#         with self._lock:
#             return list(self._latest)

#     # ------------------------------------------------------------------
#     # Extra API – used by the GUI to simulate "pressure"
#     # ------------------------------------------------------------------

#     def set_manual_state(self, channel: int, state: str):
#         """
#         Set the logical state for a given channel.

#         channel: 0–3 (Index, Middle, Ring, Pinky)
#         state:   "low" | "in_band" | "high"
#         """
#         if not (0 <= channel < NUM_CHANNELS):
#             return

#         s = state.lower()
#         if s == "low":
#             level = LOW_LEVEL
#         elif s == "in_band":
#             level = IN_BAND_LEVEL
#         elif s == "high":
#             level = HIGH_LEVEL
#         else:
#             # Ignore unknown states
#             return

#         with self._lock:
#             self._manual_levels[channel] = level

#     # ------------------------------------------------------------------
#     # Internal main loop
#     # ------------------------------------------------------------------

#     def _run_loop(self):
#         """Main simulation loop; runs in a background thread."""
#         while self._running:
#             with self._lock:
#                 base_levels = list(self._manual_levels)

#             # Add a little jitter so it doesn’t look perfectly flat
#             vals = [self._jitter(v, amount=60) for v in base_levels]

#             # Clamp and normalize
#             vals = [int(max(0, min(4095, v))) for v in vals]
#             if len(vals) < NUM_CHANNELS:
#                 vals = vals + [0] * (NUM_CHANNELS - len(vals))
#             vals = vals[:NUM_CHANNELS]

#             with self._lock:
#                 self._latest = vals

#             time.sleep(self.update_interval)

#     # ------------------------------------------------------------------
#     # Helpers
#     # ------------------------------------------------------------------

#     def _jitter(self, base: int, amount: int = 60) -> int:
#         """Small random jitter to make values less robotically constant."""
#         return base + random.randint(-amount, amount)



#########===================== SIMULATED BACKEND V3 ==============================##########


# comms/sim_backend.py

"""
SimBackend – manual-only backend with ramped squeeze and multi-speed key mapping.

Used as:
    from comms.sim_backend import SimBackend as SerialBackend

API (compatible with SerialBackend):
    SimBackend(port=None, baud=115200, timeout=0.01, update_interval=None)
    start()
    stop()
    get_latest() -> list[4 ints]

Extra API (called by patient_game_app via keyPressEvent / keyReleaseEvent):
    handle_char(ch: str, is_press: bool)

Key mapping (per your spec):

Channel 1 (Index, channel 0):
    q : slowest increase
    u : fastest increase
    w + u : medium (average of slow & fast)

Channel 2 (Middle, channel 1):
    w : slowest increase
    i : fastest increase
    q + i : medium

Channel 3 (Ring, channel 2):
    e : slowest increase
    o : fastest increase
    e + o : medium

Channel 4 (Pinky, channel 3):
    r : slowest increase
    p : fastest increase
    r + p : medium

Globals:
    z : raises everything at the same time (at least slow rate)
    x : drops everything back down faster

Releasing keys removes their contribution; channels then ramp back down toward LOW_LEVEL.
"""

import threading
import time
import random

NUM_CHANNELS = 4

# Baseline / range
MIN_LEVEL = 0
LOW_LEVEL = 400        # relaxed / clearly below target band
MAX_LEVEL = 3500       # can go above typical tmax (~2000)

# Base ramp speeds (ADC counts / second)
SLOW_UP_RATE = 800.0
FAST_UP_RATE = 2400.0
MEDIUM_UP_RATE = (SLOW_UP_RATE + FAST_UP_RATE) / 2.0

DOWN_RATE = 900.0          # natural relax speed
DOWN_RATE_FAST = 2200.0    # when 'x' is held, drop faster

JITTER_AMOUNT = 40


class SimBackend:
    """
    Software stand-in for the ESP32-S3 + FSR grid.

    - No hardware, no serial.
    - Only uses keyboard-driven rates.
    - Each channel's value ramps up/down based on which keys are pressed.
    """

    def __init__(self, port=None, baud=115200, timeout=0.01, update_interval=None):
        # Kept for API compatibility
        self.port = port
        self.baud = baud
        self.timeout = timeout

        self.update_interval = (
            update_interval if update_interval is not None else (timeout or 0.05)
        )

        # Threading / state
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Channel levels (floats, then jittered & clamped to ints)
        self._levels = [LOW_LEVEL] * NUM_CHANNELS
        self._latest = [int(LOW_LEVEL)] * NUM_CHANNELS

        # Pressed key set
        self._pressed_keys: set[str] = set()

        # For dt computation
        self._last_update_time = time.time()

    # ------------------------------------------------------------------
    # Public API – compatible with SerialBackend
    # ------------------------------------------------------------------

    def start(self):
        """Start the background simulation thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the background simulation thread."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def get_latest(self):
        """
        Return the latest 4-channel values as a list of ints.
        patient_game_app.game_tick() calls this frequently.
        """
        with self._lock:
            return list(self._latest)

    # ------------------------------------------------------------------
    # Extra API – generic key input from GUI
    # ------------------------------------------------------------------

    def handle_char(self, ch: str, is_press: bool):
        """
        Process a character key event coming from the GUI.

        ch:       single-character string (e.g., 'q', 'w', 'e', 'r', 'u', etc.)
        is_press: True if key down, False if key up.
        """
        if not ch:
            return

        ch = ch[0].lower()  # normalize to single lowercase char

        # We only care about a small subset, but it's cheap to store any.
        with self._lock:
            if is_press:
                self._pressed_keys.add(ch)
            else:
                self._pressed_keys.discard(ch)

    # ------------------------------------------------------------------
    # Internal main loop
    # ------------------------------------------------------------------

    def _run_loop(self):
        """Main simulation loop; runs in a background thread."""
        while self._running:
            now = time.time()
            dt = now - self._last_update_time
            if dt <= 0:
                dt = self.update_interval
            self._last_update_time = now

            with self._lock:
                levels = list(self._levels)
                keys = set(self._pressed_keys)

            # Compute new level for each channel
            for ch_idx in range(NUM_CHANNELS):
                up_rate = self._compute_up_rate_for_channel(ch_idx, keys)

                # Global 'z' raises everything at least at slow rate
                if "z" in keys:
                    up_rate = max(up_rate, SLOW_UP_RATE)

                if up_rate > 0:
                    # Ramp up toward MAX_LEVEL
                    levels[ch_idx] = min(
                        MAX_LEVEL,
                        levels[ch_idx] + up_rate * dt,
                    )
                else:
                    # No upward drive: ramp down toward LOW_LEVEL
                    down_rate = DOWN_RATE_FAST if "x" in keys else DOWN_RATE
                    if levels[ch_idx] > LOW_LEVEL:
                        levels[ch_idx] = max(
                            LOW_LEVEL,
                            levels[ch_idx] - down_rate * dt,
                        )
                    elif levels[ch_idx] < LOW_LEVEL:
                        # If it undershoots, gently nudge back toward LOW_LEVEL
                        levels[ch_idx] = min(
                            LOW_LEVEL,
                            levels[ch_idx] + (down_rate * 0.3) * dt,
                        )

            # Add jitter, clamp, and store
            jittered = [self._jitter(val, JITTER_AMOUNT) for val in levels]
            jittered = [int(max(MIN_LEVEL, min(4095, v))) for v in jittered]

            with self._lock:
                self._levels = levels
                self._latest = jittered

            time.sleep(self.update_interval)

    # ------------------------------------------------------------------
    # Per-channel rate logic based on pressed keys
    # ------------------------------------------------------------------

    def _compute_up_rate_for_channel(self, ch_idx: int, keys: set[str]) -> float:
        """
        Return the upward ramp rate for a channel, based on pressed keys.

        Uses your specified mapping:

        Channel 1 (0): q slow, u fast, w+u medium
        Channel 2 (1): w slow, i fast, q+i medium
        Channel 3 (2): e slow, o fast, e+o medium
        Channel 4 (3): r slow, p fast, r+p medium
        """
        if ch_idx == 0:
            # Channel 1
            if "w" in keys and "u" in keys:
                return MEDIUM_UP_RATE
            elif "u" in keys:
                return FAST_UP_RATE
            elif "q" in keys:
                return SLOW_UP_RATE
            else:
                return 0.0

        elif ch_idx == 1:
            # Channel 2
            if "q" in keys and "i" in keys:
                return MEDIUM_UP_RATE
            elif "i" in keys:
                return FAST_UP_RATE
            elif "w" in keys:
                return SLOW_UP_RATE
            else:
                return 0.0

        elif ch_idx == 2:
            # Channel 3
            if "e" in keys and "o" in keys:
                return MEDIUM_UP_RATE
            elif "o" in keys:
                return FAST_UP_RATE
            elif "e" in keys:
                return SLOW_UP_RATE
            else:
                return 0.0

        elif ch_idx == 3:
            # Channel 4
            if "r" in keys and "p" in keys:
                return MEDIUM_UP_RATE
            elif "p" in keys:
                return FAST_UP_RATE
            elif "r" in keys:
                return SLOW_UP_RATE
            else:
                return 0.0

        return 0.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _jitter(self, base: float, amount: int = 40) -> float:
        """Small random jitter to make values less robotically constant."""
        return base + random.randint(-amount, amount)