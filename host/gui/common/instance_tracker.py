# host/gui/common/instance_tracker.py 

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

# ---------- LOGGER ----------------
# Use the standard logging hierarchy. configure_logging() is called
# from the main entrypoints, so this logger will share the same handlers.
logger = logging.getLogger("cardinal_grip.instances")
instance_logger = logger  # alias for clarity inside this module


class InstanceTrackerMixin:
    """
    Mixin that provides:
      - self.instance_id    → 1, 2, 3, ...
      - self.lifetime_index → same as instance_id (alias)
      - self.index_in_active() → (zero_based_index, active_count)
      - class methods:
           .active_count()
           .lifetime_count()
           .active_ids()
           .debug_dump_active()

    NEW STYLE (MRO-FRIENDLY):

        class PatientWindow(InstanceTrackerMixin, QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)   # ONE super() call only
                ...

    The mixin itself calls super().__init__, so the QObject/QWidget
    base is initialized *before* we touch `self.destroyed`.
    """

    def __init_subclass__(cls, **kwargs):
        """
        Ensure every subclass gets its own counters.
        """
        super().__init_subclass__(**kwargs)
        cls._next_id: int = 0
        cls._lifetime_created: int = 0
        cls._active_ids: List[int] = []

    def __init__(self, *args, **kwargs):
        """
        Register this instance with its class-level counters.

        IMPORTANT:
            This must sit *before* QWidget in the MRO:

                class MyWidget(InstanceTrackerMixin, QWidget):

            and subclasses should just call:

                super().__init__(...)

            Do NOT manually call QWidget.__init__ or InstanceTrackerMixin.__init__
            when using this version.
        """
        # 1) Let QObject/QWidget (or whatever is next in MRO) initialize first.
        super().__init__(*args, **kwargs)

        cls = type(self)

        # 2) Assign IDs and mark as active
        cls._next_id += 1
        cls._lifetime_created += 1

        self._id: int = cls._next_id
        self._is_active: bool = True

        cls._active_ids.append(self._id)

        # 3) Hook into Qt's destroyed signal (if available)
        destroyed_signal = getattr(self, "destroyed", None)
        if destroyed_signal is not None:
            try:
                destroyed_signal.connect(self._on_destroyed)
            except Exception:
                logger.debug(
                    "%s #%d: could not connect destroyed signal",
                    cls.__name__,
                    self._id,
                )

        # Initial log
        self._log("created", level=logging.INFO)

    # ------------------------------------------------------------------
    #  Public properties & helpers
    # ------------------------------------------------------------------

    @property
    def instance_id(self) -> int:
        """Monotonic ID per class: 1, 2, 3, ..."""
        return getattr(self, "_id", -1)

    @property
    def lifetime_index(self) -> int:
        """Alias for instance_id; 'nth' instance of this class ever created."""
        return self.instance_id

    def index_in_active(self) -> Tuple[Optional[int], int]:
        """
        Returns (zero_based_index, active_count).

        If this instance is active and present in the active list:
            → (idx, count)

        If it has already been destroyed / deactivated:
            → (None, count_at_call_time)
        """
        cls = type(self)
        active_ids = list(getattr(cls, "_active_ids", []))
        count = len(active_ids)
        my_id = getattr(self, "_id", None)

        if my_id is None:
            return None, count

        try:
            idx = active_ids.index(my_id)
            return idx, count
        except ValueError:
            return None, count

    @classmethod
    def active_count(cls) -> int:
        """How many instances of this class are currently active."""
        return len(getattr(cls, "_active_ids", []))

    @classmethod
    def lifetime_count(cls) -> int:
        """How many instances of this class have ever been created."""
        return int(getattr(cls, "_lifetime_created", 0))

    @classmethod
    def active_ids(cls) -> list[int]:
        """Snapshot of active instance IDs for this class."""
        return list(getattr(cls, "_active_ids", []))

    @classmethod
    def debug_dump_active(cls):
        """
        Convenience method to log the current active instances of this class.
        """
        active_ids = cls.active_ids()
        instance_logger.debug(
            "%s: %d active instance(s): %s",
            cls.__name__,
            len(active_ids),
            active_ids,
        )

    # ------------------------------------------------------------------
    #  Internal logging helper
    # ------------------------------------------------------------------

    def _log(self, message: str, level: int = logging.DEBUG):
        """
        Log a message with a tag like:
            PatientWindow #6 (2/3 active; lifetime 6) - created
        or
            PatientGameWindow #3 (inactive/2 active; lifetime 3) - destroyed
        """
        cls = type(self)
        my_id = getattr(self, "_id", None)
        idx, total = self.index_in_active()

        if my_id is None:
            tag = f"{cls.__name__} <?>"
        else:
            if idx is None:
                idx_str = f"inactive/{total} active"
            else:
                idx_str = f"{idx + 1}/{total} active"
            tag = f"{cls.__name__} #{my_id} ({idx_str}; lifetime {my_id})"

        instance_logger.log(level, "%s - %s", tag, message)

    # ------------------------------------------------------------------
    #  Qt destroyed handler
    # ------------------------------------------------------------------

    def _on_destroyed(self, _obj=None):
        """
        Slot connected to the QObject.destroyed signal.
        Removes this instance from the active list and logs it.

        NOTE: This may get called multiple times during shutdown.
        We guard against double-removal.
        """
        if not getattr(self, "_is_active", False):
            # Already processed
            return

        cls = type(self)
        my_id = getattr(self, "_id", None)

        active_ids = getattr(cls, "_active_ids", [])
        if my_id in active_ids:
            active_ids.remove(my_id)
        self._is_active = False

        # Log after updating active list
        self._log("destroyed", level=logging.INFO)
