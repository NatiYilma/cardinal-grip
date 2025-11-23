# logger/app_logging.py

import sys
import os
import logging
import uuid

import colorama
from colorama import Fore, Style

colorama.init(autoreset=False)
Fore.ORANGE = "\033[38;5;208m"  # Monkey patch orange color to Fore


# ========================================================
#   Colored formatter
# ========================================================

class ColoredFormatter(logging.Formatter):
    """Custom formatter to colorize logs based on log level."""
    COLORS = {
        logging.DEBUG:    Fore.BLUE,
        logging.INFO:     Fore.GREEN,
        logging.WARNING:  Fore.YELLOW,
        logging.ERROR:    Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }

    def format(self, record):
        # base color by level
        color = self.COLORS.get(record.levelno, Fore.WHITE)

        # override for exception records (have traceback)
        if record.levelno == logging.ERROR and record.exc_info:
            color = Fore.ORANGE

        msg = super().format(record)
        return f"{color}{msg}{Style.RESET_ALL}"


# ========================================================
#   Run ID filter
# ========================================================

class RunIdFilter(logging.Filter):
    """
    Attaches a stable run_id to every LogRecord in this process.

    The run_id is created once in configure_logging() and then added
    to all records as record.run_id, so you can use %(run_id)s in
    the format strings.
    """
    def __init__(self, run_id: str):
        super().__init__()
        self.run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = self.run_id
        return True


# ========================================================
#   Main configuration
# ========================================================

def configure_logging(
    log_file: str | None,
    level: int = logging.DEBUG,
) -> logging.Logger:
    """
    Configure logging once for the 'cardinal_grip' application.

    - Sets up a colored console handler.
    - Optionally sets up a file handler if log_file is not None.
    - Attaches a per-run ID (run_id) to all records.
    - Is idempotent: calling this again will not add duplicate handlers.

    Returns the main 'cardinal_grip' logger.
    """
    root = logging.getLogger()

    # If already configured, don't add handlers again
    if root.handlers:
        return logging.getLogger("cardinal_grip")

    # Generate a short per-run ID (e.g., 'a3f9c1b2')
    run_id = uuid.uuid4().hex[:8]
    run_filter = RunIdFilter(run_id)

    # Create log directory if needed
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

    # ---- Console (colored) ----
    console_formatter = ColoredFormatter(
        "%(asctime)s - %(run_id)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%m-%d-%Y %I:%M:%S %p",
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(run_filter)

    root.setLevel(level)
    root.addHandler(console_handler)

    # ---- File (no color) ----
    if log_file:
        file_formatter = logging.Formatter(
            "%(asctime)s - %(run_id)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%m-%d-%Y %I:%M:%S %p",
        )
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(run_filter)
        root.addHandler(file_handler)

    # Main app logger
    app_logger = logging.getLogger("cardinal_grip")

    # Optional: log the run header
    app_logger.info("")
    app_logger.info("=" * 80)
    app_logger.info("= ** RUN started with run_id=%s", run_id)
    app_logger.info("=" * 80)
    app_logger.info("")

    return app_logger


# Optional convenience logger for quick tests.
# logger = logging.getLogger("cardinal_grip")

# ========================================================
# Examples:
# from logger.app_logging import configure_logging, logger
# logger = configure_logging("logger/cardinal_grip.log")
# logger.debug("This is a DEBUG logging")
# logger.info("This is an INFO logging")
# logger.warning("This is a WARNING logging")
# logger.error("This is an ERROR logging")
# logger.exception("This is an EXCEPTION logging")
# logger.critical("This is a CRITICAL logging")