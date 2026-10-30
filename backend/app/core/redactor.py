"""Universal log redactor and string sanitizer.
Intercepts logging records to mask telephone patterns from logs and traces.
"""

import logging
import re

# Comprehensive regex matching international and national phone representations
PHONE_PATTERN = re.compile(
    r"""
    (?:\+|00)[1-9]\d{0,3}[-.\s]?      # Country prefix
    (?:\(?\d{1,4}\)?[-.\s]?)?        # Optional area code with parens
    \d{3,4}[-.\s]?\d{3,4}            # Local subscriber digits
    |
    (?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}) # US standard format: (555) 123-4567
    """,
    re.VERBOSE
)


def redact_text(text: str) -> str:
    """Replaces telephone numbers in text with masked representations."""
    if not text:
        return ""
    
    def _replacer(match: re.Match) -> str:
        matched_str = match.group(0).strip()
        digits = [c for c in matched_str if c.isdigit()]
        if len(digits) < 7:
            return matched_str  # Avoid false-positive short numbers
        # Preserve prefix sign if any, mask middle, show last 2 digits
        prefix = "+" if matched_str.startswith("+") else ""
        last_two = "".join(digits[-2:])
        return f"{prefix}•••-••{last_two}" if len(digits) >= 2 else "••••"

    return PHONE_PATTERN.sub(_replacer, text)


class PhoneRedactingFilter(logging.Filter):
    """Logging filter that redacts phone numbers from log messages and arguments."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: (redact_text(v) if isinstance(v, str) else v) for k, v in record.args.items()}
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(redact_text(a) if isinstance(a, str) else a for a in record.args)
        return True


def setup_secure_logging(level: str = "INFO") -> None:
    """Configures root logger with phone redacting filter and safe formatting."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    handler.addFilter(PhoneRedactingFilter())
    root_logger.addHandler(handler)
