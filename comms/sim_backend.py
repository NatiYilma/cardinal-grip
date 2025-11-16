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
SimBackend (manual-only via GUI-provided key events)

A drop-in replacement for SerialBackend that pretends to be the ESP32-S3
streaming 4 FSR channels — but values are controlled *exclusively* by
key events forwarded from the GUI.

Used in host/gui/patient_game_app.py as:

    from comms.sim_backend import SimBackend as SerialBackend

API (compatible with SerialBackend):
    SimBackend(port=None, baud=115200, timeout=0.01, update_interval=None)
    start()
    stop()
    get_latest() -> list[4 ints]

Extra API (called by the GUI, but generic):
    handle_char(ch: str, is_press: bool)

The GUI does NOT know about channels or bands; it just forwards the
character it saw. All mapping from keys → fingers → ADC levels happens
inside this backend.
"""

import threading
import time
import random

NUM_CHANNELS = 4

# Approximate "ADC" levels relative to your default target band (1200–2000)
LOW_LEVEL = 400        # clearly below target
IN_BAND_LEVEL = 1600   # comfortably inside target band
HIGH_LEVEL = 3000      # clearly above target (not used yet, but available)


class SimBackend:
    """
    Software stand-in for the ESP32-S3 + FSR grid.

    - It does NOT read hardware.
    - It does NOT have scripted phases.
    - It ONLY outputs values based on _manual_levels, which are driven by
      key events forwarded from the GUI via handle_char(...).
    """

    def __init__(self, port=None, baud=115200, timeout=0.01, update_interval=None):
        """
        Parameters kept for compatibility with SerialBackend:
            port:          ignored
            baud:          ignored
            timeout:       used as default update interval if update_interval is None
            update_interval:
                seconds between simulated updates. If None, falls back to
                `timeout` or 0.05 seconds.
        """
        self.port = port
        self.baud = baud
        self.timeout = timeout

        # How often we update the simulated values
        self.update_interval = (
            update_interval if update_interval is not None else (timeout or 0.05)
        )

        # Threading / state
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._latest = [0] * NUM_CHANNELS  # last generated values

        # Manual levels for each channel (Index, Middle, Ring, Pinky)
        self._manual_levels = [LOW_LEVEL] * NUM_CHANNELS

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

        ch:       single-character string (e.g., '1', '2', '3', '4', '0')
        is_press: True if key down, False if key up.

        Mapping (all internal here):

            '1'  → Index finger  (channel 0) in_band while pressed
            '2'  → Middle finger (channel 1) in_band while pressed
            '3'  → Ring finger   (channel 2) in_band while pressed
            '4'  → Pinky         (channel 3) in_band while pressed
            '0'  → (on press) relax all fingers to "low"

        The GUI does NOT need to know any of this; it just calls handle_char().
        """
        if not ch:
            return

        ch = ch[0]  # ensure single char

        key_to_channel = {
            "1": 0,  # Index
            "2": 1,  # Middle
            "3": 2,  # Ring
            "4": 3,  # Pinky
        }

        if ch == "0" and is_press:
            # Relax all fingers immediately
            for c in range(NUM_CHANNELS):
                self._set_channel_state(c, "low")
            return

        if ch in key_to_channel:
            channel = key_to_channel[ch]
            if is_press:
                self._set_channel_state(channel, "in_band")
            else:
                self._set_channel_state(channel, "low")

    # ------------------------------------------------------------------
    # Internal main loop
    # ------------------------------------------------------------------

    def _run_loop(self):
        """Main simulation loop; runs in a background thread."""
        while self._running:
            with self._lock:
                base_levels = list(self._manual_levels)

            # Add a little jitter so it doesn’t look perfectly flat
            vals = [self._jitter(v, amount=60) for v in base_levels]

            # Clamp and normalize
            vals = [int(max(0, min(4095, v))) for v in vals]
            if len(vals) < NUM_CHANNELS:
                vals = vals + [0] * (NUM_CHANNELS - len(vals))
            vals = vals[:NUM_CHANNELS]

            with self._lock:
                self._latest = vals

            time.sleep(self.update_interval)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_channel_state(self, channel: int, state: str):
        """Internal helper to update one channel's target level."""
        if not (0 <= channel < NUM_CHANNELS):
            return

        s = state.lower()
        if s == "low":
            level = LOW_LEVEL
        elif s == "in_band":
            level = IN_BAND_LEVEL
        elif s == "high":
            level = HIGH_LEVEL
        else:
            return

        with self._lock:
            self._manual_levels[channel] = level

    def _jitter(self, base: int, amount: int = 60) -> int:
        """Small random jitter to make values less robotically constant."""
        return base + random.randint(-amount, amount)