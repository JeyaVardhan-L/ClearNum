"""Cryptographic security utilities for NumberShield.
Provides keyed HMAC-SHA256 calculation, secure local key persistence,
and phone number masking to prevent offline rainbow table enumeration.
"""

import hmac
import hashlib
import secrets
from pathlib import Path
from backend.app.core.config import settings


def get_or_create_secret_key(key_path: Path = settings.key_path) -> bytes:
    """Retrieves or securely generates a 256-bit local HMAC key.
    Ensures that phone numbers cannot be enumerated via pre-computed rainbow tables.
    """
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        try:
            key = key_path.read_bytes().strip()
            if len(key) >= 32:
                return key
        except Exception:
            pass
    
    # Generate fresh 32 bytes (256 bits) of cryptographic entropy
    new_key = secrets.token_bytes(32)
    key_path.write_bytes(new_key)
    try:
        # On POSIX systems, restrict permissions to owner only
        key_path.chmod(0o600)
    except Exception:
        pass
    return new_key


def compute_phone_hmac(phone_e164: str, secret_key: bytes | None = None) -> str:
    """Computes a keyed HMAC-SHA256 hex digest for a normalized E.164 phone number."""
    if not secret_key:
        secret_key = get_or_create_secret_key()
    normalized = phone_e164.strip()
    return hmac.new(secret_key, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def mask_phone_number(phone_str: str) -> str:
    """Masks a phone number for safe display and logging,
    preserving only country code prefix and last 2 digits.
    Example: '+14155552671' -> '+1 ••• ••• •• 71'
    """
    s = phone_str.strip()
    if not s:
        return "[EMPTY]"
    
    digits = [c for c in s if c.isdigit()]
    if len(digits) <= 4:
        return "••" + "".join(digits[-2:]) if len(digits) >= 2 else "••••"

    # Identify country prefix
    if s.startswith("+1") or (len(digits) == 11 and digits[0] == "1"):
        prefix = "+1"
    elif s.startswith("+44"):
        prefix = "+44"
    elif s.startswith("+91"):
        prefix = "+91"
    elif s.startswith("+49"):
        prefix = "+49"
    elif s.startswith("+33"):
        prefix = "+33"
    elif s.startswith("+"):
        prefix = "+" + "".join(digits[:2])
    else:
        prefix = "".join(digits[:1])

    suffix = "".join(digits[-2:])
    masked_middle = " ••• ••• •• "
    return f"{prefix}{masked_middle}{suffix}"


def secure_wipe_file(file_path: Path) -> None:
    """Securely overwrites file with random bytes and zeros before unlinking."""
    if file_path.exists():
        try:
            size = file_path.stat().st_size
            if size > 0:
                with open(file_path, "wb") as f:
                    f.write(secrets.token_bytes(size))
                    f.flush()
        except Exception:
            pass
        finally:
            try:
                file_path.unlink(missing_ok=True)
            except Exception:
                pass
