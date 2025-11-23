# comms/wifi_backend.py

from __future__ import annotations

import threading
import time
import logging
import socket
from collections import deque
from typing import List, Tuple, Deque, Optional

from .base_backend import BaseBackend

logger = logging.getLogger("cardinal_grip.comms.wifi")


class WifiBackend(BaseBackend):
    """
    TCP-based backend for reading *N* FSR channels from an ESP32-S3 over Wi-Fi.

    Expected protocol (line-oriented, like SerialBackend):

        Either:
            "v0,v1,v2,v3"
        or:
            "seq,t_ms,v0,v1,v2,v3"

    In all cases, the LAST num_channels comma-separated fields are treated
    as the FSR channels. Same clamping and history behavior as SerialBackend.
    """

    def __init__(
        self,
        host: str = "192.168.4.1",   # default ESP32 soft-AP address; override as needed
        port: int = 3333,            # choose any port your firmware uses
        timeout: float = 1.0,        # socket timeout (seconds)
        num_channels: int = 4,
        history_size: int = 0,       # >0 => keep last N samples
        reconnect_backoff: float = 1.0,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = max(0.1, timeout)
        self.num_channels = num_channels
        self.reconnect_backoff = max(0.1, reconnect_backoff)

        # Timestamp of when _latest was last updated
        self._last_timestamp: float = 0.0

        # Socket / thread state
        self.sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False

        # Latest sample and history
        self._lock = threading.Lock()
        self._latest: List[int] = [0] * self.num_channels
        self._history: Optional[Deque[Tuple[float, List[int]]]] = (
            deque(maxlen=history_size) if history_size > 0 else None
        )

        # Write lock for send_command
        self._write_lock = threading.Lock()

        # Line assembly buffer
        self._recv_buffer: str = ""

        logger.debug(
            "WifiBackend initialized (host=%r, port=%d, timeout=%.2f, "
            "num_channels=%d, history_size=%d)",
            self.host,
            self.port,
            self.timeout,
            self.num_channels,
            history_size,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _open_socket(self) -> None:
        """
        Open TCP socket to the ESP32 / Wi-Fi device.
        """
        logger.info("WifiBackend connecting to %s:%d", self.host, self.port)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect((self.host, self.port))
        # Optional: disable Nagle if you want very low latency
        try:
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            # not fatal
            pass
        self.sock = s
        self._recv_buffer = ""
        logger.info("WifiBackend connected to %s:%d", self.host, self.port)

    def start(self) -> None:
        """
        Start the background reader thread.
        """
        if self._thread is not None and self._thread.is_alive():
            logger.debug("WifiBackend.start() called but thread already running.")
            return

        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        logger.info("WifiBackend reader thread started for %s:%d", self.host, self.port)

    def stop(self) -> None:
        """
        Stop the reader thread and close the socket.
        """
        self._running = False
        if self._thread is not None:
            try:
                self._thread.join(timeout=0.5)
            except Exception:
                logger.exception("Error while joining WifiBackend thread.")
            self._thread = None

        self._close_socket()
        logger.info("WifiBackend stopped for %s:%d", self.host, self.port)

    def _close_socket(self) -> None:
        """
        Close the socket, if open. Idempotent and safe to call multiple times.
        """
        if self.sock is None:
            logger.debug("WifiBackend._close_socket() called but sock is already None.")
            return

        try:
            logger.debug("WifiBackend closing socket %s:%d", self.host, self.port)
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                # Already closed or not connected; ignore.
                pass
            self.sock.close()
        except OSError as e:
            # Errno 9 = bad file descriptor => already closed
            if getattr(e, "errno", None) == 9:
                logger.debug(
                    "WifiBackend socket already closed (bad file descriptor), ignoring."
                )
            else:
                logger.exception("Error while closing WifiBackend socket.")
        except Exception:
            logger.exception("Error while closing WifiBackend socket.")
        finally:
            self.sock = None

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _read_loop(self) -> None:
        """
        Continuously read from the TCP socket and update latest values.
        """
        logger.debug("WifiBackend read loop entering for %s:%d", self.host, self.port)
        while self._running:
            # Ensure connected
            if self.sock is None:
                try:
                    self._open_socket()
                except Exception as e:
                    logger.warning(
                        "WifiBackend failed to connect to %s:%d (%s), retrying in %.1fs",
                        self.host,
                        self.port,
                        e,
                        self.reconnect_backoff,
                    )
                    time.sleep(self.reconnect_backoff)
                    continue

            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    # remote closed connection
                    logger.warning(
                        "WifiBackend connection closed by remote %s:%d; reconnecting.",
                        self.host,
                        self.port,
                    )
                    self._close_socket()
                    time.sleep(self.reconnect_backoff)
                    continue
            except socket.timeout:
                # just loop again
                continue
            except Exception as e:
                logger.warning(
                    "WifiBackend recv error from %s:%d: %s; reconnecting.",
                    self.host,
                    self.port,
                    e,
                )
                self._close_socket()
                time.sleep(self.reconnect_backoff)
                continue

            try:
                text = chunk.decode(errors="ignore")
            except Exception:
                logger.debug("WifiBackend received non-text data, ignoring chunk.")
                continue

            self._recv_buffer += text
            # Process complete lines
            while "\n" in self._recv_buffer:
                line, self._recv_buffer = self._recv_buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                self._process_line(line)

        logger.debug("WifiBackend read loop exiting for %s:%d", self.host, self.port)
        self._close_socket()

    def _process_line(self, line: str) -> None:
        """
        Parse one CSV line into channel values.
        """
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) < self.num_channels:
            logger.debug(
                "WifiBackend ignoring short/malformed line from %s:%d: %r",
                self.host,
                self.port,
                line,
            )
            return

        chan_fields = parts[-self.num_channels :]
        try:
            vals = [int(float(p)) for p in chan_fields]
        except ValueError:
            logger.debug(
                "WifiBackend ignoring non-numeric line from %s:%d: %r",
                self.host,
                self.port,
                line,
            )
            return

        # Clamp to 0..4095
        vals = [max(0, min(4095, v)) for v in vals]
        ts = time.time()

        with self._lock:
            self._latest = vals
            self._last_timestamp = ts
            if self._history is not None:
                self._history.append((ts, list(vals)))

    # ------------------------------------------------------------------
    # BaseBackend API
    # ------------------------------------------------------------------

    def get_latest(self) -> List[int]:
        with self._lock:
            return list(self._latest)

    def get_last_timestamp(self) -> Optional[float]:
        with self._lock:
            ts = self._last_timestamp
        return ts or None

    def get_window(self, n: int) -> List[List[int]]:
        if n <= 0:
            return []

        with self._lock:
            if self._history is None or not self._history:
                return [list(self._latest) for _ in range(n)]
            items = list(self._history)[-n:]

        return [vals for (_ts, vals) in items]

    def send_command(self, cmd: str) -> None:
        """
        Optional host -> device control channel.

        Writes 'cmd + \\n' to the socket if connected.
        """
        if not cmd:
            return

        if self.sock is None:
            logger.debug(
                "WifiBackend.send_command(%r) ignored: socket not connected.", cmd
            )
            return

        if not cmd.endswith("\n"):
            cmd = cmd + "\n"

        data = cmd.encode("utf-8", errors="ignore")
        try:
            with self._write_lock:
                self.sock.sendall(data)
            logger.debug(
                "WifiBackend sent command to %s:%d: %r",
                self.host,
                self.port,
                cmd.strip(),
            )
        except Exception:
            logger.exception(
                "WifiBackend error while sending command %r to %s:%d",
                cmd,
                self.host,
                self.port,
            )

    def handle_char(self, ch: str, is_press: bool) -> None:
        """
        Wi-Fi backend doesn't care about keyboard events; no-op.
        """
        return
