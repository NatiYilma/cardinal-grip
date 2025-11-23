# host/gui/common/session_logging.py

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime

# ----- PATH SETUP -----
# This file is .../cardinal-grip/host/gui/common/session_logging.py
COMMON_DIR = os.path.dirname(__file__)        # .../host/gui/common
GUI_DIR = os.path.dirname(COMMON_DIR)         # .../host/gui
HOST_DIR = os.path.dirname(GUI_DIR)           # .../host
PROJECT_ROOT = os.path.dirname(HOST_DIR)      # .../cardinal-grip

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

SESSIONS_JSON_PATH = os.path.join(DATA_DIR, "sessions_log.json")
SESSIONS_DB_PATH   = os.path.join(DATA_DIR, "sessions_index.db")

# ----- LOGGER -----
logger = logging.getLogger("cardinal_grip.sessions")


# ---------- JSON LOGGING ----------

def _load_sessions_json():
    if not os.path.isfile(SESSIONS_JSON_PATH):
        logger.debug("No sessions JSON file at %s", SESSIONS_JSON_PATH)
        return []
    try:
        with open(SESSIONS_JSON_PATH, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            logger.warning(
                "sessions_log.json is not a list (type=%s); ignoring contents",
                type(data).__name__,
            )
            return []
    except Exception:
        logger.exception("Failed to load sessions JSON from %s", SESSIONS_JSON_PATH)
        return []


def _save_sessions_json(sessions):
    try:
        with open(SESSIONS_JSON_PATH, "w") as f:
            json.dump(sessions, f, indent=2)
        logger.debug("Wrote %d sessions to %s", len(sessions), SESSIONS_JSON_PATH)
    except Exception:
        # logging failure should not crash the app
        logger.exception("Failed to save sessions JSON to %s", SESSIONS_JSON_PATH)


# ---------- SQLITE INDEX ----------

def _ensure_db():
    """
    Create sessions_index.db and the sessions table if they don't exist.
    """
    try:
        conn = sqlite3.connect(SESSIONS_DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    mode TEXT,
                    source TEXT,
                    fingers_used INTEGER,
                    combo_reps INTEGER,
                    total_reps INTEGER,
                    csv_path TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()
        logger.debug("Ensured sessions_index.db exists at %s", SESSIONS_DB_PATH)
    except Exception:
        logger.exception("Failed to initialize sessions_index.db at %s", SESSIONS_DB_PATH)


def _insert_into_db(session_dict: dict):
    """
    Insert / replace a session row into SQLite index.
    Expects keys:
       id, timestamp, mode, source, fingers_used, combo_reps, total_reps, csv_path
    """
    _ensure_db()
    try:
        conn = sqlite3.connect(SESSIONS_DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO sessions
                (id, timestamp, mode, source, fingers_used, combo_reps, total_reps, csv_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_dict.get("id"),
                    session_dict.get("timestamp"),
                    session_dict.get("mode"),
                    session_dict.get("source"),
                    int(session_dict.get("fingers_used", 0)),
                    int(session_dict.get("combo_reps", 0)),
                    int(session_dict.get("total_reps", 0)),
                    session_dict.get("csv_path"),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        logger.debug(
            "Indexed session %s (%s, source=%s) into SQLite",
            session_dict.get("id"),
            session_dict.get("mode"),
            session_dict.get("source"),
        )
    except Exception:
        logger.exception(
            "Failed to insert session %s into SQLite index",
            session_dict.get("id"),
        )


# ---------- PUBLIC API ----------

def log_session_completion(
    *,
    mode: str,
    source: str,
    reps_per_channel=None,
    combo_reps: int = 0,
    csv_path: str | None = None,
    timestamp: datetime | None = None,
    session_id: str | None = None,
):
    """
    Append a completed session to the JSON log + SQLite index.

    mode   – e.g. "game", "monitor", "dual", "clinician"
    source – file name or window name, e.g. "patient_game_app"
    reps_per_channel – list[int | float], length up to 4
    combo_reps – total combo reps from game mode
    csv_path – optional path to the saved CSV (for monitor/clinician)
    """
    if timestamp is None:
        timestamp = datetime.now()

    ts_str = timestamp.isoformat(timespec="seconds")
    if session_id is None:
        session_id = timestamp.strftime("session_%Y%m%d_%H%M%S")

    if reps_per_channel is None:
        reps_per_channel = []

    # How many fingers had at least 1 rep?
    fingers_used = sum(
        1 for r in reps_per_channel
        if isinstance(r, (int, float)) and r > 0
    )
    total_reps = sum(
        int(r) for r in reps_per_channel
        if isinstance(r, (int, float))
    )

    json_entry = {
        "id": session_id,
        "timestamp": ts_str,
        "mode": mode,
        "source": source,
        "reps_per_channel": reps_per_channel,
        "combo_reps": int(combo_reps),
        "fingers_used": int(fingers_used),
        "total_reps": int(total_reps),
        "csv_path": csv_path,
    }

    logger.info(
        "Logging session %s: mode=%s, source=%s, fingers_used=%d, total_reps=%d, combo_reps=%d",
        session_id,
        mode,
        source,
        int(fingers_used),
        int(total_reps),
        int(combo_reps),
    )

    # --- JSON append ---
    sessions = _load_sessions_json()
    sessions.append(json_entry)
    _save_sessions_json(sessions)

    # --- SQLite row ---
    _insert_into_db(json_entry)


def record_session(session_id: str, reps_per_channel, combo_reps: int):
    """
    Backwards-compatible wrapper so older code can still call record_session(...)
    and it will end up in the same JSON + SQLite flows.
    """
    log_session_completion(
        mode="game",
        source="patient_game_app",
        reps_per_channel=reps_per_channel,
        combo_reps=combo_reps,
        csv_path=None,
        timestamp=datetime.now(),
        session_id=session_id,
    )
