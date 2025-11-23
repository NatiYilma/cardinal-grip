# cardial-grip/model/db.py

import os
import sqlite3

# model/db.py → parent = model/, grandparent = project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "patient_stats.sqlite")

def get_connection():
    """Open (or create) the SQLite DB and return a connection."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   TEXT NOT NULL,
            timestamp    TEXT NOT NULL,
            fingers_used INTEGER NOT NULL,
            combo_reps   INTEGER NOT NULL,
            total_reps   INTEGER NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()
