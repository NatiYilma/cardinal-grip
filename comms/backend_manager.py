# comms/backend_manager.py

from __future__ import annotations

import threading
import logging
from typing import Optional

from .base_backend import BaseBackend

logger = logging.getLogger("cardinal_grip.comms.manager")


class BackendManager:
    """
    Singleton-style manager that owns exactly ONE active backend instance.

    - All GUIs call BackendManager.instance().get_backend(...)
      instead of constructing SerialBackend/SimBackend/etc. directly.
    - Ensures only one hardware connection (serial/Wi-Fi/Bluetooth) is active.
    - Handles switching transport: serial <-> sim <-> wifi <-> bluetooth.
    """

    _instance: Optional["BackendManager"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        # Currently active backend and its kind
        self._backend: Optional[BaseBackend] = None
        self._kind: Optional[str] = None
        # Optional: store last config kwargs if you want to re-create
        self._last_kwargs: dict = {}

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def instance(cls) -> "BackendManager":
        """
        Return the global BackendManager instance.
        """
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Public API for GUIs / apps
    # ------------------------------------------------------------------

    def get_backend(
        self,
        kind: str = "serial",
        autostart: bool = True,
        **kwargs,
    ) -> BaseBackend:
        """
        Get (and optionally start) the active backend.

        - If a backend of the same kind already exists, reuse it and ignore kwargs.
        - If a backend of a different kind is active, stop it and create a new one.
        - kind:
            "serial"    -> SerialBackend
            "sim"       -> SimBackend
            "wifi"      -> WifiBackend
            "bluetooth" / "ble" / "bt" -> BluetoothBackend
        """
        kind_norm = (kind or "serial").strip().lower()

        # Reuse existing backend if same kind already active
        if self._backend is not None and self._kind == kind_norm:
            logger.debug(
                "BackendManager reusing existing backend kind=%s", self._kind
            )
            return self._backend

        # If a different backend is running, stop it first
        if self._backend is not None:
            logger.info(
                "BackendManager switching backend: %s -> %s",
                self._kind,
                kind_norm,
            )
            try:
                self._backend.stop()
            except Exception:
                logger.exception(
                    "Error while stopping previous backend (%s).", self._kind
                )
            finally:
                self._backend = None
                self._kind = None

        # Create a new backend of requested kind
        backend = self._create_backend(kind_norm, **kwargs)
        self._backend = backend
        self._kind = kind_norm
        self._last_kwargs = dict(kwargs)

        if autostart:
            try:
                backend.start()
            except Exception:
                logger.exception("Failed to start backend kind=%s", kind_norm)
                # If start fails, clear the backend so we don't reuse a broken instance
                self._backend = None
                self._kind = None
                raise

        logger.info("BackendManager created backend kind=%s", kind_norm)
        return backend

    def current_backend(self) -> Optional[BaseBackend]:
        """
        Return the currently active backend instance, or None.
        """
        return self._backend

    def current_kind(self) -> Optional[str]:
        """
        Return the kind string ("serial", "sim", "wifi", "bluetooth") or None.
        """
        return self._kind

    def shutdown(self) -> None:
        """
        Stop and clear the active backend. Call this once on full app exit.
        """
        if self._backend is None:
            logger.debug("BackendManager.shutdown() called with no active backend.")
            return

        try:
            logger.info("BackendManager shutting down backend kind=%s", self._kind)
            self._backend.stop()
        except Exception:
            logger.exception("Error while stopping backend during shutdown.")
        finally:
            self._backend = None
            self._kind = None
            self._last_kwargs.clear()

    # ------------------------------------------------------------------
    # Internal factory
    # ------------------------------------------------------------------

    def _create_backend(self, kind: str, **kwargs) -> BaseBackend:
        """
        Actually instantiate the correct backend class.
        """
        if kind == "serial":
            from .serial_backend import SerialBackend

            return SerialBackend(**kwargs)

        if kind == "sim":
            from .sim_backend import SimBackend

            return SimBackend(**kwargs)

        if kind == "wifi":
            from .wifi_backend import WifiBackend

            return WifiBackend(**kwargs)

        if kind in ("bluetooth", "ble", "bt"):
            from .bluetooth_backend import BluetoothBackend

            return BluetoothBackend(**kwargs)

        raise ValueError(f"Unknown backend kind: {kind!r}")
