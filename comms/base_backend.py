# comms/base_backend.py

from __future__ import annotations

from typing import Protocol, runtime_checkable, List, Optional


@runtime_checkable
class BaseBackend(Protocol):
    """
    Common interface for all Cardinal Grip backends.

    Minimal contract:
      - start() / stop(): manage any background worker
      - get_latest(): non-blocking, returns the most recent sample
      - send_command(): optional host -> device control channel
      - handle_char(): optional, for keyboard-driven simulation

    Optional but recommended:
      - get_last_timestamp(): host timestamp (time.time()) when the last
        sample was updated. Backends that don't track this may return None.

    Backends may also expose:
      - get_window(n): last n samples for stats / smoothing
    """

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def get_latest(self) -> List[float] | None:
        ...

    def send_command(self, cmd: str) -> None:
        """
        Optional control channel from host to device / simulator.
        Backends that don't support commands may no-op.
        """
        ...

    def handle_char(self, ch: str, is_press: bool) -> None:
        """
        Optional key input channel (used by SimBackend).
        Hardware backends may safely no-op.
        """
        ...

    def get_last_timestamp(self) -> Optional[float]:
        """
        Optional: return the host-side timestamp (time.time()) when the last
        sample was updated. Backends that don't track this may return None.
        """
        ...
