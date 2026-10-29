"""Tests for privacy redactor, masking, keyed HMAC, and cryptographic purge."""

import pytest
from backend.app.core.security import compute_phone_hmac, mask_phone_number
from backend.app.core.redactor import redact_text
from backend.app.core.database import purge_all_data, get_db_connection
from backend.app.core.config import settings


def test_mask_phone_number():
    assert mask_phone_number("+14155552671") == "+1 ••• ••• •• 71"
    assert mask_phone_number("+442079460991") == "+44 ••• ••• •• 91"
    assert mask_phone_number("4155552671") == "4 ••• ••• •• 71"


def test_keyed_hmac_stability_and_uniqueness():
    hmac1 = compute_phone_hmac("+14155552671")
    hmac2 = compute_phone_hmac("+14155552671")
    hmac3 = compute_phone_hmac("+14155559999")
    
    assert hmac1 == hmac2
    assert hmac1 != hmac3
    assert len(hmac1) == 64  # SHA-256 hex digest length


def test_log_redaction_filter():
    log_line = "Discovered exposure on example.com for user phone +1 (415) 555-2671 in database."
    sanitized = redact_text(log_line)
    assert "+1 (415) 555-2671" not in sanitized
    assert "•••-••71" in sanitized


def test_cryptographic_purge():
    # Ensure clean slate before test with explicit confirmation
    purge_all_data(confirmed=True, confirmation_code="PURGE")

    # Insert dummy identity
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO identities (id, hmac_id, masked_phone, created_at)
        VALUES ('test-id', 'test-hmac', '+1 ••• 71', '2026-10-26T00:00:00')
    """)
    conn.commit()
    conn.close()

    # Verify present
    conn = get_db_connection()
    assert conn.execute("SELECT COUNT(*) FROM identities").fetchone()[0] == 1
    conn.close()

    # Execute purge with explicit confirmation
    res = purge_all_data(confirmed=True, confirmation_code="PURGE")
    assert res["success"] is True

    # Verify zero records
    conn = get_db_connection()
    assert conn.execute("SELECT COUNT(*) FROM identities").fetchone()[0] == 0
    conn.close()
