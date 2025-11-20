# comms/sim_backend.py #version 4

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