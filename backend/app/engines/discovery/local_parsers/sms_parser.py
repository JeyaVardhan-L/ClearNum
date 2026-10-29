"""Local SMS backup parser and commercial SMS investigator.
Parses user-authorized SMS backups (XML, JSON, CSV) or individual message headers in local memory.
Identifies commercial shortcodes, DLT alphanumeric headers (e.g. VM-HDFCBK, AD-SWIGGY),
telemarketing categories, STOP opt-out commands, and statutory DND complaint details.
"""

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import xml.etree.ElementTree as ET


@dataclass
class DiscoveredSMSSender:
    sender_number: str
    is_shortcode: bool
    message_count: int
    has_opt_out_keyword: bool
    opt_out_command: str  # e.g. "STOP"
    sample_body: str
    category: str  # e.g. "COMMERCIAL_BANKING", "COMMERCIAL_SHOPPING", "COMMERCIAL_TELECOM", "TRANSACTIONAL_OTP", "MARKETING_SMS", "DIRECT_NUMBER", "UNKNOWN"
    brand_name: str = ""
    dlt_prefix: str = ""
    recommended_action: str = ""


STOP_KEYWORD_PATTERN = re.compile(
    r"\b(?:reply\s+)?(STOP|UNSUBSCRIBE|CANCEL|QUIT|END|OPTOUT)\b",
    re.IGNORECASE,
)

DLT_HEADER_PATTERN = re.compile(r"^([A-Za-z]{2})-([A-Za-z0-9]{3,8})$")

OTP_PATTERN = re.compile(
    r"\b(?:otp|one[- ]time[- ]password|verification code|is your code|auth code|secret code|do not share)\b",
    re.IGNORECASE,
)

PROMO_PATTERN = re.compile(
    r"\b(?:offer|discount|sale|cashback|flat\s+\d+%|\d+%\s*off|win|loan|pre-approved|approved|deal|promo|coupon|voucher|special|credit card|invest)\b",
    re.IGNORECASE,
)

# Known commercial brand markers for enterprise SMS classification
BANKING_BRANDS = [
    "HDFC", "SBI", "ICICI", "AXIS", "KOTAK", "CITI", "BOB", "PNB", "INDUS", "RBL",
    "YESBK", "CANBK", "UNIONB", "IDFC", "FEDERAL", "HSBC", "PAYTM", "GPAY", "PHONEPE",
    "BAJAJ", "CHOLA", "CRED", "LOAN", "CARD", "INSUR", "FIN",
]

SHOPPING_BRANDS = [
    "AMAZON", "AMZN", "SWIGGY", "ZOMATO", "FLIPKT", "MYNTRA", "ZEPTO", "BLINKIT",
    "AJIO", "MEESHO", "NYKAA", "BIGBSK", "DOMINO", "PIZZA", "MCDON", "KFC", "BBDLY",
    "SHOP", "MART", "STORE",
]

TELECOM_BRANDS = [
    "AIRTEL", "JIO", "VODA", "IDEA", "BSNL", "MTNL", "VI",
]

TRAVEL_BRANDS = [
    "UBER", "OLA", "RAPIDO", "IRCTC", "MMT", "GOIBIBO", "INDIGO", "SPICE", "AIRIND",
]


def classify_sender_and_message(sender: str, body: str) -> Tuple[str, str, str, str]:
    """Classifies a sender address and body into category, brand_name, dlt_prefix, and recommended_action."""
    sender_clean = sender.strip().upper()
    body_clean = body.strip()

    dlt_match = DLT_HEADER_PATTERN.match(sender_clean)
    dlt_prefix = ""
    brand_tag = ""

    if dlt_match:
        dlt_prefix = dlt_match.group(1)
        brand_tag = dlt_match.group(2)
    elif "-" in sender_clean and len(sender_clean.split("-")[0]) == 2:
        parts = sender_clean.split("-", 1)
        dlt_prefix = parts[0]
        brand_tag = parts[1]
    elif sender_clean.isalpha() and len(sender_clean) <= 11:
        brand_tag = sender_clean

    digits_only = "".join(c for c in sender if c.isdigit())
    is_numeric_shortcode = 4 <= len(digits_only) <= 6 and len(sender.strip()) <= 8

    # Determine brand and category
    brand_name = brand_tag or sender_clean
    is_otp = bool(OTP_PATTERN.search(body_clean))
    is_promo = bool(PROMO_PATTERN.search(body_clean))

    # Check known brand categories
    if any(b in brand_tag for b in BANKING_BRANDS):
        category = "TRANSACTIONAL_OTP" if is_otp and not is_promo else "COMMERCIAL_BANKING"
        brand_name = brand_tag
        action = "TRAI 1909 DND Complaint" if is_promo else "Bank Security Alert / Account Service"
    elif any(b in brand_tag for b in SHOPPING_BRANDS):
        category = "TRANSACTIONAL_OTP" if is_otp and not is_promo else "COMMERCIAL_SHOPPING"
        brand_name = brand_tag
        action = "TRAI 1909 DND Complaint / App Notification Toggle" if is_promo else "Delivery / Order Update"
    elif any(b in brand_tag for b in TELECOM_BRANDS):
        category = "COMMERCIAL_TELECOM"
        brand_name = brand_tag
        action = "Carrier DND 1909 (Send 'START 0' to 1909 for Full DND)"
    elif any(b in brand_tag for b in TRAVEL_BRANDS):
        category = "TRANSACTIONAL_OTP" if is_otp and not is_promo else "COMMERCIAL_TRAVEL"
        brand_name = brand_tag
        action = "Ride / Booking Notification"
    elif dlt_prefix or (brand_tag and not is_numeric_shortcode and not digits_only):
        if is_otp:
            category = "TRANSACTIONAL_OTP"
            action = "Authentication Code"
        elif is_promo:
            category = "MARKETING_SMS"
            action = "TRAI 1909 Complaint / Statutory Opt-Out"
        else:
            category = "COMMERCIAL_ENTERPRISE"
            action = "Commercial Sender Notice"
    elif is_numeric_shortcode:
        category = "MARKETING_SMS" if (is_promo or bool(OTP_PATTERN.search(body_clean) is None)) else "SHORTCODE_SERVICE"
        action = "Reply STOP to Opt Out"
    elif len(digits_only) >= 10:
        category = "DIRECT_NUMBER"
        action = "Block Caller / Carrier 7726 Report" if is_promo else "Personal Contact"
    else:
        category = "UNKNOWN"
        action = "Inspect Sender"

    return category, brand_name, dlt_prefix, action


def analyze_single_sms(sender: str, body: str, region: str = "IN") -> DiscoveredSMSSender:
    """Analyzes an individual promotional SMS header or message."""
    category, brand_name, dlt_prefix, rec_action = classify_sender_and_message(sender, body)
    digits_only = "".join(c for c in sender if c.isdigit())
    is_shortcode = 4 <= len(digits_only) <= 6

    opt_match = STOP_KEYWORD_PATTERN.search(body)
    has_opt_out = bool(opt_match)
    opt_out_cmd = opt_match.group(1).upper() if opt_match else ("STOP" if is_shortcode else "")

    return DiscoveredSMSSender(
        sender_number=sender.strip(),
        is_shortcode=is_shortcode,
        message_count=1,
        has_opt_out_keyword=has_opt_out,
        opt_out_command=opt_out_cmd,
        sample_body=body.strip()[:160],
        category=category,
        brand_name=brand_name,
        dlt_prefix=dlt_prefix,
        recommended_action=rec_action,
    )


def parse_sms_backup_file(file_path: Path | str, max_records: int = 1000) -> List[DiscoveredSMSSender]:
    """Parses an SMS backup file (.xml, .json, or .csv) and returns aggregated senders with rich commercial classification."""
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
        content = path.read_text(encoding="utf-8", errors="replace")[:1000].strip()
        if content.startswith("<?xml") or "<smses" in content:
            raw_messages = _parse_sms_xml(path, max_records)
        elif content.startswith("[") or content.startswith("{"):
            raw_messages = _parse_sms_json(path, max_records)
        else:
            raw_messages = _parse_sms_csv(path, max_records)

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
        sample = data["samples"][0] if data["samples"] else ""
        category, brand_name, dlt_prefix, rec_action = classify_sender_and_message(addr, sample)
        digits_only = "".join(c for c in addr if c.isdigit())
        is_shortcode = 4 <= len(digits_only) <= 6

        results.append(DiscoveredSMSSender(
            sender_number=addr,
            is_shortcode=is_shortcode,
            message_count=data["count"],
            has_opt_out_keyword=data["has_opt_out"],
            opt_out_command=data["opt_out_word"] or ("STOP" if is_shortcode else ""),
            sample_body=sample[:160],
            category=category,
            brand_name=brand_name,
            dlt_prefix=dlt_prefix,
            recommended_action=rec_action,
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
                addr = row.get("address") or row.get("sender") or row.get("phone") or ""
                body = row.get("body") or row.get("message") or row.get("text") or ""
                messages.append({"address": addr, "body": body})
    except Exception:
        pass
    return messages
