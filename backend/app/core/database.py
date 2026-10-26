"""SQLite local persistence layer for NumberShield.
Initializes tables, handles safe parameterized queries, and provides zero-trace purge.
"""

import sqlite3
import datetime
from pathlib import Path
from typing import Any
from backend.app.core.config import settings
from backend.app.core.security import secure_wipe_file


def get_db_connection(db_path: Path = settings.db_path) -> sqlite3.Connection:
    """Returns a connection to the local SQLite database with row factory enabled."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        try:
            with open(db_path, "rb") as f:
                header = f.read(16)
            if len(header) < 16 or not header.startswith(b"SQLite format 3\x00"):
                db_path.unlink(missing_ok=True)
        except Exception:
            pass
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Path = settings.db_path) -> None:
    """Initializes database schema if tables do not exist."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS identities (
        id TEXT PRIMARY KEY,
        hmac_id TEXT UNIQUE NOT NULL,
        masked_phone TEXT NOT NULL,
        country_code TEXT,
        carrier_name TEXT,
        line_type TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS exposures (
        id TEXT PRIMARY KEY,
        identity_hmac TEXT NOT NULL,
        source_id TEXT NOT NULL,
        url TEXT NOT NULL,
        domain TEXT NOT NULL,
        title TEXT,
        match_type TEXT NOT NULL, -- 'EXACT', 'PROBABLE', 'WEAK', 'FALSE_POSITIVE'
        confidence REAL NOT NULL,
        snippet TEXT,
        discovered_at TEXT NOT NULL,
        last_checked_at TEXT NOT NULL,
        UNIQUE(identity_hmac, url)
    );

    CREATE TABLE IF NOT EXISTS remediation_actions (
        id TEXT PRIMARY KEY,
        exposure_id TEXT,
        identity_hmac TEXT NOT NULL,
        source_id TEXT NOT NULL,
        status TEXT NOT NULL, -- 'DISCOVERED', 'VERIFIED', 'ACTION_AVAILABLE', 'SUBMITTED', 'ACKNOWLEDGED', 'VERIFIED_REMOVED', 'REJECTED', 'MANUAL_ACTION_REQUIRED'
        official_url TEXT,
        submission_ref TEXT,
        notes TEXT,
        submitted_at TEXT,
        verified_at TEXT,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(exposure_id) REFERENCES exposures(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS subscriptions (
        id TEXT PRIMARY KEY,
        identity_hmac TEXT NOT NULL,
        sender_name TEXT NOT NULL,
        sender_contact TEXT NOT NULL,
        channel TEXT NOT NULL, -- 'EMAIL', 'SMS'
        unsubscribe_method TEXT, -- 'HEADER_URL', 'HEADER_MAILTO', 'BODY_LINK', 'SMS_STOP'
        unsubscribe_target TEXT,
        status TEXT NOT NULL, -- 'ACTIVE', 'UNSUBSCRIBE_PENDING', 'UNSUBSCRIBED'
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS spam_incidents (
        id TEXT PRIMARY KEY,
        identity_hmac TEXT NOT NULL,
        sender_number TEXT NOT NULL,
        channel TEXT NOT NULL, -- 'CALL', 'SMS', 'WHATSAPP'
        category TEXT NOT NULL, -- 'ROBOCALL', 'LIVE_AGENT', 'MARKETING_SMS', 'PHISHING'
        spoof_suspected INTEGER NOT NULL DEFAULT 0,
        campaign_summary TEXT,
        reported_at TEXT NOT NULL
    );
    """)
    conn.commit()
    conn.close()


def purge_all_data(db_path: Path = settings.db_path, key_path: Path = settings.key_path) -> None:
    """Cryptographically purges all stored databases, tables, and secret keys."""
    import gc
    gc.collect()

    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path), check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS spam_incidents;")
            cursor.execute("DROP TABLE IF EXISTS subscriptions;")
            cursor.execute("DROP TABLE IF EXISTS remediation_actions;")
            cursor.execute("DROP TABLE IF EXISTS exposures;")
            cursor.execute("DROP TABLE IF EXISTS identities;")
            cursor.execute("VACUUM;")
            conn.commit()
            conn.close()
        except Exception:
            pass

    gc.collect()

    # Overwrite and remove key
    secure_wipe_file(key_path)

    # Wipe journal and database files
    for p in [Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm"), db_path]:
        if p.exists():
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass

    gc.collect()
    init_db(db_path)


def utc_now_iso() -> str:
    """Returns current UTC timestamp in ISO 8601 format."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
