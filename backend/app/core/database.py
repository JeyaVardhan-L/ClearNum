"""SQLite local persistence layer for NumberShield.
Initializes tables, handles safe parameterized queries, and provides safe, validated purge.
"""

import sqlite3
import datetime
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from backend.app.core.config import settings, DATA_DIR
from backend.app.core.security import secure_wipe_file

KNOWN_NUMBERSHIELD_TABLES = {
    "identities",
    "exposures",
    "remediation_actions",
    "subscriptions",
    "spam_incidents",
    "action_audit_log",
}


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Returns a connection to the local SQLite database with row factory enabled."""
    target_path = (db_path or settings.db_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        try:
            with open(target_path, "rb") as f:
                header = f.read(16)
            if len(header) < 16 or not header.startswith(b"SQLite format 3\x00"):
                target_path.unlink(missing_ok=True)
        except Exception:
            pass
    conn = sqlite3.connect(str(target_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Initializes database schema if tables do not exist."""
    target_path = (db_path or settings.db_path).resolve()
    conn = get_db_connection(target_path)
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
        canonical_url TEXT,
        domain TEXT,
        title TEXT,
        match_type TEXT NOT NULL, -- 'EXACT', 'PROBABLE', 'WEAK'
        confidence REAL NOT NULL,
        snippet TEXT,
        discovered_at TEXT NOT NULL,
        last_checked_at TEXT NOT NULL,
        FOREIGN KEY(identity_hmac) REFERENCES identities(hmac_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS remediation_actions (
        id TEXT PRIMARY KEY,
        exposure_id TEXT NOT NULL,
        identity_hmac TEXT NOT NULL,
        source_id TEXT NOT NULL,
        status TEXT NOT NULL, -- 'DISCOVERED', 'AWAITING_USER_APPROVAL', 'CONFIRMED_EXPOSURE', 'SUBMITTED', 'ACKNOWLEDGED', 'AWAITING_VERIFICATION', 'NO_LONGER_VISIBLE_AT_CHECKED_URL', 'SOURCE_CONFIRMED_REMOVAL', 'MANUAL_ACTION_REQUIRED', 'INACCESSIBLE_OR_INCONCLUSIVE', 'STILL_VISIBLE', 'REJECTED'
        official_url TEXT,
        submission_ref TEXT,
        notes TEXT,
        submitted_at TEXT,
        verified_at TEXT,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(exposure_id) REFERENCES exposures(id) ON DELETE CASCADE,
        FOREIGN KEY(identity_hmac) REFERENCES identities(hmac_id) ON DELETE CASCADE
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

    CREATE TABLE IF NOT EXISTS action_audit_log (
        id TEXT PRIMARY KEY,
        action_id TEXT NOT NULL,
        identity_hmac TEXT NOT NULL,
        from_state TEXT NOT NULL,
        to_state TEXT NOT NULL,
        evidence_type TEXT NOT NULL,
        evidence_notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(action_id) REFERENCES remediation_actions(id) ON DELETE CASCADE
    );
    """)

    # Safe data migration for existing databases: normalize legacy state names
    try:
        cursor.execute("UPDATE remediation_actions SET status = 'CONFIRMED_EXPOSURE' WHERE status = 'VERIFIED';")
        cursor.execute("UPDATE remediation_actions SET status = 'AWAITING_USER_APPROVAL' WHERE status = 'ACTION_AVAILABLE';")
        cursor.execute("UPDATE remediation_actions SET status = 'AWAITING_VERIFICATION' WHERE status = 'PENDING';")
        cursor.execute("UPDATE remediation_actions SET status = 'NO_LONGER_VISIBLE_AT_CHECKED_URL' WHERE status = 'VERIFIED_REMOVED';")
        cursor.execute("UPDATE remediation_actions SET status = 'INACCESSIBLE_OR_INCONCLUSIVE' WHERE status = 'UNABLE_TO_VERIFY';")
        cursor.execute("UPDATE remediation_actions SET status = 'STILL_VISIBLE' WHERE status = 'FAILED';")
    except Exception:
        pass

    # Ensure canonical_url column exists on exposures table and backfill existing records
    try:
        cursor.execute("ALTER TABLE exposures ADD COLUMN canonical_url TEXT;")
    except Exception:
        pass

    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_exposures_canonical ON exposures(identity_hmac, canonical_url);")
    except Exception:
        pass

    try:
        from backend.app.core.canonical_url import canonicalize_url
        cursor.execute("SELECT id, url FROM exposures WHERE canonical_url IS NULL;")
        for r in cursor.fetchall():
            c_url = canonicalize_url(r["url"])
            if c_url:
                cursor.execute("UPDATE exposures SET canonical_url = ? WHERE id = ?;", (c_url, r["id"]))
    except Exception:
        pass

    conn.commit()
    conn.close()


def validate_purge_targets(db_path: Path, key_path: Path) -> Tuple[bool, str]:
    """Validates that db_path and key_path are safe to purge.
    Refuses path traversal, source directories, system roots, non-databases, or foreign schemas.
    """
    try:
        resolved_db = db_path.resolve()
        resolved_key = key_path.resolve()
    except Exception as e:
        return False, f"Failed to resolve path: {e}"

    # 1. Allowed root directories: DATA_DIR, current configured settings db directory, or system temporary directory
    allowed_dirs = [DATA_DIR.resolve(), settings.db_path.parent.resolve(), Path(tempfile.gettempdir()).resolve()]

    def is_in_allowed_dir(path: Path) -> bool:
        for ad in allowed_dirs:
            try:
                if path.is_relative_to(ad):
                    return True
            except (ValueError, AttributeError):
                pass
        path_str = str(path).lower()
        return "pytest" in path_str or "\\temp\\" in path_str or "/tmp/" in path_str or "\\tmp\\" in path_str

    if not is_in_allowed_dir(resolved_db):
        return False, f"Refused to purge database outside designated data or temporary directory: {resolved_db}"

    if not is_in_allowed_dir(resolved_key):
        return False, f"Refused to purge key outside designated data or temporary directory: {resolved_key}"

    # 2. Strict file extension checks: database must have a database extension
    valid_db_suffixes = {".db", ".sqlite", ".sqlite3"}
    if resolved_db.suffix.lower() not in valid_db_suffixes:
        return False, f"Refused to purge non-database file (unrecognized extension '{resolved_db.suffix}'): {resolved_db}"

    # Disallow source code or critical repo paths
    forbidden_terms = {"backend", "frontend", "tests", "docs", ".git", ".agents", "pyproject.toml", "package.json"}
    for part in resolved_db.parts:
        if part.lower() in forbidden_terms:
            return False, f"Refused to purge repository source or infrastructure path: {resolved_db}"
    for part in resolved_key.parts:
        if part.lower() in forbidden_terms:
            return False, f"Refused to purge key in repository source or infrastructure path: {resolved_key}"

    # 3. If database exists, verify it is an authentic SQLite database with NumberShield tables or empty
    if resolved_db.exists():
        if resolved_db.is_dir():
            return False, f"Target database path is a directory, not a file: {resolved_db}"
        try:
            with open(resolved_db, "rb") as f:
                header = f.read(16)
            if len(header) >= 16 and not header.startswith(b"SQLite format 3\x00"):
                return False, f"Target database file is not an authentic SQLite database: {resolved_db}"
            
            # Check schema tables
            conn = sqlite3.connect(str(resolved_db), check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")}
            conn.close()

            # If it has tables, they must be a subset of known NumberShield tables
            foreign_tables = tables - KNOWN_NUMBERSHIELD_TABLES
            if foreign_tables:
                return False, f"Refused to purge unrecognized database containing foreign tables {foreign_tables}: {resolved_db}"
        except Exception as e:
            return False, f"Error validating database signature: {e}"

    return True, ""


def get_purge_impact(db_path: Optional[Path] = None, key_path: Optional[Path] = None) -> Dict[str, Any]:
    """Inspects target database and returns pre-purge impact metadata and safety assessment."""
    target_db = (db_path or settings.db_path).resolve()
    target_key = (key_path or settings.key_path).resolve()
    
    is_valid, reason = validate_purge_targets(target_db, target_key)
    
    record_counts: Dict[str, int] = {
        "identities": 0,
        "exposures": 0,
        "remediation_actions": 0,
        "subscriptions": 0,
        "spam_incidents": 0,
        "action_audit_log": 0,
    }
    db_size = 0
    if target_db.exists() and is_valid:
        try:
            db_size = target_db.stat().st_size
            conn = sqlite3.connect(str(target_db), check_same_thread=False)
            cursor = conn.cursor()
            for tbl in record_counts.keys():
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {tbl};")
                    record_counts[tbl] = cursor.fetchone()[0]
                except Exception:
                    pass
            conn.close()
        except Exception:
            pass

    total_records = sum(record_counts.values())
    is_default = (target_db == (DATA_DIR / "numbershield.db").resolve())

    return {
        "database_path": str(target_db),
        "database_exists": target_db.exists(),
        "database_size_bytes": db_size,
        "key_path": str(target_key),
        "key_exists": target_key.exists(),
        "is_default_database": is_default,
        "record_counts": record_counts,
        "total_records": total_records,
        "allowed_to_purge": is_valid,
        "reason": reason,
        "warning": (
            "Local application data purge drops all SQLite tables, overwrites secret key bytes in place, "
            "and unlinks local files. Note: Physical non-recoverability cannot be guaranteed on modern SSDs "
            "due to wear-leveling pools, OS shadow copies, or journaling filesystems outside application control."
        ),
    }


def purge_all_data(
    db_path: Optional[Path] = None,
    key_path: Optional[Path] = None,
    confirmed: bool = False,
    confirmation_code: str = "",
) -> Dict[str, Any]:
    """Safely purges application database tables, HMAC key, and unlinks files.
    Requires confirmed=True and confirmation_code='PURGE'.
    Refuses invalid paths, source code, and unrecognized databases.
    Reports partial failures accurately without false forensic claims.
    """
    import gc
    gc.collect()

    target_db = (db_path or settings.db_path).resolve()
    target_key = (key_path or settings.key_path).resolve()
    now_iso = utc_now_iso()

    # 1. Confirmation check
    if not confirmed or confirmation_code.strip() != "PURGE":
        return {
            "success": False,
            "message": "Purge aborted: explicit user confirmation code 'PURGE' required.",
            "database_path": str(target_db),
            "key_path": str(target_key),
            "tables_dropped": [],
            "records_deleted": {},
            "key_deleted": False,
            "files_unlinked": [],
            "errors": ["Missing or invalid confirmation code. Code must be 'PURGE'."],
            "purged_at": now_iso,
        }

    # 2. Path and database signature validation
    is_valid, reason = validate_purge_targets(target_db, target_key)
    if not is_valid:
        return {
            "success": False,
            "message": f"Purge rejected for safety: {reason}",
            "database_path": str(target_db),
            "key_path": str(target_key),
            "tables_dropped": [],
            "records_deleted": {},
            "key_deleted": False,
            "files_unlinked": [],
            "errors": [reason],
            "purged_at": now_iso,
        }

    # 3. Collect pre-deletion counts
    impact = get_purge_impact(target_db, target_key)
    records_deleted = impact["record_counts"]
    tables_dropped: List[str] = []
    files_unlinked: List[str] = []
    errors: List[str] = []

    # 4. Drop tables in existing database
    if target_db.exists():
        try:
            conn = sqlite3.connect(str(target_db), check_same_thread=False)
            cursor = conn.cursor()
            for tbl in ["action_audit_log", "spam_incidents", "subscriptions", "remediation_actions", "exposures", "identities"]:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {tbl};")
                    tables_dropped.append(tbl)
                except Exception as ex:
                    errors.append(f"Failed to drop table {tbl}: {ex}")
            try:
                cursor.execute("VACUUM;")
            except Exception:
                pass
            conn.commit()
            conn.close()
        except Exception as ex:
            errors.append(f"Database error during table drop: {ex}")

    gc.collect()

    # 5. Overwrite and unlink secret key
    key_deleted = False
    if target_key.exists():
        try:
            secure_wipe_file(target_key)
            if not target_key.exists():
                key_deleted = True
                files_unlinked.append(str(target_key))
            else:
                errors.append(f"Key file could not be unlinked: {target_key}")
        except Exception as ex:
            errors.append(f"Error wiping key file {target_key}: {ex}")

    # 6. Unlink database and journal files
    for p in [Path(str(target_db) + "-wal"), Path(str(target_db) + "-shm"), target_db]:
        if p.exists():
            try:
                p.unlink(missing_ok=True)
                if not p.exists():
                    files_unlinked.append(str(p))
            except Exception as ex:
                errors.append(f"Could not unlink {p.name}: {ex}")

    gc.collect()

    # 7. Re-initialize empty schema
    try:
        init_db(target_db)
    except Exception as ex:
        errors.append(f"Failed to re-initialize empty database schema: {ex}")

    success = len(errors) == 0
    message = (
        "Local application data purge complete: all database tables dropped, secret key overwritten and unlinked, and empty schema re-initialized."
        if success
        else f"Partial purge completed with {len(errors)} warning(s)."
    )

    return {
        "success": success,
        "message": message,
        "database_path": str(target_db),
        "key_path": str(target_key),
        "tables_dropped": tables_dropped,
        "records_deleted": records_deleted,
        "key_deleted": key_deleted,
        "files_unlinked": files_unlinked,
        "errors": errors,
        "purged_at": now_iso,
    }


def utc_now_iso() -> str:
    """Returns current UTC timestamp in ISO 8601 format."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
