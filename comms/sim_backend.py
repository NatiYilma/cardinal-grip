# comms/sim_backend.py # version 9 with latency + BaseBackend API

"""
SimBackend – manual-only backend with ramped squeeze and multi-speed key mapping.

Used as:
    from comms.sim_backend import SimBackend as SerialBackend

API (compatible with SerialBackend + BaseBackend):
    SimBackend(
        port=None,
        baud=115200,
        timeout=0.01,
        update_interval=None,
        num_channels=4,
        history_size=0,
        ...
    )
    start()
    stop()
    get_latest()        -> list[4 ints]
    get_window(n)       -> list of last n samples (simulated)
    get_last_timestamp()-> float | None   # host-side timestamp of last update
    send_command(cmd: str) -> tweak noise / levels (optional)

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
"""

from __future__ import annotations

import random
import threading
import time
from collections import deque
from typing import List, Deque, Tuple, Optional, Set

from .base_backend import BaseBackend

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

DEFAULT_JITTER_AMOUNT = 40


class SimBackend(BaseBackend):
    """
    Software stand-in for the ESP32-S3 + FSR grid.

    - No hardware, no serial.
    - Only uses keyboard-driven rates.
    - Each channel's value ramps up/down based on which keys are pressed.
    """

    def __init__(
        self,
        port: Optional[str] = None,
        baud: int = 115200,
        timeout: float = 0.01,
        update_interval: Optional[float] = None,
        history_size: int = 0,
        num_channels: int = NUM_CHANNELS,
        **kwargs,
    ):
        """
        Accepts num_channels for API compatibility with SerialBackend.
        We currently simulate 4 channels regardless, but keep the signature
        so callers can pass num_channels=4 without errors.
        """
        # Optional: warn if someone passes a channel count that doesn't match
        if num_channels != NUM_CHANNELS:
            print(
                f"[SimBackend] Warning: num_channels={num_channels} requested, "
                f"simulator uses {NUM_CHANNELS} fixed channels."
            )

        # Kept for API symmetry; unused by simulator
        self.port = port
        self.baud = baud
        self.timeout = timeout

        self.update_interval = (
            update_interval if update_interval is not None else (timeout or 0.05)
        )

        # Threading / state
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Channel levels (floats, then jittered & clamped to ints)
        self._levels: List[float] = [LOW_LEVEL] * NUM_CHANNELS
        self._latest: List[int] = [int(LOW_LEVEL)] * NUM_CHANNELS

        # Optional history for stats/debugging
        self._history: Optional[Deque[Tuple[float, List[int]]]] = (
            deque(maxlen=history_size) if history_size > 0 else None
        )

        # Pressed key set
        self._pressed_keys: Set[str] = set()

        # Noise / jitter amplitude (can be tuned via send_command)
        self._jitter_amount: int = DEFAULT_JITTER_AMOUNT

        # For dt computation (simulation loop step)
        now = time.time()
        self._last_update_time = now

        # For latency API: host timestamp of last sample update
        self._last_timestamp: float = 0.0

    # ------------------------------------------------------------------
    # Public API – compatible with SerialBackend/BaseBackend
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background simulation thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background simulation thread."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def get_latest(self) -> List[int]:
        """
        Return the latest 4-channel values as a list of ints.
        patient_game_app.game_tick() / patient_app.poll_sensor() call this frequently.
        """
        with self._lock:
            return list(self._latest)

    def get_window(self, n: int) -> List[List[int]]:
        """
        Return up to the last n samples (most recent last).

        If history is disabled, this falls back to repeating the latest sample.
        """
        if n <= 0:
            return []

        with self._lock:
            if self._history is None or not self._history:
                return [list(self._latest) for _ in range(n)]

            items = list(self._history)[-n:]
        return [vals for (_ts, vals) in items]

    def get_last_timestamp(self) -> Optional[float]:
        """
        Return host-side timestamp (time.time()) when _latest was last updated.

        This matches the SerialBackend API so GUIs can compute:
            age_ms = (now_gui - backend.get_last_timestamp()) * 1000
        """
        with self._lock:
            ts = self._last_timestamp
        return ts or None

    def get_age_ms(self) -> Optional[float]:
        """
        Convenience helper: directly return age (in ms) of the latest sample.
        Not required by BaseBackend, but handy for debugging.
        """
        ts = self.get_last_timestamp()
        if ts is None:
            return None
        return (time.time() - ts) * 1000.0

    # Simple control channel for tweaking simulation parameters
    def send_command(self, cmd: str) -> None:
        """
        Basic command parser for tuning the simulator, e.g.:

          "noise 0"       -> disable jitter
          "noise 40"      -> default jitter
          "noise 100"     -> very noisy
          "reset"         -> reset all channels to LOW_LEVEL

        Unknown commands are ignored.
        """
        if not cmd:
            return

        parts = cmd.strip().lower().split()
        if not parts:
            return

        head = parts[0]

        with self._lock:
            if head == "noise" and len(parts) >= 2:
                try:
                    amt = int(parts[1])
                    self._jitter_amount = max(0, min(200, amt))
                except ValueError:
                    pass
            elif head == "reset":
                self._levels = [LOW_LEVEL] * NUM_CHANNELS
                self._latest = [int(LOW_LEVEL)] * NUM_CHANNELS
                self._last_timestamp = time.time()
                if self._history is not None:
                    self._history.clear()

    # ------------------------------------------------------------------
    # Extra API – generic key input from GUI
    # ------------------------------------------------------------------

    def handle_char(self, ch: str, is_press: bool) -> None:
        """
        Process a character key event coming from the GUI.

        ch:       single-character string (e.g., 'q', 'w', 'e', 'r', 'u', etc.)
        is_press: True if key down, False if key up.
        """
        if not ch:
            return

        c = ch[0].lower()  # normalize to single lowercase char

        with self._lock:
            if is_press:
                self._pressed_keys.add(c)
            else:
                self._pressed_keys.discard(c)

    # ------------------------------------------------------------------
    # Internal main loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
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
                jitter_amount = self._jitter_amount

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
            jittered = [self._jitter(val, jitter_amount) for val in levels]
            jittered = [int(max(MIN_LEVEL, min(4095, v))) for v in jittered]
            ts = time.time()

            with self._lock:
                self._levels = levels
                self._latest = jittered
                self._last_timestamp = ts
                if self._history is not None:
                    self._history.append((ts, list(jittered)))

            time.sleep(self.update_interval)

    # ------------------------------------------------------------------
    # Per-channel rate logic based on pressed keys
    # ------------------------------------------------------------------

    def _compute_up_rate_for_channel(self, ch_idx: int, keys: Set[str]) -> float:
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

        if ch_idx == 1:
            # Channel 2
            if "q" in keys and "i" in keys:
                return MEDIUM_UP_RATE
            elif "i" in keys:
                return FAST_UP_RATE
            elif "w" in keys:
                return SLOW_UP_RATE
            else:
                return 0.0

        if ch_idx == 2:
            # Channel 3
            if "e" in keys and "o" in keys:
                return MEDIUM_UP_RATE
            elif "o" in keys:
                return FAST_UP_RATE
            elif "e" in keys:
                return SLOW_UP_RATE
            else:
                return 0.0

        if ch_idx == 3:
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

    @staticmethod
    def _jitter(base: float, amount: int = 40) -> float:
        """Small random jitter to make values less robotically constant."""
        if amount <= 0:
            return base
        return base + random.randint(-amount, amount)


# # comms/sim_backend.py # version 9 with latency + BaseBackend API
# """
# SimBackend – manual-only backend with ramped squeeze and multi-speed key mapping.

# Used as:
#     from comms.sim_backend import SimBackend as SerialBackend

# API (compatible with SerialBackend + BaseBackend):
#     SimBackend(
#         port=None,
#         baud=115200,
#         timeout=0.01,
#         update_interval=None,
#         history_size=0,
#         num_channels=4,
#         ...
#     )
#     start()
#     stop()
#     get_latest()          -> list[int]
#     get_window(n)         -> list[list[int]]
#     send_command(cmd)     -> tweak noise / levels (optional)
#     get_last_timestamp()  -> float | None   # host-side timestamp of last update
#     handle_char(ch, is_press)

# Extra API (optional helper):
#     get_age_ms()          -> float  # age of latest sample in milliseconds

# Key mapping:

# Channel 1 (Index, channel 0):
#     q : slowest increase
#     u : fastest increase
#     w + u : medium (average of slow & fast)

# Channel 2 (Middle, channel 1):
#     w : slowest increase
#     i : fastest increase
#     q + i : medium

# Channel 3 (Ring, channel 2):
#     e : slowest increase
#     o : fastest increase
#     e + o : medium

# Channel 4 (Pinky, channel 3):
#     r : slowest increase
#     p : fastest increase
#     r + p : medium

# Globals:
#     z : raises everything at the same time (at least slow rate)
#     x : drops everything back down faster
# """

# from __future__ import annotations

# import random
# import threading
# import time
# from collections import deque
# from typing import List, Deque, Tuple, Optional, Set

# from .base_backend import BaseBackend

# NUM_CHANNELS = 4

# # Baseline / range
# MIN_LEVEL = 0
# LOW_LEVEL = 400        # relaxed / clearly below target band
# MAX_LEVEL = 3500       # can go above typical tmax (~2000)

# # Base ramp speeds (ADC counts / second)
# SLOW_UP_RATE = 800.0
# FAST_UP_RATE = 2400.0
# MEDIUM_UP_RATE = (SLOW_UP_RATE + FAST_UP_RATE) / 2.0

# DOWN_RATE = 900.0          # natural relax speed
# DOWN_RATE_FAST = 2200.0    # when 'x' is held, drop faster

# DEFAULT_JITTER_AMOUNT = 40


# class SimBackend(BaseBackend):
#     """
#     Software stand-in for the ESP32-S3 + FSR grid.

#     - No hardware, no serial.
#     - Only uses keyboard-driven rates.
#     - Each channel's value ramps up/down based on which keys are pressed.
#     """

#     def __init__(
#         self,
#         port: Optional[str] = None,
#         baud: int = 115200,
#         timeout: float = 0.01,
#         update_interval: Optional[float] = None,
#         history_size: int = 0,
#         num_channels: int = NUM_CHANNELS,
#         **kwargs,
#     ):
#         """
#         Accepts num_channels for API compatibility with SerialBackend.

#         We currently simulate 4 channels (NUM_CHANNELS). If num_channels
#         differs, we ignore it by default, but you could assert here if you
#         want strict behavior.
#         """
#         # Optional strictness:
#         # if num_channels != NUM_CHANNELS:
#         #     raise ValueError(f"SimBackend only supports {NUM_CHANNELS} channels")

#         # Kept for API compatibility; unused by simulator.
#         self.port = port
#         self.baud = baud
#         self.timeout = timeout

#         self.update_interval = (
#             update_interval if update_interval is not None else (timeout or 0.05)
#         )

#         # Threading / state
#         self._running = False
#         self._thread: Optional[threading.Thread] = None
#         self._lock = threading.Lock()

#         # Channel levels (floats, then jittered & clamped to ints)
#         self._levels: List[float] = [LOW_LEVEL] * NUM_CHANNELS
#         self._latest: List[int] = [int(LOW_LEVEL)] * NUM_CHANNELS

#         # Optional history for stats/debugging
#         self._history: Optional[Deque[Tuple[float, List[int]]]] = (
#             deque(maxlen=history_size) if history_size > 0 else None
#         )

#         # Pressed key set
#         self._pressed_keys: Set[str] = set()

#         # Noise / jitter amplitude (can be tuned via send_command)
#         self._jitter_amount: int = DEFAULT_JITTER_AMOUNT

#         # For dt computation (simulation loop step)
#         now = time.time()
#         self._last_update_time = now

#         # For latency API: host timestamp of last sample update
#         self._last_timestamp: float = 0.0

#     # ------------------------------------------------------------------
#     # Public API – compatible with SerialBackend/BaseBackend
#     # ------------------------------------------------------------------

#     def start(self) -> None:
#         """Start the background simulation thread."""
#         if self._running:
#             return
#         self._running = True
#         self._thread = threading.Thread(target=self._run_loop, daemon=True)
#         self._thread.start()

#     def stop(self) -> None:
#         """Stop the background simulation thread."""
#         self._running = False
#         if self._thread is not None:
#             self._thread.join(timeout=1.0)
#             self._thread = None

#     def get_latest(self) -> List[int]:
#         """
#         Return the latest 4-channel values as a list of ints.
#         patient_game_app / patient_app call this frequently.
#         """
#         with self._lock:
#             return list(self._latest)

#     def get_window(self, n: int) -> List[List[int]]:
#         """
#         Return up to the last n samples (most recent last).

#         If history is disabled, this falls back to repeating the latest sample.
#         """
#         if n <= 0:
#             return []

#         with self._lock:
#             if self._history is None or not self._history:
#                 return [list(self._latest) for _ in range(n)]

#             items = list(self._history)[-n:]
#         return [vals for (_ts, vals) in items]

#     def get_last_timestamp(self) -> Optional[float]:
#         """
#         Return host-side timestamp (time.time()) when _latest was last updated.

#         This matches the SerialBackend API so GUIs can compute:
#             age_ms = (time.time() - backend.get_last_timestamp()) * 1000
#         """
#         with self._lock:
#             ts = self._last_timestamp
#         return ts or None

#     def get_age_ms(self) -> Optional[float]:
#         """
#         Convenience helper: directly return the age (in ms) of the latest sample.
#         Not required by BaseBackend, but handy for quick debugging.
#         """
#         ts = self.get_last_timestamp()
#         if ts is None:
#             return None
#         return (time.time() - ts) * 1000.0

#     # Simple control channel for tweaking simulation parameters
#     def send_command(self, cmd: str) -> None:
#         """
#         Basic command parser for tuning the simulator, e.g.:

#           "noise 0"       -> disable jitter
#           "noise 40"      -> default jitter
#           "noise 100"     -> very noisy
#           "reset"         -> reset all channels to LOW_LEVEL

#         Unknown commands are ignored.
#         """
#         if not cmd:
#             return

#         parts = cmd.strip().lower().split()
#         if not parts:
#             return

#         head = parts[0]

#         with self._lock:
#             if head == "noise" and len(parts) >= 2:
#                 try:
#                     amt = int(parts[1])
#                     self._jitter_amount = max(0, min(200, amt))
#                 except ValueError:
#                     pass
#             elif head == "reset":
#                 self._levels = [LOW_LEVEL] * NUM_CHANNELS
#                 self._latest = [int(LOW_LEVEL)] * NUM_CHANNELS
#                 self._last_timestamp = time.time()
#                 if self._history is not None:
#                     self._history.clear()

#     # ------------------------------------------------------------------
#     # Extra API – generic key input from GUI
#     # ------------------------------------------------------------------

#     def handle_char(self, ch: str, is_press: bool) -> None:
#         """
#         Process a character key event coming from the GUI.

#         ch:       single-character string (e.g., 'q', 'w', 'e', 'r', 'u', etc.)
#         is_press: True if key down, False if key up.
#         """
#         if not ch:
#             return

#         c = ch[0].lower()  # normalize to single lowercase char

#         with self._lock:
#             if is_press:
#                 self._pressed_keys.add(c)
#             else:
#                 self._pressed_keys.discard(c)

#     # ------------------------------------------------------------------
#     # Internal main loop
#     # ------------------------------------------------------------------

#     def _run_loop(self) -> None:
#         """Main simulation loop; runs in a background thread."""
#         while self._running:
#             now = time.time()
#             dt = now - self._last_update_time
#             if dt <= 0:
#                 dt = self.update_interval
#             self._last_update_time = now

#             with self._lock:
#                 levels = list(self._levels)
#                 keys = set(self._pressed_keys)
#                 jitter_amount = self._jitter_amount

#             # Compute new level for each channel
#             for ch_idx in range(NUM_CHANNELS):
#                 up_rate = self._compute_up_rate_for_channel(ch_idx, keys)

#                 # Global 'z' raises everything at least at slow rate
#                 if "z" in keys:
#                     up_rate = max(up_rate, SLOW_UP_RATE)

#                 if up_rate > 0:
#                     # Ramp up toward MAX_LEVEL
#                     levels[ch_idx] = min(
#                         MAX_LEVEL,
#                         levels[ch_idx] + up_rate * dt,
#                     )
#                 else:
#                     # No upward drive: ramp down toward LOW_LEVEL
#                     down_rate = DOWN_RATE_FAST if "x" in keys else DOWN_RATE
#                     if levels[ch_idx] > LOW_LEVEL:
#                         levels[ch_idx] = max(
#                             LOW_LEVEL,
#                             levels[ch_idx] - down_rate * dt,
#                         )
#                     elif levels[ch_idx] < LOW_LEVEL:
#                         # If it undershoots, gently nudge back toward LOW_LEVEL
#                         levels[ch_idx] = min(
#                             LOW_LEVEL,
#                             levels[ch_idx] + (down_rate * 0.3) * dt,
#                         )

#             # Add jitter, clamp, and store
#             jittered = [self._jitter(val, jitter_amount) for val in levels]
#             jittered = [int(max(MIN_LEVEL, min(4095, v))) for v in jittered]
#             ts = time.time()

#             with self._lock:
#                 self._levels = levels
#                 self._latest = jittered
#                 self._last_timestamp = ts
#                 if self._history is not None:
#                     self._history.append((ts, list(jittered)))

#             time.sleep(self.update_interval)

#     # ------------------------------------------------------------------
#     # Per-channel rate logic based on pressed keys
#     # ------------------------------------------------------------------

#     def _compute_up_rate_for_channel(self, ch_idx: int, keys: Set[str]) -> float:
#         """
#         Return the upward ramp rate for a channel, based on pressed keys.

#         Uses your specified mapping:

#         Channel 1 (0): q slow, u fast, w+u medium
#         Channel 2 (1): w slow, i fast, q+i medium
#         Channel 3 (2): e slow, o fast, e+o medium
#         Channel 4 (3): r slow, p fast, r+p medium
#         """
#         if ch_idx == 0:
#             # Channel 1
#             if "w" in keys and "u" in keys:
#                 return MEDIUM_UP_RATE
#             elif "u" in keys:
#                 return FAST_UP_RATE
#             elif "q" in keys:
#                 return SLOW_UP_RATE
#             else:
#                 return 0.0

#         if ch_idx == 1:
#             # Channel 2
#             if "q" in keys and "i" in keys:
#                 return MEDIUM_UP_RATE
#             elif "i" in keys:
#                 return FAST_UP_RATE
#             elif "w" in keys:
#                 return SLOW_UP_RATE
#             else:
#                 return 0.0

#         if ch_idx == 2:
#             # Channel 3
#             if "e" in keys and "o" in keys:
#                 return MEDIUM_UP_RATE
#             elif "o" in keys:
#                 return FAST_UP_RATE
#             elif "e" in keys:
#                 return SLOW_UP_RATE
#             else:
#                 return 0.0

#         if ch_idx == 3:
#             # Channel 4
#             if "r" in keys and "p" in keys:
#                 return MEDIUM_UP_RATE
#             elif "p" in keys:
#                 return FAST_UP_RATE
#             elif "r" in keys:
#                 return SLOW_UP_RATE
#             else:
#                 return 0.0

#         return 0.0

#     # ------------------------------------------------------------------
#     # Helpers
#     # ------------------------------------------------------------------

#     @staticmethod
#     def _jitter(base: float, amount: int = 40) -> float:
#         """Small random jitter to make values less robotically constant."""
#         if amount <= 0:
#             return base
#         return base + random.randint(-amount, amount)



# # # comms/sim_backend.py # version 9 with latency + BaseBackend API

# # """
# # SimBackend – manual-only backend with ramped squeeze and multi-speed key mapping.

# # Used as:
# #     from comms.sim_backend import SimBackend as SerialBackend

# # API (compatible with SerialBackend + BaseBackend):
# #     SimBackend(
# #         port=None,
# #         baud=115200,
# #         timeout=0.01,
# #         update_interval=None,
# #         num_channels=4,
# #         history_size=0,
# #         ...
# #     )
# #     start()
# #     stop()
# #     get_latest()      -> list[4 ints]
# #     get_window(n)     -> list of last n samples (simulated)
# #     get_age_ms()      -> age (ms) of the latest sample
# #     send_command(cmd: str) -> tweak noise / levels (optional)

# # Extra API (called by patient_game_app via keyPressEvent / keyReleaseEvent):
# #     handle_char(ch: str, is_press: bool)

# # Key mapping (per your spec):

# # Channel 1 (Index, channel 0):
# #     q : slowest increase
# #     u : fastest increase
# #     w + u : medium (average of slow & fast)

# # Channel 2 (Middle, channel 1):
# #     w : slowest increase
# #     i : fastest increase
# #     q + i : medium

# # Channel 3 (Ring, channel 2):
# #     e : slowest increase
# #     o : fastest increase
# #     e + o : medium

# # Channel 4 (Pinky, channel 3):
# #     r : slowest increase
# #     p : fastest increase
# #     r + p : medium

# # Globals:
# #     z : raises everything at the same time (at least slow rate)
# #     x : drops everything back down faster
# # """

# # from __future__ import annotations

# # import random
# # import threading
# # import time
# # from collections import deque
# # from typing import List, Deque, Tuple, Optional, Set

# # from .base_backend import BaseBackend

# # NUM_CHANNELS = 4

# # # Baseline / range
# # MIN_LEVEL = 0
# # LOW_LEVEL = 400        # relaxed / clearly below target band
# # MAX_LEVEL = 3500       # can go above typical tmax (~2000)

# # # Base ramp speeds (ADC counts / second)
# # SLOW_UP_RATE = 800.0
# # FAST_UP_RATE = 2400.0
# # MEDIUM_UP_RATE = (SLOW_UP_RATE + FAST_UP_RATE) / 2.0

# # DOWN_RATE = 900.0          # natural relax speed
# # DOWN_RATE_FAST = 2200.0    # when 'x' is held, drop faster

# # DEFAULT_JITTER_AMOUNT = 40


# # class SimBackend(BaseBackend):
# #     """
# #     Software stand-in for the ESP32-S3 + FSR grid.

# #     - No hardware, no serial.
# #     - Only uses keyboard-driven rates.
# #     - Each channel's value ramps up/down based on which keys are pressed.
# #     """

# #     def __init__(
# #         self,
# #         port: Optional[str] = None,
# #         baud: int = 115200,
# #         timeout: float = 0.01,
# #         update_interval: Optional[float] = None,
# #         history_size: int = 0,
# #         num_channels: int = NUM_CHANNELS,
# #         **kwargs,
# #     ):
# #         """
# #         Accepts num_channels for API compatibility with SerialBackend.
# #         We currently assume 4 channels; if num_channels differs, we still
# #         simulate 4 channels but you *could* assert on mismatch if desired.
# #         """
# #         # Optional: enforce matching channel count
# #         if num_channels != NUM_CHANNELS:
# #             # You can change this to raise if you want strict behavior
# #             # raise ValueError(f"SimBackend only supports {NUM_CHANNELS} channels")
# #             pass

# #         # These are kept only for API symmetry; they are unused by the simulator.
# #         self.port = port
# #         self.baud = baud
# #         self.timeout = timeout

# #         self.update_interval = (
# #             update_interval if update_interval is not None else (timeout or 0.05)
# #         )

# #         # Threading / state
# #         self._running = False
# #         self._thread: Optional[threading.Thread] = None
# #         self._lock = threading.Lock()

# #         # Channel levels (floats, then jittered & clamped to ints)
# #         self._levels: List[float] = [LOW_LEVEL] * NUM_CHANNELS
# #         self._latest: List[int] = [int(LOW_LEVEL)] * NUM_CHANNELS

# #         # Optional history for stats/debugging
# #         self._history: Optional[Deque[Tuple[float, List[int]]]] = (
# #             deque(maxlen=history_size) if history_size > 0 else None
# #         )

# #         # Pressed key set
# #         self._pressed_keys: Set[str] = set()

# #         # Noise / jitter amplitude (can be tuned via send_command)
# #         self._jitter_amount: int = DEFAULT_JITTER_AMOUNT

# #         # For dt computation (simulation loop step)
# #         self._last_update_time = time.time()

# #         # For latency/age computation (time of most recent sample pushed)
# #         self._last_sample_time = self._last_update_time

# #     # ------------------------------------------------------------------
# #     # Public API – compatible with SerialBackend/BaseBackend
# #     # ------------------------------------------------------------------

# #     def start(self) -> None:
# #         """Start the background simulation thread."""
# #         if self._running:
# #             return
# #         self._running = True
# #         self._thread = threading.Thread(target=self._run_loop, daemon=True)
# #         self._thread.start()

# #     def stop(self) -> None:
# #         """Stop the background simulation thread."""
# #         self._running = False
# #         if self._thread is not None:
# #             self._thread.join(timeout=1.0)
# #             self._thread = None

# #     def get_latest(self) -> List[int]:
# #         """
# #         Return the latest 4-channel values as a list of ints.
# #         patient_game_app.game_tick() calls this frequently.
# #         """
# #         with self._lock:
# #             return list(self._latest)

# #     def get_window(self, n: int) -> List[List[int]]:
# #         """
# #         Return up to the last n samples (most recent last).

# #         If history is disabled, this falls back to repeating the latest sample.
# #         """
# #         if n <= 0:
# #             return []

# #         with self._lock:
# #             if self._history is None or not self._history:
# #                 return [list(self._latest) for _ in range(n)]

# #             items = list(self._history)[-n:]
# #         return [vals for (_ts, vals) in items]

# #     def get_age_ms(self) -> float:
# #         """
# #         Age (in milliseconds) of the most recent sample.

# #         This is what patient_app / patient_game_app use for latency logging.
# #         """
# #         with self._lock:
# #             ts = self._last_sample_time
# #         return (time.time() - ts) * 1000.0

# #     # Simple control channel for tweaking simulation parameters
# #     def send_command(self, cmd: str) -> None:
# #         """
# #         Basic command parser for tuning the simulator, e.g.:

# #           "noise 0"       -> disable jitter
# #           "noise 40"      -> default jitter
# #           "noise 100"     -> very noisy
# #           "reset"         -> reset all channels to LOW_LEVEL

# #         Unknown commands are ignored.
# #         """
# #         if not cmd:
# #             return

# #         parts = cmd.strip().lower().split()
# #         if not parts:
# #             return

# #         head = parts[0]

# #         with self._lock:
# #             if head == "noise" and len(parts) >= 2:
# #                 try:
# #                     amt = int(parts[1])
# #                     self._jitter_amount = max(0, min(200, amt))
# #                 except ValueError:
# #                     pass
# #             elif head == "reset":
# #                 self._levels = [LOW_LEVEL] * NUM_CHANNELS
# #                 self._latest = [int(LOW_LEVEL)] * NUM_CHANNELS
# #                 if self._history is not None:
# #                     self._history.clear()
# #                 # Also reset sample-time so age_ms doesn't look huge
# #                 self._last_sample_time = time.time()

# #     # ------------------------------------------------------------------
# #     # Extra API – generic key input from GUI
# #     # ------------------------------------------------------------------

# #     def handle_char(self, ch: str, is_press: bool) -> None:
# #         """
# #         Process a character key event coming from the GUI.

# #         ch:       single-character string (e.g., 'q', 'w', 'e', 'r', 'u', etc.)
# #         is_press: True if key down, False if key up.
# #         """
# #         if not ch:
# #             return

# #         c = ch[0].lower()  # normalize to single lowercase char

# #         with self._lock:
# #             if is_press:
# #                 self._pressed_keys.add(c)
# #             else:
# #                 self._pressed_keys.discard(c)

# #     # ------------------------------------------------------------------
# #     # Internal main loop
# #     # ------------------------------------------------------------------

# #     def _run_loop(self) -> None:
# #         """Main simulation loop; runs in a background thread."""
# #         while self._running:
# #             now = time.time()
# #             dt = now - self._last_update_time
# #             if dt <= 0:
# #                 dt = self.update_interval
# #             self._last_update_time = now

# #             with self._lock:
# #                 levels = list(self._levels)
# #                 keys = set(self._pressed_keys)
# #                 jitter_amount = self._jitter_amount

# #             # Compute new level for each channel
# #             for ch_idx in range(NUM_CHANNELS):
# #                 up_rate = self._compute_up_rate_for_channel(ch_idx, keys)

# #                 # Global 'z' raises everything at least at slow rate
# #                 if "z" in keys:
# #                     up_rate = max(up_rate, SLOW_UP_RATE)

# #                 if up_rate > 0:
# #                     # Ramp up toward MAX_LEVEL
# #                     levels[ch_idx] = min(
# #                         MAX_LEVEL,
# #                         levels[ch_idx] + up_rate * dt,
# #                     )
# #                 else:
# #                     # No upward drive: ramp down toward LOW_LEVEL
# #                     down_rate = DOWN_RATE_FAST if "x" in keys else DOWN_RATE
# #                     if levels[ch_idx] > LOW_LEVEL:
# #                         levels[ch_idx] = max(
# #                             LOW_LEVEL,
# #                             levels[ch_idx] - down_rate * dt,
# #                         )
# #                     elif levels[ch_idx] < LOW_LEVEL:
# #                         # If it undershoots, gently nudge back toward LOW_LEVEL
# #                         levels[ch_idx] = min(
# #                             LOW_LEVEL,
# #                             levels[ch_idx] + (down_rate * 0.3) * dt,
# #                         )

# #             # Add jitter, clamp, and store
# #             jittered = [self._jitter(val, jitter_amount) for val in levels]
# #             jittered = [int(max(MIN_LEVEL, min(4095, v))) for v in jittered]
# #             ts = time.time()

# #             with self._lock:
# #                 self._levels = levels
# #                 self._latest = jittered
# #                 self._last_sample_time = ts
# #                 if self._history is not None:
# #                     self._history.append((ts, list(jittered)))

# #             time.sleep(self.update_interval)

# #     # ------------------------------------------------------------------
# #     # Per-channel rate logic based on pressed keys
# #     # ------------------------------------------------------------------

# #     def _compute_up_rate_for_channel(self, ch_idx: int, keys: Set[str]) -> float:
# #         """
# #         Return the upward ramp rate for a channel, based on pressed keys.

# #         Uses your specified mapping:

# #         Channel 1 (0): q slow, u fast, w+u medium
# #         Channel 2 (1): w slow, i fast, q+i medium
# #         Channel 3 (2): e slow, o fast, e+o medium
# #         Channel 4 (3): r slow, p fast, r+p medium
# #         """
# #         if ch_idx == 0:
# #             # Channel 1
# #             if "w" in keys and "u" in keys:
# #                 return MEDIUM_UP_RATE
# #             elif "u" in keys:
# #                 return FAST_UP_RATE
# #             elif "q" in keys:
# #                 return SLOW_UP_RATE
# #             else:
# #                 return 0.0

# #         if ch_idx == 1:
# #             # Channel 2
# #             if "q" in keys and "i" in keys:
# #                 return MEDIUM_UP_RATE
# #             elif "i" in keys:
# #                 return FAST_UP_RATE
# #             elif "w" in keys:
# #                 return SLOW_UP_RATE
# #             else:
# #                 return 0.0

# #         if ch_idx == 2:
# #             # Channel 3
# #             if "e" in keys and "o" in keys:
# #                 return MEDIUM_UP_RATE
# #             elif "o" in keys:
# #                 return FAST_UP_RATE
# #             elif "e" in keys:
# #                 return SLOW_UP_RATE
# #             else:
# #                 return 0.0

# #         if ch_idx == 3:
# #             # Channel 4
# #             if "r" in keys and "p" in keys:
# #                 return MEDIUM_UP_RATE
# #             elif "p" in keys:
# #                 return FAST_UP_RATE
# #             elif "r" in keys:
# #                 return SLOW_UP_RATE
# #             else:
# #                 return 0.0

# #         return 0.0

# #     # ------------------------------------------------------------------
# #     # Helpers
# #     # ------------------------------------------------------------------

# #     @staticmethod
# #     def _jitter(base: float, amount: int = 40) -> float:
# #         """Small random jitter to make values less robotically constant."""
# #         if amount <= 0:
# #             return base
# #         return base + random.randint(-amount, amount)
    

# # # comms/sim_backend.py  # version 6
# # # """
# # # SimBackend – manual-only backend with ramped squeeze and multi-speed key mapping.

# # # Used as:
# # #     from comms.sim_backend import SimBackend as SerialBackend

# # # API (compatible with SerialBackend + BaseBackend):
# # #     SimBackend(port=None, baud=115200, timeout=0.01, update_interval=None)
# # #     start()
# # #     stop()
# # #     get_latest() -> list[4 ints]
# # #     get_window(n) -> list of last n samples (simulated)
# # #     send_command(cmd: str) -> tweak noise / levels (optional)
# # #     get_last_timestamp() -> float | None   # host-side timestamp of last update

# # # Extra API (called by patient_game_app via keyPressEvent / keyReleaseEvent):
# # #     handle_char(ch: str, is_press: bool)

# # # Key mapping (per your spec):

# # # Channel 1 (Index, channel 0):
# # #     q : slowest increase
# # #     u : fastest increase
# # #     w + u : medium (average of slow & fast)

# # # Channel 2 (Middle, channel 1):
# # #     w : slowest increase
# # #     i : fastest increase
# # #     q + i : medium

# # # Channel 3 (Ring, channel 2):
# # #     e : slowest increase
# # #     o : fastest increase
# # #     e + o : medium

# # # Channel 4 (Pinky, channel 3):
# # #     r : slowest increase
# # #     p : fastest increase
# # #     r + p : medium

# # # Globals:
# # #     z : raises everything at the same time (at least slow rate)
# # #     x : drops everything back down faster
# # # """

# # # from __future__ import annotations

# # # import random
# # # import threading
# # # import time
# # # from collections import deque
# # # from typing import List, Deque, Tuple, Optional, Set

# # # from .base_backend import BaseBackend

# # # NUM_CHANNELS = 4

# # # # Baseline / range
# # # MIN_LEVEL = 0
# # # LOW_LEVEL = 400        # relaxed / clearly below target band
# # # MAX_LEVEL = 3500       # can go above typical tmax (~2000)

# # # # Base ramp speeds (ADC counts / second)
# # # SLOW_UP_RATE = 800.0
# # # FAST_UP_RATE = 2400.0
# # # MEDIUM_UP_RATE = (SLOW_UP_RATE + FAST_UP_RATE) / 2.0

# # # DOWN_RATE = 900.0          # natural relax speed
# # # DOWN_RATE_FAST = 2200.0    # when 'x' is held, drop faster

# # # DEFAULT_JITTER_AMOUNT = 40


# # # class SimBackend(BaseBackend):
# # #     """
# # #     Software stand-in for the ESP32-S3 + FSR grid.

# # #     - No hardware, no serial.
# # #     - Only uses keyboard-driven rates.
# # #     - Each channel's value ramps up/down based on which keys are pressed.
# # #     """

# # #     def __init__(
# # #         self,
# # #         port: Optional[str] = None,
# # #         baud: int = 115200,
# # #         timeout: float = 0.01,
# # #         update_interval: Optional[float] = None,
# # #         history_size: int = 0,
# # #     ):
# # #         # Kept for API compatibility; unused by simulator
# # #         self.port = port
# # #         self.baud = baud
# # #         self.timeout = timeout

# # #         self.update_interval = (
# # #             update_interval if update_interval is not None else (timeout or 0.05)
# # #         )

# # #         # Threading / state
# # #         self._running = False
# # #         self._thread: Optional[threading.Thread] = None
# # #         self._lock = threading.Lock()

# # #         # Channel levels (floats, then jittered & clamped to ints)
# # #         self._levels: List[float] = [LOW_LEVEL] * NUM_CHANNELS
# # #         self._latest: List[int] = [int(LOW_LEVEL)] * NUM_CHANNELS

# # #         # Optional history for stats/debugging
# # #         self._history: Optional[Deque[Tuple[float, List[int]]]] = (
# # #             deque(maxlen=history_size) if history_size > 0 else None
# # #         )

# # #         # Pressed key set
# # #         self._pressed_keys: Set[str] = set()

# # #         # Noise / jitter amplitude (can be tuned via send_command)
# # #         self._jitter_amount: int = DEFAULT_JITTER_AMOUNT

# # #         # For dt computation
# # #         self._last_update_time = time.time()

# # #         # For latency API: host timestamp of last sample update
# # #         self._last_timestamp: float = 0.0

# # #     # ------------------------------------------------------------------
# # #     # Public API – compatible with SerialBackend/BaseBackend
# # #     # ------------------------------------------------------------------

# # #     def start(self) -> None:
# # #         """Start the background simulation thread."""
# # #         if self._running:
# # #             return
# # #         self._running = True
# # #         self._thread = threading.Thread(target=self._run_loop, daemon=True)
# # #         self._thread.start()

# # #     def stop(self) -> None:
# # #         """Stop the background simulation thread."""
# # #         self._running = False
# # #         if self._thread is not None:
# # #             self._thread.join(timeout=1.0)
# # #             self._thread = None

# # #     def get_latest(self) -> List[int]:
# # #         """
# # #         Return the latest 4-channel values as a list of ints.
# # #         patient_game_app.game_tick() / patient_app.poll_sensor() call this frequently.
# # #         """
# # #         with self._lock:
# # #             return list(self._latest)

# # #     def get_window(self, n: int) -> List[List[int]]:
# # #         """
# # #         Return up to the last n samples (most recent last).

# # #         If history is disabled, this falls back to repeating the latest sample.
# # #         """
# # #         if n <= 0:
# # #             return []

# # #         with self._lock:
# # #             if self._history is None or not self._history:
# # #                 return [list(self._latest) for _ in range(n)]

# # #             items = list(self._history)[-n:]
# # #         return [vals for (_ts, vals) in items]

# # #     def get_last_timestamp(self) -> Optional[float]:
# # #         """
# # #         Return host-side timestamp (time.time()) when _latest was last updated.

# # #         This matches the SerialBackend API so GUIs can compute:
# # #             age_ms = (now_gui - backend.get_last_timestamp()) * 1000
# # #         """
# # #         with self._lock:
# # #             return self._last_timestamp or None

# # #     # Simple control channel for tweaking simulation parameters
# # #     def send_command(self, cmd: str) -> None:
# # #         """
# # #         Basic command parser for tuning the simulator, e.g.:

# # #           "noise 0"       -> disable jitter
# # #           "noise 40"      -> default jitter
# # #           "noise 100"     -> very noisy
# # #           "reset"         -> reset all channels to LOW_LEVEL

# # #         Unknown commands are ignored.
# # #         """
# # #         if not cmd:
# # #             return

# # #         parts = cmd.strip().lower().split()
# # #         if not parts:
# # #             return

# # #         head = parts[0]

# # #         with self._lock:
# # #             if head == "noise" and len(parts) >= 2:
# # #                 try:
# # #                     amt = int(parts[1])
# # #                     self._jitter_amount = max(0, min(200, amt))
# # #                 except ValueError:
# # #                     pass
# # #             elif head == "reset":
# # #                 self._levels = [LOW_LEVEL] * NUM_CHANNELS
# # #                 self._latest = [int(LOW_LEVEL)] * NUM_CHANNELS
# # #                 self._last_timestamp = time.time()
# # #                 if self._history is not None:
# # #                     self._history.clear()

# # #     # ------------------------------------------------------------------
# # #     # Extra API – generic key input from GUI
# # #     # ------------------------------------------------------------------

# # #     def handle_char(self, ch: str, is_press: bool) -> None:
# # #         """
# # #         Process a character key event coming from the GUI.

# # #         ch:       single-character string (e.g., 'q', 'w', 'e', 'r', 'u', etc.)
# # #         is_press: True if key down, False if key up.
# # #         """
# # #         if not ch:
# # #             return

# # #         c = ch[0].lower()  # normalize to single lowercase char

# # #         with self._lock:
# # #             if is_press:
# # #                 self._pressed_keys.add(c)
# # #             else:
# # #                 self._pressed_keys.discard(c)

# # #     # ------------------------------------------------------------------
# # #     # Internal main loop
# # #     # ------------------------------------------------------------------

# # #     def _run_loop(self) -> None:
# # #         """Main simulation loop; runs in a background thread."""
# # #         while self._running:
# # #             now = time.time()
# # #             dt = now - self._last_update_time
# # #             if dt <= 0:
# # #                 dt = self.update_interval
# # #             self._last_update_time = now

# # #             with self._lock:
# # #                 levels = list(self._levels)
# # #                 keys = set(self._pressed_keys)
# # #                 jitter_amount = self._jitter_amount

# # #             # Compute new level for each channel
# # #             for ch_idx in range(NUM_CHANNELS):
# # #                 up_rate = self._compute_up_rate_for_channel(ch_idx, keys)

# # #                 # Global 'z' raises everything at least at slow rate
# # #                 if "z" in keys:
# # #                     up_rate = max(up_rate, SLOW_UP_RATE)

# # #                 if up_rate > 0:
# # #                     # Ramp up toward MAX_LEVEL
# # #                     levels[ch_idx] = min(
# # #                         MAX_LEVEL,
# # #                         levels[ch_idx] + up_rate * dt,
# # #                     )
# # #                 else:
# # #                     # No upward drive: ramp down toward LOW_LEVEL
# # #                     down_rate = DOWN_RATE_FAST if "x" in keys else DOWN_RATE
# # #                     if levels[ch_idx] > LOW_LEVEL:
# # #                         levels[ch_idx] = max(
# # #                             LOW_LEVEL,
# # #                             levels[ch_idx] - down_rate * dt,
# # #                         )
# # #                     elif levels[ch_idx] < LOW_LEVEL:
# # #                         # If it undershoots, gently nudge back toward LOW_LEVEL
# # #                         levels[ch_idx] = min(
# # #                             LOW_LEVEL,
# # #                             levels[ch_idx] + (down_rate * 0.3) * dt,
# # #                         )

# # #             # Add jitter, clamp, and store
# # #             jittered = [self._jitter(val, jitter_amount) for val in levels]
# # #             jittered = [int(max(MIN_LEVEL, min(4095, v))) for v in jittered]
# # #             ts = time.time()

# # #             with self._lock:
# # #                 self._levels = levels
# # #                 self._latest = jittered
# # #                 self._last_timestamp = ts
# # #                 if self._history is not None:
# # #                     self._history.append((ts, list(jittered)))

# # #             time.sleep(self.update_interval)

# # #     # ------------------------------------------------------------------
# # #     # Per-channel rate logic based on pressed keys
# # #     # ------------------------------------------------------------------

# # #     def _compute_up_rate_for_channel(self, ch_idx: int, keys: Set[str]) -> float:
# # #         """
# # #         Return the upward ramp rate for a channel, based on pressed keys.

# # #         Uses your specified mapping:

# # #         Channel 1 (0): q slow, u fast, w+u medium
# # #         Channel 2 (1): w slow, i fast, q+i medium
# # #         Channel 3 (2): e slow, o fast, e+o medium
# # #         Channel 4 (3): r slow, p fast, r+p medium
# # #         """
# # #         if ch_idx == 0:
# # #             # Channel 1
# # #             if "w" in keys and "u" in keys:
# # #                 return MEDIUM_UP_RATE
# # #             elif "u" in keys:
# # #                 return FAST_UP_RATE
# # #             elif "q" in keys:
# # #                 return SLOW_UP_RATE
# # #             else:
# # #                 return 0.0

# # #         if ch_idx == 1:
# # #             # Channel 2
# # #             if "q" in keys and "i" in keys:
# # #                 return MEDIUM_UP_RATE
# # #             elif "i" in keys:
# # #                 return FAST_UP_RATE
# # #             elif "w" in keys:
# # #                 return SLOW_UP_RATE
# # #             else:
# # #                 return 0.0

# # #         if ch_idx == 2:
# # #             # Channel 3
# # #             if "e" in keys and "o" in keys:
# # #                 return MEDIUM_UP_RATE
# # #             elif "o" in keys:
# # #                 return FAST_UP_RATE
# # #             elif "e" in keys:
# # #                 return SLOW_UP_RATE
# # #             else:
# # #                 return 0.0

# # #         if ch_idx == 3:
# # #             # Channel 4
# # #             if "r" in keys and "p" in keys:
# # #                 return MEDIUM_UP_RATE
# # #             elif "p" in keys:
# # #                 return FAST_UP_RATE
# # #             elif "r" in keys:
# # #                 return SLOW_UP_RATE
# # #             else:
# # #                 return 0.0

# # #         return 0.0

# # #     # ------------------------------------------------------------------
# # #     # Helpers
# # #     # ------------------------------------------------------------------

# # #     @staticmethod
# # #     def _jitter(base: float, amount: int = 40) -> float:
# # #         """Small random jitter to make values less robotically constant."""
# # #         if amount <= 0:
# # #             return base
# # #         return base + random.randint(-amount, amount)



# # # # comms/sim_backend.py #version 5

# # # """
# # # SimBackend – manual-only backend with ramped squeeze and multi-speed key mapping.

# # # Used as:
# # #     from comms.sim_backend import SimBackend as SerialBackend

# # # API (compatible with SerialBackend + BaseBackend):
# # #     SimBackend(port=None, baud=115200, timeout=0.01, update_interval=None)
# # #     start()
# # #     stop()
# # #     get_latest() -> list[4 ints]
# # #     get_window(n) -> list of last n samples (simulated)
# # #     send_command(cmd: str) -> tweak noise / levels (optional)

# # # Extra API (called by patient_game_app via keyPressEvent / keyReleaseEvent):
# # #     handle_char(ch: str, is_press: bool)

# # # Key mapping (per your spec):

# # # Channel 1 (Index, channel 0):
# # #     q : slowest increase
# # #     u : fastest increase
# # #     w + u : medium (average of slow & fast)

# # # Channel 2 (Middle, channel 1):
# # #     w : slowest increase
# # #     i : fastest increase
# # #     q + i : medium

# # # Channel 3 (Ring, channel 2):
# # #     e : slowest increase
# # #     o : fastest increase
# # #     e + o : medium

# # # Channel 4 (Pinky, channel 3):
# # #     r : slowest increase
# # #     p : fastest increase
# # #     r + p : medium

# # # Globals:
# # #     z : raises everything at the same time (at least slow rate)
# # #     x : drops everything back down faster
# # # """

# # # from __future__ import annotations

# # # import random
# # # import threading
# # # import time
# # # from collections import deque
# # # from typing import List, Deque, Tuple, Optional, Set

# # # from .base_backend import BaseBackend

# # # NUM_CHANNELS = 4

# # # # Baseline / range
# # # MIN_LEVEL = 0
# # # LOW_LEVEL = 400        # relaxed / clearly below target band
# # # MAX_LEVEL = 3500       # can go above typical tmax (~2000)

# # # # Base ramp speeds (ADC counts / second)
# # # SLOW_UP_RATE = 800.0
# # # FAST_UP_RATE = 2400.0
# # # MEDIUM_UP_RATE = (SLOW_UP_RATE + FAST_UP_RATE) / 2.0

# # # DOWN_RATE = 900.0          # natural relax speed
# # # DOWN_RATE_FAST = 2200.0    # when 'x' is held, drop faster

# # # DEFAULT_JITTER_AMOUNT = 40


# # # class SimBackend(BaseBackend):
# # #     """
# # #     Software stand-in for the ESP32-S3 + FSR grid.

# # #     - No hardware, no serial.
# # #     - Only uses keyboard-driven rates.
# # #     - Each channel's value ramps up/down based on which keys are pressed.
# # #     """

# # #     def __init__(
# # #         self,
# # #         port: Optional[str] = None,
# # #         baud: int = 115200,
# # #         timeout: float = 0.01,
# # #         update_interval: Optional[float] = None,
# # #         history_size: int = 0,
# # #     ):
# # #         # Kept for API compatibility; unused by simulator
# # #         self.port = port
# # #         self.baud = baud
# # #         self.timeout = timeout

# # #         self.update_interval = (
# # #             update_interval if update_interval is not None else (timeout or 0.05)
# # #         )

# # #         # Threading / state
# # #         self._running = False
# # #         self._thread: Optional[threading.Thread] = None
# # #         self._lock = threading.Lock()

# # #         # Channel levels (floats, then jittered & clamped to ints)
# # #         self._levels: List[float] = [LOW_LEVEL] * NUM_CHANNELS
# # #         self._latest: List[int] = [int(LOW_LEVEL)] * NUM_CHANNELS

# # #         # Optional history for stats/debugging
# # #         self._history: Optional[Deque[Tuple[float, List[int]]]] = (
# # #             deque(maxlen=history_size) if history_size > 0 else None
# # #         )

# # #         # Pressed key set
# # #         self._pressed_keys: Set[str] = set()

# # #         # Noise / jitter amplitude (can be tuned via send_command)
# # #         self._jitter_amount: int = DEFAULT_JITTER_AMOUNT

# # #         # For dt computation
# # #         self._last_update_time = time.time()

# # #     # ------------------------------------------------------------------
# # #     # Public API – compatible with SerialBackend/BaseBackend
# # #     # ------------------------------------------------------------------

# # #     def start(self) -> None:
# # #         """Start the background simulation thread."""
# # #         if self._running:
# # #             return
# # #         self._running = True
# # #         self._thread = threading.Thread(target=self._run_loop, daemon=True)
# # #         self._thread.start()

# # #     def stop(self) -> None:
# # #         """Stop the background simulation thread."""
# # #         self._running = False
# # #         if self._thread is not None:
# # #             self._thread.join(timeout=1.0)
# # #             self._thread = None

# # #     def get_latest(self) -> List[int]:
# # #         """
# # #         Return the latest 4-channel values as a list of ints.
# # #         patient_game_app.game_tick() calls this frequently.
# # #         """
# # #         with self._lock:
# # #             return list(self._latest)

# # #     def get_window(self, n: int) -> List[List[int]]:
# # #         """
# # #         Return up to the last n samples (most recent last).

# # #         If history is disabled, this falls back to repeating the latest sample.
# # #         """
# # #         if n <= 0:
# # #             return []

# # #         with self._lock:
# # #             if self._history is None or not self._history:
# # #                 return [list(self._latest) for _ in range(n)]

# # #             items = list(self._history)[-n:]
# # #         return [vals for (_ts, vals) in items]

# # #     # Simple control channel for tweaking simulation parameters
# # #     def send_command(self, cmd: str) -> None:
# # #         """
# # #         Basic command parser for tuning the simulator, e.g.:

# # #           "noise 0"       -> disable jitter
# # #           "noise 40"      -> default jitter
# # #           "noise 100"     -> very noisy
# # #           "reset"         -> reset all channels to LOW_LEVEL

# # #         Unknown commands are ignored.
# # #         """
# # #         if not cmd:
# # #             return

# # #         parts = cmd.strip().lower().split()
# # #         if not parts:
# # #             return

# # #         head = parts[0]

# # #         with self._lock:
# # #             if head == "noise" and len(parts) >= 2:
# # #                 try:
# # #                     amt = int(parts[1])
# # #                     self._jitter_amount = max(0, min(200, amt))
# # #                 except ValueError:
# # #                     pass
# # #             elif head == "reset":
# # #                 self._levels = [LOW_LEVEL] * NUM_CHANNELS
# # #                 self._latest = [int(LOW_LEVEL)] * NUM_CHANNELS
# # #                 if self._history is not None:
# # #                     self._history.clear()

# # #     # ------------------------------------------------------------------
# # #     # Extra API – generic key input from GUI
# # #     # ------------------------------------------------------------------

# # #     def handle_char(self, ch: str, is_press: bool) -> None:
# # #         """
# # #         Process a character key event coming from the GUI.

# # #         ch:       single-character string (e.g., 'q', 'w', 'e', 'r', 'u', etc.)
# # #         is_press: True if key down, False if key up.
# # #         """
# # #         if not ch:
# # #             return

# # #         c = ch[0].lower()  # normalize to single lowercase char

# # #         with self._lock:
# # #             if is_press:
# # #                 self._pressed_keys.add(c)
# # #             else:
# # #                 self._pressed_keys.discard(c)

# # #     # ------------------------------------------------------------------
# # #     # Internal main loop
# # #     # ------------------------------------------------------------------

# # #     def _run_loop(self) -> None:
# # #         """Main simulation loop; runs in a background thread."""
# # #         while self._running:
# # #             now = time.time()
# # #             dt = now - self._last_update_time
# # #             if dt <= 0:
# # #                 dt = self.update_interval
# # #             self._last_update_time = now

# # #             with self._lock:
# # #                 levels = list(self._levels)
# # #                 keys = set(self._pressed_keys)
# # #                 jitter_amount = self._jitter_amount

# # #             # Compute new level for each channel
# # #             for ch_idx in range(NUM_CHANNELS):
# # #                 up_rate = self._compute_up_rate_for_channel(ch_idx, keys)

# # #                 # Global 'z' raises everything at least at slow rate
# # #                 if "z" in keys:
# # #                     up_rate = max(up_rate, SLOW_UP_RATE)

# # #                 if up_rate > 0:
# # #                     # Ramp up toward MAX_LEVEL
# # #                     levels[ch_idx] = min(
# # #                         MAX_LEVEL,
# # #                         levels[ch_idx] + up_rate * dt,
# # #                     )
# # #                 else:
# # #                     # No upward drive: ramp down toward LOW_LEVEL
# # #                     down_rate = DOWN_RATE_FAST if "x" in keys else DOWN_RATE
# # #                     if levels[ch_idx] > LOW_LEVEL:
# # #                         levels[ch_idx] = max(
# # #                             LOW_LEVEL,
# # #                             levels[ch_idx] - down_rate * dt,
# # #                         )
# # #                     elif levels[ch_idx] < LOW_LEVEL:
# # #                         # If it undershoots, gently nudge back toward LOW_LEVEL
# # #                         levels[ch_idx] = min(
# # #                             LOW_LEVEL,
# # #                             levels[ch_idx] + (down_rate * 0.3) * dt,
# # #                         )

# # #             # Add jitter, clamp, and store
# # #             jittered = [self._jitter(val, jitter_amount) for val in levels]
# # #             jittered = [int(max(MIN_LEVEL, min(4095, v))) for v in jittered]
# # #             ts = time.time()

# # #             with self._lock:
# # #                 self._levels = levels
# # #                 self._latest = jittered
# # #                 if self._history is not None:
# # #                     self._history.append((ts, list(jittered)))

# # #             time.sleep(self.update_interval)

# # #     # ------------------------------------------------------------------
# # #     # Per-channel rate logic based on pressed keys
# # #     # ------------------------------------------------------------------

# # #     def _compute_up_rate_for_channel(self, ch_idx: int, keys: Set[str]) -> float:
# # #         """
# # #         Return the upward ramp rate for a channel, based on pressed keys.

# # #         Uses your specified mapping:

# # #         Channel 1 (0): q slow, u fast, w+u medium
# # #         Channel 2 (1): w slow, i fast, q+i medium
# # #         Channel 3 (2): e slow, o fast, e+o medium
# # #         Channel 4 (3): r slow, p fast, r+p medium
# # #         """
# # #         if ch_idx == 0:
# # #             # Channel 1
# # #             if "w" in keys and "u" in keys:
# # #                 return MEDIUM_UP_RATE
# # #             elif "u" in keys:
# # #                 return FAST_UP_RATE
# # #             elif "q" in keys:
# # #                 return SLOW_UP_RATE
# # #             else:
# # #                 return 0.0

# # #         if ch_idx == 1:
# # #             # Channel 2
# # #             if "q" in keys and "i" in keys:
# # #                 return MEDIUM_UP_RATE
# # #             elif "i" in keys:
# # #                 return FAST_UP_RATE
# # #             elif "w" in keys:
# # #                 return SLOW_UP_RATE
# # #             else:
# # #                 return 0.0

# # #         if ch_idx == 2:
# # #             # Channel 3
# # #             if "e" in keys and "o" in keys:
# # #                 return MEDIUM_UP_RATE
# # #             elif "o" in keys:
# # #                 return FAST_UP_RATE
# # #             elif "e" in keys:
# # #                 return SLOW_UP_RATE
# # #             else:
# # #                 return 0.0

# # #         if ch_idx == 3:
# # #             # Channel 4
# # #             if "r" in keys and "p" in keys:
# # #                 return MEDIUM_UP_RATE
# # #             elif "p" in keys:
# # #                 return FAST_UP_RATE
# # #             elif "r" in keys:
# # #                 return SLOW_UP_RATE
# # #             else:
# # #                 return 0.0

# # #         return 0.0

# # #     # ------------------------------------------------------------------
# # #     # Helpers
# # #     # ------------------------------------------------------------------

# # #     @staticmethod
# # #     def _jitter(base: float, amount: int = 40) -> float:
# # #         """Small random jitter to make values less robotically constant."""
# # #         if amount <= 0:
# # #             return base
# # #         return base + random.randint(-amount, amount)
