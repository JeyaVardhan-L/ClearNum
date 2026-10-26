"""Local SMS backup parser.
Parses user-authorized SMS backups (XML, JSON, CSV) in local memory to identify
commercial shortcodes, telemarketing senders, and STOP opt-out commands.
"""

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import xml.etree.ElementTree as ET


@dataclass
class DiscoveredSMSSender:
    sender_number: str
    is_shortcode: bool
    message_count: int
    has_opt_out_keyword: bool
    opt_out_command: str  # e.g. "STOP"
    sample_body: str
    category: str  # "MARKETING_SMS", "TRANSACTIONAL", "ROBOCALL"


STOP_KEYWORD_PATTERN = re.compile(
    r"\b(?:reply\s+)?(STOP|UNSUBSCRIBE|CANCEL|QUIT|END|OPTOUT)\b",
    re.IGNORECASE
)


def parse_sms_backup_file(file_path: Path | str, max_records: int = 1000) -> List[DiscoveredSMSSender]:
    """Parses an SMS backup file (.xml, .json, or .csv) and returns aggregated senders."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"SMS backup file not found at: {file_path}")

    suffix = path.suffix.lower()
    raw_messages = []

    if suffix == ".xml":
        raw_messages = _parse_sms_xml(path, max_records)
    elif suffix == ".json":
        raw_messages = _parse_sms_json(path, max_records)
    elif suffix == ".csv":
        raw_messages = _parse_sms_csv(path, max_records)
    else:
        # Attempt auto-detection
        content = path.read_text(encoding="utf-8", errors="replace")[:1000].strip()
        if content.startswith("<?xml") or "<smses" in content:
            raw_messages = _parse_sms_xml(path, max_records)
        elif content.startswith("[") or content.startswith("{"):
            raw_messages = _parse_sms_json(path, max_records)
        else:
            raw_messages = _parse_sms_csv(path, max_records)

    # Aggregate by sender
    sender_map = {}
    for msg in raw_messages:
        addr = msg.get("address", "").strip()
        body = msg.get("body", "").strip()
        if not addr:
            continue

        if addr not in sender_map:
            sender_map[addr] = {
                "count": 0,
                "has_opt_out": False,
                "opt_out_word": "",
                "samples": [],
            }
        sender_map[addr]["count"] += 1
        
        opt_match = STOP_KEYWORD_PATTERN.search(body)
        if opt_match and not sender_map[addr]["has_opt_out"]:
            sender_map[addr]["has_opt_out"] = True
            sender_map[addr]["opt_out_word"] = opt_match.group(1).upper()
            
        if len(sender_map[addr]["samples"]) < 2 and body:
            sender_map[addr]["samples"].append(body)

    results: List[DiscoveredSMSSender] = []
    for addr, data in sender_map.items():
        digits_only = "".join(c for c in addr if c.isdigit())
        # Shortcodes are typically 4 to 6 digits
        is_shortcode = 4 <= len(digits_only) <= 6
        
        # Categorize
        if is_shortcode or data["has_opt_out"]:
            category = "MARKETING_SMS"
        elif len(digits_only) >= 10:
            category = "DIRECT_NUMBER"
        else:
            category = "UNKNOWN"

        sample = data["samples"][0] if data["samples"] else ""
        results.append(DiscoveredSMSSender(
            sender_number=addr,
            is_shortcode=is_shortcode,
            message_count=data["count"],
            has_opt_out_keyword=data["has_opt_out"],
            opt_out_command=data["opt_out_word"] or ("STOP" if is_shortcode else ""),
            sample_body=sample[:100],
            category=category,
        ))

    return results


def _parse_sms_xml(path: Path, max_records: int) -> List[dict]:
    messages = []
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        for elem in root.iter("sms"):
            if len(messages) >= max_records:
                break
            messages.append({
                "address": elem.get("address", ""),
                "body": elem.get("body", ""),
                "date": elem.get("date", ""),
            })
    except Exception:
        pass
    return messages


def _parse_sms_json(path: Path, max_records: int) -> List[dict]:
    messages = []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        items = data if isinstance(data, list) else data.get("messages", [])
        for item in items[:max_records]:
            messages.append({
                "address": str(item.get("address", "") or item.get("sender", "")),
                "body": str(item.get("body", "") or item.get("text", "")),
                "date": str(item.get("date", "")),
            })
    except Exception:
        pass
    return messages


def _parse_sms_csv(path: Path, max_records: int) -> List[dict]:
    messages = []
    try:
        with open(path, mode="r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if len(messages) >= max_records:
                    break
                # Try common column names
                addr = row.get("address") or row.get("sender") or row.get("phone") or ""
                body = row.get("body") or row.get("message") or row.get("text") or ""
                messages.append({"address": addr, "body": body})
    except Exception:
        pass
    return messages
