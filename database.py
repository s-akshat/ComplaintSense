"""
database.py - everything about connecting to SQLite and creating the tables.

SQLite stores the whole database in ONE file (complainsense.db), so there is
nothing to install and no password to remember.

Key ideas (beginner level):
  * Table       = like a spreadsheet sheet: rows (records) and columns (fields).
  * Primary key = a column whose value is unique for every row (the row's ID).
  * Foreign key = a column that points at the primary key of another table.
                  It creates a relationship, e.g. each update belongs to one complaint.
"""

import os
import sqlite3
from contextlib import closing

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "complainsense.db")


def get_db_path():
    """Where the database file lives. Tests set COMPLAINSENSE_DB to use a temporary file."""
    return os.environ.get("COMPLAINSENSE_DB", DEFAULT_DB_PATH)


def get_connection():
    """Open a connection to the database.

    row_factory = sqlite3.Row lets us read columns by name, e.g. row["status"].
    PRAGMA foreign_keys = ON makes SQLite actually enforce foreign keys
    (it is OFF by default!).
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# One user can file many complaints; one complaint has many updates.
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    email_or_username TEXT NOT NULL UNIQUE,
    password_hash     TEXT NOT NULL,
    role              TEXT NOT NULL DEFAULT 'admin' CHECK (role IN ('admin', 'student'))
);

CREATE TABLE IF NOT EXISTS complaints (
    complaint_id           TEXT PRIMARY KEY,
    user_id                INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    complainant_name       TEXT NOT NULL,
    contact                TEXT NOT NULL,
    category               TEXT NOT NULL,
    description            TEXT NOT NULL,
    location               TEXT NOT NULL,
    urgency                INTEGER NOT NULL CHECK (urgency BETWEEN 1 AND 5),
    severity               INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 5),
    priority_score         REAL NOT NULL,
    priority_level         TEXT NOT NULL CHECK (priority_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    needs_immediate_review INTEGER NOT NULL DEFAULT 0,
    status                 TEXT NOT NULL DEFAULT 'Pending'
                           CHECK (status IN ('Pending', 'In Progress', 'Resolved')),
    created_at             TEXT NOT NULL,
    updated_at             TEXT NOT NULL,
    assigned_to            INTEGER REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_complaints_status   ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_complaints_priority ON complaints(priority_score);

CREATE TABLE IF NOT EXISTS complaint_updates (
    update_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id TEXT NOT NULL REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    old_status   TEXT,
    new_status   TEXT NOT NULL,
    updated_by   INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    update_time  TEXT NOT NULL,
    remarks      TEXT
);

CREATE INDEX IF NOT EXISTS idx_updates_complaint ON complaint_updates(complaint_id);
"""


def init_db():
    """Create the tables if they do not exist yet. Safe to call every time the app starts."""
    # closing() makes sure the connection is closed even if an error happens.
    with closing(get_connection()) as conn:
        conn.executescript(SCHEMA)
        conn.commit()
